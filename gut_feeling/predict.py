"""
Gut Feeling Match Prediction Tool
Usage:
  python gut_feeling/predict.py --home "Arsenal" --away "Chelsea"
  python gut_feeling/predict.py --matchweek
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import csv
import argparse
from typing import Tuple, Dict, Any
from gut_feeling.model import GutFeelingEngine

CSV_PATH = os.path.join(os.path.dirname(__file__), "clean_matches.csv")


def load_latest_engine_state() -> Tuple[GutFeelingEngine, Dict[str, float], float, float]:
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        matches = list(csv.DictReader(f))

    for m in matches:
        m["fthg"] = int(m["fthg"])
        m["ftag"] = int(m["ftag"])
        m["target"] = int(m["target"])

    # Selected optimal settings from walk-forward tuning
    engine = GutFeelingEngine(
        w_elo=0.9,
        w_form=0.1,
        k_goal=0.35,
        sigma_noise=0.05,
        n_sim=10000,
        strong_threshold=0.55,
        lean_threshold=0.45,
        random_seed=42,
    )

    proc = engine.process_season_data(matches)

    # Compute league averages from the most recent full season
    last_season = matches[-1]["season"]
    s_matches = [m for m in matches if m["season"] == last_season]
    h_avg = sum(m["fthg"] for m in s_matches) / len(s_matches)
    a_avg = sum(m["ftag"] for m in s_matches) / len(s_matches)

    # Latest ratings & form
    latest_team_stats = {}
    for m in proc:
        latest_team_stats[m["home_team"]] = {"z_elo": m["z_elo_h"], "z_form": m["z_form_h"]}
        latest_team_stats[m["away_team"]] = {"z_elo": m["z_elo_a"], "z_form": m["z_form_a"]}

    return engine, latest_team_stats, h_avg, a_avg


def predict_match(home: str, away: str):
    engine, team_stats, h_avg, a_avg = load_latest_engine_state()

    h_stat = team_stats.get(home, {"z_elo": 0.0, "z_form": 0.0})
    a_stat = team_stats.get(away, {"z_elo": 0.0, "z_form": 0.0})

    s_h, s_a, gap = engine.compute_strength_gap(
        h_stat["z_elo"], h_stat["z_form"], a_stat["z_elo"], a_stat["z_form"]
    )
    h_xg, a_xg = engine.convert_strength_to_xg(gap, h_avg, a_avg)
    ph, pd, pa = engine.simulate_probabilities(h_xg, a_xg, match_seed=42)
    conf, label = engine.label_confidence(ph, pd, pa)

    print("\n" + "=" * 60)
    print(f"GUT FEELING MATCH PREDICTION: {home} vs {away}")
    print("=" * 60)
    print(f"Home Strength:  {s_h:+.3f} (Elo z: {h_stat['z_elo']:+.2f}, Form z: {h_stat['z_form']:+.2f})")
    print(f"Away Strength:  {s_a:+.3f} (Elo z: {a_stat['z_elo']:+.2f}, Form z: {a_stat['z_form']:+.2f})")
    print(f"Strength Gap:   {gap:+.3f}")
    print(f"Expected Goals: {home} {h_xg:.2f} - {a_xg:.2f} {away}")
    print("-" * 60)
    print(f"Simulated Win/Draw/Loss Probabilities (10,000 runs):")
    print(f"  [Home] {home} Win:   {ph*100:.2f}% (Implied Fair Odds: {1.0/ph:.2f})")
    print(f"  [Draw] Draw:             {pd*100:.2f}% (Implied Fair Odds: {1.0/pd:.2f})")
    print(f"  [Away] {away} Win:   {pa*100:.2f}% (Implied Fair Odds: {1.0/pa:.2f})")
    print("-" * 60)
    print(f"Confidence:     {conf*100:.2f}%")
    print(f"Verdict:        {label.upper()}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Gut Feeling Football Predictor")
    parser.add_argument("--home", default="Arsenal", help="Home Team Name")
    parser.add_argument("--away", default="Chelsea", help="Away Team Name")
    args = parser.parse_args()

    predict_match(args.home, args.away)


if __name__ == "__main__":
    main()
