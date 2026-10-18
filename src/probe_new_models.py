"""
THROWAWAY SPIKE — three-way algorithm comparison for the forecast engine.
Run:  python -m src.probe_new_models

Probes (all on the identical chronological no-look-ahead 2025/26 test set):
  A. Fitted Dixon-Coles MLE   — attack/defense fit by weighted maximum likelihood
  B. Shot-quality strength    — rolling SoT-based xG proxies through v3's lambda curve
  C. Market ceiling           — de-vigged Bet365 closing odds (the efficiency benchmark)
Baseline: v3 published backtest (Brier 0.6139, hit 49.7%, n=320).
"""
import sqlite3, csv, math, datetime, sys
import numpy as np

sys.path.insert(0, '.')
from src.mirror_footballdata import TEAM_ALIAS

DB = 'data/laliga_profiles.db'
TEST_SEASON = 2025

conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
rows = conn.execute("""
  SELECT f.season, f.id, f.home_team_id, f.away_team_id, f.home_score, f.away_score, f.kickoff_time,
         m.home_sot, m.away_sot
  FROM fixtures f LEFT JOIN match_team_stats m ON m.fixture_id = f.id
  WHERE f.status='FINISHED' AND f.home_score IS NOT NULL
  ORDER BY f.kickoff_time, f.id
""").fetchall()
conn.close()

hist = [r for r in rows if r['season'] < TEST_SEASON]
test = [r for r in rows if r['season'] == TEST_SEASON]
print(f"data: {len(hist)} historical + {len(test)} test matches")


def dc_probs(lh, la, rho, max_goals=8):
    k = np.arange(max_goals + 1)
    fact = np.array([math.factorial(x) for x in k], float)
    ph = np.exp(-lh) * lh ** k / fact
    pa = np.exp(-la) * la ** k / fact
    M = np.outer(ph, pa)
    tau = np.ones((max_goals + 1, max_goals + 1))
    tau[0, 0] = 1 - lh * la * rho
    tau[0, 1] = 1 + lh * rho
    tau[1, 0] = 1 + la * rho
    tau[1, 1] = 1 - rho
    M *= np.clip(tau, 1e-9, None)
    M /= M.sum()
    h = np.tril(M, -1).sum(); d = np.trace(M); a = np.triu(M, 1).sum()
    sh = 0.2  # identical shrinkage to v3
    hv = (1 - sh) * h + sh * 0.44; dv = (1 - sh) * d + sh * 0.25; av = (1 - sh) * a + sh * 0.31
    t = hv + dv + av
    return np.array([hv / t, dv / t, av / t])


def metrics(preds, outcomes):
    n = len(preds)
    Y = np.zeros((n, 3)); Y[np.arange(n), outcomes] = 1.0
    brier = float(((preds - Y) ** 2).sum(axis=1).mean())
    ll = float(-np.log(np.clip(preds[np.arange(n), outcomes], 1e-12, 1)).mean())
    hit = float((preds.argmax(axis=1) == outcomes).mean())
    cal = tuple((float(preds[:, i].sum() / n), float((outcomes == i).mean())) for i in range(3))
    return dict(n=n, brier=brier, logloss=ll, hit=hit, cal=cal)


# ================= PROBE A: fitted Dixon-Coles MLE =================
t0 = datetime.date(2025, 7, 1)
W = np.array([0.5 ** (max((t0 - datetime.date.fromisoformat(r['kickoff_time'][:10])).days, 0) / 550.0) for r in hist])
hg = np.array([r['home_score'] for r in hist], float)
ag = np.array([r['away_score'] for r in hist], float)

clubs = sorted({r['home_team_id'] for r in hist} | {r['away_team_id'] for r in hist})
idx = {c: i for i, c in enumerate(clubs)}
n_clubs = len(clubs)
hi = np.array([idx[r['home_team_id']] for r in hist])
ai = np.array([idx[r['away_team_id']] for r in hist])


def dc_loglik(a_, d_, hm, rho):
    lh = a_[hi] * d_[ai] * hm
    la = a_[ai] * d_[hi]
    ll = W * (hg * np.log(lh) - lh + ag * np.log(la) - la)
    tau = np.ones(len(hg))
    m00 = (hg == 0) & (ag == 0); m01 = (hg == 0) & (ag == 1)
    m10 = (hg == 1) & (ag == 0); m11 = (hg == 1) & (ag == 1)
    tau[m00] = 1 - lh[m00] * la[m00] * rho
    tau[m01] = 1 + lh[m01] * rho
    tau[m10] = 1 + la[m10] * rho
    tau[m11] = 1 - rho
    return (ll + W * np.log(np.clip(tau, 1e-9, None))).sum()


best = None
for hm in (1.0, 1.15, 1.3, 1.45):
    for rho in (-0.15, -0.10, -0.08, -0.05, 0.0):
        a_, d_ = np.ones(n_clubs), np.ones(n_clubs)
        for _ in range(120):
            lh = a_[hi] * d_[ai] * hm
            la = a_[ai] * d_[hi]
            gf = np.bincount(hi, W * hg, n_clubs) + np.bincount(ai, W * ag, n_clubs)
            ef = np.bincount(hi, W * lh, n_clubs) + np.bincount(ai, W * la, n_clubs)
            a_ *= (gf / np.maximum(ef, 1e-9)) ** 0.7
            ga = np.bincount(ai, W * hg, n_clubs) + np.bincount(hi, W * ag, n_clubs)
            ea = np.bincount(ai, W * lh, n_clubs) + np.bincount(hi, W * la, n_clubs)
            d_ *= (ga / np.maximum(ea, 1e-9)) ** 0.7
            a_ /= np.exp(np.log(a_).mean())
            d_ /= np.exp(np.log(d_).mean())
        ll = dc_loglik(a_, d_, hm, rho)
        if best is None or ll > best[0]:
            best = (ll, hm, rho, a_.copy(), d_.copy())
_, hm_fit, rho_fit, att_fit, deff_fit = best
print(f"A fit: home_mult={hm_fit} rho={rho_fit} weighted-loglik={best[0]:.1f}")

Wg_h = float((W * hg).sum() / W.sum())
Wg_a = float((W * ag).sum() / W.sum())

predsA, outsA, playedA = [], [], {}
for r in sorted(test, key=lambda x: (x['kickoff_time'], x['id'])):
    h_, a_ = r['home_team_id'], r['away_team_id']
    if playedA.get(h_, 0) >= 6 and playedA.get(a_, 0) >= 6:
        # Newly promoted clubs with no fitted params use league-average (1.0)
        at_h = att_fit[idx[h_]] if h_ in idx else 1.0
        df_a = deff_fit[idx[a_]] if a_ in idx else 1.0
        at_a = att_fit[idx[a_]] if a_ in idx else 1.0
        df_h = deff_fit[idx[h_]] if h_ in idx else 1.0
        lh = Wg_h * at_h * df_a * hm_fit
        la = Wg_a * at_a * df_h
        predsA.append(dc_probs(lh, la, rho_fit))
        outsA.append(0 if r['home_score'] > r['away_score'] else 2 if r['away_score'] > r['home_score'] else 1)
    playedA[h_] = playedA.get(h_, 0) + 1
    playedA[a_] = playedA.get(a_, 0) + 1
mA = metrics(np.array(predsA), np.array(outsA))

# ================= PROBE B: shot-quality strength =================
sot_rows = [r for r in rows if r['home_sot'] is not None]


def conv_for(season):
    sel = [r for r in sot_rows if r['season'] == season]
    g = sum(r['home_score'] + r['away_score'] for r in sel)
    s = sum(r['home_sot'] + r['away_sot'] for r in sel)
    return g / s if s else 0.30


conv = {s: conv_for(s) for s in sorted({r['season'] for r in sot_rows})}


def shot_model(season, S):
    prev = {}
    preds, outs = [], []
    for r in sorted([x for x in sot_rows if x['season'] == season], key=lambda x: (x['kickoff_time'], x['id'])):
        h_, a_ = r['home_team_id'], r['away_team_id']
        ph, pa = prev.get(h_, []), prev.get(a_, [])
        c = conv[season]
        if len(ph) >= 6 and len(pa) >= 6:

            def rolling(lst, key):
                w = [0.85 ** i for i in range(len(lst))][::-1]
                return sum(wi * x[key] for wi, x in zip(w, lst)) / sum(w)

            xgf_h, xga_h = rolling(ph, 'xgf'), rolling(ph, 'xga')
            xgf_a, xga_a = rolling(pa, 'xgf'), rolling(pa, 'xga')
            diff = math.log((xgf_h * xga_a + 1e-9) / (xgf_a * xga_h + 1e-9))
            net = max(-8.0, min(8.0, S * diff + 2.0))
            lh = max(0.55, min(3.0, 1.45 * math.exp((net / 14) * 0.45)))
            la = max(0.45, min(2.7, 1.17 * math.exp(-(net / 14) * 0.45)))
            preds.append(dc_probs(lh, la, -0.08))
            outs.append(0 if r['home_score'] > r['away_score'] else 2 if r['away_score'] > r['home_score'] else 1)
        rec = {'xgf': r['home_sot'] * c, 'xga': r['away_sot'] * c}
        prev.setdefault(h_, []).append(rec)
        prev.setdefault(a_, []).append({'xgf': rec['xga'], 'xga': rec['xgf']})
    return preds, outs


grid = []
for S in (1.5, 2.0, 2.5, 3.0):
    p24, o24 = shot_model(2024, S)
    grid.append((S, metrics(np.array(p24), np.array(o24))['brier']))
S_best = min(grid, key=lambda t: t[1])[0]
print(f"B scale tuned on 2024/25: S={S_best} (pseudo-brier={min(g[1] for g in grid):.4f})")
predsB, outsB = shot_model(TEST_SEASON, S_best)
mB = metrics(np.array(predsB), np.array(outsB))

# ================= PROBE C: market ceiling (de-vig closing odds) =================
conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
cid = {r['slug']: r['id'] for r in conn.execute("SELECT id, slug FROM clubs")}
conn.close()
key_fx = {(r['home_team_id'], r['away_team_id'], r['kickoff_time'][:10]): r for r in test}
predsM, outsM = [], []
with open('data/cache/footballdata/SP1_2526.csv', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        try:
            d = datetime.datetime.strptime(row['Date'], '%d/%m/%Y').date().isoformat()
        except Exception:
            continue
        h_id = cid.get(TEAM_ALIAS.get(row['HomeTeam'], ''))
        a_id = cid.get(TEAM_ALIAS.get(row['AwayTeam'], ''))
        o = (row.get('B365CH'), row.get('B365CD'), row.get('B365CA'))
        if not (h_id and a_id and all(o)):
            continue
        fx = key_fx.get((h_id, a_id, d))
        if not fx:
            continue
        inv = np.array([1 / float(x) for x in o]); p = inv / inv.sum()
        out = 0 if fx['home_score'] > fx['away_score'] else 2 if fx['away_score'] > fx['home_score'] else 1
        predsM.append(p); outsM.append(out)
mC = metrics(np.array(predsM), np.array(outsM))


# ================= REPORT =================
def show(name, m):
    c = m['cal']
    print(f"{name:30s} n={m['n']:3d}  brier={m['brier']:.4f}  logloss={m['logloss']:.4f}  hit={m['hit'] * 100:5.1f}%  "
          f"cal(H/D/A): {c[0][0] * 100:4.1f}/{c[1][0] * 100:4.1f}/{c[2][0] * 100:4.1f} vs "
          f"{c[0][1] * 100:4.1f}/{c[1][1] * 100:4.1f}/{c[2][1] * 100:4.1f}")


print("=" * 122)
print("MODEL COMPARISON - test: 2025/26 chronological, no look-ahead, identical match set")
print("=" * 122)
show("v3 baseline (published)", dict(n=320, brier=0.6139, logloss=1.0246, hit=0.497,
                                     cal=((0.461, 0.497), (0.268, 0.234), (0.271, 0.269))))
show("A. fitted Dixon-Coles MLE", mA)
show("B. shot-quality strength", mB)
show("C. market ceiling (de-vig)", mC)
print("=" * 122)
