# The Gut Feeling Algorithm: Football Match Forecasting

A rigorous, data-driven football prediction system combining a long-term dynamic Elo rating anchor with short-term 3-match weighted form momentum and lognormal-Poisson Monte Carlo simulations.

## Project Structure

- `data_cleaning.py`: Fetches 9 seasons (2016-17 through 2024-25) of Premier League data from `football-data.co.uk`, cleans timestamps, normalizes club nomenclature, and generates `clean_matches.csv`.
- `model.py`: Core algorithm implementation containing Elo updates with goal difference multiplier, match scoring with opponent strength adjustment, 3-game weighted form ($0.5/0.3/0.2$), expected goals conversion, and 10,000 lognormal-Poisson simulations.
- `walk_forward.py`: 3-season walk-forward testing and tuning script. Strictly trains on prior seasons, tunes hyperparameters, computes paired bootstrap 95% confidence intervals, and evaluates calibration across 10 bins.
- `predict.py`: CLI tool for predicting any upcoming match duel.
- `clean_matches.csv`: Standardized, chronological dataset containing 3,420 English Premier League matches.

## Core Rules

1. **Strict Temporal Integrity**: Only matches completed prior to kickoff are used. No future lookahead or data leakage.
2. **Chronological Ordering**: Matches are sorted strictly by date. No random splitting or cross-validation shuffling.
3. **Walk-Forward Tuning**: Weights ($w_{elo}, w_{form}$), scale $k$, noise $\sigma$, and confidence thresholds are chosen exclusively on past seasons.
4. **Reproducibility**: Fixed random seed ensures identical numbers on every run.
5. **Expected Performance**: Form-only achieves 45–50% accuracy; Elo anchor achieves 50–55%. Any full-season result above 60% indicates leakage.

## How to Run

### 1. Data Cleaning
```bash
python gut_feeling/data_cleaning.py
```
Outputs `clean_matches.csv` with 3,420 matches and 0 missing values.

### 2. Walk-Forward Testing & Benchmark Evaluation
```bash
python gut_feeling/walk_forward.py
```
Evaluates out-of-sample performance on seasons 2022-23, 2023-24, and 2024-25 (1,140 matches) against:
- Base Rate (Historical)
- Elo Anchor Only (1.0 / 0.0)
- 3-Match Form Only (0.0 / 1.0)
- Bookmaker Closing Odds (Pinnacle devigged)

### 3. Predict an Upcoming Match
```bash
python gut_feeling/predict.py --home "Arsenal" --away "Chelsea"
```
Outputs home/away ratings, expected goals, 10,000 simulation win/draw/loss probabilities, fair odds, and confidence verdict (`STRONG GUT FEELING`, `LEAN`, or `NO GUT FEELING`).
