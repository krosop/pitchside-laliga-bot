"""
Tests for UEFA Champions League (uefa.champions) Integration
============================================================
Verifies:
  * 36 authentic European club profiles seeded into SQLite
  * Elo calibration for European giants in club_ratings
  * Standings parsing and qualification zones (1-8 direct R16, 9-24 play-offs, 25-36 out)
  * Fixtures ingestion across 8 league phase matchdays
  * Database query bounds (max position 36)
  * Strict competition isolation (no contamination between La Liga, Serie A, and UCL)
"""

import os
import sqlite3
import pytest
from src.database import Database
from src.champions_league import (
    CHAMPIONS_LEAGUE_CLUBS,
    ESPN_UCL_ALIAS,
    seed_champions_league_clubs,
    sync_champions_league_standings,
    sync_champions_league_fixtures,
    _resolve_ucl_slug,
)


@pytest.fixture
def db():
    database = Database()
    seed_champions_league_clubs(database)
    return database


def test_ucl_club_profiles_count(db):
    """Verifies that all 36 UCL clubs are defined and have valid metadata."""
    assert len(CHAMPIONS_LEAGUE_CLUBS) == 36
    for c in CHAMPIONS_LEAGUE_CLUBS:
        assert c["id"] >= 301 and c["id"] <= 336
        assert c["slug"].startswith("ucl-")
        assert len(c["shortname"]) >= 2
        assert c["overall_rating"] >= 65 and c["overall_rating"] <= 95
        assert c["elo"] >= 1400.0 and c["elo"] <= 1900.0
        assert str(c["espn_id"]).isdigit()


def test_ucl_slug_resolution():
    """Verifies that ESPN IDs and various team names resolve to canonical UCL slugs."""
    assert _resolve_ucl_slug({"id": "160", "displayName": "Paris Saint-Germain"}) == "ucl-psg"
    assert _resolve_ucl_slug({"id": "83", "displayName": "Barcelona"}) == "ucl-barcelona"
    assert _resolve_ucl_slug({"id": "364", "displayName": "Liverpool"}) == "ucl-liverpool"
    assert _resolve_ucl_slug({"id": "86", "displayName": "Real Madrid"}) == "ucl-real-madrid"
    assert _resolve_ucl_slug({"id": "132", "displayName": "Bayern Munich"}) == "ucl-bayern-munich"
    assert _resolve_ucl_slug({"id": "382", "displayName": "Manchester City"}) == "ucl-manchester-city"
    assert _resolve_ucl_slug({"id": "110", "displayName": "Internazionale"}) == "ucl-inter"


def test_seed_champions_league_clubs(db):
    """Verifies that seed_champions_league_clubs creates exactly 36 records in clubs and club_ratings."""
    seeded = seed_champions_league_clubs(db)
    assert seeded == 36

    with db.get_connection() as conn:
        cursor = conn.cursor()
        ucl_clubs = cursor.execute("SELECT count(*) FROM clubs WHERE competition='champions_league'").fetchone()[0]
        assert ucl_clubs == 36

        ucl_ratings = cursor.execute(
            "SELECT count(*) FROM club_ratings cr JOIN clubs c ON cr.club_id=c.id WHERE c.competition='champions_league'"
        ).fetchone()[0]
        assert ucl_ratings == 36


def test_get_standings_ucl_bounds(db):
    """Verifies that Database.get_standings returns all 36 clubs for champions_league."""
    sync_champions_league_standings(db)
    st = db.get_standings(competition="champions_league")
    assert len(st) == 36

    # Verify order is monotonic 1 to 36
    positions = [c["position"] for c in st]
    assert positions == list(range(1, 37))

    # Verify qualification tags
    top_8 = st[:8]
    for c in top_8:
        assert "Direct Round of 16" in c["qualification"]

    playoffs = st[8:24]
    for c in playoffs:
        assert "Knockout Play-offs" in c["qualification"]

    eliminated = st[24:]
    for c in eliminated:
        assert "Eliminated" in c["qualification"]


def test_competition_isolation(db):
    """Verifies that UCL standings and clubs do not leak into domestic leagues."""
    laliga_st = db.get_standings(competition="laliga")
    seriea_st = db.get_standings(competition="serie_a")
    ucl_st = db.get_standings(competition="champions_league")

    assert len(laliga_st) == 20
    assert len(seriea_st) == 20
    assert len(ucl_st) == 36

    laliga_slugs = {c["slug"] for c in laliga_st}
    seriea_slugs = {c["slug"] for c in seriea_st}
    ucl_slugs = {c["slug"] for c in ucl_st}

    # All UCL slugs start with ucl-
    for s in ucl_slugs:
        assert s.startswith("ucl-")

    # No domestic club has a ucl- slug
    for s in laliga_slugs:
        assert not s.startswith("ucl-")
    for s in seriea_slugs:
        assert not s.startswith("ucl-")


def test_sync_champions_league_fixtures(db):
    """Verifies ingestion of official UCL fixtures and matchday sequencing."""
    res = sync_champions_league_fixtures(db, months=["202610"])
    assert res["total_events"] >= 36

    fixtures = db.get_fixtures(competition="champions_league")
    assert len(fixtures) >= 36

    for f in fixtures:
        assert f["competition"] == "champions_league"
        assert f["home_id"] >= 301 and f["home_id"] <= 336
        assert f["away_id"] >= 301 and f["away_id"] <= 336
        assert f["kickoff_time"] is not None
        assert f["status"] in ("FINISHED", "LIVE", "SCHEDULED")
