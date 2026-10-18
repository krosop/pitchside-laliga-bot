"""
ESPN public feed (site.api.espn.com) — the live-layer mirror for La Liga (esp.1).

Free and unauthenticated (requires a browser-like User-Agent). This module:
  * pulls the full current-season schedule (scoreboard per monthly chunk)
  * inserts fixtures missing from the DB (ESPN carries the complete calendar)
  * updates exact kickoff times / statuses / final scores for existing rows
  * fetches per-match summaries to build goal-scorer timelines (goals_json)
    and the per-player match rows that power the momentum index

Only touches the CURRENT season. Historical seasons stay owned by the
football-data.co.uk mirror so they are immutable and reproducible.
"""
import json
import re
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .mirror_footballdata import DB_PATH, TEAM_ALIAS

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1"
UA = {"User-Agent": "curl/8.4.0", "Accept": "application/json"}

# ESPN displayName -> canonical DB club slug (falls back to the mirror alias table)
ESPN_ALIAS: Dict[str, str] = {
    "Athletic Club": "athletic-club",
    "Club Atlético de Madrid": "atletico-madrid",
    "Atlético Madrid": "atletico-madrid",
    "Atlético de Madrid": "atletico-madrid",
    "FC Barcelona": "fc-barcelona",
    "Barcelona": "fc-barcelona",
    "Real Madrid": "real-madrid",
    "Real Betis": "real-betis",
    "Betis": "real-betis",
    "Celta Vigo": "rc-celta",
    "Celta": "rc-celta",
    "RCD Espanyol": "rcd-espanyol",
    "Espanyol": "rcd-espanyol",
    "Rayo Vallecano": "rayo-vallecano",
    "Rayo": "rayo-vallecano",
    "CA Osasuna": "c-a-osasuna",
    "Osasuna": "c-a-osasuna",
    "RCD Mallorca": "mallorca",
    "Mallorca": "mallorca",
    "Real Sociedad": "real-sociedad",
    "Sociedad": "real-sociedad",
    "Valencia CF": "valencia-cf",
    "Valencia": "valencia-cf",
    "Getafe CF": "getafe-cf",
    "Getafe": "getafe-cf",
    "Deportivo Alavés": "d-alaves",
    "Alavés": "d-alaves",
    "Alaves": "d-alaves",
    "Girona FC": "girona",
    "Girona": "girona",
    "Sevilla FC": "sevilla-fc",
    "Sevilla": "sevilla-fc",
    "Villarreal CF": "villarreal-cf",
    "Villarreal": "villarreal-cf",
    "Real Oviedo": "real-oviedo",
    "Oviedo": "real-oviedo",
    "Elche CF": "elche-c-f",
    "Elche": "elche-c-f",
    "Levante UD": "levante-ud",
    "Levante": "levante-ud",
    "RC Deportivo": "rc-deportivo",
    "Deportivo": "rc-deportivo",
    "Racing Santander": "r-racing-club",
    "Racing": "r-racing-club",
    "Málaga CF": "malaga-cf",
    "Málaga": "malaga-cf",
    "Malaga": "malaga-cf",
}


def _get_json(url: str, retries: int = 2) -> dict:
    last_err: Optional[Exception] = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as e:  # transient network/WAF hiccups
            last_err = e
            time.sleep(1.5)
    raise last_err  # type: ignore[misc]


def _resolve_slug(team: dict) -> Optional[str]:
    name = (team.get("displayName") or "").strip()
    short = (team.get("shortDisplayName") or "").strip()
    if name in ESPN_ALIAS:
        return ESPN_ALIAS[name]
    if short in ESPN_ALIAS:
        return ESPN_ALIAS[short]
    return TEAM_ALIAS.get(name)


def _espn_status_to_db(status: dict) -> str:
    st = status or {}
    desc = ((st.get("type") or {}).get("description") or "").lower()
    state = (st.get("state") or "").lower()
    if "full time" in desc or "final" in desc or state == "post" or st.get("completed") is True:
        return "FINISHED"
    if state == "in" or any(w in desc for w in ("first half", "second half", "halftime", "in progress", "live")):
        return "LIVE"
    if "postponed" in desc:
        return "POSTPONED"
    if "canceled" in desc or "cancelled" in desc:
        return "CANCELLED"
    return "SCHEDULED"


def _clock_to_minute(clock: Optional[str]) -> Optional[int]:
    if not clock:
        return None
    m = re.match(r"(\d+)", clock)
    return int(m.group(1)) if m else None


def sync_schedule(season: int, conn: sqlite3.Connection) -> Dict[str, int]:  # noqa: C901
    """Pulls the season's full calendar and upserts fixtures. Returns counters."""
    today = datetime.now(timezone.utc)
    year = season if today.month >= 7 else season - 1
    months = [f"{year}{m:02d}" for m in range(7, 13)] + [f"{year + 1}{m:02d}" for m in range(1, 7)]

    counters = {"seen": 0, "updated": 0, "inserted": 0, "unresolved": 0}
    for month in months:
        sb = _get_json(f"{BASE}/scoreboard?dates={month}")
        for ev in sb.get("events", []):
            counters["seen"] += 1
            comps = (ev.get("competitions") or [{}])[0]
            competitors = comps.get("competitors") or []
            if len(competitors) != 2:
                continue
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
            h_slug, a_slug = _resolve_slug(home.get("team", {})), _resolve_slug(away.get("team", {}))
            if not h_slug or not a_slug:
                counters["unresolved"] += 1
                continue
            h_id = conn.execute("SELECT id FROM clubs WHERE slug=?", (h_slug,)).fetchone()
            a_id = conn.execute("SELECT id FROM clubs WHERE slug=?", (a_slug,)).fetchone()
            if not h_id or not a_id:
                counters["unresolved"] += 1
                continue

            kickoff = (ev.get("date") or "").replace("Z", "+00:00")
            status = _espn_status_to_db(ev.get("status", {}))
            hs = home.get("score")
            as_ = away.get("score")
            hs_i = int(hs) if isinstance(hs, (int, str)) and str(hs).isdigit() else None
            as_i = int(as_) if isinstance(as_, (int, str)) and str(as_).isdigit() else None

            row = conn.execute(
                "SELECT id FROM fixtures WHERE season=? AND home_team_id=? AND away_team_id=? "
                "AND DATE(kickoff_time)=DATE(?)",
                (season, h_id["id"], a_id["id"], kickoff or "1970-01-01"),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE fixtures SET status=?, home_score=?, away_score=?, kickoff_time=? WHERE id=?",
                    (status, hs_i, as_i, kickoff or None, row["id"]),
                )
                counters["updated"] += 1
            else:
                conn.execute(
                    "INSERT INTO fixtures (matchday, home_team_id, away_team_id, home_score, away_score, "
                    "status, kickoff_time, season, goals_json) VALUES (NULL,?,?,?,?,?,?,?,NULL)",
                    (h_id["id"], a_id["id"], hs_i, as_i, status, kickoff or None, season),
                )
                counters["inserted"] += 1
    return counters


def backfill_matchdays(season: int, conn: sqlite3.Connection) -> int:
    """Assigns chronological round numbers to fixtures with NULL matchday:
    each team's k-th fixture of the season (by date) lands in round k."""
    counts = {}
    fixed = 0
    rows = conn.execute(
        "SELECT id, home_team_id, away_team_id, kickoff_time FROM fixtures "
        "WHERE season=? AND matchday IS NULL ORDER BY kickoff_time ASC, id ASC",
        (season,),
    ).fetchall()
    for r in rows:
        h, a = counts.get(r["home_team_id"], 0), counts.get(r["away_team_id"], 0)
        md = max(h, a) + 1
        conn.execute("UPDATE fixtures SET matchday=? WHERE id=?", (md, r["id"]))
        counts[r["home_team_id"]] = md
        counts[r["away_team_id"]] = md
        fixed += 1
    return fixed


def sync_match_timeline(season: int, conn: sqlite3.Connection, limit: int = 20) -> Dict[str, int]:
    """
    Builds goals_json for recent finished fixtures missing scorer data, and
    records per-player goal rows (momentum raw material). Returns counters.
    """
    counters = {"matches": 0, "goal_events": 0, "player_rows": 0}
    pending = conn.execute(
        """
        SELECT f.id, f.kickoff_time, f.home_score, f.away_score,
               hs.slug AS h_slug, aslug.slug AS a_slug
        FROM fixtures f
        JOIN clubs hs ON hs.id = f.home_team_id
        JOIN clubs aslug ON aslug.id = f.away_team_id
        WHERE f.season = ? AND f.status = 'FINISHED'
          AND (f.goals_json IS NULL OR f.goals_json = '' OR f.goals_json = '[]')
        ORDER BY f.kickoff_time DESC LIMIT ?
        """,
        (season, limit),
    ).fetchall()

    for fx in pending:
        # ESPN summaries are keyed by event id; resolve it via that day's scoreboard.
        date_compact = (fx["kickoff_time"] or "")[:10].replace("-", "")
        if not date_compact:
            continue
        try:
            sb = _get_json(f"{BASE}/scoreboard?dates={date_compact}")
            ev = next((e for e in sb.get("events", []) if (e.get("shortName") or "").count(" ") >= 0
                       and _match_event(e, fx["h_slug"], fx["a_slug"])), None)
            if not ev:
                continue
            summary = _get_json(f"{BASE}/summary?event={ev['id']}")
        except Exception:
            continue

        goals = []
        seen_keys = set()
        for k in summary.get("keyEvents", []) or []:
            t = ((k.get("type") or {}).get("text") or "").lower()
            if "goal" not in t or "penalty - missed" in t or "shot" in t and "saved" in t:
                continue
            if not ("goal" in t):
                continue
            ath = ((k.get("participants") or [{}])[0] or {}).get("athlete", {}) or {}
            team_id = ((k.get("participants") or [{}])[0] or {}).get("teamId") \
                or ((k.get("team") or {}).get("id"))
            minute = _clock_to_minute((k.get("clock") or {}).get("displayValue"))
            scorer = ath.get("displayName")
            if not scorer or minute is None:
                continue
            key = (scorer, minute)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            goals.append({
                "player": scorer,
                "player_id": ath.get("id"),
                "team": team_id,
                "minute": minute,
                "type": "goal",
            })
            counters["goal_events"] += 1

        if goals:
            conn.execute("UPDATE fixtures SET goals_json=? WHERE id=?", (json.dumps(goals), fx["id"]))
            counters["matches"] += 1
            # player momentum rows: goals only (timeline-level data)
            h_slug, a_slug = fx["h_slug"], fx["a_slug"]
            team_side = {  # ESPN team ids are opaque; map via summary header competitors
                (c.get("team") or {}).get("id"): (h_slug if c.get("homeAway") == "home" else a_slug)
                for c in (summary.get("header", {}).get("competitions", [{}])[0].get("competitors") or [])
            }
            for g in goals:
                club_slug = team_side.get(str(g["team"])) or team_side.get(g["team"]) or h_slug
                conn.execute(
                    """
                    INSERT INTO player_match_stats
                        (player_id, player_key, player_name, club_slug, season, fixture_date,
                         opponent_slug, is_home, xg, xa, goals, assists, shots, key_passes)
                    VALUES (?,?,?,?,?,?,?,?,0,0,?,0,0,0)
                    ON CONFLICT(player_key, fixture_date) DO UPDATE SET goals=excluded.goals
                    """,
                    (g.get("player_id"), f"espn-{g.get('player_id')}", g["player"], club_slug,
                     season, (fx["kickoff_time"] or "")[:10], a_slug if club_slug == h_slug else h_slug,
                     1 if club_slug == h_slug else 0, 1),
                )
                counters["player_rows"] += 1
        time.sleep(0.4)  # be polite to the free feed
    return counters


def _match_event(ev: dict, h_slug: str, a_slug: str) -> bool:
    """Matches a scoreboard event to our fixture via team aliases."""
    comps = (ev.get("competitions") or [{}])[0]
    slugs = []
    for c in comps.get("competitors") or []:
        s = _resolve_slug(c.get("team", {}))
        if s:
            slugs.append(s)
    return h_slug in slugs and a_slug in slugs


def _espn_team_ids(conn: sqlite3.Connection) -> Dict[str, str]:
    """club slug -> ESPN team id, from the league teams listing (1 request)."""
    d = _get_json(f"{BASE}/teams")
    out: Dict[str, str] = {}
    try:
        groups = (((d.get("sports") or [{}])[0].get("leagues") or [{}])[0].get("teams")) or []
    except (IndexError, AttributeError):
        groups = []
    for grp in groups:
        t = grp.get("team") or {}
        slug = _resolve_slug(t)
        if slug and t.get("id"):
            out[slug] = str(t["id"])
    return out


def _parse_height_cm(raw: Optional[str]) -> Optional[int]:
    """6' 2\" -> 188 cm; also accepts '1.88 m' style."""
    if not raw:
        return None
    m = re.search(r"(\d+)\s*'.*?(\d+)", raw)
    if m:
        return int(round((int(m.group(1)) * 12 + int(m.group(2))) * 2.54))
    m = re.search(r"(\d(?:\.\d{1,2})?)\s*m", raw)
    if m:
        return int(round(float(m.group(1)) * 100))
    return None


def _parse_weight_kg(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"(\d{2,3})\s*kg", raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{2,3})\s*lbs", raw, re.I)
    if m:
        return int(round(float(m.group(1)) * 0.4536))
    return None


def sync_player_bios(db_path: Optional[str] = None, log=print) -> Dict[str, int]:
    """Fill missing player bio facts (DOB, height cm, weight kg, headshot) from
    ESPN club rosters — complete 30-athlete squads per request, unlike
    TheSportsDB's partial listings. Fills NULLs only; ~1 request per club."""
    from .tsdb_feed import best_player_match  # shared fuzzy name matcher

    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    stats = {"dob": 0, "height": 0, "weight": 0, "photo": 0, "clubs": 0}
    try:
        try:
            conn.execute("ALTER TABLE clubs ADD COLUMN espn_id TEXT")
        except sqlite3.OperationalError:
            pass
        ids = _espn_team_ids(conn)
        for slug, espn_id in sorted(ids.items()):
            club = conn.execute("SELECT id FROM clubs WHERE slug=?", (slug,)).fetchone()
            if not club:
                continue
            if not conn.execute(
                "SELECT COUNT(*) FROM players WHERE club_id=? AND (date_of_birth IS NULL "
                "OR height IS NULL OR weight IS NULL)", (club["id"],)
            ).fetchone()[0]:
                continue
            conn.execute("UPDATE clubs SET espn_id=? WHERE id=?", (espn_id, club["id"]))
            try:
                d = _get_json(f"{BASE}/teams/{espn_id}/roster")
            except Exception:
                continue
            athletes = d.get("athletes") or []
            if not athletes:
                continue
            stats["clubs"] += 1
            for p in conn.execute(
                "SELECT id, name, nickname, date_of_birth, height, weight, photo_url "
                "FROM players WHERE club_id=?", (club["id"],)
            ).fetchall():
                m = best_player_match(p["name"], p["nickname"],
                                      [{"strPlayer": a.get("fullName") or "", "_a": a} for a in athletes])
                if not m:
                    continue
                a = m["_a"]
                dob = (a.get("dateOfBirth") or "")[:10] or None
                h = _parse_height_cm(a.get("displayHeight"))
                w = _parse_weight_kg(a.get("displayWeight"))
                shot = ((a.get("headshot") or {}).get("href")) or None
                if dob and not p["date_of_birth"]:
                    stats["dob"] += 1
                if h and not p["height"]:
                    stats["height"] += 1
                if w and not p["weight"]:
                    stats["weight"] += 1
                if shot and not p["photo_url"]:
                    stats["photo"] += 1
                if (dob and not p["date_of_birth"]) or (h and not p["height"]) or \
                   (w and not p["weight"]) or (shot and not p["photo_url"]):
                    conn.execute(
                        "UPDATE players SET date_of_birth=COALESCE(date_of_birth, ?), "
                        "height=COALESCE(height, ?), weight=COALESCE(weight, ?), "
                        "photo_url=COALESCE(photo_url, ?) WHERE id=?",
                        (dob, h, w, shot, p["id"]),
                    )
            time.sleep(0.4)  # be polite; ESPN is generous but not infinite
        conn.commit()
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def sync_all(season: Optional[int] = None, with_timelines: bool = True,
             with_bios: bool = True, db_path: Optional[str] = None) -> Dict[str, object]:
    """Full ESPN live-layer refresh for the current season."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    report: Dict[str, object] = {}
    try:
        if season is None:
            row = conn.execute("SELECT value FROM app_meta WHERE key='current_season'").fetchone()
            season = int(row[0]) if row else 2026
        report["schedule"] = sync_schedule(season, conn)
        report["matchdays_backfilled"] = backfill_matchdays(season, conn)
        if with_timelines:
            report["timelines"] = sync_match_timeline(season, conn)
        conn.commit()
        conn.close()
        if with_bios:
            try:
                report["bios"] = sync_player_bios(db_path=db_path, log=lambda *_: None)
            except Exception as e:  # bio enrichment must never break the schedule sync
                report["bios"] = {"status": f"skipped: {type(e).__name__}: {e}"}
        conn = sqlite3.connect(db_path or DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO sync_log (source, last_sync, rows_affected, status) VALUES ('espn', ?, ?, 'ok') "
            "ON CONFLICT(source) DO UPDATE SET last_sync=excluded.last_sync, "
            "rows_affected=excluded.rows_affected, status=excluded.status",
            (datetime.now(timezone.utc).isoformat(), report["schedule"].get("updated", 0)),
        )
        conn.commit()
        report["status"] = "ok"
    except Exception as e:
        conn.rollback()
        report["status"] = f"failed: {type(e).__name__}: {e}"
    finally:
        conn.close()
    return report


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    print(json.dumps(sync_all(), indent=2, default=str))
