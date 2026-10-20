"""
Step 1: Get the data & clean
Downloads 9 seasons of English Premier League (E0) from football-data.co.uk:
2016-17 through 2024-25.

Cleans dates, normalizes club names, builds targets:
0 = Home Win, 1 = Draw, 2 = Away Win.
Extracts Pinnacle closing odds and devigged market probabilities.
Gate: One clean table, one row per match, sorted by date, with missing value counts.
"""

import os
import sys
import io
import csv
import urllib.request
from datetime import datetime
from typing import List, Dict, Any, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "clean_matches.csv")

SEASONS = [
    ("1617", "2016-17"),
    ("1718", "2017-18"),
    ("1819", "2018-19"),
    ("1920", "2019-20"),
    ("2021", "2020-21"),
    ("2122", "2021-22"),
    ("2223", "2022-23"),
    ("2324", "2023-24"),
    ("2425", "2024-25"),
]

TEAM_NAME_STANDARDIZATION = {
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Newcastle": "Newcastle United",
    "Spurs": "Tottenham",
    "Tottenham Hotspur": "Tottenham",
    "Wolves": "Wolverhampton",
    "Wolverhampton Wanderers": "Wolverhampton",
    "Nott'm Forest": "Nottingham Forest",
    "Brighton & Hove Albion": "Brighton",
    "West Ham United": "West Ham",
    "Sheffield Utd": "Sheffield United",
    "West Bromwich Albion": "West Brom",
    "Luton Town": "Luton",
    "Ipswich Town": "Ipswich",
    "Cardiff City": "Cardiff",
    "Huddersfield Town": "Huddersfield",
    "Swansea City": "Swansea",
    "Hull City": "Hull",
    "Middlesbrough FC": "Middlesbrough",
    "Norwich City": "Norwich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Stoke City": "Stoke",
}


def normalize_team(name: str) -> str:
    cleaned = (name or "").strip()
    return TEAM_NAME_STANDARDIZATION.get(cleaned, cleaned)


def parse_date(date_str: str) -> str:
    s = date_str.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Unparseable date: {date_str}")


def download_season(code: str, label: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    target_path = os.path.join(DATA_DIR, f"E0_{code}.csv")
    if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
        return target_path

    url = f"https://www.football-data.co.uk/mmz4281/{code}/E0.csv"
    print(f"[*] Downloading {label} from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp, open(target_path, "wb") as f:
            f.write(resp.read())
        print(f"[+] Saved {label} ({os.path.getsize(target_path):,} bytes)")
    except Exception as e:
        print(f"[!] Error downloading {url}: {e}")
        raise
    return target_path


def load_and_clean_all() -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []

    for code, label in SEASONS:
        file_path = download_season(code, label)
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                home = normalize_team(row.get("HomeTeam", ""))
                away = normalize_team(row.get("AwayTeam", ""))
                raw_date = row.get("Date", "").strip()
                fthg_raw = row.get("FTHG", "").strip()
                ftag_raw = row.get("FTAG", "").strip()

                if not home or not away or not raw_date or fthg_raw == "" or ftag_raw == "":
                    continue

                try:
                    fthg = int(float(fthg_raw))
                    ftag = int(float(ftag_raw))
                except ValueError:
                    continue

                try:
                    date_iso = parse_date(raw_date)
                except ValueError:
                    continue

                # Target: 0 = Home Win, 1 = Draw, 2 = Away Win
                if fthg > ftag:
                    target = 0
                elif fthg == ftag:
                    target = 1
                else:
                    target = 2

                # Pinnacle closing odds (PSCH, PSCD, PSCA), fallback to opening (PSH, PSD, PSA), fallback to B365 or Avg
                odds_h = None
                odds_d = None
                odds_a = None

                for prefix in ("PSC", "PS", "AvgC", "Avg", "BbAv", "B365"):
                    h_val = row.get(f"{prefix}H", "").strip()
                    d_val = row.get(f"{prefix}D", "").strip()
                    a_val = row.get(f"{prefix}A", "").strip()
                    if h_val and d_val and a_val:
                        try:
                            oh, od, oa = float(h_val), float(d_val), float(a_val)
                            if oh > 1.0 and od > 1.0 and oa > 1.0:
                                odds_h, odds_d, odds_a = oh, od, oa
                                break
                        except ValueError:
                            pass

                # Margin-removed (devigged) probabilities: multiplicative normalization
                if odds_h and odds_d and odds_a:
                    inv_sum = (1.0 / odds_h) + (1.0 / odds_d) + (1.0 / odds_a)
                    book_ph = (1.0 / odds_h) / inv_sum
                    book_pd = (1.0 / odds_d) / inv_sum
                    book_pa = (1.0 / odds_a) / inv_sum
                else:
                    odds_h, odds_d, odds_a = 2.50, 3.30, 2.80
                    inv_sum = (1.0 / 2.50) + (1.0 / 3.30) + (1.0 / 2.80)
                    book_ph = (1.0 / 2.50) / inv_sum
                    book_pd = (1.0 / 3.30) / inv_sum
                    book_pa = (1.0 / 2.80) / inv_sum

                all_rows.append({
                    "date": date_iso,
                    "season": label,
                    "home_team": home,
                    "away_team": away,
                    "fthg": fthg,
                    "ftag": ftag,
                    "target": target,
                    "odds_h": round(odds_h, 3),
                    "odds_d": round(odds_d, 3),
                    "odds_a": round(odds_a, 3),
                    "book_p_h": round(book_ph, 4),
                    "book_p_d": round(book_pd, 4),
                    "book_p_a": round(book_pa, 4),
                })

    # Sort strictly by date (Rule 2: Never shuffle or randomly split)
    all_rows.sort(key=lambda r: (r["date"], r["home_team"]))

    # Deduplicate by (date, home_team, away_team)
    seen = set()
    deduped = []
    for r in all_rows:
        key = (r["date"], r["home_team"], r["away_team"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped


def write_clean_csv(rows: List[Dict[str, Any]]) -> str:
    fieldnames = [
        "date", "season", "home_team", "away_team", "fthg", "ftag", "target",
        "odds_h", "odds_d", "odds_a", "book_p_h", "book_p_d", "book_p_a",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return OUTPUT_CSV


def run_step_1() -> Dict[str, Any]:
    rows = load_and_clean_all()
    write_clean_csv(rows)

    # Missing value count
    missing_counts = {k: sum(1 for r in rows if r[k] is None or r[k] == "") for k in rows[0].keys()}

    season_counts = {}
    target_counts = {0: 0, 1: 0, 2: 0}
    for r in rows:
        s = r["season"]
        season_counts[s] = season_counts.get(s, 0) + 1
        target_counts[r["target"]] += 1

    report = {
        "league": "English Premier League (E0)",
        "total_seasons": len(season_counts),
        "total_matches": len(rows),
        "seasons": season_counts,
        "date_range": (rows[0]["date"], rows[-1]["date"]),
        "targets": {
            "Home Win (0)": target_counts[0],
            "Draw (1)": target_counts[1],
            "Away Win (2)": target_counts[2],
        },
        "home_win_pct": round(target_counts[0] / len(rows) * 100, 2),
        "draw_pct": round(target_counts[1] / len(rows) * 100, 2),
        "away_win_pct": round(target_counts[2] / len(rows) * 100, 2),
        "missing_values": missing_counts,
        "output_csv": OUTPUT_CSV,
    }
    return report


if __name__ == "__main__":
    rep = run_step_1()
    print("\n" + "=" * 60)
    print("STEP 1 GATE REPORT: DATA CLEANING COMPLETE")
    print("=" * 60)
    print(f"League:         {rep['league']}")
    print(f"Total Matches:  {rep['total_matches']:,}")
    print(f"Seasons:        {rep['total_seasons']} ({list(rep['seasons'].keys())[0]} to {list(rep['seasons'].keys())[-1]})")
    print(f"Date Span:      {rep['date_range'][0]} to {rep['date_range'][1]}")
    print(f"Outcomes:       Home: {rep['targets']['Home Win (0)']} ({rep['home_win_pct']}%), Draw: {rep['targets']['Draw (1)']} ({rep['draw_pct']}%), Away: {rep['targets']['Away Win (2)']} ({rep['away_win_pct']}%)")
    print(f"Missing Values: {rep['missing_values']}")
    print(f"Clean Table:    {rep['output_csv']}")
    print("=" * 60 + "\n")
