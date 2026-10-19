"""
SQLite Database Manager for La Liga Football Profiler.
Multi-season aware: fixtures carry a `season` INTEGER (start year, e.g. 2026
= 2026/27) and all read paths default to the CURRENT season so historical
mirror data (5+ seasons) never leaks into the live league view.
"""
import sqlite3
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import Club, PlayerBio, PlayerStats, PlayerProfile, ClubProfile, ClubStats, ClubScores
from .simulation_engine import SimulationEngine


class Database:
    # ------------------------------------------------------------------
    # Season helpers
    # ------------------------------------------------------------------
    def set_current_season(self, season: int):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO app_meta (key, value) VALUES ('current_season', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(season),),
            )
            conn.commit()

    def get_current_season(self) -> int:
        """The season the site treats as 'live'. Stored in app_meta; falls back
        to the highest season that actually has fixtures."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT value FROM app_meta WHERE key='current_season'").fetchone()
            if row and row[0]:
                try:
                    return int(row[0])
                except (TypeError, ValueError):
                    pass
            row = conn.execute("SELECT MAX(season) FROM fixtures WHERE season IS NOT NULL").fetchone()
            return int(row[0]) if row and row[0] else 2024

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            data_dir = base_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "laliga_profiles.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # Clubs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clubs (
                    id INTEGER PRIMARY KEY,
                    slug TEXT UNIQUE,
                    name TEXT,
                    nickname TEXT,
                    shortname TEXT,
                    foundation TEXT,
                    shield_url TEXT,
                    color TEXT,
                    color_secondary TEXT,
                    stadium TEXT,
                    stadium_name TEXT,
                    stadium_image_url TEXT,
                    president TEXT,
                    address TEXT,
                    web_url TEXT,
                    position INTEGER,
                    played INTEGER DEFAULT 0,
                    won INTEGER DEFAULT 0,
                    drawn INTEGER DEFAULT 0,
                    lost INTEGER DEFAULT 0,
                    goals_for INTEGER DEFAULT 0,
                    goals_against INTEGER DEFAULT 0,
                    goal_difference INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0,
                    qualification TEXT,
                    att_rating INTEGER DEFAULT 50,
                    mid_rating INTEGER DEFAULT 50,
                    def_rating INTEGER DEFAULT 50,
                    overall_rating INTEGER DEFAULT 50
                )
            """)

            # Run safe migrations for existing tables
            new_club_cols = [
                ("stadium_name", "TEXT"),
                ("stadium_image_url", "TEXT"),
                ("president", "TEXT"),
                ("address", "TEXT"),
                ("web_url", "TEXT"),
                ("position", "INTEGER"),
                ("played", "INTEGER DEFAULT 0"),
                ("won", "INTEGER DEFAULT 0"),
                ("drawn", "INTEGER DEFAULT 0"),
                ("lost", "INTEGER DEFAULT 0"),
                ("goals_for", "INTEGER DEFAULT 0"),
                ("goals_against", "INTEGER DEFAULT 0"),
                ("goal_difference", "INTEGER DEFAULT 0"),
                ("points", "INTEGER DEFAULT 0"),
                ("qualification", "TEXT"),
                ("att_rating", "INTEGER DEFAULT 50"),
                ("mid_rating", "INTEGER DEFAULT 50"),
                ("def_rating", "INTEGER DEFAULT 50"),
                ("overall_rating", "INTEGER DEFAULT 50"),
                ("formation", "TEXT DEFAULT '4-3-3'"),
                ("competition", "TEXT DEFAULT 'laliga'"),
            ]
            for col_name, col_type in new_club_cols:
                try:
                    cursor.execute(f"ALTER TABLE clubs ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass  # column already exists

            # Detailed Club Data (Stats, Scores, Profiles)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS club_profiles (
                    club_id INTEGER PRIMARY KEY,
                    stats_json TEXT,
                    scores_json TEXT,
                    profile_json TEXT,
                    FOREIGN KEY(club_id) REFERENCES clubs(id)
                )
            """)

            # Players table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY,
                    opta_id TEXT,
                    slug TEXT UNIQUE,
                    name TEXT,
                    nickname TEXT,
                    shirt_number INTEGER,
                    position_name TEXT,
                    position_slug TEXT,
                    country_code TEXT,
                    photo_url TEXT,
                    club_id INTEGER,
                    date_of_birth TEXT,
                    place_of_birth TEXT,
                    height INTEGER,
                    weight INTEGER,
                    archetype TEXT,
                    overall_rating INTEGER DEFAULT 50,
                    FOREIGN KEY(club_id) REFERENCES clubs(id)
                )
            """)

            # Detailed Player Data (Stats, Rankings, Profiles)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_profiles (
                    player_id INTEGER PRIMARY KEY,
                    stats_json TEXT,
                    rankings_json TEXT,
                    scores_json TEXT,
                    profile_json TEXT,
                    FOREIGN KEY(player_id) REFERENCES players(id)
                )
            """)

            # Enrichment columns (TheSportsDB feed). Guarded ALTERs keep both
            # fresh checkouts and existing DBs on the same schema.
            for col_name, col_type in [
                ("cutout_url", "TEXT"),
                ("bio_summary", "TEXT"),
                ("market_value", "TEXT"),
                ("wage", "TEXT"),
                ("availability_status", "TEXT DEFAULT 'available'"),
                ("availability_reason", "TEXT"),
                ("suspended_matchday", "INTEGER"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE players ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass  # column already exists

            # Performance indices for fast searching/sorting
            # --- Multi-season + intelligence tables (safe idempotent migrations) ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS match_team_stats (
                    fixture_id INTEGER PRIMARY KEY,
                    season INTEGER,
                    home_shots INTEGER, home_sot INTEGER, home_corners INTEGER,
                    home_fouls INTEGER, home_yellows INTEGER, home_reds INTEGER,
                    away_shots INTEGER, away_sot INTEGER, away_corners INTEGER,
                    away_fouls INTEGER, away_yellows INTEGER, away_reds INTEGER,
                    FOREIGN KEY(fixture_id) REFERENCES fixtures(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_match_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER,
                    player_key TEXT,
                    player_name TEXT,
                    club_slug TEXT,
                    season INTEGER,
                    fixture_date TEXT,
                    opponent_slug TEXT,
                    is_home INTEGER,
                    xg REAL DEFAULT 0, xa REAL DEFAULT 0,
                    goals INTEGER DEFAULT 0, assists INTEGER DEFAULT 0,
                    shots INTEGER DEFAULT 0, key_passes INTEGER DEFAULT 0,
                    yellow_cards INTEGER DEFAULT 0, red_cards INTEGER DEFAULT 0,
                    UNIQUE(player_key, fixture_date)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS club_ratings (
                    club_id INTEGER PRIMARY KEY,
                    elo REAL DEFAULT 1500,
                    difficulty REAL DEFAULT 2.5,
                    rank INTEGER,
                    matches_counted INTEGER DEFAULT 0,
                    updated_at TEXT,
                    FOREIGN KEY(club_id) REFERENCES clubs(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    source TEXT PRIMARY KEY,
                    last_sync TEXT,
                    rows_affected INTEGER,
                    status TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fixtures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    matchday INTEGER,
                    home_team_id INTEGER,
                    away_team_id INTEGER,
                    home_score INTEGER,
                    away_score INTEGER,
                    status TEXT,
                    kickoff_time TEXT,
                    goals_json TEXT,
                    cards_json TEXT,
                    season INTEGER
                )
            """)
            # season & cards_json columns on fixtures (legacy rows backfilled to 2024).
            try:
                cursor.execute("ALTER TABLE fixtures ADD COLUMN season INTEGER")
                cursor.execute("UPDATE fixtures SET season = 2024 WHERE season IS NULL")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_fixtures_season ON fixtures(season, matchday)")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE fixtures ADD COLUMN cards_json TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE fixtures ADD COLUMN competition TEXT DEFAULT 'laliga'")
            except sqlite3.OperationalError:
                pass
            for col_name, col_type in [
                ("player_key", "TEXT"),
                ("player_name", "TEXT"),
                ("yellow_cards", "INTEGER DEFAULT 0"),
                ("red_cards", "INTEGER DEFAULT 0"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE player_match_stats ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pms_player ON player_match_stats(player_id, season)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pms_club ON player_match_stats(club_slug, season)")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_slug ON players(slug)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_name ON players(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_nickname ON players(nickname)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_position ON players(position_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_club ON players(club_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_rating ON players(overall_rating)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clubs_slug ON clubs(slug)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clubs_pos ON clubs(position)")

            conn.commit()
        finally:
            conn.close()

    def upsert_club(self, club: Club):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            comp = getattr(club, "competition", "laliga") or "laliga"
            att = getattr(club, "att_rating", 50) or 50
            mid = getattr(club, "mid_rating", 50) or 50
            df = getattr(club, "def_rating", 50) or 50
            ovr = getattr(club, "overall_rating", 50) or 50
            cursor.execute("""
                INSERT INTO clubs (
                    id, slug, name, nickname, shortname, foundation, shield_url,
                    color, color_secondary, stadium, stadium_name, stadium_image_url,
                    president, address, web_url, position, played, won, drawn, lost,
                    goals_for, goals_against, goal_difference, points, qualification, formation,
                    competition, att_rating, mid_rating, def_rating, overall_rating
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    slug=excluded.slug,
                    name=excluded.name,
                    nickname=excluded.nickname,
                    shortname=excluded.shortname,
                    foundation=COALESCE(excluded.foundation, clubs.foundation),
                    shield_url=COALESCE(excluded.shield_url, clubs.shield_url),
                    color=COALESCE(excluded.color, clubs.color),
                    color_secondary=COALESCE(excluded.color_secondary, clubs.color_secondary),
                    stadium=COALESCE(excluded.stadium, clubs.stadium),
                    stadium_name=COALESCE(excluded.stadium_name, clubs.stadium_name),
                    stadium_image_url=COALESCE(excluded.stadium_image_url, clubs.stadium_image_url),
                    president=COALESCE(excluded.president, clubs.president),
                    address=COALESCE(excluded.address, clubs.address),
                    web_url=COALESCE(excluded.web_url, clubs.web_url),
                    position=COALESCE(excluded.position, clubs.position),
                    played=COALESCE(excluded.played, clubs.played),
                    won=COALESCE(excluded.won, clubs.won),
                    drawn=COALESCE(excluded.drawn, clubs.drawn),
                    lost=COALESCE(excluded.lost, clubs.lost),
                    goals_for=COALESCE(excluded.goals_for, clubs.goals_for),
                    goals_against=COALESCE(excluded.goals_against, clubs.goals_against),
                    goal_difference=COALESCE(excluded.goal_difference, clubs.goal_difference),
                    points=COALESCE(excluded.points, clubs.points),
                    qualification=COALESCE(excluded.qualification, clubs.qualification),
                    formation=COALESCE(excluded.formation, clubs.formation),
                    competition=COALESCE(excluded.competition, clubs.competition),
                    att_rating=COALESCE(excluded.att_rating, clubs.att_rating),
                    mid_rating=COALESCE(excluded.mid_rating, clubs.mid_rating),
                    def_rating=COALESCE(excluded.def_rating, clubs.def_rating),
                    overall_rating=COALESCE(excluded.overall_rating, clubs.overall_rating)
            """, (
                club.id, club.slug, club.name, club.nickname, club.shortname,
                club.foundation, club.shield_url, club.color, club.color_secondary,
                club.stadium, club.stadium_name, club.stadium_image_url,
                club.president, club.address, club.web_url,
                club.position, club.played, club.won, club.drawn, club.lost,
                club.goals_for, club.goals_against, club.goal_difference,
                club.points, club.qualification, club.formation,
                comp, att, mid, df, ovr
            ))
            conn.commit()

    def upsert_player_profile(self, profile: PlayerProfile):
        bio = profile.bio
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Insert or update player master record
            cursor.execute("""
                INSERT INTO players (
                    id, opta_id, slug, name, nickname, shirt_number,
                    position_name, position_slug, country_code, photo_url,
                    club_id, date_of_birth, place_of_birth, height, weight,
                    archetype, overall_rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    opta_id=excluded.opta_id,
                    slug=excluded.slug,
                    name=excluded.name,
                    nickname=excluded.nickname,
                    shirt_number=excluded.shirt_number,
                    position_name=excluded.position_name,
                    position_slug=excluded.position_slug,
                    country_code=excluded.country_code,
                    photo_url=excluded.photo_url,
                    club_id=excluded.club_id,
                    date_of_birth=COALESCE(excluded.date_of_birth, players.date_of_birth),
                    place_of_birth=COALESCE(excluded.place_of_birth, players.place_of_birth),
                    height=COALESCE(excluded.height, players.height),
                    weight=COALESCE(excluded.weight, players.weight),
                    archetype=excluded.archetype,
                    overall_rating=excluded.overall_rating
            """, (
                bio.id, bio.opta_id, bio.slug, bio.name, bio.nickname, bio.shirt_number,
                bio.position_name, bio.position_slug, bio.country_code, bio.photo_url,
                bio.club_id, bio.date_of_birth, bio.place_of_birth, bio.height, bio.weight,
                profile.archetype, profile.scores.overall_rating
            ))

            # Insert or update profile JSON blobs
            cursor.execute("""
                INSERT INTO player_profiles (
                    player_id, stats_json, rankings_json, scores_json, profile_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    stats_json=excluded.stats_json,
                    rankings_json=excluded.rankings_json,
                    scores_json=excluded.scores_json,
                    profile_json=excluded.profile_json
            """, (
                bio.id,
                json.dumps(profile.stats.to_dict()),
                json.dumps(profile.rankings),
                json.dumps(profile.scores.to_dict()),
                json.dumps(profile.to_dict())
            ))

            conn.commit()

    # ------------------------------------------------------------------
    # Profile enrichment — live momentum, ratings, form, fixtures
    # (all read-only, best-effort: enrichment never breaks a profile)
    # ------------------------------------------------------------------
    def _live_season(self, conn) -> int:
        row = conn.execute("SELECT value FROM app_meta WHERE key='current_season'").fetchone()
        try:
            return int(row[0]) if row and row[0] else 2026
        except (TypeError, ValueError):
            return 2026

    def _player_enrichment(self, bio: Dict[str, Any], club_slug: Optional[str]) -> Optional[Dict[str, Any]]:
        if not club_slug:
            return None
        try:
            from .momentum import compute_momentum
            m = compute_momentum(self, bio, club_slug)
            if not m.matches:
                return None
            out = m.to_dict()
            out["last_matches"] = m.last_matches
            # Goal log: real scoring appearances joined to fixtures for deep links
            goal_log = []
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                season = self._live_season(conn)
                rows = conn.execute(
                    "SELECT player_name, goals, assists, xg, fixture_date, opponent_slug, is_home "
                    "FROM player_match_stats WHERE club_slug=? ORDER BY fixture_date DESC LIMIT 400",
                    (club_slug,),
                ).fetchall()
                import unicodedata
                def _norm(s):
                    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower()
                    return " ".join(t for t in s.split() if t)
                target = _norm(bio.get("name") or bio.get("nickname") or "")
                tset = {t for t in target.split() if len(t) > 2}
                for r in rows:
                    nm = _norm(r["player_name"])
                    if not nm or not (nm == target or (tset and tset & {t for t in nm.split() if len(t) > 2})):
                        continue
                    if not (r["goals"] or r["assists"]):
                        continue
                    fid = None
                    if r["opponent_slug"] and r["fixture_date"]:
                        fx = conn.execute(
                            """SELECT f.id FROM fixtures f                               JOIN clubs ho ON ho.id=f.home_team_id JOIN clubs aw ON aw.id=f.away_team_id                               WHERE f.season=? AND f.kickoff_time LIKE ? AND                                     ((ho.slug=? AND aw.slug=?) OR (aw.slug=? AND ho.slug=?))
                               LIMIT 1""",
                            (season, str(r["fixture_date"])[:10] + "%", club_slug, r["opponent_slug"],
                             club_slug, r["opponent_slug"]),
                        ).fetchone()
                        fid = fx["id"] if fx else None
                    opp = conn.execute("SELECT nickname, name FROM clubs WHERE slug=?", (r["opponent_slug"],)).fetchone() if r["opponent_slug"] else None
                    goal_log.append({
                        "date": r["fixture_date"], "goals": r["goals"], "assists": r["assists"],
                        "xg": r["xg"], "venue": "H" if r["is_home"] else "A",
                        "opponent": (opp["nickname"] or opp["name"]) if opp else (r["opponent_slug"] or "?"),
                        "opponent_slug": r["opponent_slug"], "fixture_id": fid,
                    })
                    if len(goal_log) >= 8:
                        break
            out["goal_log"] = goal_log
            return out
        except Exception:
            return None

    def _club_enrichment(self, club_slug: str) -> Optional[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                season = self._live_season(conn)
                club = conn.execute("SELECT id FROM clubs WHERE slug=?", (club_slug,)).fetchone()
                if not club:
                    return None
                cid = club["id"]
                opp_meta = {}
                for o in conn.execute("SELECT id, name, nickname, slug, shield_url FROM clubs"):
                    opp_meta[o["id"]] = dict(o)

                def opponent(oid):
                    o = opp_meta.get(oid, {})
                    return {"name": o.get("nickname") or o.get("name") or "?", "slug": o.get("slug"),
                            "shield": o.get("shield_url")}

                # Last 5 finished, chronological
                rows = conn.execute(
                    """SELECT id fid, matchday, kickoff_time, home_team_id, away_team_id, home_score, away_score
                       FROM fixtures WHERE season=? AND status='FINISHED' AND home_score IS NOT NULL
                         AND (home_team_id=? OR away_team_id=?) ORDER BY kickoff_time DESC, id DESC LIMIT 5""",
                    (season, cid, cid),
                ).fetchall()
                form = []
                for r in reversed(rows):
                    home = r["home_team_id"] == cid
                    gf = r["home_score"] if home else r["away_score"]
                    ga = r["away_score"] if home else r["home_score"]
                    form.append({
                        "fixture_id": r["fid"], "matchday": r["matchday"], "kickoff_time": r["kickoff_time"],
                        "result": "W" if gf > ga else "D" if gf == ga else "L", "score": f"{gf}-{ga}",
                        "venue": "H" if home else "A", "opponent": opponent(r["away_team_id"] if home else r["home_team_id"]),
                    })
                # Next 4 scheduled
                upcoming = []
                for r in conn.execute(
                    """SELECT id fid, matchday, kickoff_time, home_team_id, away_team_id
                       FROM fixtures WHERE season=? AND status='SCHEDULED'
                         AND (home_team_id=? OR away_team_id=?) ORDER BY kickoff_time ASC, id ASC LIMIT 4""",
                    (season, cid, cid),
                ).fetchall():
                    home = r["home_team_id"] == cid
                    upcoming.append({
                        "fixture_id": r["fid"], "matchday": r["matchday"], "kickoff_time": r["kickoff_time"],
                        "venue": "H" if home else "A", "opponent": opponent(r["away_team_id"] if home else r["home_team_id"]),
                    })

            from .ratings import RatingsEngine
            from .momentum import team_momentum
            rating = RatingsEngine.get_or_none(self, club_slug)
            squad = [{"name": n} for n in (
                r[0] for r in self.get_connection().execute(
                    "SELECT p.name FROM players p JOIN clubs c ON p.club_id=c.id WHERE c.slug=?",
                    (club_slug,),
                ).fetchall()
            )]
            tm = team_momentum(self, club_slug, squad) if squad else {"index": 50.0, "status": "stable", "hot": [], "cold": []}
            for fx in upcoming:  # opponent difficulty for the next matches
                r = RatingsEngine.get_or_none(self, fx["opponent"]["slug"] or "") if fx["opponent"]["slug"] else None
                fx["opponent_elo"] = r.get("elo") if r else None
                fx["opponent_tier"] = r.get("difficulty") if r else None
            return {"form": form, "upcoming": upcoming, "rating": rating, "team_momentum": tm}
        except Exception:
            return None

    def get_player_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        clean = slug.strip().lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pp.profile_json, p.cutout_url, p.date_of_birth, p.height, p.weight,
                       p.place_of_birth, p.country_code, p.photo_url, p.bio_summary,
                       p.market_value, p.wage, p.availability_status, p.availability_reason,
                       p.suspended_matchday, c.slug AS club_slug
                FROM players p
                JOIN player_profiles pp ON p.id = pp.player_id
                LEFT JOIN clubs c ON p.club_id = c.id
                WHERE p.slug = ? OR p.slug LIKE ? OR LOWER(p.nickname) = ? OR LOWER(p.name) = ? OR LOWER(p.nickname) LIKE ?
                ORDER BY CASE WHEN p.slug = ? THEN 1 WHEN LOWER(p.nickname) = ? THEN 2 ELSE 3 END
                LIMIT 1
            """, (clean, f"%{clean}%", clean, clean, f"%{clean}%", clean, clean))
            row = cursor.fetchone()
            if row and row["profile_json"]:
                profile = json.loads(row["profile_json"])
                bio = profile.setdefault("bio", {})
                # The enrichment feeds write to the players TABLE; the profile
                # blob can be stale. Fresh column values win when present.
                for k in ("cutout_url", "date_of_birth", "height", "weight",
                          "place_of_birth", "country_code", "photo_url",
                          "bio_summary", "market_value", "wage",
                          "availability_status", "availability_reason", "suspended_matchday"):
                    if row[k] is not None:
                        bio[k] = row[k]
                momentum = self._player_enrichment(profile.get("bio", {}), row["club_slug"])
                if momentum:
                    profile["momentum"] = momentum
                return profile
            return None

    def set_player_availability(self, player_id_or_slug: Any, status: str = "available",
                                reason: Optional[str] = None, suspended_matchday: Optional[int] = None) -> bool:
        """
        Sets a player's availability status ('available', 'suspended', 'injured', 'doubtful')
        and optional reason (e.g., 'Red Card Suspension', 'Hamstring Injury').
        """
        status_clean = (status or "available").strip().lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(player_id_or_slug, int) or (isinstance(player_id_or_slug, str) and player_id_or_slug.isdigit()):
                cursor.execute(
                    "UPDATE players SET availability_status=?, availability_reason=?, suspended_matchday=? WHERE id=?",
                    (status_clean, reason, suspended_matchday, int(player_id_or_slug)),
                )
            else:
                s = str(player_id_or_slug).strip().lower()
                cursor.execute(
                    "UPDATE players SET availability_status=?, availability_reason=?, suspended_matchday=? "
                    "WHERE LOWER(slug)=? OR LOWER(name)=? OR LOWER(nickname)=?",
                    (status_clean, reason, suspended_matchday, s, s, s),
                )
            conn.commit()
            return cursor.rowcount > 0

    def record_match_red_card(self, fixture_id: int, player_id_or_slug: Any,
                              minute: int = 75, card_type: str = "red_card") -> bool:
        """
        Records a red card for a player in a completed fixture (`fixtures.cards_json`
        and `player_match_stats.red_cards = 1`), which automatically suspends the player
        for their club's next league fixture.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            fx = cursor.execute(
                """
                SELECT f.id, f.season, f.matchday, f.kickoff_time, f.cards_json,
                       h.slug AS h_slug, a.slug AS a_slug
                FROM fixtures f
                JOIN clubs h ON f.home_team_id = h.id
                JOIN clubs a ON f.away_team_id = a.id
                WHERE f.id = ?
                """,
                (fixture_id,),
            ).fetchone()
            if not fx:
                return False

            if isinstance(player_id_or_slug, int) or (isinstance(player_id_or_slug, str) and str(player_id_or_slug).isdigit()):
                prow = cursor.execute(
                    "SELECT p.id, p.slug, p.name, p.nickname, c.slug AS club_slug "
                    "FROM players p LEFT JOIN clubs c ON p.club_id = c.id WHERE p.id = ?",
                    (int(player_id_or_slug),),
                ).fetchone()
            else:
                s = str(player_id_or_slug).strip().lower()
                prow = cursor.execute(
                    "SELECT p.id, p.slug, p.name, p.nickname, c.slug AS club_slug "
                    "FROM players p LEFT JOIN clubs c ON p.club_id = c.id "
                    "WHERE LOWER(p.slug)=? OR LOWER(p.name)=? OR LOWER(p.nickname)=? LIMIT 1",
                    (s, s, s),
                ).fetchone()
            if not prow:
                return False

            cards = []
            if fx["cards_json"]:
                try:
                    cards = json.loads(fx["cards_json"])
                except Exception:
                    cards = []

            pname = prow["name"] or prow["nickname"]
            club_slug = prow["club_slug"] or fx["h_slug"]
            cards.append({
                "player": pname,
                "player_id": prow["id"],
                "player_slug": prow["slug"],
                "club_slug": club_slug,
                "minute": minute,
                "type": card_type,
            })
            cursor.execute("UPDATE fixtures SET cards_json=? WHERE id=?", (json.dumps(cards), fixture_id))

            fx_date = str(fx["kickoff_time"] or "2026-08-15")[:10]
            opp_slug = fx["a_slug"] if club_slug == fx["h_slug"] else fx["h_slug"]
            is_home = 1 if club_slug == fx["h_slug"] else 0
            p_key = f"db-{prow['id']}"
            cursor.execute(
                """
                INSERT INTO player_match_stats
                    (player_id, player_key, player_name, club_slug, season, fixture_date,
                     opponent_slug, is_home, xg, xa, goals, assists, shots, key_passes, yellow_cards, red_cards)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 1)
                ON CONFLICT(player_key, fixture_date) DO UPDATE SET red_cards = 1, player_id = excluded.player_id
                """,
                (prow["id"], p_key, pname, club_slug, fx["season"] or self.get_current_season(), fx_date, opp_slug, is_home),
            )
            conn.commit()
            return True

    def get_unavailable_players_for_fixture(self, club_slug: str, matchday: Optional[int] = None,
                                            season: Optional[int] = None) -> Dict[int, Dict[str, Any]]:
        """
        Determines all unavailable players for `club_slug` at `matchday`:
        1. Players explicitly marked `suspended` or `injured` on `players.availability_status`
           (matching `suspended_matchday` if specified).
        2. Players who received a RED CARD in the club's immediately preceding finished league
           fixture (`cards_json`, `goals_json`, or `player_match_stats.red_cards > 0`).
        Returns a mapping of `player_id -> {status, reason, icon}`.
        """
        unavailable: Dict[int, Dict[str, Any]] = {}
        c_slug = {"atletico-madrid": "atletico-de-madrid", "celta-vigo": "rc-celta"}.get(
            (club_slug or "").strip().lower(), (club_slug or "").strip().lower()
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if season is None:
                season = self._live_season(conn)

            # 1. Explicit status on players table
            rows = cursor.execute(
                """
                SELECT p.id, p.name, p.nickname, p.slug, p.availability_status,
                       p.availability_reason, p.suspended_matchday
                FROM players p
                JOIN clubs c ON p.club_id = c.id
                WHERE (c.slug = ? OR LOWER(c.nickname) = LOWER(?))
                """,
                (c_slug, c_slug),
            ).fetchall()

            squad_by_id = {r["id"]: dict(r) for r in rows}
            for r in rows:
                st = (r["availability_status"] or "available").strip().lower()
                if st in ("suspended", "red_card"):
                    susp_md = r["suspended_matchday"]
                    if susp_md is None or matchday is None or int(susp_md) == int(matchday):
                        unavailable[r["id"]] = {
                            "status": "suspended",
                            "reason": r["availability_reason"] or "Red Card Suspension",
                            "icon": "🟥",
                        }
                elif st in ("injured", "injury", "out"):
                    unavailable[r["id"]] = {
                        "status": "injured",
                        "reason": r["availability_reason"] or "Medical / Injury Absence",
                        "icon": "🏥",
                    }

            # 2. Automatic previous-match red card detection
            club_row = cursor.execute("SELECT id FROM clubs WHERE slug=?", (c_slug,)).fetchone()
            if club_row and squad_by_id:
                cid = club_row["id"]
                if matchday is not None:
                    prev_fx = cursor.execute(
                        """
                        SELECT id, matchday, kickoff_time, goals_json, cards_json
                        FROM fixtures
                        WHERE season=? AND status='FINISHED' AND (home_team_id=? OR away_team_id=?)
                          AND matchday < ?
                        ORDER BY matchday DESC, kickoff_time DESC, id DESC LIMIT 1
                        """,
                        (season, cid, cid, int(matchday)),
                    ).fetchone()
                else:
                    prev_fx = cursor.execute(
                        """
                        SELECT id, matchday, kickoff_time, goals_json, cards_json
                        FROM fixtures
                        WHERE season=? AND status='FINISHED' AND (home_team_id=? OR away_team_id=?)
                        ORDER BY matchday DESC, kickoff_time DESC, id DESC LIMIT 1
                        """,
                        (season, cid, cid),
                    ).fetchone()

                if prev_fx:
                    prev_md = prev_fx["matchday"]
                    prev_date = str(prev_fx["kickoff_time"] or "")[:10]
                    red_names = set()
                    red_ids = set()

                    for raw_col in (prev_fx["cards_json"], prev_fx["goals_json"]):
                        if not raw_col:
                            continue
                        try:
                            ev_list = json.loads(raw_col)
                        except Exception:
                            ev_list = []
                        for ev in ev_list:
                            ev_type = (ev.get("type") or "").lower()
                            if "red" in ev_type or "second_yellow" in ev_type:
                                ev_club = ev.get("club_slug")
                                if ev_club and ev_club != c_slug:
                                    continue
                                if ev.get("player_id") is not None:
                                    try:
                                        red_ids.add(int(ev["player_id"]))
                                    except (TypeError, ValueError):
                                        pass
                                if ev.get("player"):
                                    red_names.add(str(ev["player"]).strip().lower())

                    if prev_date:
                        pms_reds = cursor.execute(
                            """
                            SELECT player_id, player_name FROM player_match_stats
                            WHERE club_slug=? AND fixture_date=? AND red_cards > 0
                            """,
                            (c_slug, prev_date),
                        ).fetchall()
                        for pr in pms_reds:
                            if pr["player_id"]:
                                try:
                                    red_ids.add(int(pr["player_id"]))
                                except (TypeError, ValueError):
                                    pass
                            if pr["player_name"]:
                                red_names.add(str(pr["player_name"]).strip().lower())

                    for pid, pinfo in squad_by_id.items():
                        pname_l = (pinfo.get("name") or "").strip().lower()
                        pnick_l = (pinfo.get("nickname") or "").strip().lower()
                        pslug_l = (pinfo.get("slug") or "").strip().lower()
                        matched = (pid in red_ids) or (pname_l and pname_l in red_names) or (pnick_l and pnick_l in red_names) or (pslug_l and pslug_l in red_names)
                        if not matched and red_names:
                            # Token match for e.g. ESPN display name vs DB name
                            for rn in red_names:
                                if (pname_l and (rn in pname_l or pname_l in rn)) or (pnick_l and len(pnick_l) > 3 and pnick_l in rn):
                                    matched = True
                                    break
                        if matched:
                            unavailable[pid] = {
                                "status": "suspended",
                                "reason": f"Red Card Suspension (MD {prev_md})",
                                "icon": "🟥",
                            }

        return unavailable

    def search_players(self, query: str = "", position: str = "", club_slug: str = "",
                       min_rating: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT p.id, p.slug, p.name, p.nickname, p.shirt_number, p.position_name,
                       p.country_code, p.photo_url, p.cutout_url, p.bio_summary, p.market_value, p.wage, p.date_of_birth,
                       p.archetype, p.overall_rating,
                       p.availability_status, p.availability_reason, p.suspended_matchday,
                       c.name AS club_name, c.nickname AS club_nickname, c.slug AS club_slug, c.shield_url AS club_shield,
                       pp.scores_json, pp.stats_json, pp.profile_json
                FROM players p
                LEFT JOIN clubs c ON p.club_id = c.id
                LEFT JOIN player_profiles pp ON p.id = pp.player_id
                WHERE c.position IS NOT NULL AND c.position >= 1 AND c.position <= 20
            """
            params = []

            if query:
                clean = query.strip().lower()
                pattern = f"%{clean}%"
                sql += """
                    AND (
                        LOWER(p.name) LIKE ?
                        OR LOWER(p.nickname) LIKE ?
                        OR LOWER(p.slug) LIKE ?
                        OR LOWER(c.name) LIKE ?
                        OR LOWER(c.nickname) LIKE ?
                        OR LOWER(p.archetype) LIKE ?
                    )
                """
                params.extend([pattern, pattern, pattern, pattern, pattern, pattern])

            if position and position.lower() != "all":
                sql += " AND LOWER(p.position_name) = LOWER(?)"
                params.append(position)

            if club_slug and club_slug.lower() != "all":
                c_slug = club_slug.strip().lower()
                c_slug = {"atletico-madrid": "atletico-de-madrid", "celta-vigo": "rc-celta"}.get(c_slug, c_slug)
                sql += " AND (c.slug = ? OR LOWER(c.nickname) = LOWER(?))"
                params.extend([c_slug, c_slug])

            if min_rating > 0:
                sql += " AND p.overall_rating >= ?"
                params.append(min_rating)

            sql += " ORDER BY p.overall_rating DESC, p.id ASC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                if not item.get("availability_status"):
                    item["availability_status"] = "available"
                if item.get("scores_json"):
                    item["scores"] = json.loads(item["scores_json"])
                    del item["scores_json"]
                if item.get("stats_json"):
                    item["stats"] = json.loads(item["stats_json"])
                    del item["stats_json"]
                
                if item.get("profile_json"):
                    prof = json.loads(item["profile_json"])
                    item["no_match_data"] = prof.get("no_match_data", False)
                    if "per90" in prof:
                        item["per90"] = prof["per90"]
                    if not item.get("cutout_url") and prof.get("cutout_url"):
                        item["cutout_url"] = prof["cutout_url"]
                    if not item.get("market_value") and prof.get("market_value"):
                        item["market_value"] = prof["market_value"]
                    del item["profile_json"]
                else:
                    item["no_match_data"] = False
                    
                results.append(item)
            return results

    def get_all_clubs(self, competition: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT c.*, COUNT(p.id) AS squad_count
                FROM clubs c
                LEFT JOIN players p ON c.id = p.club_id
                WHERE c.position IS NOT NULL AND c.position >= 1 AND c.position <= 20
            """
            params = []
            if competition:
                query += " AND (c.competition = ? OR (? = 'laliga' AND c.competition IS NULL))"
                params.extend([competition, competition])
            query += """
                GROUP BY c.id
                ORDER BY c.position ASC
            """
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    
    def get_fixtures(self, matchday=None, club_slug=None, season: Optional[int] = None,
                     all_seasons: bool = False, competition: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fixture list. By default scoped to the CURRENT season; pass an
        explicit `season` for a historical one or `all_seasons=True` for the
        full mirror archive (used by the Elo engine). Supports competition filtering."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    f.id, f.matchday, f.home_score, f.away_score, f.status, f.kickoff_time, f.goals_json, f.cards_json, f.season,
                    h.id as home_id, h.name as home_name, h.nickname as home_nickname, h.shield_url as home_shield, h.slug as home_slug,
                    a.id as away_id, a.name as away_name, a.nickname as away_nickname, a.shield_url as away_shield, a.slug as away_slug
                FROM fixtures f
                JOIN clubs h ON f.home_team_id = h.id
                JOIN clubs a ON f.away_team_id = a.id
                WHERE 1=1
            '''
            params = []
            if competition:
                query += " AND (f.competition = ? OR (? = 'laliga' AND f.competition IS NULL))"
                params.extend([competition, competition])
            if not all_seasons:
                if season is None:
                    season = self.get_current_season()
                query += " AND f.season = ?"
                params.append(int(season))
            if matchday:
                query += " AND f.matchday = ?"
                params.append(matchday)
            if club_slug:
                query += " AND (h.slug = ? OR a.slug = ?)"
                params.extend([club_slug, club_slug])
                
            query += " ORDER BY f.matchday ASC, f.kickoff_time ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            res = []
            for row in rows:
                item = dict(row)
                if item.get("goals_json"):
                    try:
                        item["goals"] = json.loads(item["goals_json"])
                    except Exception:
                        item["goals"] = []
                    del item["goals_json"]
                else:
                    item["goals"] = []
                if item.get("cards_json"):
                    try:
                        item["cards"] = json.loads(item["cards_json"])
                    except Exception:
                        item["cards"] = []
                    del item["cards_json"]
                else:
                    item["cards"] = []
                res.append(item)
            return res
            
    def get_current_matchday(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            season = self.get_current_season()
            # 1. Check if there are active LIVE matches
            cursor.execute("SELECT matchday as md FROM fixtures WHERE status IN ('LIVE', 'IN_PROGRESS') AND season = ? ORDER BY kickoff_time ASC LIMIT 1", (season,))
            row = cursor.fetchone()
            if row and row['md']:
                return row['md']
            # 2. Otherwise find the matchday of the next chronologically upcoming match
            cursor.execute("SELECT matchday as md FROM fixtures WHERE status = 'SCHEDULED' AND season = ? ORDER BY kickoff_time ASC LIMIT 1", (season,))
            row = cursor.fetchone()
            if row and row['md']:
                return row['md']
            # 3. Season complete: last matchday with fixtures
            cursor.execute("SELECT MAX(matchday) FROM fixtures WHERE season = ?", (season,))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] else 38

    def get_recent_form(self, club_slug: str, n: int = 3, before_matchday: Optional[int] = None,
                        season: Optional[int] = None) -> Dict[str, Any]:
        """
        Real recent-form signal derived from actually finished league fixtures.
        Returns weighted points-per-game over the last `n` matches (most recent
        weighted highest) plus goals for/against — the base of the forecast's
        form term, replacing the old single-last-result heuristic.
        `before_matchday` prevents look-ahead leakage: when set, only fixtures
        from EARLIER matchdays count (used when previewing a specific fixture).
        """
        finished = [
            f for f in self.get_fixtures(club_slug=club_slug, season=season)
            if f["status"] == "FINISHED" and (before_matchday is None or (f.get("matchday") or 0) < before_matchday)
        ]
        # get_fixtures orders by matchday ASC, kickoff ASC; most recent last.
        recent = finished[-n:]
        if not recent:
            return {"has_data": False, "played": 0, "weighted_ppg": 0.0, "gf": 0, "ga": 0}
        weights = [0.2, 0.3, 0.5][-len(recent):]  # oldest -> newest, newest counts most
        played = len(recent)
        pts, gf, ga = 0.0, 0, 0
        for w, fx in zip(weights, recent):
            is_home = fx["home_slug"] == club_slug
            scored = (fx.get("home_score") if is_home else fx.get("away_score")) or 0
            conceded = (fx.get("away_score") if is_home else fx.get("home_score")) or 0
            gf += scored
            ga += conceded
            res = 3.0 if scored > conceded else 1.0 if scored == conceded else 0.0
            pts += w * res
        return {
            "has_data": True,
            "played": played,
            "weighted_ppg": round(pts / sum(weights), 3),
            "gf": gf,
            "ga": ga,
        }

    def get_leaders(self, metric: str = "goals", limit: int = 10) -> List[Dict[str, Any]]:
        valid_stat_metrics = [
            "goals", "assists", "shots", "shots_on_target", "minutes_played",
            "passes_total", "key_passes", "tackles_won", "clearances", "interceptions",
            "dribbles_won", "clean_sheets", "saves_total",
        ]
        valid_score_metrics = [
            "shooting", "passing", "dribbling", "pace", "defending", "physical",
        ]
        valid_metrics = valid_stat_metrics + valid_score_metrics + ["overall_rating"]
        if metric not in valid_metrics:
            metric = "goals"

        all_players = self.search_players(limit=600)

        if metric == "overall_rating":
            # Include everyone for overall rating leaderboard
            sorted_players = sorted(all_players, key=lambda x: x.get("overall_rating", 0), reverse=True)
        elif metric in valid_score_metrics:
            # Score-based (PAC/SHO/PAS/DRI/DEF/PHY) — only players with real minutes
            score_key_map = {
                "shooting": "shooting", "passing": "passing", "dribbling": "dribbling",
                "pace": "pace", "defending": "defending", "physical": "physical",
            }
            key = score_key_map[metric]
            players_with_data = [p for p in all_players
                                  if (p.get("stats") or {}).get("minutes_played", 0)]
            sorted_players = sorted(
                players_with_data,
                key=lambda x: (x.get("scores") or {}).get(key, 0),
                reverse=True
            )
        else:
            # Raw stat-based: only players who've actually played
            players_with_data = [p for p in all_players
                                  if (p.get("stats") or {}).get("minutes_played", 0)]
            sorted_players = sorted(
                players_with_data,
                key=lambda x: (x.get("stats") or {}).get(metric, 0),
                reverse=True
            )
        return sorted_players[:limit]


    def get_total_counts(self) -> Dict[str, int]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM players")
            players_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM clubs")
            clubs_count = cursor.fetchone()[0]
            return {"players": players_count, "clubs": clubs_count}

    def export_to_json(self, output_path: Optional[str] = None):
        if output_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            output_path = str(base_dir / "data" / "laliga_players.json")

        all_players = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT profile_json FROM player_profiles ORDER BY player_id ASC")
            for row in cursor.fetchall():
                if row[0]:
                    all_players.append(json.loads(row[0]))

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_players, f, indent=2, ensure_ascii=False)
        return output_path

    def upsert_club_profile(self, profile: ClubProfile):
        """Saves full club intelligence profile and updates club ratings in database."""
        c = profile.club
        stats = profile.stats
        scores = profile.scores
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Update ratings on master clubs table
            cursor.execute("""
                UPDATE clubs SET
                    att_rating = ?,
                    mid_rating = ?,
                    def_rating = ?,
                    overall_rating = ?,
                    stadium_name = COALESCE(?, stadium_name),
                    stadium_image_url = COALESCE(?, stadium_image_url),
                    president = COALESCE(?, president),
                    address = COALESCE(?, address),
                    web_url = COALESCE(?, web_url)
                WHERE id = ?
            """, (
                scores.att_rating, scores.mid_rating, scores.def_rating, scores.overall_rating,
                c.stadium_name, c.stadium_image_url, c.president, c.address, c.web_url,
                c.id
            ))

            # 2. Insert or update club_profiles
            profile_dict = profile.to_dict()
            cursor.execute("""
                INSERT INTO club_profiles (club_id, stats_json, scores_json, profile_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(club_id) DO UPDATE SET
                    stats_json=excluded.stats_json,
                    scores_json=excluded.scores_json,
                    profile_json=excluded.profile_json
            """, (
                c.id,
                json.dumps(stats.to_dict()),
                json.dumps(scores.to_dict()),
                json.dumps(profile_dict)
            ))
            conn.commit()

    def get_club_by_id_or_slug(self, identifier: Any) -> Optional[Dict[str, Any]]:
        slug_aliases = {
            "atletico-madrid": "atletico-de-madrid",
            "celta-vigo": "rc-celta",
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
                cursor.execute("SELECT * FROM clubs WHERE id = ?", (int(identifier),))
            else:
                s = str(identifier).strip().lower()
                s = slug_aliases.get(s, s)
                cursor.execute("""
                    SELECT * FROM clubs
                    WHERE (LOWER(slug) = ? OR LOWER(nickname) = ? OR LOWER(shortname) = ? OR LOWER(name) LIKE ?)
                      AND (position IS NOT NULL AND position >= 1 AND position <= 20)
                    LIMIT 1
                """, (s, s, s, f"%{s}%"))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                cursor.execute("""
                    SELECT * FROM clubs
                    WHERE LOWER(slug) = ? OR LOWER(nickname) = ? OR LOWER(shortname) = ? OR LOWER(name) LIKE ?
                    LIMIT 1
                """, (s, s, s, f"%{s}%"))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_club_profile(self, identifier: Any) -> Optional[Dict[str, Any]]:
        club_meta = self.get_club_by_id_or_slug(identifier)
        if not club_meta:
            return None

        club_id = club_meta["id"]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT profile_json FROM club_profiles WHERE club_id = ?", (club_id,))
            row = cursor.fetchone()
            if row and row[0]:
                data = json.loads(row[0])
                # Ensure latest club table values
                data["club"].update({k: club_meta[k] for k in club_meta if club_meta[k] is not None})
                enrichment = self._club_enrichment(club_meta.get("slug") or "")
                if enrichment:
                    data["live"] = enrichment
                return data

        # Fallback: construct lightweight profile dictionary from club_meta
        return {
            "club": club_meta,
            "stats": {},
            "scores": {
                "att_rating": club_meta.get("att_rating", 50),
                "mid_rating": club_meta.get("mid_rating", 50),
                "def_rating": club_meta.get("def_rating", 50),
                "overall_rating": club_meta.get("overall_rating", 50),
            },
            "archetype": "Organized Tactical Unit",
            "strengths": [],
            "weaknesses": [],
            "top_scorer": None,
            "top_assister": None,
            "defensive_leader": None,
            "star_player": None,
            "squad_breakdown": {},
            "roster": [],
        }

    def get_all_club_profiles(self) -> List[Dict[str, Any]]:
        """Returns all 20 active La Liga club profiles sorted by position or points."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cp.profile_json, c.*
                FROM clubs c
                LEFT JOIN club_profiles cp ON c.id = cp.club_id
                WHERE c.position IS NOT NULL AND c.position >= 1 AND c.position <= 20
                ORDER BY c.position ASC, c.points DESC
            """)
            profiles = []
            for row in cursor.fetchall():
                r = dict(row)
                if r.get("profile_json"):
                    item = json.loads(r["profile_json"])
                    # Sync club fields
                    for k in ["position", "played", "won", "drawn", "lost", "goals_for", "goals_against", "goal_difference", "points", "qualification", "att_rating", "mid_rating", "def_rating", "overall_rating"]:
                        if r.get(k) is not None:
                            item["club"][k] = r[k]
                    profiles.append(item)
                else:
                    # Construct basic item
                    profiles.append({
                        "club": r,
                        "scores": {
                            "att_rating": r.get("att_rating", 50),
                            "mid_rating": r.get("mid_rating", 50),
                            "def_rating": r.get("def_rating", 50),
                            "overall_rating": r.get("overall_rating", 50),
                            "possession_control": 50,
                            "attacking_potency": 50,
                            "defensive_solidity": 50,
                            "pressing_workrate": 50,
                            "physical_dominance": 50
                        },
                        "stats": {},
                        "archetype": "Organized Tactical Unit",
                        "strengths": [],
                        "weaknesses": [],
                        "squad_breakdown": {},
                        "roster": [],
                    })
            return profiles

    def get_standings(self, competition: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns official league table sorted by position with optional competition filtering."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    id, slug, name, nickname, shortname, shield_url,
                    position, played, won, drawn, lost,
                    goals_for, goals_against, goal_difference, points, qualification, formation,
                    att_rating, mid_rating, def_rating, overall_rating, competition
                FROM clubs
                WHERE position IS NOT NULL AND position >= 1 AND position <= 20
            """
            params = []
            if competition:
                query += " AND (competition = ? OR (? = 'laliga' AND competition IS NULL))"
                params.extend([competition, competition])
            query += " ORDER BY position ASC, points DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def export_clubs_to_json(self, output_path: Optional[str] = None) -> str:
        """Exports all club profiles to JSON."""
        if output_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            output_path = str(base_dir / "data" / "laliga_clubs.json")

        clubs = self.get_all_club_profiles()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(clubs, f, indent=2, ensure_ascii=False)
        return output_path

    def get_match_detail(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """
        Returns full match preview intelligence including dual-team formations,
        starting XIs with pitch coordinates, player rosters, and previous match tactical history.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    f.id, f.matchday, f.season, f.home_score, f.away_score, f.status, f.kickoff_time, f.goals_json, f.cards_json,
                    h.id as home_id, h.name as home_name, h.nickname as home_nickname, h.shield_url as home_shield, h.slug as home_slug,
                    h.stadium as home_stadium, h.stadium_name as home_stadium_name, h.position as home_position,
                    a.id as away_id, a.name as away_name, a.nickname as away_nickname, a.shield_url as away_shield, a.slug as away_slug,
                    a.position as away_position
                FROM fixtures f
                JOIN clubs h ON f.home_team_id = h.id
                JOIN clubs a ON f.away_team_id = a.id
                WHERE f.id = ?
            """, (fixture_id,))
            row = cursor.fetchone()
            if not row:
                return None
            match = dict(row)
            try:
                match["goals"] = json.loads(match["goals_json"]) if match.get("goals_json") else []
            except Exception:
                match["goals"] = []
            try:
                match["cards"] = json.loads(match["cards_json"]) if match.get("cards_json") else []
            except Exception:
                match["cards"] = []

        sim_engine = SimulationEngine(self)

        club_tactics = {
            "real-betis": {"formation": "4-2-3-1", "manager": "Manuel Pellegrini", "style": "Fluid Positional Possession"},
            "leganes": {"formation": "4-2-3-1", "manager": "Borja Jiménez", "style": "Compact Low-Block & Fast Counters"},
            "fc-barcelona": {"formation": "4-2-3-1", "manager": "Hansi Flick", "style": "High-Intensity Press & Vertical Transitions"},
            "real-madrid": {"formation": "4-3-3", "manager": "Carlo Ancelotti", "style": "Dynamic Free-Flowing Attacking Trio"},
            "atletico-madrid": {"formation": "5-3-2", "manager": "Diego Simeone", "style": "Aggressive Pragmatic Midfield Press"},
            "atletico-de-madrid": {"formation": "5-3-2", "manager": "Diego Simeone", "style": "Aggressive Pragmatic Midfield Press"},
            "athletic-club": {"formation": "4-2-3-1", "manager": "Ernesto Valverde", "style": "High-Tempo Wing Overloads"},
            "girona": {"formation": "4-3-3", "manager": "Míchel", "style": "Fluid Positional Play & Inverted Fullbacks"},
            "real-sociedad": {"formation": "4-3-3", "manager": "Imanol Alguacil", "style": "Technical Circulation & High Press"},
            "villarreal-cf": {"formation": "4-4-2", "manager": "Marcelino", "style": "Direct Two-Striker Vertical Transitions"},
            "sevilla-fc": {"formation": "4-3-3", "manager": "García Pimienta", "style": "Ball Dominance & Wide Wing Play"},
            "rc-celta": {"formation": "3-4-3", "manager": "Claudio Giráldez", "style": "Adventurous 3-at-the-back Direct Play"},
            "celta-vigo": {"formation": "3-4-3", "manager": "Claudio Giráldez", "style": "Adventurous 3-at-the-back Direct Play"},
            "mallorca": {"formation": "4-2-3-1", "manager": "Jagoba Arrasate", "style": "Aerial Strength & Target Man Play"},
            "d-alaves": {"formation": "4-2-3-1", "manager": "Luis García Plaza", "style": "Physical High-Workrate Press"},
            "rayo-vallecano": {"formation": "4-2-3-1", "manager": "Iñigo Pérez", "style": "Relentless Gegenpressing"},
            "getafe-cf": {"formation": "4-2-3-1", "manager": "José Bordalás", "style": "Tenacious Defensive Combativeness"},
            "las-palmas": {"formation": "4-3-3", "manager": "Luis Carrión", "style": "Short-Passing Tiki-Taka Build-Up"},
            "rcd-espanyol": {"formation": "4-4-2", "manager": "Manolo González", "style": "Resilient Mid-Block & Direct Counters"},
            "valladolid": {"formation": "4-3-3", "manager": "Paulo Pezzolano", "style": "Direct Flank Crosses & Pace"},
            "valencia-cf": {"formation": "4-4-2", "manager": "Rubén Baraja", "style": "Youthful Energy & Compact Defending"},
            "c-a-osasuna": {"formation": "4-3-3", "manager": "Vicente Moreno", "style": "Stamina-Driven Flank Pressing"},
            "rc-deportivo": {"formation": "4-2-3-1", "manager": "Imanol Idiakez", "style": "Attacking Transition & High Intensity"},
            "r-racing-club": {"formation": "4-2-3-1", "manager": "José Alberto López", "style": "Fast Direct Flank Counters"},
            "malaga-cf": {"formation": "4-4-2", "manager": "Sergio Pellicer", "style": "Compact Low-Block & Resilient Defending"},
            "levante-ud": {"formation": "4-3-3", "manager": "Julián Calero", "style": "Vertical Counter-Pressing"},
            "elche-c-f": {"formation": "4-3-3", "manager": "Eder Sarabia", "style": "Possession Control & Positional Play"}
        }

        formation_slots = {
            "4-2-3-1": [
                {"slot": "GK", "pos": "Goalkeeper", "x": 50, "y": 88},
                {"slot": "LB", "pos": "Defender", "x": 15, "y": 70},
                {"slot": "LCB", "pos": "Defender", "x": 38, "y": 74},
                {"slot": "RCB", "pos": "Defender", "x": 62, "y": 74},
                {"slot": "RB", "pos": "Defender", "x": 85, "y": 70},
                {"slot": "LDM", "pos": "Midfielder", "x": 36, "y": 54},
                {"slot": "RDM", "pos": "Midfielder", "x": 64, "y": 54},
                {"slot": "LAM", "pos": "Forward", "x": 18, "y": 34},
                {"slot": "CAM", "pos": "Midfielder", "x": 50, "y": 32},
                {"slot": "RAM", "pos": "Forward", "x": 82, "y": 34},
                {"slot": "ST", "pos": "Forward", "x": 50, "y": 14}
            ],
            "4-3-3": [
                {"slot": "GK", "pos": "Goalkeeper", "x": 50, "y": 88},
                {"slot": "LB", "pos": "Defender", "x": 15, "y": 70},
                {"slot": "LCB", "pos": "Defender", "x": 38, "y": 74},
                {"slot": "RCB", "pos": "Defender", "x": 62, "y": 74},
                {"slot": "RB", "pos": "Defender", "x": 85, "y": 70},
                {"slot": "LCM", "pos": "Midfielder", "x": 28, "y": 50},
                {"slot": "CDM", "pos": "Midfielder", "x": 50, "y": 56},
                {"slot": "RCM", "pos": "Midfielder", "x": 72, "y": 50},
                {"slot": "LW", "pos": "Forward", "x": 20, "y": 26},
                {"slot": "ST", "pos": "Forward", "x": 50, "y": 16},
                {"slot": "RW", "pos": "Forward", "x": 80, "y": 26}
            ],
            "4-4-2": [
                {"slot": "GK", "pos": "Goalkeeper", "x": 50, "y": 88},
                {"slot": "LB", "pos": "Defender", "x": 15, "y": 70},
                {"slot": "LCB", "pos": "Defender", "x": 38, "y": 74},
                {"slot": "RCB", "pos": "Defender", "x": 62, "y": 74},
                {"slot": "RB", "pos": "Defender", "x": 85, "y": 70},
                {"slot": "LM", "pos": "Midfielder", "x": 16, "y": 48},
                {"slot": "LCM", "pos": "Midfielder", "x": 38, "y": 50},
                {"slot": "RCM", "pos": "Midfielder", "x": 62, "y": 50},
                {"slot": "RM", "pos": "Midfielder", "x": 84, "y": 48},
                {"slot": "LST", "pos": "Forward", "x": 36, "y": 18},
                {"slot": "RST", "pos": "Forward", "x": 64, "y": 18}
            ],
            "5-3-2": [
                {"slot": "GK", "pos": "Goalkeeper", "x": 50, "y": 88},
                {"slot": "LWB", "pos": "Defender", "x": 12, "y": 62},
                {"slot": "LCB", "pos": "Defender", "x": 30, "y": 75},
                {"slot": "CB", "pos": "Defender", "x": 50, "y": 77},
                {"slot": "RCB", "pos": "Defender", "x": 70, "y": 75},
                {"slot": "RWB", "pos": "Defender", "x": 88, "y": 62},
                {"slot": "LCM", "pos": "Midfielder", "x": 32, "y": 46},
                {"slot": "CM", "pos": "Midfielder", "x": 50, "y": 48},
                {"slot": "RCM", "pos": "Midfielder", "x": 68, "y": 46},
                {"slot": "LST", "pos": "Forward", "x": 38, "y": 18},
                {"slot": "RST", "pos": "Forward", "x": 62, "y": 18}
            ],
            "3-4-3": [
                {"slot": "GK", "pos": "Goalkeeper", "x": 50, "y": 88},
                {"slot": "LCB", "pos": "Defender", "x": 26, "y": 75},
                {"slot": "CB", "pos": "Defender", "x": 50, "y": 77},
                {"slot": "RCB", "pos": "Defender", "x": 74, "y": 75},
                {"slot": "LWB", "pos": "Midfielder", "x": 12, "y": 52},
                {"slot": "LCM", "pos": "Midfielder", "x": 38, "y": 52},
                {"slot": "RCM", "pos": "Midfielder", "x": 62, "y": 52},
                {"slot": "RWB", "pos": "Midfielder", "x": 88, "y": 52},
                {"slot": "LW", "pos": "Forward", "x": 22, "y": 24},
                {"slot": "ST", "pos": "Forward", "x": 50, "y": 16},
                {"slot": "RW", "pos": "Forward", "x": 78, "y": 24}
            ],
            "3-5-2": [
                {"slot": "GK", "pos": "Goalkeeper", "x": 50, "y": 88},
                {"slot": "LCB", "pos": "Defender", "x": 26, "y": 75},
                {"slot": "CB", "pos": "Defender", "x": 50, "y": 77},
                {"slot": "RCB", "pos": "Defender", "x": 74, "y": 75},
                {"slot": "LWB", "pos": "Midfielder", "x": 12, "y": 54},
                {"slot": "LCM", "pos": "Midfielder", "x": 34, "y": 52},
                {"slot": "CM", "pos": "Midfielder", "x": 50, "y": 50},
                {"slot": "RCM", "pos": "Midfielder", "x": 66, "y": 52},
                {"slot": "RWB", "pos": "Midfielder", "x": 88, "y": 54},
                {"slot": "LST", "pos": "Forward", "x": 38, "y": 18},
                {"slot": "RST", "pos": "Forward", "x": 62, "y": 18}
            ],
            "3-4-2-1": [
                {"slot": "GK", "pos": "Goalkeeper", "x": 50, "y": 88},
                {"slot": "LCB", "pos": "Defender", "x": 26, "y": 75},
                {"slot": "CB", "pos": "Defender", "x": 50, "y": 77},
                {"slot": "RCB", "pos": "Defender", "x": 74, "y": 75},
                {"slot": "LWB", "pos": "Midfielder", "x": 12, "y": 54},
                {"slot": "LCM", "pos": "Midfielder", "x": 38, "y": 54},
                {"slot": "RCM", "pos": "Midfielder", "x": 62, "y": 54},
                {"slot": "RWB", "pos": "Midfielder", "x": 88, "y": 54},
                {"slot": "LAM", "pos": "Forward", "x": 32, "y": 28},
                {"slot": "RAM", "pos": "Forward", "x": 68, "y": 28},
                {"slot": "ST", "pos": "Forward", "x": 50, "y": 14}
            ]
        }

        def build_lineup(club_slug, club_name):
            if club_slug in club_tactics:
                t_info = club_tactics[club_slug]
            else:
                try:
                    from .club_tactics import ClubTacticsRegistry
                    prof = ClubTacticsRegistry.get_profile(club_slug)
                    t_info = {
                        "formation": prof.get("formation", "4-2-3-1"),
                        "manager": prof.get("manager", "Head Coach"),
                        "style": prof.get("tactical_identity", "Organized Balanced Unit"),
                    }
                except Exception:
                    t_info = {"formation": "4-2-3-1", "manager": "Head Coach", "style": "Organized Balanced Unit"}
            form_name = t_info["formation"]
            slots = formation_slots.get(form_name, formation_slots["4-2-3-1"])

            # Real per-match momentum data for this squad (one query per club).
            from .momentum import rows_for_club, compute_momentum
            club_rows = rows_for_club(self, club_slug)

            def momentum_for(p):
                try:
                    return compute_momentum(self, p, club_slug, club_rows=club_rows)
                except Exception:
                    from .momentum import PlayerMomentum
                    return PlayerMomentum()

            all_club_players = self.search_players(club_slug=club_slug, limit=50)
            unavailable_map = self.get_unavailable_players_for_fixture(
                club_slug=club_slug,
                matchday=match.get("matchday"),
                season=match.get("season"),
            )

            available_players = []
            missing_list = []
            for p in all_club_players:
                pid = p["id"]
                unavail_info = unavailable_map.get(pid)
                if unavail_info:
                    missing_list.append({
                        "id": pid,
                        "name": p.get("name") or p.get("nickname"),
                        "nickname": p.get("nickname") or p.get("name"),
                        "shirt_number": p.get("shirt_number") or 99,
                        "position": p.get("position_name"),
                        "overall_rating": p.get("overall_rating", 75),
                        "availability_status": unavail_info["status"],
                        "availability_reason": unavail_info["reason"],
                        "status_icon": unavail_info["icon"],
                        "slug": p.get("slug"),
                    })
                else:
                    available_players.append(p)

            gks = [p for p in available_players if "goalkeeper" in (p.get("position_name") or "").lower()]
            defs = [p for p in available_players if "defender" in (p.get("position_name") or "").lower()]
            mids = [p for p in available_players if "midfielder" in (p.get("position_name") or "").lower()]
            fwds = [p for p in available_players if "forward" in (p.get("position_name") or "").lower()]

            gks.sort(key=lambda x: x.get("overall_rating", 50), reverse=True)
            defs.sort(key=lambda x: x.get("overall_rating", 50), reverse=True)
            mids.sort(key=lambda x: x.get("overall_rating", 50), reverse=True)
            fwds.sort(key=lambda x: x.get("overall_rating", 50), reverse=True)

            used_ids = set()
            starters = []

            sim_engine = SimulationEngine()
            club_finished = [fx for fx in self.get_fixtures(club_slug=club_slug) if fx["status"] == "FINISHED"]
            recent_3 = club_finished[-3:] if club_finished else []

            gk_idx = def_idx = mid_idx = fwd_idx = 0
            for s in slots:
                req = s["pos"]
                p = None
                if req == "Goalkeeper" and gk_idx < len(gks):
                    p = gks[gk_idx]; gk_idx += 1
                elif req == "Defender" and def_idx < len(defs):
                    p = defs[def_idx]; def_idx += 1
                elif req == "Midfielder" and mid_idx < len(mids):
                    p = mids[mid_idx]; mid_idx += 1
                elif req == "Forward" and fwd_idx < len(fwds):
                    p = fwds[fwd_idx]; fwd_idx += 1
                
                if not p:
                    for rem in available_players:
                        if rem["id"] not in used_ids:
                            p = rem
                            break
                
                if p:
                    used_ids.add(p["id"])
                    p_form = sim_engine.calculate_player_form(p, club_slug, recent_3)
                    p_mom = momentum_for(p)
                    base_ovr = p.get("overall_rating", 75)
                    eff_ovr = base_ovr + p_form["form_modifier"]
                    starters.append({
                        "id": p["id"],
                        "name": p.get("name") or p.get("nickname"),
                        "nickname": p.get("nickname") or p.get("name"),
                        "shirt_number": p.get("shirt_number") or 99,
                        "position": p.get("position_name"),
                        "slot": s["slot"],
                        "x": s["x"],
                        "y": s["y"],
                        "overall_rating": base_ovr,
                        "effective_rating": eff_ovr,
                        "form_modifier": p_form["form_modifier"],
                        "form_status": p_form["form_status"],
                        "streak_label": p_form["streak_label"],
                        "streak_icon": p_form["streak_icon"],
                        "momentum": p_mom.to_dict(),
                        "archetype": p.get("archetype", "Tactical Player"),
                        "photo_url": p.get("photo_url") or p.get("cutout_url"),
                        "slug": p.get("slug"),
                        "availability_status": "available",
                    })

            bench = [p for p in available_players if p["id"] not in used_ids]
            bench_list = []
            for p in bench:
                p_form = sim_engine.calculate_player_form(p, club_slug, recent_3)
                p_mom = momentum_for(p)
                base_ovr = p.get("overall_rating", 75)
                bench_list.append({
                    "id": p["id"],
                    "name": p.get("name") or p.get("nickname"),
                    "shirt_number": p.get("shirt_number") or 99,
                    "position": p.get("position_name"),
                    "overall_rating": base_ovr,
                    "effective_rating": base_ovr + p_form["form_modifier"],
                    "form_modifier": p_form["form_modifier"],
                    "form_status": p_form["form_status"],
                    "streak_label": p_form["streak_label"],
                    "streak_icon": p_form["streak_icon"],
                    "archetype": p.get("archetype", "Squad Player"),
                    "photo_url": p.get("photo_url") or p.get("cutout_url"),
                    "slug": p.get("slug"),
                    "availability_status": "available",
                })

            return {
                "formation": form_name,
                "manager": t_info["manager"],
                "style": t_info["style"],
                "starting_xi": starters,
                "bench": bench_list,
                "missing_players": missing_list,
                "squad_total": len(all_club_players),
                "all_players": all_club_players
            }

        def get_last_match_intelligence(club_slug, current_md):
            all_club_fx = self.get_fixtures(club_slug=club_slug)
            finished = [f for f in all_club_fx if f["status"] == "FINISHED" and f["matchday"] < current_md]
            if not finished:
                finished = [f for f in all_club_fx if f["status"] == "FINISHED"]
            
            if not finished:
                return None
                
            last_fx = finished[-1]
            is_home = last_fx["home_slug"] == club_slug
            opp_name = last_fx["away_name"] if is_home else last_fx["home_name"]
            opp_shield = last_fx["away_shield"] if is_home else last_fx["home_shield"]
            team_score = last_fx["home_score"] if is_home else last_fx["away_score"]
            opp_score = last_fx["away_score"] if is_home else last_fx["home_score"]
            
            if team_score > opp_score:
                result = "WIN"
                res_badge = "W"
            elif team_score < opp_score:
                result = "LOSS"
                res_badge = "L"
            else:
                result = "DRAW"
                res_badge = "D"

            tactics = club_tactics.get(club_slug, {"formation": "4-2-3-1", "manager": "Head Coach", "style": "Tactical"})
            
            recap_notes = f"Fielded a {tactics['formation']} setup under {tactics['manager']} against {opp_name} in Matchday {last_fx['matchday']}."
            if result == "WIN":
                recap_notes += f" Controlled attacking momentum with clinical execution, securing a {team_score}-{opp_score} victory."
            elif result == "LOSS":
                recap_notes += f" Suffered a {team_score}-{opp_score} defeat after intense end-to-end pressure."
            else:
                recap_notes += f" Fought to a disciplined {team_score}-{opp_score} stalemate."

            return {
                "matchday": last_fx["matchday"],
                "opponent_name": opp_name,
                "opponent_shield": opp_shield,
                "venue": "Home" if is_home else "Away",
                "score": f"{team_score} - {opp_score}",
                "result": result,
                "res_badge": res_badge,
                "formation_used": tactics["formation"],
                "manager": tactics["manager"],
                "recap_notes": recap_notes
            }

        home_lineup = build_lineup(match["home_slug"], match["home_name"])
        away_lineup = build_lineup(match["away_slug"], match["away_name"])
        home_last = get_last_match_intelligence(match["home_slug"], match["matchday"])
        away_last = get_last_match_intelligence(match["away_slug"], match["matchday"])

        # Head to head recent records
        all_h2h = [
            f for f in self.get_fixtures()
            if (f["home_slug"] == match["home_slug"] and f["away_slug"] == match["away_slug"]) or
               (f["home_slug"] == match["away_slug"] and f["away_slug"] == match["home_slug"])
        ]

        home_fatigue = sim_engine.calculate_match_fatigue(match["home_slug"], match.get("kickoff_time"))
        away_fatigue = sim_engine.calculate_match_fatigue(match["away_slug"], match.get("kickoff_time"))

        home_team_data = {
            "id": match["home_id"],
            "name": match["home_name"],
            "nickname": match["home_nickname"],
            "slug": match["home_slug"],
            "shield": match["home_shield"],
            "shield_url": match["home_shield"],
            "stadium": match.get("home_stadium_name") or match.get("home_stadium") or "Estadio Benito Villamarín",
            "position": match.get("home_position") or 10,
            "tactics": home_lineup,
            "recent_form": self.get_recent_form(match["home_slug"], before_matchday=match.get("matchday")),
            "last_match": home_last,
            "fatigue": home_fatigue
        }
        away_team_data = {
            "id": match["away_id"],
            "name": match["away_name"],
            "nickname": match["away_nickname"],
            "slug": match["away_slug"],
            "shield": match["away_shield"],
            "shield_url": match["away_shield"],
            "position": match.get("away_position") or 12,
            "tactics": away_lineup,
            "recent_form": self.get_recent_form(match["away_slug"], before_matchday=match.get("matchday")),
            "last_match": away_last,
            "fatigue": away_fatigue
        }

        radar_data = sim_engine.calculate_tactical_radar(home_team_data, away_team_data)

        res_dict = {
            "fixture": match,
            "home_team": home_team_data,
            "away_team": away_team_data,
            "head_to_head": all_h2h,
            "tactical_radar": radar_data
        }

        return res_dict

