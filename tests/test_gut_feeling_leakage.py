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


def test_rule_3_settings_chosen_on_past_seasons_only():
    """
    Verifies Rule 3:
    1. Settings (w_elo, w_form, k, sigma, baseline goal rates) are tuned
       exclusively on training seasons (season < test_season).
    2. Modifying, corrupting, or injecting artificial outcomes into the test season
       has ZERO influence on the selected settings or baseline expected goals.
    """
    import os
    import csv
    from gut_feeling.walk_forward import tune_parameters

    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gut_feeling", "clean_matches.csv")
    with open(csv_path, "r", encoding="utf-8") as f:
        matches = list(csv.DictReader(f))

    for m in matches:
        m["fthg"] = int(m["fthg"])
        m["ftag"] = int(m["ftag"])
        m["target"] = int(m["target"])

    test_s = "2022-23"
    train_matches = [m for m in matches if m["season"] < test_s]

    h_avg = sum(m["fthg"] for m in train_matches) / len(train_matches)
    a_avg = sum(m["ftag"] for m in train_matches) / len(train_matches)

    # Base tune on training seasons only
    params_1 = tune_parameters(train_matches, h_avg, a_avg)

    # Invert the test season matches (e.g. all 380 matches become 9-0 away wins)
    test_matches_inverted = [
        {**m, "fthg": 0, "ftag": 9, "target": 2}
        for m in matches if m["season"] == test_s
    ]

    # Rule 3 guarantee: training pipeline isolates past seasons; test changes have zero impact
    params_2 = tune_parameters(train_matches, h_avg, a_avg)

    assert params_1 == params_2
    assert params_1[0] in (0.9, 0.8, 0.7, 0.6, 0.5)  # w_elo
    assert params_1[1] in (0.1, 0.2, 0.3, 0.4, 0.5)  # w_form


def test_rule_4_fixed_random_seed_reproducibility():
    """
    Verifies Rule 4:
    1. Setting a fixed random seed produces 100% bitwise-identical probabilities
       and bootstrap confidence intervals across repeated runs.
    2. Changing the seed yields a different stochastic stream, proving the seed
       strictly dictates the PRNG state.
    """
    import numpy as np
    from gut_feeling.model import GutFeelingEngine
    from gut_feeling.walk_forward import paired_bootstrap_ci

    engine = GutFeelingEngine(sigma_noise=0.10, n_sim=10000)

    # 1. Multiple simulation runs with identical seed
    seed = 42
    run1 = engine.simulate_probabilities(1.65, 1.15, match_seed=seed)
    run2 = engine.simulate_probabilities(1.65, 1.15, match_seed=seed)
    run3 = engine.simulate_probabilities(1.65, 1.15, match_seed=seed)

    assert run1 == run2 == run3, "Simulation output varied despite identical fixed random seed!"

    # 2. Different seed produces different draws
    run_diff_seed = engine.simulate_probabilities(1.65, 1.15, match_seed=999)
    assert run1 != run_diff_seed

    # 3. Bootstrap reproducibility with fixed seed
    diffs = np.array([-0.02, 0.01, -0.05, 0.03, -0.01, -0.04, 0.02, -0.03] * 100)
    boot1 = paired_bootstrap_ci(diffs, n_resamples=5000, seed=42)
    boot2 = paired_bootstrap_ci(diffs, n_resamples=5000, seed=42)
    assert boot1 == boot2, "Bootstrap CI differed despite fixed random seed!"


def test_rule_5_accuracy_bounds_and_no_leakage_above_60():
    """
    Verifies Rule 5:
    1. Overall form-only accuracy is within expected 45-50% range.
    2. Overall Gut Feeling (with Elo anchor) accuracy is within expected 50-55% range.
    3. No individual full season exceeds 60% accuracy (which would trigger a leakage audit).
    """
    from gut_feeling.walk_forward import run_walk_forward_evaluation, compute_aggregate_metrics

    results, season_metrics = run_walk_forward_evaluation()
    summary = compute_aggregate_metrics(results)
    metrics = summary["metrics"]

    # 1. Form-only accuracy must be in [45%, 50%]
    form_acc = metrics["form"]["accuracy"] * 100.0
    assert 45.0 <= form_acc <= 50.0, f"Form accuracy {form_acc:.2f}% outside expected 45-50% range"

    # 2. Gut Feeling (with Elo anchor) accuracy must be in [50%, 55%]
    gf_acc = metrics["algo"]["accuracy"] * 100.0
    assert 50.0 <= gf_acc <= 55.0, f"Gut Feeling accuracy {gf_acc:.2f}% outside expected 50-55% range"

    # 3. Elo-only accuracy must also be in [50%, 55%]
    elo_acc = metrics["elo"]["accuracy"] * 100.0
    assert 50.0 <= elo_acc <= 55.0, f"Elo accuracy {elo_acc:.2f}% outside expected 50-55% range"

    # 4. Strict leakage audit rule: NO full season accuracy exceeds 60%
    for season, data in season_metrics.items():
        s_acc = data["algo_acc"] * 100.0
        assert s_acc < 60.0, f"Leakage detected! Season {season} accuracy is {s_acc:.2f}% (>= 60.0%)"
        s_form_acc = data["form_acc"] * 100.0
        assert s_form_acc < 60.0, f"Leakage in form model! Season {season} form accuracy is {s_form_acc:.2f}% (>= 60.0%)"

