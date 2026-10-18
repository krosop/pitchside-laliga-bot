"""
TheSportsDB enrichment feed (www.thesportsdb.com, free test key "3").

Adds what our other feeds don't carry:
  * club badges + stadium images for clubs missing them (Cádiz, Granada, Almería, Real Oviedo)
  * transparent player cutouts (strCutout) — squad lookup is ONE request per club
  * bio facts: date of birth, height (cm), weight (kg), birthplace, nationality

All writes are COALESCE-guarded: never overwrites a value we already have.
Network calls are polite (0.3s apart) and failures are per-club, never fatal.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(BASE_DIR / "data" / "laliga_profiles.db")
API = "https://www.thesportsdb.com/api/v1/json/3"
UA = "curl/8.4.0"  # passes TheSportsDB's edge filters reliably
PACE = 1.5  # seconds between network calls — free key is rate-limited (429)


def _get(url: str, timeout: int = 30, retries: int = 4) -> dict:
    """GET with 429-aware exponential backoff (free key is rate-limited)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    delay = 15.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == retries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 1.6, 60.0)
    raise RuntimeError("unreachable")


def _norm(s: str) -> str:
    """ascii-fold + lowercase + single spaces, for name matching."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(t for t in s.lower().split() if t)


def _tokens(s: str) -> set:
    """Name tokens, punctuation-stripped so 'I.' matches 'inaki'."""
    s = re.sub(r"[^\w\s]", " ", _norm(s))
    return {t for t in s.split() if len(t) > 1}


def parse_height_m(raw: str) -> Optional[int]:
    """'1.86 m (6 ft 1 in)' -> 186 (cm)."""
    if not raw:
        return None
    m = re.search(r"(\d\.\d{1,2})\s*m", raw)
    if m:
        return int(round(float(m.group(1)) * 100))
    return None


def parse_weight_kg(raw: str) -> Optional[int]:
    """'78 kg (172 lb)' / '174 lbs' -> 78 (kg)."""
    if not raw:
        return None
    m = re.search(r"(\d{2,3})\s*kg", raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{2,3})\s*lbs", raw, re.I)
    if m:
        return int(round(float(m.group(1)) * 0.4536))
    return None


# nationality (ascii-folded) -> ISO-3166 flag code used by our UI
NATIONALITY_FLAGS = {
    "england": "gb-eng", "spain": "es", "france": "fr", "germany": "de", "brazil": "br",
    "argentina": "ar", "uruguay": "uy", "portugal": "pt", "netherlands": "nl", "belgium": "be",
    "croatia": "hr", "serbia": "rs", "morocco": "ma", "senegal": "sn", "nigeria": "ng",
    "ghana": "gh", "mali": "ml", "ivory coast": "ci", "cote divoire": "ci", "algeria": "dz",
    "egypt": "eg", "japan": "jp", "south korea": "kr", "korea republic": "kr", "usa": "us",
    "united states": "us", "mexico": "mx", "colombia": "co", "chile": "cl", "peru": "pe",
    "ecuador": "ec", "venezuela": "ve", "paraguay": "py", "bolivia": "bo", "poland": "pl",
    "ukraine": "ua", "russia": "ru", "turkey": "tr", "turkiye": "tr", "italy": "it",
    "austria": "at", "switzerland": "ch", "denmark": "dk", "sweden": "se", "norway": "no",
    "ireland": "ie", "scotland": "gb-sct", "wales": "gb-wls", "israel": "il", "georgia": "ge",
    "slovenia": "si", "slovakia": "sk", "czech republic": "cz", "hungary": "hu", "gabon": "ga",
    "moldova": "md", "macedonia": "mk", "north macedonia": "mk", "bosnia": "ba",
    "bosnia and herzegovina": "ba", "kosovo": "xk", "albania": "al", "greece": "gr",
    "romania": "ro", "bulgaria": "bg", "finland": "fi", "iceland": "is", "cuba": "cu",
    "dominican republic": "do", "costa rica": "cr", "honduras": "hn", "panama": "pa",
    "cameroon": "cm", "tunisia": "tn", "dr congo": "cd", "congo dr": "cd", "guinea": "gn",
    "gambia": "gm", "burkina faso": "bf", "angola": "ao", "kenya": "ke", "mauritania": "mr",
    "australia": "au", "canada": "ca", "china": "cn", "india": "in", "holland": "nl",
}


def flag_for(nat: Optional[str]) -> Optional[str]:
    if not nat:
        return None
    return NATIONALITY_FLAGS.get(_norm(nat))


def fetch_team(team_name: str) -> Optional[dict]:
    """searchteams.php -> best match (the Spanish La Liga entry preferred)."""
    try:
        d = _get(f"{API}/searchteams.php?t={urllib.parse.quote(team_name)}")
    except Exception:
        return None
    teams = d.get("teams") or []
    if not teams:
        return None
    for t in teams:
        if (t.get("strLeague") or "") == "Spanish La Liga":
            return t
    return teams[0]


def fetch_squad(team_id: str) -> List[dict]:
    """lookup_all_players.php -> the whole squad in one request."""
    try:
        d = _get(f"{API}/lookup_all_players.php?id={team_id}")
    except Exception:
        return []
    return d.get("player") or []


def _initial_ok(a: str, b: str) -> bool:
    """Two differing tokens are compatible when one is an initial of the other
    ('i' ~ 'inaki'). Full-word mismatches ('jobe' vs 'jude') are NOT compatible."""
    if a == b:
        return True
    return (len(a) <= 2 and b.startswith(a)) or (len(b) <= 2 and a.startswith(b))


def best_player_match(name: str, nickname: str, squad: List[dict]) -> Optional[dict]:
    """Match a DB player to a TSDB/ESPN squad member by name tokens.

    Guards against namesakes:
      * differing full-word tokens reject the candidate outright (Jobe
        Bellingham can never take Jude Bellingham's photo)
      * a shared-surname match only counts when the nickname bonus is UNIQUE
        in the squad (two Williamses can not be told apart by surname)
    Initials ('I. Williams' vs 'Iñaki Williams') stay compatible."""
    db_tokens = _tokens(name or "")
    nick_norm = _norm(nickname or "")

    pre = []
    for p in squad:
        tsdb_tokens = _tokens(p.get("strPlayer") or "")
        if not tsdb_tokens:
            continue
        shared = tsdb_tokens & db_tokens
        if not shared:
            continue
        diff_db, diff_ts = db_tokens - tsdb_tokens, tsdb_tokens - db_tokens
        if diff_db and diff_ts:
            # one differing word on each side: only initials may bridge them
            if len(diff_db) != 1 or len(diff_ts) != 1 or not all(
                _initial_ok(a, b) for a in diff_db for b in diff_ts
            ):
                continue
        pre.append((len(shared), len(tsdb_tokens), nick_norm in tsdb_tokens, p))
    if not pre:
        return None

    # nickname bonus only when it identifies exactly one squad member
    nick_hits = [x for x in pre if x[2]]
    unique_nick = len(nick_hits) == 1
    scored = [
        (s + (2 if nk and unique_nick else 0), n_tok, p)
        for s, n_tok, nk, p in pre
    ]
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0]
    return best[2] if best[0] >= 2 else None


def _enrich_clubs(conn: sqlite3.Connection, log) -> int:
    """Fill shield_url / stadium_image_url for clubs missing them."""
    need = conn.execute(
        "SELECT id, name, nickname FROM clubs WHERE shield_url IS NULL OR shield_url = ''"
    ).fetchall()
    fixed = 0
    for row in need:
        t = fetch_team(row["nickname"] or row["name"])
        time.sleep(PACE)
        if not t:
            log(f"  club {row['name']}: no TSDB match")
            continue
        badge = t.get("strBadge") or t.get("strTeamBadge")
        stadium_img = t.get("strStadiumThumb") or t.get("strStadiumFanart") or t.get("strBanner")
        if not badge:
            log(f"  club {row['name']}: TSDB match has no badge")
            continue
        founded = (str(t["intFormedYear"]) + "-01-01") if t.get("intFormedYear") else None
        conn.execute(
            "UPDATE clubs SET shield_url=COALESCE(shield_url, ?), "
            "stadium_image_url=COALESCE(stadium_image_url, ?), "
            "foundation=COALESCE(foundation, ?) WHERE id=?",
            (badge, stadium_img, founded, row["id"]),
        )
        fixed += 1
        log(f"  club {row['name']}: badge + stadium image set")
    return fixed


def _enrich_squad(conn: sqlite3.Connection, club: sqlite3.Row, team_id: str, log) -> Dict[str, int]:
    """One squad request; fill missing cutouts + bio facts for the club's players."""
    stats = {"cutout": 0, "bio": 0}
    squad = fetch_squad(team_id)
    time.sleep(PACE)
    if not squad:
        log(f"  {club['slug']}: empty squad response")
        return stats
    players = conn.execute(
        "SELECT id, name, nickname, cutout_url, date_of_birth, height, weight, "
        "place_of_birth, country_code FROM players WHERE club_id=?",
        (club["id"],),
    ).fetchall()
    for p in players:
        needs = (
            (not p["cutout_url"]) or (not p["date_of_birth"]) or (not p["height"])
            or (not p["place_of_birth"]) or (not p["country_code"])
        )
        if not needs:
            continue
        m = best_player_match(p["name"], p["nickname"], squad)
        if not m:
            continue
        cutout = m.get("strCutout") or m.get("strThumb")
        dob = m.get("dateBorn") or None
        h = parse_height_m(m.get("strHeight") or "")
        w = parse_weight_kg(m.get("strWeight") or "")
        birth = m.get("strBirthLocation") or None
        nat = m.get("strNationality") or None
        new_cutout = cutout if (cutout and not p["cutout_url"]) else None
        new_cc = flag_for(nat) if (nat and not p["country_code"]) else None
        if any([new_cutout, dob and not p["date_of_birth"], h and not p["height"],
                birth and not p["place_of_birth"], new_cc]):
            conn.execute(
                "UPDATE players SET cutout_url=COALESCE(cutout_url, ?), "
                "date_of_birth=COALESCE(date_of_birth, ?), height=COALESCE(height, ?), "
                "weight=COALESCE(weight, ?), place_of_birth=COALESCE(place_of_birth, ?), "
                "country_code=COALESCE(country_code, ?) WHERE id=?",
                (new_cutout, dob, h, w, birth, new_cc, p["id"]),
            )
            stats["cutout"] += 1 if new_cutout else 0
            stats["bio"] += 1
    return stats


def run_enrichment(db_path: Optional[str] = None, log=print) -> Dict[str, object]:
    """Full enrichment pass. Safe to re-run; only fills NULLs."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        n_clubs = _enrich_clubs(conn, log)
        n_cutout = n_bio = 0
        # Cache TheSportsDB team ids so each club is searched at most once ever.
        try:
            conn.execute("ALTER TABLE clubs ADD COLUMN tsdb_id TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

        clubs = conn.execute(
            "SELECT id, slug, name, nickname, tsdb_id FROM clubs WHERE position IS NOT NULL ORDER BY position"
        ).fetchall()
        for club in clubs:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM players WHERE club_id=? AND (cutout_url IS NULL OR cutout_url='')",
                (club["id"],),
            ).fetchone()[0]
            if not remaining:
                continue
            team_id = club["tsdb_id"]
            if not team_id:
                t = fetch_team(club["nickname"] or club["name"])
                time.sleep(PACE)
                if not t or not t.get("idTeam"):
                    log(f"  {club['slug']}: no TSDB team id")
                    continue
                team_id = t["idTeam"]
                conn.execute("UPDATE clubs SET tsdb_id=? WHERE id=?", (team_id, club["id"]))
                conn.commit()
            s = _enrich_squad(conn, club, team_id, log)
            n_cutout += s["cutout"]
            n_bio += s["bio"]
        conn.commit()

        tot = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        cut = conn.execute(
            "SELECT COUNT(*) FROM players WHERE cutout_url IS NOT NULL AND cutout_url != ''"
        ).fetchone()[0]
        dob = conn.execute(
            "SELECT COUNT(*) FROM players WHERE date_of_birth IS NOT NULL AND date_of_birth != ''"
        ).fetchone()[0]
        h = conn.execute("SELECT COUNT(*) FROM players WHERE height IS NOT NULL").fetchone()[0]
        birth = conn.execute(
            "SELECT COUNT(*) FROM players WHERE place_of_birth IS NOT NULL AND place_of_birth != ''"
        ).fetchone()[0]
        club_img = conn.execute(
            "SELECT COUNT(*) FROM clubs WHERE shield_url IS NOT NULL AND shield_url != ''"
        ).fetchone()[0]
        return {
            "clubs_fixed": n_clubs,
            "players_cutouts_added": n_cutout,
            "players_bio_added": n_bio,
            "coverage": {"cutouts": f"{cut}/{tot}", "dob": f"{dob}/{tot}",
                         "height": f"{h}/{tot}", "birthplace": f"{birth}/{tot}",
                         "club_shields": f"{club_img}/30"},
        }
    finally:
        conn.close()


if __name__ == "__main__":
    res = run_enrichment()
    print(json.dumps(res, indent=2))
