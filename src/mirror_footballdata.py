"""
football-data.co.uk CSV mirror importer (the "mirror -> apply -> ship" pipeline).

Downloads the official per-season La Liga CSVs (free, no auth, structured),
caches them under data/cache/footballdata/, and upserts every match into the
fixtures table with derived matchdays, per-team match stats, and a recomputed
league table. Historical seasons (2021/22 .. 2025/26) feed the Elo engine;
the newest season (2026/27) becomes the live view.

Safety model (same discipline as the API-Football sync):
  * database backup taken once per run before any write
  * count guards: a season must yield a sane number of rows before commit
  * idempotent: re-running updates in place instead of duplicating
"""
import csv
import io
import shutil
import sqlite3
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "laliga_profiles.db"
CACHE_DIR = BASE_DIR / "data" / "cache" / "footballdata"
BACKUP_DIR = BASE_DIR / "data" / "backups"

CSV_BASE = "https://www.football-data.co.uk/mmz4281/{code}/SP1.csv"

# Season CSV codes -> internal season int (start year)
SEASON_CODES: List[Tuple[str, int]] = [
    ("2122", 2021), ("2223", 2022), ("2324", 2023), ("2425", 2024),
    ("2526", 2025), ("2627", 2026),
]

# football-data.co.uk exonym -> canonical DB club slug
TEAM_ALIAS: Dict[str, str] = {
    "Alaves": "d-alaves",
    "Almeria": "almeria-cf",
    "Ath Bilbao": "athletic-club",
    "Ath Madrid": "atletico-madrid",
    "Barcelona": "fc-barcelona",
    "Betis": "real-betis",
    "Cadiz": "cadiz-cf",
    "Celta": "rc-celta",
    "Elche": "elche-c-f",
    "Espanol": "rcd-espanyol",
    "Getafe": "getafe-cf",
    "Girona": "girona",
    "Granada": "granada-cf",
    "La Coruna": "rc-deportivo",
    "Las Palmas": "las-palmas",
    "Leganes": "leganes",
    "Levante": "levante-ud",
    "Malaga": "malaga-cf",
    "Mallorca": "mallorca",
    "Osasuna": "c-a-osasuna",
    "Oviedo": "real-oviedo",
    "Real Madrid": "real-madrid",
    "Santander": "r-racing-club",
    "Sevilla": "sevilla-fc",
    "Sociedad": "real-sociedad",
    "Valencia": "valencia-cf",
    "Vallecano": "rayo-vallecano",
    "Valladolid": "valladolid",
    "Villarreal": "villarreal-cf",
}

# Fallback identity for clubs the mirror may need to create (no LaLiga feed data)
CREATED_CLUBS: Dict[str, Dict[str, str]] = {
    "cadiz-cf": {"name": "Cadiz CF", "nickname": "Cadiz", "shortname": "CAD"},
    "granada-cf": {"name": "Granada CF", "nickname": "Granada", "shortname": "GRA"},
    "real-oviedo": {"name": "Real Oviedo", "nickname": "Oviedo", "shortname": "OVI"},
    "almeria-cf": {"name": "Almeria", "nickname": "Almeria", "shortname": "ALM"},
}


def _fetch_csv(season_code: str, force: bool = False) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"SP1_{season_code}.csv"
    if not force and cache_file.exists() and cache_file.stat().st_size > 5000:
        return cache_file.read_text(encoding="utf-8-sig")
    url = CSV_BASE.format(code=season_code)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (statsphere-mirror)"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        text = resp.read().decode("utf-8-sig")
    cache_file.write_text(text, encoding="utf-8")
    return text


def _slug_for(exonym: str, conn: sqlite3.Connection) -> Optional[str]:
    slug = TEAM_ALIAS.get(exonym)
    if slug:
        return slug
    # Unknown exonym: try matching against existing clubs before giving up
    row = conn.execute(
        "SELECT slug FROM clubs WHERE LOWER(name) LIKE ? OR LOWER(nickname) LIKE ? OR LOWER(shortname) = ? LIMIT 1",
        (f"%{exonym.lower()}%", f"%{exonym.lower()}%", exonym.lower()[:3]),
    ).fetchone()
    return row["slug"] if row else None


def _ensure_club(slug: str, conn: sqlite3.Connection) -> Optional[int]:
    row = conn.execute("SELECT id FROM clubs WHERE slug = ?", (slug,)).fetchone()
    if row:
        return row["id"]
    meta = CREATED_CLUBS.get(slug, {"name": slug.replace("-", " ").title(),
                                    "nickname": slug.replace("-", " ").title(),
                                    "shortname": slug[:3].upper()})
    cur = conn.execute(
        "INSERT INTO clubs (slug, name, nickname, shortname, att_rating, mid_rating, def_rating, overall_rating) "
        "VALUES (?, ?, ?, ?, 50, 50, 50, 50)",
        (slug, meta["name"], meta["nickname"], meta["shortname"]),
    )
    return cur.lastrowid


def _parse_date(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _derive_matchdays(matches: List[Dict]) -> Dict[Tuple[str, str], int]:
    """
    The CSV has no matchday column. Assign each match a round number from
    chronology: walking matches in date order, a team's k-th match lands in
    round k, so `matchday = max(home_count, away_count) + 1` per match keeps
    every team's sequence 1..38 without collisions.
    """
    counts: Dict[str, int] = {}
    assignment: Dict[Tuple[str, str], int] = {}
    for m in sorted(matches, key=lambda x: (x["date"], x["home"], x["away"])):
        h, a = counts.get(m["home"], 0), counts.get(m["away"], 0)
        md = max(h, a) + 1
        assignment[(m["home"], m["away"], m["date"])] = md
        counts[m["home"]] = md
        counts[m["away"]] = md
    return assignment


def _recompute_standings(conn: sqlite3.Connection, season: int):
    """Rebuilds played/won/drawn/lost/GF/GA/GD/points/position for a season from finished fixtures."""
    stats: Dict[int, Dict[str, int]] = {}
    rows = conn.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score FROM fixtures "
        "WHERE season = ? AND status = 'FINISHED'", (season,)
    ).fetchall()
    for r in rows:
        for tid in (r["home_team_id"], r["away_team_id"]):
            stats.setdefault(tid, {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "points": 0})
        hs, as_ = r["home_score"] or 0, r["away_score"] or 0
        h, a = stats[r["home_team_id"]], stats[r["away_team_id"]]
        h["played"] += 1; a["played"] += 1
        h["gf"] += hs; h["ga"] += as_
        a["gf"] += as_; a["ga"] += hs
        if hs > as_:
            h["won"] += 1; h["points"] += 3; a["lost"] += 1
        elif hs < as_:
            a["won"] += 1; a["points"] += 3; h["lost"] += 1
        else:
            h["drawn"] += 1; a["drawn"] += 1; h["points"] += 1; a["points"] += 1
    ordered = sorted(stats.items(), key=lambda kv: (kv[1]["points"], kv[1]["gf"] - kv[1]["ga"], kv[1]["gf"]), reverse=True)
    # De-position every club first so removed/relegated sides drop out of the view
    conn.execute("UPDATE clubs SET position = NULL WHERE position IS NOT NULL")
    for pos, (tid, s) in enumerate(ordered, start=1):
        gd = s["gf"] - s["ga"]
        conn.execute(
            "UPDATE clubs SET position=?, played=?, won=?, drawn=?, lost=?, goals_for=?, goals_against=?, "
            "goal_difference=?, points=? WHERE id=?",
            (pos, s["played"], s["won"], s["drawn"], s["lost"], s["gf"], s["ga"], gd, s["points"], tid),
        )


def _log_sync(conn: sqlite3.Connection, source: str, rows: int, status: str):
    conn.execute(
        "INSERT INTO sync_log (source, last_sync, rows_affected, status) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(source) DO UPDATE SET last_sync=excluded.last_sync, rows_affected=excluded.rows_affected, "
        "status=excluded.status",
        (source, datetime.utcnow().isoformat(), rows, status),
    )


def sync_all(seasons: Optional[List[Tuple[str, int]]] = None, backup: bool = True,
             set_live: bool = True, fresh_codes: Tuple[str, ...] = (),
             db_path: Optional[str] = None) -> Dict[str, object]:
    """`fresh_codes`: season codes to always re-download (the live season)."""
    """
    Imports (or refreshes) all configured mirror seasons. Returns a report dict.
    Idempotent: safe to run repeatedly; each run picks up newly played matches.
    """
    seasons = seasons or SEASON_CODES
    target = Path(db_path or DB_PATH)
    if backup and target.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(target, BACKUP_DIR / f"laliga_profiles_{stamp}.db")

    report: Dict[str, object] = {"seasons": {}, "created_clubs": []}
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        total_new = 0
        for code, season in seasons:
            text = _fetch_csv(code, force=code in fresh_codes)
            rows = list(csv.DictReader(io.StringIO(text)))
            if len(rows) < 50:
                report["seasons"][season] = {"error": f"only {len(rows)} rows — aborting season", "rows": len(rows)}
                continue

            # Resolve team exonyms -> club ids (creating missing clubs)
            ids: Dict[str, int] = {}
            for r in rows:
                for ex in (r["HomeTeam"], r["AwayTeam"]):
                    if ex in ids:
                        continue
                    slug = _slug_for(ex, conn)
                    if not slug:
                        raise ValueError(f"Unmapped mirror team '{ex}' in season {code}")
                    ids[ex] = _ensure_club(slug, conn)

            matches = []
            for r in rows:
                date = _parse_date(r.get("Date"))
                if not date:
                    continue
                matches.append({
                    "home": r["HomeTeam"], "away": r["AwayTeam"], "date": date,
                    "time": (r.get("Time") or "20:00").strip() or "20:00",
                    "hs": r.get("FTHG"), "as": r.get("FTAG"),
                    "hsot": r.get("HST"), "asot": r.get("AST"),
                    "hshots": r.get("HS"), "ashots": r.get("AS"),
                    "hcorners": r.get("HC"), "acorners": r.get("AC"),
                    "hfouls": r.get("HF"), "afouls": r.get("AF"),
                    "hY": r.get("HY"), "aY": r.get("AY"), "hR": r.get("HR"), "aR": r.get("AR"),
                })
            md_map = _derive_matchdays(matches)

            new_or_updated = 0
            for m in matches:
                h_id, a_id = ids[m["home"]], ids[m["away"]]
                md = md_map[(m["home"], m["away"], m["date"])]
                kickoff = f"{m['date']}T{m['time']}:00"
                played = m["hs"] not in (None, "",) and m["as"] not in (None, "",)
                hs = int(m["hs"]) if played else None
                as_ = int(m["as"]) if played else None
                status = "FINISHED" if played else "SCHEDULED"

                existing = conn.execute(
                    "SELECT id FROM fixtures WHERE season=? AND home_team_id=? AND away_team_id=? "
                    "AND DATE(kickoff_time)=DATE(?)",
                    (season, h_id, a_id, kickoff),
                ).fetchone()
                if existing:
                    fid = existing["id"]
                    conn.execute(
                        "UPDATE fixtures SET matchday=?, home_score=?, away_score=?, status=? WHERE id=?",
                        (md, hs, as_, status, fid),
                    )
                else:
                    cur = conn.execute(
                        "INSERT INTO fixtures (matchday, home_team_id, away_team_id, home_score, away_score, "
                        "status, kickoff_time, season, goals_json) VALUES (?,?,?,?,?,?,?,?,?)",
                        (md, h_id, a_id, hs, as_, status, kickoff, season, None),
                    )
                    fid = cur.lastrowid
                new_or_updated += 1

                # Per-team match stats from the CSV box score
                def _int(v):
                    try:
                        return int(v) if v not in (None, "") else None
                    except (TypeError, ValueError):
                        return None
                conn.execute(
                    "INSERT INTO match_team_stats (fixture_id, season, home_shots, home_sot, home_corners, home_fouls, "
                    "home_yellows, home_reds, away_shots, away_sot, away_corners, away_fouls, away_yellows, away_reds) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fixture_id) DO UPDATE SET "
                    "home_shots=excluded.home_shots, home_sot=excluded.home_sot, home_corners=excluded.home_corners, "
                    "home_fouls=excluded.home_fouls, home_yellows=excluded.home_yellows, home_reds=excluded.home_reds, "
                    "away_shots=excluded.away_shots, away_sot=excluded.away_sot, away_corners=excluded.away_corners, "
                    "away_fouls=excluded.away_fouls, away_yellows=excluded.away_yellows, away_reds=excluded.away_reds",
                    (fid, season, _int(m["hshots"]), _int(m["hsot"]), _int(m["hcorners"]), _int(m["hfouls"]),
                     _int(m["hY"]), _int(m["hR"]), _int(m["ashots"]), _int(m["asot"]), _int(m["acorners"]),
                     _int(m["afouls"]), _int(m["aY"]), _int(m["aR"])),
                )

            report["seasons"][season] = {"rows": len(rows), "upserted": new_or_updated}
            total_new += new_or_updated

        # Live season = the newest one that imported successfully
        imported = sorted(int(k) for k in report["seasons"] if "error" not in report["seasons"][k])
        if imported and set_live:
            live = max(imported)
            _recompute_standings(conn, live)
            conn.execute(
                "INSERT INTO app_meta (key, value) VALUES ('current_season', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(live),)
            )
            report["live_season"] = live

        _log_sync(conn, "footballdata", total_new, "ok")
        conn.commit()
        report["status"] = "ok"
    except Exception as e:
        conn.rollback()
        report["status"] = f"failed: {type(e).__name__}: {e}"
    finally:
        conn.close()
    return report


if __name__ == "__main__":
    rep = sync_all()
    print(rep)
