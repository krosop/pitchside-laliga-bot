"""
The Gut Feeling Algorithm Implementation
Steps 2 through 8:
- Step 2: Long-term Elo anchor (1500 start, +70 home field, GD-multiplier, K=20, in-season z-score)
- Step 3: Match scoring (0.5 * points + 0.5 * capped GD + 0.1 * opponent Elo z-score)
- Step 4: 3-game weighted form score (0.5, 0.3, 0.2 + cross-season padding + in-season z-score)
- Step 5: Team strength combination (w_elo * z_elo + w_form * z_form, gap = home - away)
- Step 6: Expected goals via exponential strength gap (lambda_H, lambda_A)
- Step 7: Gut feeling simulation (10,000 lognormal noise + Poisson draws, seeded)
- Step 8: Confidence labeling (Strong, Lean, No gut feeling, threshold sweep)
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional


def elo_expected_score(r_home: float, r_away: float, home_advantage: float = 70.0) -> Tuple[float, float]:
    dr = (r_home + home_advantage) - r_away
    e_home = 1.0 / (1.0 + 10.0 ** (-dr / 400.0))
    e_away = 1.0 - e_home
    return e_home, e_away


def goal_diff_multiplier(gd: int) -> float:
    abs_gd = abs(gd)
    if abs_gd <= 1:
        return 1.0
    elif abs_gd == 2:
        return 1.5
    elif abs_gd == 3:
        return 1.75
    else:
        return 1.75 + (abs_gd - 3) * 0.125


class GutFeelingEngine:
    def __init__(
        self,
        k_elo: float = 20.0,
        home_advantage_elo: float = 70.0,
        w_elo: float = 0.7,
        w_form: float = 0.3,
        k_goal: float = 0.25,
        sigma_noise: float = 0.10,
        n_sim: int = 10000,
        strong_threshold: float = 0.55,
        lean_threshold: float = 0.45,
        random_seed: int = 42,
    ):
        self.k_elo = k_elo
        self.home_advantage_elo = home_advantage_elo
        self.w_elo = w_elo
        self.w_form = w_form
        self.k_goal = k_goal
        self.sigma_noise = sigma_noise
        self.n_sim = n_sim
        self.strong_threshold = strong_threshold
        self.lean_threshold = lean_threshold
        self.random_seed = random_seed

    def process_season_data(
        self,
        matches: List[Dict[str, Any]],
        initial_ratings: Optional[Dict[str, float]] = None,
        initial_match_history: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Processes matches in chronological order.
        Strictly computes all pre-match metrics (Elo, Form, Strength, xG) BEFORE updating ratings.
        Never uses match result for pre-match features (Rule 1 & Rule 2).
        """
        # Ratings dictionary
        ratings: Dict[str, float] = dict(initial_ratings) if initial_ratings else {}
        # Team match history: list of prior match records for form calculation
        history: Dict[str, List[Dict[str, Any]]] = {
            t: list(h) for t, h in (initial_match_history or {}).items()
        }

        # Track active ratings by season to compute in-season z-score
        processed_matches: List[Dict[str, Any]] = []

        cur_season = None
        season_teams: set = set()

        for m in matches:
            season = m["season"]
            if season != cur_season:
                cur_season = season
                season_teams = set()

            h_team = m["home_team"]
            a_team = m["away_team"]
            fthg = int(m["fthg"])
            ftag = int(m["ftag"])
            target = int(m["target"])

            # Initialize newly seen teams to 1500 (Step 2.1)
            if h_team not in ratings:
                ratings[h_team] = 1500.0
            if a_team not in ratings:
                ratings[a_team] = 1500.0

            season_teams.add(h_team)
            season_teams.add(a_team)

            # --- STEP 2: Pre-match Elo ratings & in-season z-scores ---
            # Store ratings BEFORE the match (Step 2.4)
            pre_h_elo = ratings[h_team]
            pre_a_elo = ratings[a_team]

            # In-season Elo z-score (Step 2.5)
            season_elos = [ratings[t] for t in season_teams]
            mu_elo = float(np.mean(season_elos))
            std_elo = float(np.std(season_elos))
            if std_elo < 1e-4:
                std_elo = 100.0  # prior standard deviation

            z_elo_h = (pre_h_elo - mu_elo) / std_elo
            z_elo_a = (pre_a_elo - mu_elo) / std_elo

            # --- STEP 4: Form score (last 3 matches) ---
            h_form_raw = self._compute_team_form(h_team, history)
            a_form_raw = self._compute_team_form(a_team, history)

            processed_matches.append({
                **m,
                "pre_h_elo": pre_h_elo,
                "pre_a_elo": pre_a_elo,
                "z_elo_h": z_elo_h,
                "z_elo_a": z_elo_a,
                "form_raw_h": h_form_raw,
                "form_raw_a": a_form_raw,
            })

            # --- STEP 2.2 & 2.3: POST-MATCH Elo Update ---
            e_h, e_a = elo_expected_score(pre_h_elo, pre_a_elo, self.home_advantage_elo)
            gd = fthg - ftag
            mult = goal_diff_multiplier(gd)

            if target == 0:
                s_h, s_a = 1.0, 0.0
            elif target == 1:
                s_h, s_a = 0.5, 0.5
            else:
                s_h, s_a = 0.0, 1.0

            ratings[h_team] = pre_h_elo + self.k_elo * mult * (s_h - e_h)
            ratings[a_team] = pre_a_elo + self.k_elo * mult * (s_a - e_a)

            # --- STEP 3: Score this match for both teams & record to history ---
            score_h = self._calc_match_score(fthg, ftag, z_elo_a)
            score_a = self._calc_match_score(ftag, fthg, z_elo_h)

            history.setdefault(h_team, []).append({
                "date": m["date"],
                "score": score_h,
                "gf": fthg,
                "ga": ftag,
            })
            history.setdefault(a_team, []).append({
                "date": m["date"],
                "score": score_a,
                "gf": ftag,
                "ga": fthg,
            })

        # Now compute in-season form z-scores (Step 4.4) grouped by season so far
        # To maintain no-leakage, compute running mean and std of form scores
        final_records: List[Dict[str, Any]] = []
        cur_season = None
        running_forms: List[float] = []

        for r in processed_matches:
            if r["season"] != cur_season:
                cur_season = r["season"]
                running_forms = []

            running_forms.append(r["form_raw_h"])
            running_forms.append(r["form_raw_a"])

            mu_f = float(np.mean(running_forms))
            std_f = float(np.std(running_forms))
            if std_f < 1e-4:
                std_f = 0.15  # default scale

            z_form_h = (r["form_raw_h"] - mu_f) / std_f
            z_form_a = (r["form_raw_a"] - mu_f) / std_f

            final_records.append({
                **r,
                "z_form_h": z_form_h,
                "z_form_a": z_form_a,
            })

        return final_records

    @staticmethod
    def _calc_match_score(gf: int, ga: int, opp_z_elo: float) -> float:
        """
        Step 3: Score each past match between 0 and 1.
        1. Points: 3 for win, 1 for draw, 0 for loss / 3
        2. Performance: GD capped between -3 and +3, rescaled to 0-1
        3. Match score = 0.5 * points + 0.5 * perf
        4. Opponent adjustment: add 0.1 * opp_z_elo, cap between 0 and 1
        """
        if gf > ga:
            pts = 1.0  # 3/3
        elif gf == ga:
            pts = 1.0 / 3.0  # 1/3
        else:
            pts = 0.0

        gd = gf - ga
        gd_capped = max(-3.0, min(3.0, float(gd)))
        perf = (gd_capped + 3.0) / 6.0

        raw_score = 0.5 * pts + 0.5 * perf
        adj_score = raw_score + 0.1 * opp_z_elo
        return max(0.0, min(1.0, adj_score))

    @staticmethod
    def _compute_team_form(team: str, history: Dict[str, List[Dict[str, Any]]]) -> float:
        """
        Step 4: Form score from last 3 matches:
        Form score = 0.5 * newest + 0.3 * second newest + 0.2 * oldest.
        If fewer than 3 matches, pad with 0.5 for each missing match.
        """
        past = history.get(team, [])
        scores = [m["score"] for m in past[-3:]]
        # pad to 3 with 0.5
        while len(scores) < 3:
            scores.insert(0, 0.5)

        oldest, mid, newest = scores[0], scores[1], scores[2]
        return 0.5 * newest + 0.3 * mid + 0.2 * oldest

    def compute_strength_gap(self, z_elo_h: float, z_form_h: float, z_elo_a: float, z_form_a: float) -> Tuple[float, float, float]:
        """
        Step 5: Combine into team strength:
        Strength = w_elo * z_elo + w_form * z_form.
        Strength gap = home strength - away strength.
        """
        s_h = self.w_elo * z_elo_h + self.w_form * z_form_h
        s_a = self.w_elo * z_elo_a + self.w_form * z_form_a
        gap = s_h - s_a
        return s_h, s_a, gap

    def convert_strength_to_xg(self, gap: float, home_avg_goals: float, away_avg_goals: float) -> Tuple[float, float]:
        """
        Step 6: Expected goals via exponential formula:
        Home xG = home_avg * exp(k * gap / 2)
        Away xG = away_avg * exp(-k * gap / 2)
        """
        h_xg = home_avg_goals * math.exp(self.k_goal * gap / 2.0)
        a_xg = away_avg_goals * math.exp(-self.k_goal * gap / 2.0)
        return max(0.2, min(5.0, h_xg)), max(0.2, min(5.0, a_xg))

    def simulate_probabilities(self, h_xg: float, a_xg: float, match_seed: int) -> Tuple[float, float, float]:
        """
        Step 7: Gut feeling simulation:
        10,000 simulations per match.
        Noise drawn from Lognormal(0, sigma).
        Goals drawn from Poisson.
        Counts Home Win, Draw, Away Win.
        """
        rng = np.random.default_rng(match_seed)
        noise_h = rng.lognormal(0.0, self.sigma_noise, size=self.n_sim)
        noise_a = rng.lognormal(0.0, self.sigma_noise, size=self.n_sim)

        noisy_h = h_xg * noise_h
        noisy_a = a_xg * noise_a

        goals_h = rng.poisson(noisy_h)
        goals_a = rng.poisson(noisy_a)

        h_wins = np.sum(goals_h > goals_a)
        draws = np.sum(goals_h == goals_a)
        a_wins = np.sum(goals_h < goals_a)

        p_h = float(h_wins) / float(self.n_sim)
        p_d = float(draws) / float(self.n_sim)
        p_a = float(a_wins) / float(self.n_sim)

        # Normalize to avoid roundoff drift
        total = p_h + p_d + p_a
        return p_h / total, p_d / total, p_a / total

    def label_confidence(self, p_h: float, p_d: float, p_a: float) -> Tuple[float, str]:
        """
        Step 8: Confidence labels:
        Confidence = max(p_h, p_d, p_a).
        Strong: conf >= strong_threshold and (|top1 - top2| > 0.05).
        Lean: lean_threshold <= conf < strong_threshold and (|top1 - top2| > 0.05).
        No gut feeling: conf < lean_threshold or (|top1 - top2| <= 0.05).
        """
        probs = sorted([p_h, p_d, p_a], reverse=True)
        top1, top2 = probs[0], probs[1]
        conf = top1

        if (top1 - top2) <= 0.05:
            return conf, "No gut feeling"

        if conf >= self.strong_threshold:
            return conf, "Strong gut feeling"
        elif conf >= self.lean_threshold:
            return conf, "Lean"
        else:
            return conf, "No gut feeling"
