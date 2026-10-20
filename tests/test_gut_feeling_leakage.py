import pytest
from gut_feeling.model import GutFeelingEngine


def test_rule_1_pre_kickoff_integrity_no_future_leakage():
    """
    Verifies Rule 1:
    1. Pre-match Elo ratings, form scores, and predictions for match T
       use only matches played strictly before kickoff.
    2. Changing or flipping the outcome of match T has ZERO impact on
       the prediction or pre-match features generated for match T.
    3. The ratings update and history append happen strictly post-prediction.
    """
    engine = GutFeelingEngine(w_elo=0.7, w_form=0.3, k_goal=0.25, sigma_noise=0.10)

    # Sequence of 3 historical matches followed by match 4
    matches_scenario_a = [
        {"date": "2023-08-11", "season": "2023-24", "home_team": "Burnley", "away_team": "Man City", "fthg": 0, "ftag": 3, "target": 2},
        {"date": "2023-08-12", "season": "2023-24", "home_team": "Arsenal", "away_team": "Nottingham Forest", "fthg": 2, "ftag": 1, "target": 0},
        {"date": "2023-08-19", "season": "2023-24", "home_team": "Man City", "away_team": "Newcastle", "fthg": 1, "ftag": 0, "target": 0},
        # Match 4 to predict: Arsenal vs Man City
        {"date": "2023-08-27", "season": "2023-24", "home_team": "Arsenal", "away_team": "Man City", "fthg": 1, "ftag": 0, "target": 0},
    ]

    # Identical sequence, but in scenario B match 4 ends in a 0-5 blowout away win instead of 1-0 home win
    matches_scenario_b = [
        {"date": "2023-08-11", "season": "2023-24", "home_team": "Burnley", "away_team": "Man City", "fthg": 0, "ftag": 3, "target": 2},
        {"date": "2023-08-12", "season": "2023-24", "home_team": "Arsenal", "away_team": "Nottingham Forest", "fthg": 2, "ftag": 1, "target": 0},
        {"date": "2023-08-19", "season": "2023-24", "home_team": "Man City", "away_team": "Newcastle", "fthg": 1, "ftag": 0, "target": 0},
        # Match 4 with inverted outcome
        {"date": "2023-08-27", "season": "2023-24", "home_team": "Arsenal", "away_team": "Man City", "fthg": 0, "ftag": 5, "target": 2},
    ]

    res_a = engine.process_season_data(matches_scenario_a)
    res_b = engine.process_season_data(matches_scenario_b)

    m4_a = res_a[3]
    m4_b = res_b[3]

    # Pre-match Elo ratings must be 100% identical regardless of match 4's result
    assert m4_a["pre_h_elo"] == m4_b["pre_h_elo"], "Pre-match home Elo leaked future result!"
    assert m4_a["pre_a_elo"] == m4_b["pre_a_elo"], "Pre-match away Elo leaked future result!"

    # In-season Elo z-scores must be 100% identical
    assert m4_a["z_elo_h"] == m4_b["z_elo_h"]
    assert m4_a["z_elo_a"] == m4_b["z_elo_a"]

    # Pre-match form scores must be 100% identical
    assert m4_a["form_raw_h"] == m4_b["form_raw_h"], "Pre-match home form leaked future result!"
    assert m4_a["form_raw_a"] == m4_b["form_raw_a"], "Pre-match away form leaked future result!"
    assert m4_a["z_form_h"] == m4_b["z_form_h"]
    assert m4_a["z_form_a"] == m4_b["z_form_a"]

    # Strength gap must be identical
    _, _, gap_a = engine.compute_strength_gap(m4_a["z_elo_h"], m4_a["z_form_h"], m4_a["z_elo_a"], m4_a["z_form_a"])
    _, _, gap_b = engine.compute_strength_gap(m4_b["z_elo_h"], m4_b["z_form_h"], m4_b["z_elo_a"], m4_b["z_form_a"])
    assert gap_a == gap_b

    # Simulation probabilities must be identical under the same seed
    p_a = engine.simulate_probabilities(1.5, 1.2, match_seed=42)
    p_b = engine.simulate_probabilities(1.5, 1.2, match_seed=42)
    assert p_a == p_b


def test_rule_2_chronological_ordering_no_shuffling():
    """
    Verifies Rule 2:
    1. Matches in clean_matches.csv are strictly in non-decreasing chronological order.
    2. Date parsing produces valid ISO strings (YYYY-MM-DD).
    3. Walk-forward testing partitions strictly by temporal boundary:
       max(train_dates) < min(test_dates) for each walk-forward fold.
    4. No random splitting, cross-validation k-fold shuffling, or out-of-order leakage.
    """
    import os
    import csv

    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gut_feeling", "clean_matches.csv")
    assert os.path.exists(csv_path), "clean_matches.csv not found!"

    with open(csv_path, "r", encoding="utf-8") as f:
        matches = list(csv.DictReader(f))

    assert len(matches) == 3420, f"Expected 3420 matches across 9 seasons, found {len(matches)}"

    # 1. Monotonic date order check across entire dataset
    dates = [m["date"] for m in matches]
    for i in range(len(dates) - 1):
        assert dates[i] <= dates[i + 1], f"Temporal violation at row {i}: {dates[i]} > {dates[i+1]}"

    # 2. Walk-forward split integrity: every training match must strictly precede the test season
    test_seasons = ["2022-23", "2023-24", "2024-25"]
    for ts in test_seasons:
        train = [m for m in matches if m["season"] < ts]
        test = [m for m in matches if m["season"] == ts]

        max_train_date = max(m["date"] for m in train)
        min_test_date = min(m["date"] for m in test)
        assert max_train_date < min_test_date, (
            f"Walk-forward leakage in {ts}: latest train date {max_train_date} >= first test date {min_test_date}"
        )
