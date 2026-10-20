"""Forecast + ratings engine tests — real DB reads, no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import Database
from src.simulation_engine import SimulationEngine
from src.ratings import RatingsEngine

db = Database()
engine = SimulationEngine(db)


def _any_fixture_with_two_clubs():
    fx = db.get_fixtures()  # current season
    for f in fx:
        if f.get("home_slug") and f.get("away_slug"):
            return f
    return None


def test_ratings_present_and_sane():
    rows = RatingsEngine(db).recompute_all() if False else None
    conn = db.get_connection()
    rated = conn.execute(
        "SELECT c.slug, r.elo, r.difficulty, r.matches_counted FROM club_ratings r "
        "JOIN clubs c ON c.id=r.club_id WHERE r.matches_counted > 50"
    ).fetchall()
    conn.close()
    assert len(rated) >= 20, "expected the 20 active clubs to be rated from real results"
    elos = [r["elo"] for r in rated]
    assert min(elos) > 1150 and max(elos) < 2000, "Elo should stay in a plausible band"
    # best Elo should carry the top difficulty tier
    best = max(rated, key=lambda r: r["elo"])
    assert best["difficulty"] >= 4.5


def test_get_or_none_shape():
    r = RatingsEngine.get_or_none(db, "real-madrid")
    if r:  # rated clubs must expose the full contract
        assert {"elo", "difficulty", "rank", "matches_counted"} <= set(r.keys())


def test_forecast_deterministic_and_complete():
    fx = _any_fixture_with_two_clubs()
    if not fx:
        return  # no fixtures in DB — nothing to assert
    detail = db.get_match_detail(fx["id"])
    a = engine.monte_carlo_forecast(detail)
    b = engine.monte_carlo_forecast(detail)
    keys = ("home_win_pct", "draw_pct", "away_win_pct")
    for k in keys:
        assert a[k] == b[k], f"forecast must be deterministic ({k})"
        assert 0 <= a[k] <= 100
    total = sum(a[k] for k in keys)
    assert abs(total - 100.0) < 1.5, f"1X2 must sum to ~100% (got {total})"


def test_dixon_coles_matrix_is_distribution():
    m = engine.calculate_dixon_coles_matrix(1.4, 1.1)
    total = sum(m.values())
    assert abs(total - 1.0) < 0.01
    assert all(v >= 0 for v in m.values())


def test_stronger_team_gets_higher_strength():
    strong = {"slug": "real-madrid", "tactics": {"starting_xi": [
        {"effective_rating": 88 + i} for i in range(11)
    ]}}
    weak = {"slug": "d-alaves", "tactics": {"starting_xi": [
        {"effective_rating": 62 + i} for i in range(11)
    ]}}
    s = engine._team_strength_inputs(strong, None)
    w = engine._team_strength_inputs(weak, None)
    assert s["avg_ovr"] > w["avg_ovr"]


def test_player_form_bounds():
    fx = _any_fixture_with_two_clubs()
    player = {"overall_rating": 75}
    slug = (fx or {}).get("home_slug")
    if not slug:
        return
    recent = [f for f in db.get_fixtures(club_slug=slug) if f["status"] == "FINISHED"][-3:]
    form = engine.calculate_player_form(player, slug, recent)
    assert -10 <= form["form_modifier"] <= 10
    assert form["form_status"] in ("hot", "in_form", "stable", "cold")
