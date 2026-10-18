"""
Market-odds mirror — the second data layer for prediction blending.

Two sources, both free and already part of the football-data.co.uk family:
  1. Historical season CSVs (cached by src/mirror_footballdata) carry pre-match
     1X2 odds (B365/Avg/Max/BW/PS) for every played fixture.
  2. The weekly fixtures file (matches.php → "fixtures in CSV format") carries
     the upcoming matchdays with fresh odds, collected Fridays/Tuesdays.

Both are de-vigged into fair probabilities (1/odds normalized) and attached to
fixtures as p_market_home/draw/away + market_source. Never fatal: if the
fixtures file is unreachable or odds are missing for a match, the column stays
NULL and the prediction engine falls back to the pure fitted MLE.
"""
import csv
import io
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from .mirror_footballdata import TEAM_ALIAS, DB_PATH, CACHE_DIR

FIXTURES_CSV_URL = "https://www.football-data.co.uk/fixtures.csv"

DDL = [
    "ALTER TABLE fixtures ADD COLUMN p_market_home REAL",
    "ALTER TABLE fixtures ADD COLUMN p_market_draw REAL",
    "ALTER TABLE fixtures ADD COLUMN p_market_away REAL",
    "ALTER TABLE fixtures ADD COLUMN market_source TEXT",
]


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {r[1] for r in conn.execute("PRAGMA table_info(fixtures)")}
    for stmt in DDL:
        col = stmt.split("ADD COLUMN ")[1].split(" ")[0]
        if col not in existing:
            conn.execute(stmt)
    conn.commit()


def _devig(h, d, a) -> Optional[Tuple[float, float, float]]:
    """Convert decimal odds to fair probabilities (normalize 1/odds)."""
    if not (h and d and a):
        return None
    try:
        ih, idd, ia = 1.0 / float(h), 1.0 / float(d), 1.0 / float(a)
    except (ValueError, ZeroDivisionError):
        return None
    s = ih + idd + ia
    return (ih / s, idd / s, ia / s)


def _pick_pre(row: Dict[str, str]) -> Optional[Tuple[float, float, float]]:
    """Best available pre-match odds: B365 → Avg → Max → BW → PS."""
    for h, d, a in (("B365H", "B365D", "B365A"), ("AvgH", "AvgD", "AvgA"),
                    ("MaxH", "MaxD", "MaxA"), ("BWH", "BWD", "BWA"),
                    ("PSH", "PSD", "PSA")):
        v = _devig(row.get(h), row.get(d), row.get(a))
        if v:
            return v
    return None


def _pick_close(row: Dict[str, str]) -> Optional[Tuple[float, float, float]]:
    for h, d, a in (("B365CH", "B365CD", "B365CA"), ("AvgCH", "AvgCD", "AvgCA"),
                    ("PSCH", "PSCD", "PSCA")):
        v = _devig(row.get(h), row.get(d), row.get(a))
        if v:
            return v
    return None


def _date_iso(raw: str) -> Optional[str]:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except (ValueError, TypeError):
            continue
    return None


def _fixture_lookup(conn: sqlite3.Connection) -> Dict[Tuple[str, str, str], int]:
    """(date_iso, home_slug, away_slug) → fixture id for all fixtures."""
    rows = conn.execute(
        "SELECT f.id, f.kickoff_time, h.slug hs, a.slug as_ "
        "FROM fixtures f JOIN clubs h ON h.id=f.home_team_id JOIN clubs a ON a.id=f.away_team_id"
    ).fetchall()
    out = {}
    for r in rows:
        d = (r["kickoff_time"] or "")[:10]
        if d:
            out[(d, r["hs"], r["as_"])] = r["id"]
    return out


def _write_market(conn: sqlite3.Connection, fixture_id: int, probs, source: str) -> None:
    conn.execute(
        "UPDATE fixtures SET p_market_home=?, p_market_draw=?, p_market_away=?, market_source=? WHERE id=?",
        (round(probs[0], 4), round(probs[1], 4), round(probs[2], 4), source, fixture_id),
    )


def sync_historical(db_path: Optional[str] = None) -> Dict[str, int]:
    """Attach odds from the cached season CSVs (played fixtures)."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    counts = {"rows": 0, "attached": 0}
    try:
        _ensure_columns(conn)
        lookup = _fixture_lookup(conn)
        for code in ("2122", "2223", "2324", "2425", "2526", "2627"):
            csv_path = CACHE_DIR / f"SP1_{code}.csv"
            if not csv_path.exists():
                continue
            with open(csv_path, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    counts["rows"] += 1
                    d = _date_iso(row.get("Date", ""))
                    hx = TEAM_ALIAS.get(row.get("HomeTeam", ""))
                    ax = TEAM_ALIAS.get(row.get("AwayTeam", ""))
                    if not (d and hx and ax):
                        continue
                    fid = lookup.get((d, hx, ax))
                    if not fid:
                        continue
                    probs = _pick_close(row) or _pick_pre(row)
                    if probs:
                        _write_market(conn, fid, probs, "fd-hist")
                        counts["attached"] += 1
        conn.commit()
    finally:
        conn.close()
    return counts


def sync_upcoming(db_path: Optional[str] = None) -> Dict[str, object]:
    """Fetch the weekly fixtures CSV and attach odds to SCHEDULED fixtures."""
    path = db_path or DB_PATH
    report: Dict[str, object] = {"source": "fd-weekly", "rows": 0, "attached": 0}
    try:
        req = urllib.request.Request(FIXTURES_CSV_URL,
                                     headers={"User-Agent": "Mozilla/5.0 (statsphere-mirror)"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            text = resp.read().decode("utf-8-sig")
    except Exception as e:
        report["status"] = f"unreachable: {type(e).__name__}"
        return report

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_columns(conn)
        lookup = _fixture_lookup(conn)
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            if row.get("Div") != "SP1":
                continue
            report["rows"] += 1
            d = _date_iso(row.get("Date", ""))
            hx = TEAM_ALIAS.get(row.get("HomeTeam", ""))
            ax = TEAM_ALIAS.get(row.get("AwayTeam", ""))
            if not (d and hx and ax):
                continue
            fid = lookup.get((d, hx, ax))
            if not fid:
                continue
            probs = _pick_pre(row)
            if probs:
                _write_market(conn, fid, probs, "fd-weekly")
                report["attached"] += 1
        conn.commit()
        # The weekly file only covers the immediately upcoming matchdays; the
        # rest of the season has no odds yet. Nothing else to do — the ledger
        # falls back to the fitted MLE for fixtures without market odds.
    finally:
        conn.close()
    report["status"] = "ok"
    return report


def run(db_path: Optional[str] = None) -> Dict[str, object]:
    hist = sync_historical(db_path)
    up = sync_upcoming(db_path)
    conn = sqlite3.connect(db_path or DB_PATH)
    n = conn.execute(
        "SELECT COUNT(*), SUM(season=(SELECT CAST(value AS INTEGER) FROM app_meta WHERE key='current_season')) "
        "FROM fixtures WHERE p_market_home IS NOT NULL").fetchone()
    conn.close()
    return {"historical": hist, "upcoming": up,
            "fixtures_with_market": {"total": n[0], "current_season": n[1]}}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, default=str))
