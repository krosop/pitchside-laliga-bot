"""
STATSPHERE High-Fidelity Match Simulation Engine with Dynamic Player Form.
Calibrated on real La Liga historical match data (~2.62 goals/game).
Incorporates:
- Baseline club offensive & defensive ratings
- Starting XI player individual ratings
- Hidden Dynamic Player Form & Streak System (last 2-3 matches momentum)
- Real recent-form signals derived from actual finished fixtures (weighted PPG)
- European Match Load & Squad Fatigue Model (config-driven UCL/UEL calendar rest days)
- Interactive Manager Mode (Live Tactical Stance & Pitch Substitutions)
- Calibrated Bivariate Dixon-Coles goal distributions (tau_x,y parameterization, rho = -0.08)
- Deterministic closed-form probability forecast (exact 1X2 / O-U / BTTS from the DC matrix)
- Seeded reproducible single-match simulation with event timeline
- 6-Axis Tactical Radar Matchup Comparison
- 1-to-1 event timeline generation ensuring goals and scorers match with 100% precision
"""
import json
import random
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from .club_tactics import ClubTacticsRegistry
from .ratings import RatingsEngine
from .momentum import team_momentum, compute_momentum


class SimulationEngine:
    def __init__(self, db=None):
        self.db = db

    def calculate_player_form(self, player: Dict[str, Any], club_slug: str, recent_fixtures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates hidden player form modifier based on performance in the last 2-3 matches.
        Returns:
            {
                'form_modifier': int (-3 to +5),
                'form_status': 'hot' | 'in_form' | 'shield' | 'cold' | 'stable',
                'streak_label': str,
                'streak_icon': str
            }
        """
        pos = (player.get("position_name") or player.get("position") or "").lower()
        ovr = player.get("overall_rating", 75)
        
        # Analyze team's last 2-3 completed fixtures
        recent = recent_fixtures[:3] if recent_fixtures else []
        if not recent:
            return {
                "form_modifier": 0,
                "form_status": "stable",
                "streak_label": "Standard Form",
                "streak_icon": "➡️"
            }

        team_goals_scored = 0
        team_goals_conceded = 0
        team_wins = 0
        team_clean_sheets = 0
        
        for f in recent:
            is_home = f.get("home_slug") == club_slug
            scored = (f.get("home_score") if is_home else f.get("away_score")) or 0
            conceded = (f.get("away_score") if is_home else f.get("home_score")) or 0
            
            team_goals_scored += scored
            team_goals_conceded += conceded
            if scored > conceded:
                team_wins += 1
            if conceded == 0:
                team_clean_sheets += 1

        # 1. Attacking players (Forwards / Wingers / Attacking Midfielders)
        if "forward" in pos or "winger" in pos or "striker" in pos:
            if team_goals_scored >= 4 and team_wins >= 2:
                return {
                    "form_modifier": 4,
                    "form_status": "hot",
                    "streak_label": f"Goal Streak: {team_goals_scored} goals in last {len(recent)} games",
                    "streak_icon": "🔥"
                }
            elif team_goals_scored >= 2:
                return {
                    "form_modifier": 2,
                    "form_status": "in_form",
                    "streak_label": f"Attacking Rhythm: {team_goals_scored} goals in last {len(recent)} games",
                    "streak_icon": "⚡"
                }
            elif team_goals_scored <= 1 and len(recent) >= 2:
                return {
                    "form_modifier": -2,
                    "form_status": "cold",
                    "streak_label": f"Goal Drought: {team_goals_scored} goal in last {len(recent)} matches",
                    "streak_icon": "❄️"
                }

        # 2. Goalkeepers & Defenders
        elif "goalkeeper" in pos or "defender" in pos:
            if team_clean_sheets >= 2:
                return {
                    "form_modifier": 4,
                    "form_status": "shield",
                    "streak_label": f"Defensive Wall: {team_clean_sheets} clean sheets in last {len(recent)} games",
                    "streak_icon": "🛡️"
                }
            elif team_clean_sheets >= 1 or team_goals_conceded <= 1:
                return {
                    "form_modifier": 2,
                    "form_status": "in_form",
                    "streak_label": f"Resilient Defense: {team_clean_sheets} clean sheet in last {len(recent)} games",
                    "streak_icon": "🛡️"
                }
            elif team_goals_conceded >= 4 and len(recent) >= 2:
                return {
                    "form_modifier": -3,
                    "form_status": "cold",
                    "streak_label": f"Vulnerable: {team_goals_conceded} goals conceded recently",
                    "streak_icon": "❄️"
                }

        # 3. Midfielders
        else:
            if team_wins >= 2:
                return {
                    "form_modifier": 3,
                    "form_status": "hot",
                    "streak_label": "Midfield Dominance & Control Streak",
                    "streak_icon": "⚡"
                }
            elif team_wins >= 1 or team_clean_sheets >= 1:
                return {
                    "form_modifier": 1,
                    "form_status": "in_form",
                    "streak_label": "Midfield Composure & Passing Stability",
                    "streak_icon": "⚡"
                }
            elif team_wins == 0 and len(recent) >= 2:
                return {
                    "form_modifier": -2,
                    "form_status": "cold",
                    "streak_label": "Midfield Fatigue & Ball Retention Dip",
                    "streak_icon": "❄️"
                }

        return {
            "form_modifier": 0,
            "form_status": "stable",
            "streak_label": "Consistent Base Level",
            "streak_icon": "➡️"
        }

    # European competition nights (2026/27 season), loaded from the calendar
    # config so new Euro fixtures only need a data edit, not a code change.
    EURO_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "euro_schedule.json"
    _euro_nights_cache: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def _load_euro_nights(cls) -> List[Dict[str, Any]]:
        if cls._euro_nights_cache is None:
            try:
                with open(cls.EURO_CONFIG_PATH, "r", encoding="utf-8") as fh:
                    cls._euro_nights_cache = [n for n in json.load(fh).get("nights", []) if n.get("slug") and n.get("date")]
            except Exception:
                cls._euro_nights_cache = []
        return cls._euro_nights_cache

    def calculate_match_fatigue(self, club_slug: str, fixture_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates squad fatigue based on European midweek load.
        Fatigue only applies if the league fixture falls within 5 days after
        one of the club's European nights (from the config calendar);
        otherwise the squad is considered rested.
        """
        fresh = {
            "is_european": False,
            "competition": None,
            "opponent": None,
            "midweek_date": None,
            "days_rest": 7,
            "fatigue_modifier": 1,
            "fatigue_status": "fresh",
            "freshness_badge": "⚡ 7d Fully Rested",
            "notes": "Full 7-day domestic training cycle and tactical preparation.",
        }
        nights = [n for n in self._load_euro_nights() if n.get("slug") == club_slug]
        if not nights:
            return fresh
        # Date-aware: only penalize congested turnarounds after the most recent
        # European night preceding this fixture.
        if fixture_date:
            try:
                from datetime import date as _date
                fx_d = _date.fromisoformat(str(fixture_date)[:10])
            except Exception:
                fx_d = None
            if fx_d is not None:
                candidates = []
                for n in nights:
                    try:
                        eu_d = _date.fromisoformat(str(n["date"])[:10])
                    except Exception:
                        continue
                    delta = (fx_d - eu_d).days
                    if 0 <= delta <= 5:
                        candidates.append((delta, n))
                if not candidates:
                    return fresh
                candidates.sort(key=lambda t: t[0])
                rest_days, info = candidates[0]
            else:
                # Unparseable date: fall back to the nearest upcoming-or-past night.
                info = nights[-1]
                rest_days = 4
        else:
            info = nights[-1]
            rest_days = 4
        modifier = -3 if rest_days <= 3 else -2
        return {
            "is_european": True,
            "competition": info["comp"],
            "opponent": info["opponent"],
            "midweek_date": info["date"],
            "days_rest": rest_days,
            "fatigue_modifier": modifier,
            "fatigue_status": "fatigued",
            "freshness_badge": f"European Midweek ({rest_days}d Rest)",
            "notes": f"Squad rotation required after midweek {info['comp']} match vs {info['opponent']} ({rest_days} days rest).",
        }

    def calculate_dixon_coles_matrix(self, lambda_h: float, lambda_a: float, rho: float = -0.08, max_goals: int = 7) -> Dict[Tuple[int, int], float]:
        """
        Calculates bivariate score probability matrix with Dixon-Coles adjustment
        for low-scoring match correlation (tau_x,y parameterization).
        """
        matrix = {}
        total_prob = 0.0

        def poisson_pmf(k: int, lmbda: float) -> float:
            return (lmbda ** k) * math.exp(-lmbda) / math.factorial(k)

        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                if x == 0 and y == 0:
                    tau = 1.0 - lambda_h * lambda_a * rho
                elif x == 0 and y == 1:
                    tau = 1.0 + lambda_h * rho
                elif x == 1 and y == 0:
                    tau = 1.0 + lambda_a * rho
                elif x == 1 and y == 1:
                    tau = 1.0 - rho
                else:
                    tau = 1.0
                
                p = max(0.0, tau * poisson_pmf(x, lambda_h) * poisson_pmf(y, lambda_a))
                matrix[(x, y)] = p
                total_prob += p

        if total_prob > 0:
            for k in matrix:
                matrix[k] /= total_prob

        return matrix

    def _sample_dixon_coles(self, matrix: Dict[Tuple[int, int], float]) -> Tuple[int, int]:
        """Samples an exact (home_goals, away_goals) pair from the calibrated Dixon-Coles joint distribution."""
        items = list(matrix.keys())
        weights = list(matrix.values())
        return random.choices(items, weights=weights, k=1)[0]

    def get_most_probable_score(self, matrix: Dict[Tuple[int, int], float], lambda_h: float, lambda_a: float) -> Tuple[int, int]:
        """
        Determines the most probable, outcome-consistent scoreline (Zero Randomness Mode).
        Calculates category probabilities (Home Win, Draw, Away Win) and returns
        the highest-density scoreline for the favored outcome.
        """
        h_win_p = sum(p for (x, y), p in matrix.items() if x > y)
        draw_p = sum(p for (x, y), p in matrix.items() if x == y)
        a_win_p = sum(p for (x, y), p in matrix.items() if x < y)

        if h_win_p >= draw_p and h_win_p >= a_win_p:
            sub = {k: v for k, v in matrix.items() if k[0] > k[1]}
        elif a_win_p >= draw_p and a_win_p >= h_win_p:
            sub = {k: v for k, v in matrix.items() if k[0] < k[1]}
        else:
            sub = {k: v for k, v in matrix.items() if k[0] == k[1]}

        sorted_sub = sorted(sub.items(), key=lambda item: item[1], reverse=True)
        return sorted_sub[0][0]

    def _team_strength_inputs(self, team: Dict[str, Any], fixture_date: Optional[str]) -> Dict[str, Any]:
        """
        Computes the strength signals for one team used by BOTH the forecast and
        the single-match simulation, so the two paths can never drift apart:
        - starting-XI effective ratings (already include per-player form modifiers)
        - Elo club rating (5 seasons of real results) blended with squad quality
        - European fatigue modifier from the config-driven calendar
        - real recent form: weighted points-per-game over the last 3 finished
          fixtures (0.5 / 0.3 / 0.2 weights), derived from actual match results.
        - aggregated player momentum from real per-match goal data
        """
        starters = team.get("tactics", {}).get("starting_xi", [])
        ovrs = [p.get("effective_rating", p.get("overall_rating", 75)) for p in starters]
        avg_ovr = (sum(ovrs) / len(ovrs) if ovrs else 78.0 if team is not None else 76.0) + self.calculate_match_fatigue(team.get("slug", ""), fixture_date)["fatigue_modifier"]

        form = team.get("recent_form") or {}
        if form.get("has_data"):
            form_pts = float(form.get("weighted_ppg", 1.35))
            form_label = f"{form.get('weighted_ppg', 0):.1f} ppg last {form.get('played', 3)}"
        else:
            # Fallback: single last-result badge when no history is available.
            badge = (team.get("last_match", {}) or {}).get("res_badge")
            form_pts = 3.0 if badge == "W" else 1.0 if badge == "D" else 0.0
            form_label = "last result only"

        # Elo (5-season strength) blended with current squad quality:
        # elo_term converts an elo differential vs the league mean into a
        # 0..10 rating-points swing (~1.6 elo points per rating point).
        elo_term = 0.0
        elo_info = None
        if self.db is not None:
            try:
                rating = RatingsEngine.get_or_none(self.db, team.get("slug", ""))
                if rating:
                    elo_term = max(-10.0, min(10.0, (rating["elo"] - 1500.0) / 160.0))
                    elo_info = rating
            except Exception:
                elo_term = 0.0

        # Team-level momentum from real per-match player data
        mom_index, mom_hot = 50.0, []
        if self.db is not None and starters:
            try:
                mom = team_momentum(self.db, team.get("slug", ""), starters)
                mom_index = float(mom.get("index", 50.0))
                mom_hot = mom.get("hot", [])
            except Exception:
                pass

        return {
            "avg_ovr": avg_ovr,
            "position": team.get("position") or 10,
            "form_pts": form_pts,
            "form_label": form_label,
            "fatigue": self.calculate_match_fatigue(team.get("slug", ""), fixture_date),
            "elo": elo_info,
            "elo_term": elo_term,
            "momentum_index": mom_index,
            "momentum_hot": mom_hot,
        }

    def _match_strength_model(self, match_detail_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Single source of truth for net strength -> expected-goals mapping,
        shared by monte_carlo_forecast and simulate_fixture.
        """
        home = match_detail_data["home_team"]
        away = match_detail_data["away_team"]
        f = match_detail_data["fixture"]
        fixture_date = f.get("kickoff_time")

        hs = self._team_strength_inputs(home, fixture_date)
        as_ = self._team_strength_inputs(away, fixture_date)
        h_fatigue, a_fatigue = hs["fatigue"], as_["fatigue"]

        # Calibrated v3 weights. Elo (5 seasons of real results) is the primary
        # strength signal; rank/squad-quality/form temper it. Momentum from real
        # per-match player data adds a short-horizon nudge. Home advantage kept.
        elo_diff = (hs["elo_term"] - as_["elo_term"]) * 1.0
        rank_diff = (as_["position"] - hs["position"]) * 0.30
        rating_diff = (hs["avg_ovr"] - as_["avg_ovr"]) * 0.40
        form_diff = (hs["form_pts"] - as_["form_pts"]) * 0.25
        momentum_diff = (hs["momentum_index"] - as_["momentum_index"]) * 0.025
        home_advantage = 2.0

        net_h_advantage = elo_diff + rank_diff + rating_diff + form_diff + momentum_diff + home_advantage
        net_h_advantage = max(-8.0, min(8.0, net_h_advantage))

        # Base La Liga goals expectation: ~1.45 Home, ~1.17 Away (total ~2.62)
        base_h = 1.45
        base_a = 1.17
        exp_factor = net_h_advantage / 14.0
        lambda_h = max(0.55, min(3.0, base_h * math.exp(exp_factor * 0.45)))
        lambda_a = max(0.45, min(2.7, base_a * math.exp(-exp_factor * 0.45)))

        # Authentic Club & Manager Tactical Clash Evaluation
        h_pos, a_pos = hs["position"], as_["position"]
        clash = ClubTacticsRegistry.evaluate_tactical_clash(
            home.get("slug", ""),
            away.get("slug", ""),
            h_pos,
            a_pos
        )
        h_tact_mult = max(0.85, min(1.2, clash["home"]["xg_modifier"]))
        a_tact_mult = max(0.85, min(1.2, clash["away"]["xg_modifier"]))
        lambda_h = max(0.5, min(3.1, lambda_h * h_tact_mult))
        lambda_a = max(0.4, min(2.8, lambda_a * a_tact_mult))

        return {
            "home": home,
            "away": away,
            "fixture": f,
            "clash": clash,
            "lambda_h": lambda_h,
            "lambda_a": lambda_a,
            "home_strength": hs,
            "away_strength": as_,
            "fatigue": {"home": h_fatigue, "away": a_fatigue},
            "net_h_advantage": net_h_advantage,
            "components": {
                "elo_diff": round(elo_diff, 2),
                "rank_diff": round(rank_diff, 2),
                "rating_diff": round(rating_diff, 2),
                "form_diff": round(form_diff, 2),
                "momentum_diff": round(momentum_diff, 2),
                "home_advantage": home_advantage,
            },
        }

    def _outcome_probabilities(self, matrix: Dict[Tuple[int, int], float]) -> Dict[str, float]:
        """
        Closed-form outcome markets from the Dixon-Coles score matrix with
        shrinkage toward league base rates (La Liga long-run: H ~44% / D ~25% /
        A ~31%) to curb favorite overconfidence. Exact and deterministic.
        """
        raw_h = sum(p for (x, y), p in matrix.items() if x > y)
        raw_d = sum(p for (x, y), p in matrix.items() if x == y)
        raw_a = sum(p for (x, y), p in matrix.items() if x < y)
        shrink = 0.2
        h_win_p = (1 - shrink) * raw_h + shrink * 0.44
        draw_p = (1 - shrink) * raw_d + shrink * 0.25
        a_win_p = (1 - shrink) * raw_a + shrink * 0.31
        tot = h_win_p + draw_p + a_win_p
        return {"h": h_win_p / tot, "d": draw_p / tot, "a": a_win_p / tot}

    def monte_carlo_forecast(self, match_detail_data: Dict[str, Any], runs: int = 0, tactical_stance: str = "balanced") -> Dict[str, Any]:
        """
        Deterministic closed-form pre-match forecast. Aggregates the calibrated
        Dixon-Coles bivariate score matrix exactly — no random sampling.
        `runs` is accepted for backward compatibility and ignored.
        Same fixture + data => byte-identical probabilities on every call.
        """
        model = self._match_strength_model(match_detail_data)
        home, away = model["home"], model["away"]
        clash, h_fatigue, a_fatigue = model["clash"], model["fatigue"]["home"], model["fatigue"]["away"]
        lambda_h, lambda_a = model["lambda_h"], model["lambda_a"]

        matrix = self.calculate_dixon_coles_matrix(lambda_h, lambda_a, rho=-0.08)
        probs = self._outcome_probabilities(matrix)
        h_win_p, draw_p, a_win_p = probs["h"], probs["d"], probs["a"]

        over_2_5_p = sum(p for (x, y), p in matrix.items() if x + y > 2.5)
        under_2_5_p = sum(p for (x, y), p in matrix.items() if x + y <= 2.5)

        btts_yes_p = sum(p for (x, y), p in matrix.items() if x > 0 and y > 0)
        btts_no_p = sum(p for (x, y), p in matrix.items() if x == 0 or y == 0)

        # Top 3 exact scorelines
        sorted_scores = sorted(matrix.items(), key=lambda item: item[1], reverse=True)[:3]
        top_scorelines = [
            {"score": f"{x} - {y}", "probability": round(p * 100, 1)}
            for (x, y), p in sorted_scores
        ]

        hs, as_ = model["home_strength"], model["away_strength"]
        return {
            "runs": 0,
            "method": "closed_form_dixon_coles",
            "tactical_clash": clash,
            "home_win_pct": round(h_win_p * 100, 1),
            "draw_pct": round(draw_p * 100, 1),
            "away_win_pct": round(a_win_p * 100, 1),
            "top_scorelines": top_scorelines,
            "over_2_5_pct": round(over_2_5_p * 100, 1),
            "under_2_5_pct": round(under_2_5_p * 100, 1),
            "btts_yes_pct": round(btts_yes_p * 100, 1),
            "btts_no_pct": round(btts_no_p * 100, 1),
            "projected_xg": {
                "home": round(lambda_h, 2),
                "away": round(lambda_a, 2)
            },
            "form_analysis": {
                "home": {"weighted_ppg": round(hs["form_pts"], 2), "label": hs["form_label"]},
                "away": {"weighted_ppg": round(as_["form_pts"], 2), "label": as_["form_label"]}
            },
            "elo_analysis": {
                "home": {"elo": (hs.get("elo") or {}).get("elo"), "rank": (hs.get("elo") or {}).get("rank"),
                         "difficulty": (hs.get("elo") or {}).get("difficulty")},
                "away": {"elo": (as_.get("elo") or {}).get("elo"), "rank": (as_.get("elo") or {}).get("rank"),
                         "difficulty": (as_.get("elo") or {}).get("difficulty")}
            },
            "momentum_analysis": {
                "home": {"index": round(hs["momentum_index"], 1), "hot": hs["momentum_hot"]},
                "away": {"index": round(as_["momentum_index"], 1), "hot": as_["momentum_hot"]}
            },
            "model_components": model.get("components"),
            "fatigue_analysis": {
                "home": h_fatigue,
                "away": a_fatigue
            }
        }

    def calculate_tactical_radar(self, home_team: Dict[str, Any], away_team: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates 6-axis tactical matchup comparison (0-100 scale):
        1. Attack Potency
        2. Defensive Solidity
        3. Possession Control
        4. Pressing Intensity
        5. Counter & Transition Pace
        6. Form Momentum
        """
        def team_metrics(team, is_home=True):
            tactics = team.get("tactics", {})
            starters = tactics.get("starting_xi", [])
            pos = team.get("position", 10)
            style = (tactics.get("style", "")).lower()

            fwd_ovr = [p.get("effective_rating", p.get("overall_rating", 75)) for p in starters if "forward" in (p.get("position") or "").lower()]
            def_ovr = [p.get("effective_rating", p.get("overall_rating", 75)) for p in starters if "defender" in (p.get("position") or "").lower() or "goalkeeper" in (p.get("position") or "").lower()]
            mid_ovr = [p.get("effective_rating", p.get("overall_rating", 75)) for p in starters if "midfielder" in (p.get("position") or "").lower()]

            avg_fwd = sum(fwd_ovr)/len(fwd_ovr) if fwd_ovr else 76.0
            avg_def = sum(def_ovr)/len(def_ovr) if def_ovr else 76.0
            avg_mid = sum(mid_ovr)/len(mid_ovr) if mid_ovr else 76.0

            # 1. Attack Potency
            att = int(min(98, max(50, (avg_fwd - 65) * 2.2 + (21 - pos) * 1.2 + (4 if is_home else 0))))

            # 2. Defensive Solidity
            clean_sheets_boost = 6 if team.get("last_match", {}).get("res_badge") == "W" else 0
            defense = int(min(98, max(50, (avg_def - 65) * 2.1 + (21 - pos) * 1.1 + clean_sheets_boost)))

            # 3. Possession Control
            poss_boost = 12 if "possession" in style or "tiki-taka" in style or "positional" in style else -8 if "counter" in style or "low-block" in style else 2
            poss = int(min(98, max(45, (avg_mid - 65) * 2.2 + poss_boost + (3 if is_home else 0))))

            # 4. Pressing Intensity
            press_base = 92 if "gegenpressing" in style or "high-intensity" in style or "high-workrate" in style else 82 if "press" in style else 60 if "low-block" in style else 74
            press = int(min(98, max(50, press_base)))

            # 5. Counter & Transition Pace
            counter_base = 90 if "fast counter" in style or "vertical" in style or "direct" in style else 68 if "tiki-taka" in style else 78
            counter = int(min(98, max(45, counter_base)))

            # 6. Form Momentum
            last_res = team.get("last_match", {}).get("res_badge")
            form_val = 88 if last_res == "W" else 68 if last_res == "D" else 52
            form_val += (21 - pos) * 0.8
            momentum = int(min(98, max(45, form_val)))

            return {
                "attack_potency": att,
                "defensive_solidity": defense,
                "possession_control": poss,
                "pressing_intensity": press,
                "counter_pace": counter,
                "form_momentum": momentum
            }

        return {
            "axes": [
                {"key": "attack_potency", "label": "Attack Potency"},
                {"key": "defensive_solidity", "label": "Defensive Solidity"},
                {"key": "possession_control", "label": "Possession Control"},
                {"key": "pressing_intensity", "label": "Pressing Intensity"},
                {"key": "counter_pace", "label": "Counter Pace"},
                {"key": "form_momentum", "label": "Form Momentum"}
            ],
            "home": team_metrics(home_team, is_home=True),
            "away": team_metrics(away_team, is_home=False)
        }


    def generate_momentum_trend(self, home_poss: int, clash: Dict[str, Any], events: List[Dict[str, Any]], rng: random.Random) -> List[Dict[str, Any]]:
        """
        Generates minute-by-minute (1' to 90') momentum flow index (-100 to +100).
        Positive values represent Home territorial dominance, negative values represent Away dominance.
        """
        base = (home_poss - 50) * 1.5
        momentum = []
        
        goal_mins = {e["minute"]: (42.0 if e["team"] == "home" else -42.0) for e in events if e.get("type") == "goal"}
        save_mins = {e["minute"]: (18.0 if e["team"] == "home" else -18.0) for e in events if e.get("type") == "save"}
        card_mins = {e["minute"]: (-15.0 if e["team"] == "home" else 15.0) for e in events if e.get("type") == "card"}
        
        current_impulse = 0.0
        for m in range(1, 91):
            # Harmonic tactical flow waves (tactical cycles of pressing and settling)
            wave = math.sin(m / 4.4) * 15.0 + math.cos(m / 8.2) * 9.0
            
            # Event spikes
            if m in goal_mins:
                current_impulse = goal_mins[m]
            elif m in save_mins:
                current_impulse = save_mins[m]
            elif m in card_mins:
                current_impulse += card_mins[m]
            else:
                current_impulse *= 0.82 # smooth dissipation over ~6 minutes
                
            val = base + wave + current_impulse + rng.uniform(-3.5, 3.5)
            val = max(-95.0, min(95.0, val))
            dominant = "home" if val > 12.0 else "away" if val < -12.0 else "neutral"
            
            momentum.append({
                "minute": m,
                "value": round(val, 1),
                "dominant": dominant
            })
        return momentum

    def generate_phase_dominance(self, momentum: List[Dict[str, Any]], events: List[Dict[str, Any]], home_name: str, away_name: str) -> List[Dict[str, Any]]:
        """
        Divides match into 6 distinct 15-minute segments and computes territorial dominance %.
        """
        phases = [
            {"phase": 1, "start": 1, "end": 15, "name": "Opening Exchanges"},
            {"phase": 2, "start": 16, "end": 30, "name": "Tactical Settlement"},
            {"phase": 3, "start": 31, "end": 45, "name": "Pre-Interval Push"},
            {"phase": 4, "start": 46, "end": 60, "name": "Second-Half Adjustments"},
            {"phase": 5, "start": 61, "end": 75, "name": "Substitution Window"},
            {"phase": 6, "start": 76, "end": 90, "name": "Closing Drama"}
        ]
        
        results = []
        for p in phases:
            pts = [pt["value"] for pt in momentum if p["start"] <= pt["minute"] <= p["end"]]
            avg_v = sum(pts) / len(pts) if pts else 0
            h_pct = int(max(20, min(80, 50 + avg_v * 0.45)))
            a_pct = 100 - h_pct
            
            phase_events = [e for e in events if p["start"] <= e.get("minute", 0) <= p["end"]]
            goals_in_p = [f"⚽ {e.get('scorer')} ({e.get('minute')}')" for e in phase_events if e.get("type") == "goal"]
            
            dominant = home_name if h_pct >= 55 else away_name if a_pct >= 55 else "Contested"
            summary = (
                f"{home_name} high-press dominance" if h_pct >= 62 else
                f"{away_name} counter-threat territory" if a_pct >= 62 else
                f"Edge to {home_name}" if h_pct > 52 else
                f"Edge to {away_name}" if a_pct > 52 else
                "Balanced tactical stalemate"
            )
            
            results.append({
                "phase": p["phase"],
                "label": f"{p['start']}'-{p['end']}'",
                "name": p["name"],
                "home_pct": h_pct,
                "away_pct": a_pct,
                "dominant": dominant,
                "summary": summary,
                "goals": goals_in_p
            })
        return results

    def generate_xg_flow_trend(self, home_xg: float, away_xg: float, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generates cumulative xG step-ladder progression from 0' to 90'.
        """
        h_goals = {e["minute"]: 0.65 for e in events if e.get("type") == "goal" and e.get("team") == "home"}
        a_goals = {e["minute"]: 0.65 for e in events if e.get("type") == "goal" and e.get("team") == "away"}
        h_saves = {e["minute"]: 0.25 for e in events if e.get("type") == "save" and e.get("team") == "home"}
        a_saves = {e["minute"]: 0.25 for e in events if e.get("type") == "save" and e.get("team") == "away"}
        
        h_residual = max(0.05, home_xg - sum(h_goals.values()) - sum(h_saves.values()))
        a_residual = max(0.05, away_xg - sum(a_goals.values()) - sum(a_saves.values()))
        
        h_step = h_residual / 90.0
        a_step = a_residual / 90.0
        
        h_cum = 0.0
        a_cum = 0.0
        trend = []
        for m in range(0, 91):
            if m in h_goals:
                h_cum += h_goals[m]
            elif m in h_saves:
                h_cum += h_saves[m]
            else:
                h_cum += h_step
                
            if m in a_goals:
                a_cum += a_goals[m]
            elif m in a_saves:
                a_cum += a_saves[m]
            else:
                a_cum += a_step
                
            trend.append({
                "minute": m,
                "home_xg": round(min(home_xg, h_cum), 2),
                "away_xg": round(min(away_xg, a_cum), 2)
            })
        return trend

    def generate_win_probability_trend(self, home_win_pct: float, draw_pct: float, away_win_pct: float, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculates dynamic win probability evolution across match intervals.
        """
        snapshots = [0, 15, 30, 45, 60, 75, 90]
        trend = []
        
        for snap in snapshots:
            h_score = sum(1 for e in events if e.get("type") == "goal" and e.get("team") == "home" and e.get("minute") <= snap)
            a_score = sum(1 for e in events if e.get("type") == "goal" and e.get("team") == "away" and e.get("minute") <= snap)
            diff = h_score - a_score
            time_factor = snap / 90.0
            
            if snap == 0:
                h_p, d_p, a_p = home_win_pct, draw_pct, away_win_pct
            elif diff == 0:
                d_p = round(min(88.0, draw_pct + time_factor * 36.0), 1)
                rem = 100.0 - d_p
                h_share = home_win_pct / (home_win_pct + away_win_pct + 0.01)
                h_p = round(rem * h_share, 1)
                a_p = round(rem * (1.0 - h_share), 1)
            elif diff > 0:
                lead_mult = 1.0 + (diff - 1) * 0.4
                h_p = round(min(99.0, 62.0 + time_factor * 35.0 * lead_mult), 1)
                rem = 100.0 - h_p
                d_p = round(rem * 0.65, 1)
                a_p = round(rem * 0.35, 1)
            else:
                lead_mult = 1.0 + (-diff - 1) * 0.4
                a_p = round(min(99.0, 60.0 + time_factor * 36.0 * lead_mult), 1)
                rem = 100.0 - a_p
                d_p = round(rem * 0.65, 1)
                h_p = round(rem * 0.35, 1)
                
            trend.append({
                "minute": snap,
                "home_prob": h_p,
                "draw_prob": d_p,
                "away_prob": a_p,
                "score": f"{h_score} - {a_score}"
            })
        return trend

    def generate_match_trend_narrative(self, home_name: str, away_name: str, clash: Dict[str, Any], events: List[Dict[str, Any]], stats: Dict[str, Any], phase_dominance: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Produces strategic match trend narrative commentary ("How the match is going").
        """
        h_goals = stats["home_goals"]
        a_goals = stats["away_goals"]
        h_poss = stats["home_poss"]
        a_poss = stats["away_poss"]
        
        first_goal = next((e for e in events if e.get("type") == "goal"), None)
        turning_point = "Early tactical probing with both structures remaining compact."
        if first_goal:
            turning_point = f"Minute {first_goal['minute']}: Breakthrough goal by {first_goal['scorer']} forced the opposition to break their compact shape."
            
        p4 = next((p for p in phase_dominance if p["phase"] == 4), None)
        p5 = next((p for p in phase_dominance if p["phase"] == 5), None)
        
        if h_goals > a_goals:
            headline = f"{home_name} Dictates Tempo: Tactical Control Delivers Three Points"
            flow_summary = f"{home_name} successfully executed {clash['home']['manager']}'s identity, capitalizing on territory and breaking through with precision finishing."
        elif a_goals > h_goals:
            headline = f"{away_name} Clinical Counter: Tactical Resilience Stuns {home_name}"
            flow_summary = f"{away_name} absorbed early pressure and punished {home_name}'s high defensive line with lethal transitions."
        else:
            headline = f"Tactical Stalemate: Resilient Defenses Neutralize Attacking Threats"
            flow_summary = f"Neither manager conceded tactical territory, resulting in a balanced clash of styles."
            
        return {
            "headline": headline,
            "flow_summary": flow_summary,
            "turning_point": turning_point,
            "tactical_verdict": clash.get("tactical_battle_description", "Tactical matchup played out within projected statistical boundaries.")
        }

    def simulate_fixture(self, match_detail_data: Dict[str, Any], tactical_stance: str = "balanced", custom_substitutions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Simulates match using team ratings, starting XI ratings, dynamic player form,
        European fatigue modifiers, interactive manager mode tactical stance, and custom substitutions.
        Uses bivariate Dixon-Coles sampling and generates an exact 1-to-1 event timeline.
        """
        f = match_detail_data["fixture"]
        home = match_detail_data["home_team"]
        away = match_detail_data["away_team"]

        h_tactics = home.get("tactics", {})
        a_tactics = away.get("tactics", {})

        # Deep copy starting lists so substitutions do not mutate original dict permanently
        h_starters = [dict(p) for p in h_tactics.get("starting_xi", [])]
        a_starters = [dict(p) for p in a_tactics.get("starting_xi", [])]
        h_bench = h_tactics.get("bench", [])
        a_bench = a_tactics.get("bench", [])

        # Apply user substitutions if provided
        if custom_substitutions:
            for sub in custom_substitutions:
                side = sub.get("team", "home")
                out_id = sub.get("out_id")
                in_id = sub.get("in_id")
                if side == "home":
                    in_player = next((p for p in h_bench if p.get("id") == in_id), None)
                    if in_player:
                        for idx, p in enumerate(h_starters):
                            if p.get("id") == out_id:
                                swapped = dict(in_player)
                                swapped["slot"] = p.get("slot")
                                swapped["x"] = p.get("x")
                                swapped["y"] = p.get("y")
                                h_starters[idx] = swapped
                                break
                elif side == "away":
                    in_player = next((p for p in a_bench if p.get("id") == in_id), None)
                    if in_player:
                        for idx, p in enumerate(a_starters):
                            if p.get("id") == out_id:
                                swapped = dict(in_player)
                                swapped["slot"] = p.get("slot")
                                swapped["x"] = p.get("x")
                                swapped["y"] = p.get("y")
                                a_starters[idx] = swapped
                                break

        # Shared strength model (single source of truth, matches the forecast).
        # Substitutions are applied to the XI copy above, so feed the modified
        # lineups back into the model instead of the originals.
        model_input = dict(match_detail_data)
        model_input["home_team"] = {**home, "tactics": {**h_tactics, "starting_xi": h_starters}}
        model_input["away_team"] = {**away, "tactics": {**a_tactics, "starting_xi": a_starters}}
        model = self._match_strength_model(model_input)
        clash = model["clash"]
        lambda_h, lambda_a = model["lambda_h"], model["lambda_a"]
        h_fatigue = model["fatigue"]["home"]
        a_fatigue = model["fatigue"]["away"]
        h_pos = model["home_strength"]["position"]
        a_pos = model["away_strength"]["position"]

        # Per-player momentum: hot players (esp. after an explosive game vs a
        # weaker opponent) get a real scorer-weight bump in the simulation.
        h_mom_rows = a_mom_rows = None
        if self.db is not None:
            try:
                from .momentum import rows_for_club
                h_mom_rows = rows_for_club(self.db, home.get("slug", ""))
                a_mom_rows = rows_for_club(self.db, away.get("slug", ""))
            except Exception:
                pass
        for p in h_starters:
            m = compute_momentum(self.db, p, home.get("slug", ""), club_rows=h_mom_rows)
            p["momentum"] = m.to_dict()
            p["momentum_modifier"] = m.sim_modifier
        for p in a_starters:
            m = compute_momentum(self.db, p, away.get("slug", ""), club_rows=a_mom_rows)
            p["momentum"] = m.to_dict()
            p["momentum_modifier"] = m.sim_modifier

        # Calibrated Dixon-Coles score calculation (Most Probable Mode - Zero Randomness)
        dc_matrix = self.calculate_dixon_coles_matrix(lambda_h, lambda_a, rho=-0.08)
        home_goals, away_goals = self.get_most_probable_score(dc_matrix, lambda_h, lambda_a)

        # Cap extreme blowout anomalies
        home_goals = min(home_goals, 6)
        away_goals = min(away_goals, 5)

        # Reproducible PRNG seeded by fixture ID + club tactical profiles + substitutions
        fid_num = int(f.get("id") or 20260401)
        tactical_seed_val = sum(ord(c) for c in (clash["home"]["tactical_identity"] + clash["away"]["tactical_identity"]))
        subs_val = sum(int(s.get("in_id", 0)) * 31 + int(s.get("out_id", 0)) for s in (custom_substitutions or []))
        seed_val = (fid_num * 10007 + tactical_seed_val * 31 + subs_val) & 0x7FFFFFFF
        rng = random.Random(seed_val)  # local instance: no shared global state

        # 2. Build 1-to-1 Match Incident Timeline
        events = []
        used_minutes = set()

        def pick_minute():
            for _ in range(100):
                m = rng.randint(3, 93)
                if m not in used_minutes:
                    used_minutes.add(m)
                    return m
            return rng.randint(1, 90)

        # Scorer selection weights
        def select_scorer(starters, side_name):
            if not starters:
                return {"name": side_name, "id": None, "slug": None}, None
            
            # Weight attackers much higher, then midfielders, then defenders.
            # form_boost (team-result heuristic) + momentum_modifier (real
            # per-match data incl. explosive-game boost) both apply.
            weights = []
            for p in starters:
                slot = (p.get("slot") or "").upper()
                pos = (p.get("position") or "").lower()
                form_boost = p.get("form_modifier", 0) + p.get("momentum_modifier", 0)

                w = 1.0
                if slot in ["ST", "CF"]:
                    w = 18.0 + form_boost * 3
                elif slot in ["LW", "RW", "LAM", "RAM", "SS"]:
                    w = 14.0 + form_boost * 2.5
                elif slot in ["CAM", "AM"]:
                    w = 11.0 + form_boost * 2
                elif slot in ["LM", "RM", "CM", "LCM", "RCM"]:
                    w = 6.0 + form_boost * 1.5
                elif slot in ["DM", "CDM", "LDM", "RDM"]:
                    w = 3.0
                elif "defender" in pos:
                    w = 2.0
                else:
                    w = 0.1 # GK

                weights.append(max(0.2, w))

            scorer = rng.choices(starters, weights=weights, k=1)[0]
            
            # Select assist maker (different from scorer)
            assist_candidates = [p for p in starters if p.get("id") != scorer.get("id") and "goalkeeper" not in (p.get("position") or "").lower()]
            assist_weights = [10.0 if (p.get("slot") in ["CAM", "LW", "RW", "LB", "RB", "CM"]) else 4.0 for p in assist_candidates]
            
            assister = None
            if rng.random() < 0.78 and assist_candidates:
                assister = rng.choices(assist_candidates, weights=assist_weights, k=1)[0]

            return scorer, assister

        # Generate Home Goals (Exact count match)
        for _ in range(home_goals):
            min_val = pick_minute()
            scorer, assister = select_scorer(h_starters, home["name"])
            events.append({
                "type": "goal",
                "team": "home",
                "team_name": home["name"],
                "minute": min_val,
                "scorer": scorer["name"],
                "scorer_id": scorer.get("id"),
                "scorer_slug": scorer.get("slug"),
                "assist": assister["name"] if assister else None,
                "description": f"⚽ GOAL! {scorer['name']} scores for {home['name']}!{(' (Assist: ' + assister['name'] + ')') if assister else ''}"
            })

        # Generate Away Goals (Exact count match)
        for _ in range(away_goals):
            min_val = pick_minute()
            scorer, assister = select_scorer(a_starters, away["name"])
            events.append({
                "type": "goal",
                "team": "away",
                "team_name": away["name"],
                "minute": min_val,
                "scorer": scorer["name"],
                "scorer_id": scorer.get("id"),
                "scorer_slug": scorer.get("slug"),
                "assist": assister["name"] if assister else None,
                "description": f"⚽ GOAL! {scorer['name']} scores for {away['name']}!{(' (Assist: ' + assister['name'] + ')') if assister else ''}"
            })

        # Add 2-3 non-goal match events (saves, cards)
        if h_starters:
            h_defenders = [p for p in h_starters if "defender" in (p.get("position") or "").lower() or "midfielder" in (p.get("position") or "").lower()]
            if h_defenders and rng.random() < 0.85:
                card_player = rng.choice(h_defenders)
                events.append({
                    "type": "card",
                    "team": "home",
                    "team_name": home["name"],
                    "minute": pick_minute(),
                    "player": card_player["name"],
                    "description": f"🟨 Yellow Card: {card_player['name']} ({home['name']}) - Tactical foul"
                })

        if a_starters:
            a_defenders = [p for p in a_starters if "defender" in (p.get("position") or "").lower() or "midfielder" in (p.get("position") or "").lower()]
            if a_defenders and rng.random() < 0.85:
                card_player = rng.choice(a_defenders)
                events.append({
                    "type": "card",
                    "team": "away",
                    "team_name": away["name"],
                    "minute": pick_minute(),
                    "player": card_player["name"],
                    "description": f"🟨 Yellow Card: {card_player['name']} ({away['name']}) - Reckless challenge"
                })

        # Key Goalkeeper Saves
        h_gk = next((p for p in h_starters if "goalkeeper" in (p.get("position") or "").lower()), None)
        a_gk = next((p for p in a_starters if "goalkeeper" in (p.get("position") or "").lower()), None)

        if a_gk and rng.random() < 0.8:
            events.append({
                "type": "save",
                "team": "away",
                "team_name": away["name"],
                "minute": pick_minute(),
                "player": a_gk["name"],
                "description": f"🧤 Diving save by {a_gk['name']}! Denies a close-range shot."
            })

        if h_gk and rng.random() < 0.75:
            events.append({
                "type": "save",
                "team": "home",
                "team_name": home["name"],
                "minute": pick_minute(),
                "player": h_gk["name"],
                "description": f"🧤 Reflex save by {h_gk['name']}! Keeps {home['name']} solid."
            })

        # 2b. Situational Game-State Tendencies (Lead Protection vs Late Siege)
        # If Home is leading and manager has high lead preservation (e.g. Simeone, Bordalas, Baraja)
        if home_goals > away_goals and clash["home"]["lead_preservation"] >= 78:
            events.append({
                "type": "game_management",
                "team": "home",
                "team_name": home["name"],
                "minute": rng.randint(76, 86),
                "description": f"⏱️ Game Management: {clash['home']['manager']} directs {home['name']} into a structured shell to protect the lead."
            })
        elif away_goals > home_goals and clash["away"]["lead_preservation"] >= 78:
            events.append({
                "type": "game_management",
                "team": "away",
                "team_name": away["name"],
                "minute": rng.randint(76, 86),
                "description": f"⏱️ Game Management: {clash['away']['manager']} directs {away['name']} to slow the tempo and protect the away advantage."
            })

        # If a team is trailing late and has high chasing intensity (e.g. Madrid, Barca, Betis)
        if home_goals < away_goals and clash["home"]["late_chase_intensity"] >= 86:
            events.append({
                "type": "attacking_siege",
                "team": "home",
                "team_name": home["name"],
                "minute": rng.randint(84, 91),
                "description": f"⚡ Late Siege: {clash['home']['manager']} commits extra numbers into the box in a frantic search for an equalizer!"
            })
        elif away_goals < home_goals and clash["away"]["late_chase_intensity"] >= 86:
            events.append({
                "type": "attacking_siege",
                "team": "away",
                "team_name": away["name"],
                "minute": rng.randint(84, 91),
                "description": f"⚡ Late Siege: {clash['away']['manager']} orders all-out vertical bombardment into the final third!"
            })

        # Sort all events chronologically by minute
        events.sort(key=lambda x: x["minute"])

        # 3. Match Statistics Calculation based on authentic club tactical possession split
        base_h_poss = clash["expected_possession"]["home"]
        home_poss = int(base_h_poss + rng.randint(-2, 2))
        home_poss = max(32, min(68, home_poss))
        away_poss = 100 - home_poss

        home_shots = max(home_goals + 3, int(8 + (home_poss / 50.0) * 4 + home_goals * 2 + rng.randint(0, 2)))
        away_shots = max(away_goals + 2, int(6 + (away_poss / 50.0) * 4 + away_goals * 2 + rng.randint(0, 2)))

        home_target = max(home_goals, min(home_shots, int(home_goals + (home_shots - home_goals) * 0.35 + rng.randint(1, 2))))
        away_target = max(away_goals, min(away_shots, int(away_goals + (away_shots - away_goals) * 0.32 + rng.randint(1, 2))))

        home_xg = round(home_goals * 0.72 + (home_target - home_goals) * 0.16 + (home_shots - home_target) * 0.04 + rng.uniform(0.05, 0.18), 2)
        away_xg = round(away_goals * 0.72 + (away_target - away_goals) * 0.16 + (away_shots - away_target) * 0.04 + rng.uniform(0.05, 0.18), 2)

        corners_h = max(2, int(home_shots * 0.45 + rng.randint(0, 2)))
        corners_a = max(1, int(away_shots * 0.40 + rng.randint(0, 2)))

        fouls_h = rng.randint(8, 14)
        fouls_a = rng.randint(9, 15)

        # Verification check: goal events count must strictly match score
        assert len([e for e in events if e["type"] == "goal" and e["team"] == "home"]) == home_goals
        assert len([e for e in events if e["type"] == "goal" and e["team"] == "away"]) == away_goals

        # Generate Predictive Match Trends & Game Flow
        momentum_trend = self.generate_momentum_trend(home_poss, clash, events, rng)
        phase_dominance = self.generate_phase_dominance(momentum_trend, events, home["name"], away["name"])
        xg_flow = self.generate_xg_flow_trend(home_xg, away_xg, events)
        
        # Calculate theoretical Win Probability Trend based on Dixon-Coles parameters
        h_win_base = round(sum(p for (x, y), p in dc_matrix.items() if x > y) * 100, 1)
        d_base = round(sum(p for (x, y), p in dc_matrix.items() if x == y) * 100, 1)
        a_win_base = round(sum(p for (x, y), p in dc_matrix.items() if x < y) * 100, 1)
        win_prob_trend = self.generate_win_probability_trend(h_win_base, d_base, a_win_base, events)
        
        trend_narrative = self.generate_match_trend_narrative(
            home["name"], away["name"], clash, events,
            {"home_poss": home_poss, "away_poss": away_poss, "home_goals": home_goals, "away_goals": away_goals},
            phase_dominance
        )

        return {
            "fixture_id": f.get("id"),
            "mode": "authentic_club_tactics",
            "tactical_clash": clash,
            "tactical_stance": "club_identity",
            "is_deterministic": True,
            "home_score": home_goals,
            "away_score": away_goals,
            "trends": {
                "momentum": momentum_trend,
                "phases": phase_dominance,
                "xg_flow": xg_flow,
                "win_probability": win_prob_trend,
                "narrative": trend_narrative
            },
            "result_type": "home_win" if home_goals > away_goals else "away_win" if away_goals > home_goals else "draw",
            "events": events,
            "stats": {
                "possession": {"home": home_poss, "away": away_poss},
                "xg": {"home": home_xg, "away": away_xg},
                "shots": {"home": home_shots, "away": away_shots},
                "shots_on_target": {"home": home_target, "away": away_target},
                "corners": {"home": corners_h, "away": corners_a},
                "fouls": {"home": fouls_h, "away": fouls_a}
            },
            "expected_goals_lambda": {
                "home": round(lambda_h, 2),
                "away": round(lambda_a, 2)
            },
            "fatigue_analysis": {
                "home": h_fatigue,
                "away": a_fatigue
            }
        }
