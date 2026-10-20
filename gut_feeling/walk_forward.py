"""
Step 9: Walk-forward testing and parameter tuning
- Evaluates 3 test seasons: 2022-23, 2023-24, 2024-25
- Strictly trains and tunes on prior seasons only (Rule 3)
- Compares against 4 references:
  1. Base Rate (historical class probabilities)
  2. Elo Only (weight 1.0 / 0.0)
  3. Form Only (weight 0.0 / 1.0)
  4. Bookmaker Closing Odds (devigged margin-free)
- Metrics: Accuracy, Log Loss, Ranked Probability Score (RPS)
- 10,000 paired bootstrap resamples for 95% Confidence Intervals
- Calibration check across 10 probability bins
- Confidence filter table (0.40 to 0.80)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import csv
import math
import numpy as np
from typing import List, Dict, Any, Tuple
from gut_feeling.model import GutFeelingEngine

CSV_PATH = os.path.join(os.path.dirname(__file__), "clean_matches.csv")


def rps_score(p_h: float, p_d: float, p_a: float, target: int) -> float:
    """
    Ranked Probability Score (RPS):
    RPS = 0.5 * [ (p_h - a_h)^2 + ((p_h + p_d) - (a_h + a_d))^2 ]
    where a is 1 for the actual outcome and 0 otherwise.
    """
    a_h = 1.0 if target == 0 else 0.0
    a_d = 1.0 if target == 1 else 0.0
    diff1 = p_h - a_h
    diff2 = (p_h + p_d) - (a_h + a_d)
    return 0.5 * (diff1 * diff1 + diff2 * diff2)


def log_loss_score(p_h: float, p_d: float, p_a: float, target: int, eps: float = 1e-15) -> float:
    probs = [max(eps, min(1.0 - eps, p)) for p in (p_h, p_d, p_a)]
    total = sum(probs)
    probs = [p / total for p in probs]
    return -math.log(probs[target])


def paired_bootstrap_ci(
    diffs: np.ndarray,
    n_resamples: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """
    Paired bootstrap for difference in RPS (algo - ref).
    Negative mean indicates algorithm is better.
    """
    rng = np.random.default_rng(seed)
    n = len(diffs)
    indices = rng.integers(0, n, size=(n_resamples, n))
    bootstrap_means = np.mean(diffs[indices], axis=1)

    mean_diff = float(np.mean(diffs))
    low = float(np.percentile(bootstrap_means, 100.0 * (alpha / 2.0)))
    high = float(np.percentile(bootstrap_means, 100.0 * (1.0 - alpha / 2.0)))
    return mean_diff, low, high


def tune_parameters(train_matches: List[Dict[str, Any]], h_avg: float, a_avg: float) -> Tuple[float, float, float, float]:
    """
    Tune weights (w_elo, w_form), k, and sigma by minimizing log loss on the training seasons.
    Strictly uses training matches only (Rule 3).
    """
    weight_candidates = [
        (0.9, 0.1),
        (0.8, 0.2),
        (0.7, 0.3),
        (0.6, 0.4),
        (0.5, 0.5),
    ]
    k_candidates = [0.20, 0.25, 0.30, 0.35]
    sigma_candidates = [0.05, 0.10, 0.15, 0.20]

    best_loss = float("inf")
    best_params = (0.7, 0.3, 0.25, 0.10)

    # Grid search on a fast representative simulation size
    for w_elo, w_form in weight_candidates:
        engine = GutFeelingEngine(w_elo=w_elo, w_form=w_form, n_sim=1000, random_seed=42)
        proc = engine.process_season_data(train_matches)
        for k in k_candidates:
            for sig in sigma_candidates:
                engine.k_goal = k
                engine.sigma_noise = sig
                total_loss = 0.0
                # Evaluate on the last 2 seasons of the training set to prevent overfitting
                val_set = [m for m in proc if m["season"] in [train_matches[-1]["season"], train_matches[-381]["season"]]]
                for idx, m in enumerate(val_set):
                    s_h, s_a, gap = engine.compute_strength_gap(m["z_elo_h"], m["z_form_h"], m["z_elo_a"], m["z_form_a"])
                    h_xg, a_xg = engine.convert_strength_to_xg(gap, h_avg, a_avg)
                    ph, pd, pa = engine.simulate_probabilities(h_xg, a_xg, match_seed=idx + 100)
                    total_loss += log_loss_score(ph, pd, pa, m["target"])

                avg_loss = total_loss / len(val_set)
                if avg_loss < best_loss:
                    best_loss = avg_loss
                    best_params = (w_elo, w_form, k, sig)

    return best_params


def run_walk_forward_evaluation():
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_matches = list(reader)

    for m in all_matches:
        m["fthg"] = int(m["fthg"])
        m["ftag"] = int(m["ftag"])
        m["target"] = int(m["target"])
        m["book_p_h"] = float(m["book_p_h"])
        m["book_p_d"] = float(m["book_p_d"])
        m["book_p_a"] = float(m["book_p_a"])

    test_seasons = ["2022-23", "2023-24", "2024-25"]
    all_seasons = sorted(list({m["season"] for m in all_matches}))

    combined_test_results = []
    season_metrics = {}

    print("\n" + "=" * 70)
    print("STEP 9: WALK-FORWARD TESTING & TUNING ACROSS 3 TEST SEASONS")
    print("=" * 70)

    for test_s in test_seasons:
        train_matches = [m for m in all_matches if m["season"] < test_s]
        test_matches = [m for m in all_matches if m["season"] == test_s]

        # 1. Base rates from training seasons only
        n_train = len(train_matches)
        base_h = sum(1 for m in train_matches if m["target"] == 0) / n_train
        base_d = sum(1 for m in train_matches if m["target"] == 1) / n_train
        base_a = sum(1 for m in train_matches if m["target"] == 2) / n_train

        # League average goals from training seasons only
        h_avg = sum(m["fthg"] for m in train_matches) / n_train
        a_avg = sum(m["ftag"] for m in train_matches) / n_train

        # 2. Tune parameters on training seasons only (Rule 3)
        print(f"\n[*] Tuning parameters for Test Season {test_s} (Train: {len(train_matches):,} matches)...")
        best_w_elo, best_w_form, best_k, best_sig = tune_parameters(train_matches, h_avg, a_avg)
        print(f"[+] Selected settings for {test_s}: w_elo={best_w_elo:.1f}, w_form={best_w_form:.1f}, k={best_k:.2f}, sigma={best_sig:.2f}")

        # 3. Setup models
        # Model A: Full Gut Feeling Algorithm (Tuned Elo + Form + Simulation)
        engine_algo = GutFeelingEngine(
            w_elo=best_w_elo, w_form=best_w_form, k_goal=best_k, sigma_noise=best_sig,
            n_sim=10000, random_seed=42
        )
        # Model B: Elo Only Reference (weight 1.0 / 0.0)
        engine_elo = GutFeelingEngine(
            w_elo=1.0, w_form=0.0, k_goal=best_k, sigma_noise=0.0, n_sim=10000, random_seed=42
        )
        # Model C: Form Only Reference (weight 0.0 / 1.0)
        engine_form = GutFeelingEngine(
            w_elo=0.0, w_form=1.0, k_goal=best_k, sigma_noise=0.0, n_sim=10000, random_seed=42
        )

        # Process the entire chronological sequence up to this test season
        curr_stream = [m for m in all_matches if m["season"] <= test_s]
        proc_algo = engine_algo.process_season_data(curr_stream)
        proc_elo = engine_elo.process_season_data(curr_stream)
        proc_form = engine_form.process_season_data(curr_stream)

        # Slice test matches
        test_proc_algo = [m for m in proc_algo if m["season"] == test_s]
        test_proc_elo = [m for m in proc_elo if m["season"] == test_s]
        test_proc_form = [m for m in proc_form if m["season"] == test_s]

        # Evaluate match by match
        season_records = []
        for idx in range(len(test_matches)):
            m_algo = test_proc_algo[idx]
            m_elo = test_proc_elo[idx]
            m_form = test_proc_form[idx]
            target = m_algo["target"]
            match_seed = 100000 + idx * 7  # deterministic seed

            # Algo predictions
            _, _, gap_a = engine_algo.compute_strength_gap(m_algo["z_elo_h"], m_algo["z_form_h"], m_algo["z_elo_a"], m_algo["z_form_a"])
            xg_h_a, xg_a_a = engine_algo.convert_strength_to_xg(gap_a, h_avg, a_avg)
            p_h_a, p_d_a, p_a_a = engine_algo.simulate_probabilities(xg_h_a, xg_a_a, match_seed)
            conf_a, label_a = engine_algo.label_confidence(p_h_a, p_d_a, p_a_a)

            # Elo only
            _, _, gap_e = engine_elo.compute_strength_gap(m_elo["z_elo_h"], m_elo["z_form_h"], m_elo["z_elo_a"], m_elo["z_form_a"])
            xg_h_e, xg_a_e = engine_elo.convert_strength_to_xg(gap_e, h_avg, a_avg)
            p_h_e, p_d_e, p_a_e = engine_elo.simulate_probabilities(xg_h_e, xg_a_e, match_seed)

            # Form only
            _, _, gap_f = engine_form.compute_strength_gap(m_form["z_elo_h"], m_form["z_form_h"], m_form["z_elo_a"], m_form["z_form_a"])
            xg_h_f, xg_a_f = engine_form.convert_strength_to_xg(gap_f, h_avg, a_avg)
            p_h_f, p_d_f, p_a_f = engine_form.simulate_probabilities(xg_h_f, xg_a_f, match_seed)

            # Bookmaker odds (margin-removed)
            p_h_b = m_algo["book_p_h"]
            p_d_b = m_algo["book_p_d"]
            p_a_b = m_algo["book_p_a"]

            # Compute match scores
            rec = {
                "season": test_s,
                "target": target,
                # Predictions
                "algo_p": (p_h_a, p_d_a, p_a_a),
                "algo_pred": int(np.argmax([p_h_a, p_d_a, p_a_a])),
                "algo_conf": conf_a,
                "algo_label": label_a,
                "algo_rps": rps_score(p_h_a, p_d_a, p_a_a, target),
                "algo_loss": log_loss_score(p_h_a, p_d_a, p_a_a, target),

                # Reference 1: Base Rate
                "base_p": (base_h, base_d, base_a),
                "base_pred": int(np.argmax([base_h, base_d, base_a])),
                "base_rps": rps_score(base_h, base_d, base_a, target),
                "base_loss": log_loss_score(base_h, base_d, base_a, target),

                # Reference 2: Elo Only
                "elo_p": (p_h_e, p_d_e, p_a_e),
                "elo_pred": int(np.argmax([p_h_e, p_d_e, p_a_e])),
                "elo_rps": rps_score(p_h_e, p_d_e, p_a_e, target),
                "elo_loss": log_loss_score(p_h_e, p_d_e, p_a_e, target),

                # Reference 3: Form Only
                "form_p": (p_h_f, p_d_f, p_a_f),
                "form_pred": int(np.argmax([p_h_f, p_d_f, p_a_f])),
                "form_rps": rps_score(p_h_f, p_d_f, p_a_f, target),
                "form_loss": log_loss_score(p_h_f, p_d_f, p_a_f, target),

                # Reference 4: Bookmaker Closing Odds
                "book_p": (p_h_b, p_d_b, p_a_b),
                "book_pred": int(np.argmax([p_h_b, p_d_b, p_a_b])),
                "book_rps": rps_score(p_h_b, p_d_b, p_a_b, target),
                "book_loss": log_loss_score(p_h_b, p_d_b, p_a_b, target),
            }
            season_records.append(rec)
            combined_test_results.append(rec)

        # Season summary
        n_m = len(season_records)
        acc_algo = sum(1 for r in season_records if r["algo_pred"] == r["target"]) / n_m
        acc_elo = sum(1 for r in season_records if r["elo_pred"] == r["target"]) / n_m
        acc_form = sum(1 for r in season_records if r["form_pred"] == r["target"]) / n_m
        acc_book = sum(1 for r in season_records if r["book_pred"] == r["target"]) / n_m

        rps_algo = float(np.mean([r["algo_rps"] for r in season_records]))
        rps_elo = float(np.mean([r["elo_rps"] for r in season_records]))
        rps_book = float(np.mean([r["book_rps"] for r in season_records]))

        season_metrics[test_s] = {
            "matches": n_m,
            "tuned_params": {"w_elo": best_w_elo, "w_form": best_w_form, "k": best_k, "sigma": best_sig},
            "algo_acc": acc_algo,
            "elo_acc": acc_elo,
            "form_acc": acc_form,
            "book_acc": acc_book,
            "algo_rps": rps_algo,
            "elo_rps": rps_elo,
            "book_rps": rps_book,
        }
        print(f"Season {test_s} Result: Algo Acc={acc_algo*100:.2f}% (RPS={rps_algo:.4f}) | Elo Acc={acc_elo*100:.2f}% | Form Acc={acc_form*100:.2f}% | Book Acc={acc_book*100:.2f}%")

    return combined_test_results, season_metrics


def compute_aggregate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(results)
    models = ["algo", "base", "elo", "form", "book"]
    names = {
        "algo": "Gut Feeling Algorithm",
        "base": "Base Rate (Historical)",
        "elo": "Elo Anchor Only (1.0/0.0)",
        "form": "3-Match Form Only (0.0/1.0)",
        "book": "Bookmaker (Pinnacle Closing)",
    }

    metrics = {}
    for m in models:
        acc = sum(1 for r in results if r[f"{m}_pred"] == r["target"]) / n
        loss = float(np.mean([r[f"{m}_loss"] for r in results]))
        rps_arr = np.array([r[f"{m}_rps"] for r in results])
        rps_mean = float(np.mean(rps_arr))
        metrics[m] = {
            "name": names[m],
            "accuracy": acc,
            "log_loss": loss,
            "rps": rps_mean,
            "rps_array": rps_arr,
        }

    # Paired Bootstrap 95% Confidence Intervals for RPS differences: (algo - reference)
    algo_rps = metrics["algo"]["rps_array"]
    bootstrap_results = {}
    for ref in ["base", "elo", "form", "book"]:
        ref_rps = metrics[ref]["rps_array"]
        diffs = algo_rps - ref_rps  # negative means algo is superior (lower RPS)
        m_diff, ci_low, ci_high = paired_bootstrap_ci(diffs, n_resamples=10000, seed=42)
        better = ci_high < 0.0  # Whole interval below zero
        bootstrap_results[ref] = {
            "mean_diff": m_diff,
            "ci_95": (ci_low, ci_high),
            "statistically_better": better,
        }

    # Calibration Check: 10 probability bins
    # Pool all predicted outcome probabilities and check actual occurrence
    all_pred_probs = []
    all_actuals = []
    for r in results:
        ph, pd, pa = r["algo_p"]
        target = r["target"]
        # Outcome 0 (Home Win)
        all_pred_probs.append(ph)
        all_actuals.append(1.0 if target == 0 else 0.0)
        # Outcome 1 (Draw)
        all_pred_probs.append(pd)
        all_actuals.append(1.0 if target == 1 else 0.0)
        # Outcome 2 (Away Win)
        all_pred_probs.append(pa)
        all_actuals.append(1.0 if target == 2 else 0.0)

    pred_arr = np.array(all_pred_probs)
    act_arr = np.array(all_actuals)

    bin_edges = np.linspace(0.0, 1.0, 11)
    calibration_table = []
    for i in range(10):
        low, high = bin_edges[i], bin_edges[i + 1]
        mask = (pred_arr >= low) & (pred_arr < high) if i < 9 else (pred_arr >= low) & (pred_arr <= high)
        cnt = int(np.sum(mask))
        if cnt > 0:
            avg_pred = float(np.mean(pred_arr[mask]))
            avg_act = float(np.mean(act_arr[mask]))
        else:
            avg_pred = (low + high) / 2.0
            avg_act = 0.0
        calibration_table.append({
            "bin": f"[{low:.1f}, {high:.1f})",
            "count": cnt,
            "predicted_prob": round(avg_pred, 4),
            "actual_freq": round(avg_act, 4),
            "gap": round(avg_pred - avg_act, 4),
        })

    # Confidence Filter Table (Step 8): sweep thresholds from 0.40 to 0.80
    threshold_sweep = []
    thresholds = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    for th in thresholds:
        covered = [r for r in results if r["algo_conf"] >= th]
        n_cov = len(covered)
        pct_cov = (n_cov / n) * 100.0
        acc_cov = (sum(1 for r in covered if r["algo_pred"] == r["target"]) / n_cov * 100.0) if n_cov > 0 else 0.0
        threshold_sweep.append({
            "threshold": f"{th:.2f}",
            "matches_covered": n_cov,
            "share_covered_pct": round(pct_cov, 1),
            "accuracy_pct": round(acc_cov, 2),
        })

    return {
        "total_test_matches": n,
        "metrics": metrics,
        "bootstrap": bootstrap_results,
        "calibration": calibration_table,
        "threshold_sweep": threshold_sweep,
    }


if __name__ == "__main__":
    results, s_metrics = run_walk_forward_evaluation()
    summary = compute_aggregate_metrics(results)

    print("\n" + "=" * 70)
    print("STEP 9 GATE REPORT: 3-SEASON WALK-FORWARD BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Total Out-of-Sample Matches Tested: {summary['total_test_matches']:,}")
    print("\nReference Comparison Table:")
    print(f"{'Model / Reference':<32} {'Accuracy':<10} {'Log Loss':<10} {'RPS':<10} {'RPS Diff vs Algo':<18} {'95% Bootstrap CI':<24}")
    print("-" * 106)
    algo_rps = summary["metrics"]["algo"]["rps"]
    for k in ["algo", "base", "elo", "form", "book"]:
        m = summary["metrics"][k]
        acc_s = f"{m['accuracy']*100:.2f}%"
        loss_s = f"{m['log_loss']:.4f}"
        rps_s = f"{m['rps']:.4f}"
        if k == "algo":
            diff_s = "-"
            ci_s = "Baseline"
        else:
            b = summary["bootstrap"][k]
            diff_s = f"{b['mean_diff']:+.4f}"
            ci_s = f"[{b['ci_95'][0]:+.4f}, {b['ci_95'][1]:+.4f}]"
        print(f"{m['name']:<32} {acc_s:<10} {loss_s:<10} {rps_s:<10} {diff_s:<18} {ci_s:<24}")

    print("\n" + "=" * 70)
    print("STEP 8 CONFIDENCE FILTER TABLE (0.40 to 0.80)")
    print("=" * 70)
    print(f"{'Threshold':<12} {'Matches Covered':<18} {'Share Covered (%)':<20} {'Accuracy (%)':<15}")
    print("-" * 65)
    for row in summary["threshold_sweep"]:
        print(f"{row['threshold']:<12} {row['matches_covered']:<18} {row['share_covered_pct']:<20} {row['accuracy_pct']:<15}")

    print("\n" + "=" * 70)
    print("CALIBRATION CHECK (10 Probability Bins)")
    print("=" * 70)
    print(f"{'Bin':<15} {'Predictions':<15} {'Mean Predicted':<18} {'Actual Freq':<15} {'Gap (Bias)':<12}")
    print("-" * 75)
    for row in summary["calibration"]:
        print(f"{row['bin']:<15} {row['count']:<15} {row['predicted_prob']:<18} {row['actual_freq']:<15} {row['gap']:+12.4f}")
    print("=" * 70 + "\n")
