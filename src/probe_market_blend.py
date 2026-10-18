"""THROWAWAY PROBE — walk-forward blend: fitted Dixon-Coles MLE x de-vigged pre-match odds.

Scores blend weights on the identical chronological no-look-ahead test set the
ledger backfill uses, plus the closing-odds ceiling for context.

Run:  python -m src.probe_market_blend
"""
import csv
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np  # noqa: E402

from src.predictions import _fit_mle, _mle_probs  # noqa: E402

DB = "data/laliga_profiles.db"
CACHE = Path("data/cache/footballdata")
SEASON_CSV = [("2122", 2021), ("2223", 2022), ("2324", 2023),
              ("2425", 2024), ("2526", 2025), ("2627", 2026)]


def _devig(h, d, a):
    if not (h and d and a):
        return None
    try:
        ih, idd, ia = 1.0 / float(h), 1.0 / float(d), 1.0 / float(a)
    except (ValueError, ZeroDivisionError):
        return None
    s = ih + idd + ia
    return (ih / s, idd / s, ia / s)


def load_odds():
    """{(season, date_iso, homeEx, awayEx): (pre3, close3)} de-vigged."""
    out = {}
    for code, season in SEASON_CSV:
        path = CACHE / f"SP1_{code}.csv"
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                try:
                    d = datetime.strptime(r["Date"], "%d/%m/%Y").date().isoformat()
                except Exception:
                    continue
                pre = (_devig(r.get("B365H"), r.get("B365D"), r.get("B365A"))
                       or _devig(r.get("AvgH"), r.get("AvgD"), r.get("AvgA"))
                       or _devig(r.get("MaxH"), r.get("MaxD"), r.get("MaxA"))
                       or _devig(r.get("BWH"), r.get("BWD"), r.get("BWA"))
                       or _devig(r.get("PSH"), r.get("PSD"), r.get("PSA")))
                close = (_devig(r.get("B365CH"), r.get("B365CD"), r.get("B365CA"))
                         or _devig(r.get("AvgCH"), r.get("AvgCD"), r.get("AvgCA"))
                         or _devig(r.get("PSCH"), r.get("PSCD"), r.get("PSCA")))
                out[(season, d, r["HomeTeam"], r["AwayTeam"])] = (pre, close)
    return out


def run():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    all_rows = conn.execute(
        "SELECT season, home_team_id, away_team_id, home_score, away_score, kickoff_time "
        "FROM fixtures WHERE status='FINISHED' AND home_score IS NOT NULL "
        "ORDER BY kickoff_time, id").fetchall()
    slug_of = {r["id"]: r["slug"] for r in conn.execute("SELECT id, slug FROM clubs")}
    conn.close()

    odds = load_odds()
    print(f"odds rows loaded: {len(odds)}")

    # slug -> likely CSV exonym (alias values), for fixture matching
    from src.mirror_footballdata import TEAM_ALIAS
    ex_of = {}
    for ex, slug in TEAM_ALIAS.items():
        ex_of.setdefault(slug, ex)

    seasons = sorted({r["season"] for r in all_rows})
    w_grid = [0.0, 0.15, 0.3, 0.4, 0.5, 0.6, 0.7, 0.85, 1.0]
    agg = {w: {"brier": [], "hits": 0, "n": 0, "draws": 0} for w in w_grid}
    close_stats = {"brier": [], "hits": 0, "n": 0}
    matched = missed = 0

    for season in seasons:
        prior = [r for r in all_rows if r["season"] < season]
        if len(prior) < 60:
            continue
        t0 = date(season, 7, 1)
        W = np.array([0.5 ** (max((t0 - date.fromisoformat(r["kickoff_time"][:10])).days, 0) / 550.0)
                      for r in prior])
        hg = np.array([r["home_score"] for r in prior], float)
        ag = np.array([r["away_score"] for r in prior], float)
        clubs = sorted({r["home_team_id"] for r in prior} | {r["away_team_id"] for r in prior})
        idx = {c: i for i, c in enumerate(clubs)}
        hi = np.array([idx[r["home_team_id"]] for r in prior])
        ai = np.array([idx[r["away_team_id"]] for r in prior])
        att, deff, hm, Wg_h, Wg_a = _fit_mle(prior, W, len(clubs), hi, ai, hg, ag)

        for r in (x for x in all_rows if x["season"] == season):
            h, a = r["home_team_id"], r["away_team_id"]
            if h not in idx or a not in idx:
                continue
            hx, ax = ex_of.get(slug_of.get(h, "")), ex_of.get(slug_of.get(a, ""))
            pre, close = None, None
            if hx and ax:
                hit = odds.get((season, r["kickoff_time"][:10], hx, ax))
                if hit:
                    pre, close = hit
            if pre is None:
                missed += 1
                continue
            matched += 1

            p_m = _mle_probs(att, deff, hm, Wg_h, Wg_a, idx[h], idx[a])
            real = "H" if r["home_score"] > r["away_score"] else "A" if r["away_score"] > r["home_score"] else "D"
            y = {"H": 0, "D": 0, "A": 0}
            y[real] = 1

            if close:
                vec_c = dict(zip("HDA", close))
                close_stats["brier"].append(sum((vec_c[k] - y[k]) ** 2 for k in vec_c))
                close_stats["hits"] += max(vec_c, key=vec_c.get) == real
                close_stats["n"] += 1

            pre3 = dict(zip("HDA", pre))
            for w in w_grid:
                vec = {k: w * p_m[k] + (1 - w) * pre3[k] for k in p_m}
                s = sum(vec.values())
                vec = {k: v / s for k, v in vec.items()}
                agg[w]["brier"].append(sum((vec[k] - y[k]) ** 2 for k in vec))
                pred = max(vec, key=vec.get)
                agg[w]["hits"] += pred == real
                agg[w]["draws"] += pred == "D"
                agg[w]["n"] += 1

    print(f"matched with PRE odds: {matched}   unmatched: {missed}")
    n = close_stats["n"] or 1
    print(f"CLOSING ceiling: brier={sum(close_stats['brier'])/n:.4f}  acc={close_stats['hits']/n*100:.1f}%  n={close_stats['n']}")
    print(f"\n{'w(model)':>8} {'brier':>7} {'acc':>6} {'draws':>6}")
    best = None
    for w in w_grid:
        a = agg[w]
        nn = a["n"] or 1
        b = sum(a["brier"]) / nn
        acc = a["hits"] / nn * 100
        print(f"{w:>8.2f} {b:>7.4f} {acc:>5.1f}% {a['draws']:>6}")
        if best is None or b < best[1]:
            best = (w, b, acc)
    print(f"\nBEST: w_model={best[0]}  brier={best[1]:.4f}  acc={best[2]:.1f}%")


if __name__ == "__main__":
    run()
