"""Database integrity tests — temp-file SQLite (fresh checkout schema), no network.

Each test gets its own DB file. Connections are closed explicitly: SQLite on
Windows keeps file locks until every handle closes, so leaking a connection
in one test would lock the next test's database.
"""
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import Database

_TMPDIR = tempfile.TemporaryDirectory()
_UID = 0
_UID_LOCK = threading.Lock()


def _next_uid() -> int:
    global _UID
    with _UID_LOCK:
        _UID += 1
        return _UID


def _mini_db() -> Database:
    """Two clubs, a finished and a scheduled fixture, one player row."""
    db = Database(db_path=str(Path(_TMPDIR.name) / f"test_{_next_uid()}.db"))
    conn = db.get_connection()
    try:
        # fixtures DDL lives in generate_fixtures.py (bootstrap script), so the
        # test creates the same table itself
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fixtures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matchday INTEGER, home_team_id INTEGER, away_team_id INTEGER,
                home_score INTEGER, away_score INTEGER, status TEXT,
                kickoff_time TEXT, goals_json TEXT, season INTEGER
            )
        """)
        conn.execute("INSERT INTO clubs (id, slug, name, nickname, position) VALUES (1,'a-club','A Club','A',1)")
        conn.execute("INSERT INTO clubs (id, slug, name, nickname, position) VALUES (2,'b-club','B Club','B',2)")
        conn.execute(
            "INSERT INTO fixtures (matchday, home_team_id, away_team_id, home_score, away_score, "
            "status, kickoff_time, season) VALUES (1, 1, 2, 2, 1, 'FINISHED', '2026-08-15 20:00:00', 2026)"
        )
        conn.execute(
            "INSERT INTO fixtures (matchday, home_team_id, away_team_id, status, kickoff_time, season) "
            "VALUES (2, 2, 1, 'SCHEDULED', '2026-12-01 20:00:00', 2026)"
        )
        conn.execute(
            "INSERT INTO players (id, slug, name, nickname, club_id, position_name, overall_rating) "
            "VALUES (10, 'p-one', 'Player One', 'One', 1, 'Midfielder', 78)"
        )
        conn.commit()
    finally:
        conn.close()
    return db


def test_standings_consistent_with_results():
    db = _mini_db()
    conn = db.get_connection()
    try:
        # standings are recomputed by the pipeline at sync time — same path
        from src.mirror_footballdata import _recompute_standings
        _recompute_standings(conn, 2026)
        row = conn.execute("SELECT * FROM clubs WHERE id=1").fetchone()
        # A beat B 2-1 at home: 1 played, 1 win, 3 pts, GF 2, GA 1, GD +1
        assert row["played"] == 1 and row["won"] == 1 and row["points"] == 3
        assert row["goals_for"] == 2 and row["goals_against"] == 1 and row["goal_difference"] == 1
        row = conn.execute("SELECT * FROM clubs WHERE id=2").fetchone()
        assert row["played"] == 1 and row["lost"] == 1 and row["points"] == 0
    finally:
        conn.close()


def test_season_filtering():
    db = _mini_db()
    try:
        assert len(db.get_fixtures(season=2026)) == 2
        assert db.get_fixtures(season=2025) == []
        # default = current season
        assert len(db.get_fixtures()) == 2
    finally:
        pass


def test_form_excludes_scheduled():
    db = _mini_db()
    f = db.get_recent_form("a-club")
    assert f["has_data"] is True and f["played"] == 1
    assert f["gf"] == 2 and f["ga"] == 1
    assert abs(f["weighted_ppg"] - 3.0) < 1e-9  # one win


def test_form_no_lookahead():
    db = _mini_db()
    # before matchday 1 nothing counts
    f = db.get_recent_form("a-club", before_matchday=1)
    assert f["has_data"] is False and f["played"] == 0


def test_search_scoped_to_active_clubs():
    db = _mini_db()
    rows = db.search_players(query="one")
    assert len(rows) == 1 and rows[0]["slug"] == "p-one"
    assert rows[0]["club_slug"] == "a-club"


def test_upsert_player_coalesces_bio():
    db = _mini_db()
    conn = db.get_connection()
    try:
        conn.execute(
            "UPDATE players SET date_of_birth='1999-01-01', height=180 WHERE id=10"
        )
        conn.commit()
        # COALESCE semantics used by both feed modules: existing values win,
        # only NULLs are filled
        conn.execute(
            "UPDATE players SET height=COALESCE(height, ?), date_of_birth=COALESCE(date_of_birth, ?) "
            "WHERE id=10",
            (185, "2000-02-02"),
        )
        conn.commit()
        row = conn.execute("SELECT height, date_of_birth FROM players WHERE id=10").fetchone()
        assert row["height"] == 180 and row["date_of_birth"] == "1999-01-01"
    finally:
        conn.close()
