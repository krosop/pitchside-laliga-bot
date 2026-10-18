"""
Chronological backtest of the v3 forecast model (Elo + form + home advantage
through the same Dixon-Coles mapping the live engine uses).

For every match of a season (after each side has 6+ prior matches that season)
we compute the forecast using ONLY information available at that moment:
  * Elo: replayed match-by-match from the full multi-season archive
  * form: weighted last-3 PPG from that season's earlier results
  * home advantage
Then we score the closed-form probabilities against the real outcome with
proper probabilistic metrics (not just hit rate):

  Brier score  - mean squared error of the 1X2 probability vector (lower is
                 better; a blind 1/3 guess scores 0.667, decent football
                 models land 0.55-0.60 on 1X2)
  Log loss     - information-theoretic scoring
  Accuracy     - most-likely outcome hit rate
  Calibration  - predicted vs observed home-win/draw/away-win frequencies

Run:  python -m src.backtest_v3
"""
import math
import os
import sys
from typing import Dict, List

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.ratings import RatingsEngine, ELO_BASE, K_FACTOR, HOME_ADV  # noqa: E402
from src.simulation_engine import SimulationEngine  # noqa: E402
from src.mirror_footballdata import DB_PATH  # noqa: E402

import sqlite3  # noqa: E402


def _weighted_form(matches: List[int], n: int = 3) -> float:
    recent = matches[-n:]
    if not recent:
        return 1.35
    weights = [0.2, 0.3, 0.5][-len(recent):]
    return sum(w * m for w, m in zip(weights, recent)) / sum(weights)


def _match_lambda(elo_h: float, elo_a: float, form_h: float, form_a: float,
                  pos_h: int, pos_a: int, pos_count: int) -> tuple:
    """Same mapping as the live engine's v3 model (replicated for offline replay)."""
    elo_term_h = max(-10.0, min(10.0, (elo_h - 1500.0) / 160.0))
    elo_term_a = max(-10.0, min(10.0, (elo_a - 1500.0) / 160.0))
    elo_diff = elo_term_h - elo_term_a
    rank_diff = (pos_a - pos_h) * 0.30
    # squad-quality proxy: use elo-derived rating points as a stand-in for avg_ovr
    rating_h = 72.0 + elo_term_h * 1.5
    rating_a = 72.0 + elo_term_a * 1.5
    rating_diff = (rating_h - rating_a) * 0.40
    form_diff = (form_h - form_a) * 0.25
    net = elo_diff + rank_diff + rating_diff + form_diff + 2.0
    net = max(-8.0, min(8.0, net))
    exp_factor = net / 14.0
    lambda_h = max(0.55, min(3.0, 1.45 * math.exp(exp_factor * 0.45)))
    lambda_a = max(0.45, min(2.7, 1.17 * math.exp(-exp_factor * 0.45)))
    return lambda_h, lambda_a


def _outcome_probs(lambda_h: float, lambda_a: float, max_goals: int = 8) -> Dict[str, float]:
    eng = SimulationEngine()
    matrix = eng.calculate_dixon_coles_matrix(lambda_h, lambda_a, rho=-0.08, max_goals=max_goals)
    probs = eng._outcome_probabilities(matrix)
    return probs


def run(seasons: List[int] = (2025, 2026)) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    all_rows = conn.execute(
        "SELECT season, matchday, home_team_id, away_team_id, home_score, away_score, kickoff_time "
        "FROM fixtures WHERE status='FINISHED' AND home_score IS NOT NULL "
        "ORDER BY kickoff_time ASC, id ASC"
    ).fetchall()
    conn.close()

    results = {}
    for season in seasons:
        season_rows = [r for r in all_rows if r["season"] == season]
        elo: Dict[int, float] = {}
        # warm-start Elo from all PRIOR seasons
        for r in all_rows:
            if r["season"] >= season:
                break
            _update_elo(elo, r)

        pts: Dict[int, List[int]] = {}   # points sequence per team this season
        briers, loglosses, hits = [], [], 0
        calib = {"H": [0, 0.0], "D": [0, 0.0], "A": [0, 0.0]}
        tested = 0

        for r in season_rows:
            h, a = r["home_team_id"], r["away_team_id"]
            if h not in elo:
                elo[h] = ELO_BASE
            if a not in elo:
                elo[a] = ELO_BASE
            form_h = _weighted_form(pts.get(h, []))
            form_a = _weighted_form(pts.get(a, []))
            pos_h = min(len(pts.get(h, [])) + 1, 20)
            pos_a = min(len(pts.get(a, [])) + 1, 20)

            if len(pts.get(h, [])) >= 6 and len(pts.get(a, [])) >= 6:
                lh, la = _match_lambda(elo[h], elo[a], form_h, form_a, pos_h, pos_a, 20)
                p = _outcome_probs(lh, la)
                real_h, real_a = r["home_score"], r["away_score"]
                outcome = "H" if real_h > real_a else "A" if real_a > real_h else "D"

                vec = {"H": p["h"], "D": p["d"], "A": p["a"]}
                y = {"H": 0.0, "D": 0.0, "A": 0.0}
                y[outcome] = 1.0
                briers.append(sum((vec[k] - y[k]) ** 2 for k in vec))
                loglosses.append(-math.log(max(vec[outcome], 1e-9)))
                pred = max(vec, key=vec.get)
                hits += (pred == outcome)
                for k in calib:
                    calib[k][0] += 1 if outcome == k else 0
                    calib[k][1] += vec[k]
                tested += 1

            # update state AFTER prediction (no look-ahead)
            _update_elo(elo, r, preloaded=True)
            real_h, real_a = r["home_score"], r["away_score"]
            pts.setdefault(h, []).append(3 if real_h > real_a else 1 if real_h == real_a else 0)
            pts.setdefault(a, []).append(3 if real_a > real_h else 1 if real_a == real_h else 0)

        n = max(1, tested)
        results[season] = {
            "tested": tested,
            "brier": sum(briers) / n,
            "log_loss": sum(loglosses) / n,
            "accuracy": hits / n,
            "calibration": {
                k: {"predicted": round(v[1] / n, 3), "observed": round(v[0] / n, 3)}
                for k, v in calib.items()
            },
        }
    return results


def _update_elo(elo: Dict[int, float], r, preloaded: bool = False):
    h, a = r["home_team_id"], r["away_team_id"]
    if h not in elo:
        elo[h] = ELO_BASE
    if a not in elo:
        elo[a] = ELO_BASE
    hs, as_ = r["home_score"] or 0, r["away_score"] or 0
    exp_h = 1.0 / (1.0 + 10 ** ((elo[a] - elo[h] - HOME_ADV) / 400.0))
    score_h = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0
    margin = abs(hs - as_)
    mult = min(3.5, math.sqrt(margin)) if margin > 1 else 1.0
    delta = K_FACTOR * mult * (score_h - exp_h)
    elo[h] += delta
    elo[a] -= delta


if __name__ == "__main__":
    out = run()
    print("=" * 64)
    print("STATSPHERE v3 FORECAST BACKTEST (chronological, no look-ahead)")
    print("=" * 64)
    for season, m in out.items():
        label = f"{season}/{str(season + 1)[2:]}"
        print(f"\nSeason {label}: {m['tested']} matches")
        print(f"  Brier score : {m['brier']:.4f}   (blind guess 0.667, good models < 0.60)")
        print(f"  Log loss    : {m['log_loss']:.4f}")
        print(f"  Hit rate    : {m['accuracy'] * 100:.1f}%")
        print("  Calibration (predicted vs observed):")
        for k, c in m["calibration"].items():
            print(f"    {k}: {c['predicted'] * 100:5.1f}% vs {c['observed'] * 100:5.1f}%")
    print("=" * 64)
