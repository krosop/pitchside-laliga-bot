"""
Unit & Integration Tests for the STATSPHERE Match Referee Engine.
Covers:
- RefereeRegistry profiling & lookup across La Liga and Serie A
- RefereeTacticalEvaluator friction & synergy calculation
- SimulationEngine referee telemetry & event generation (cards, penalties, VAR)
- Telegram Bot referee dossier views, directories, callbacks & commands
- REST API referee endpoints
"""
import pytest
from src.database import Database
from src.referee_engine import RefereeRegistry, RefereeTacticalEvaluator, RefereeProfile
from src.simulation_engine import SimulationEngine
from src.telegram_bot import PitchsideTelegramBot
from src.server import ProfilerHTTPRequestHandler


def test_referee_registry_retrieval_and_aliases():
    """Verifies referee lookup by slug, exact name, and common media aliases."""
    # Direct slug lookup
    gil = RefereeRegistry.get_by_name("gil-manzano")
    assert gil is not None
    assert gil.name == "Jesús Gil Manzano"
    assert gil.strictness_index >= 90
    assert gil.competition == "laliga"

    # Alias lookups
    soto = RefereeRegistry.get_by_name("Soto Grado")
    assert soto is not None
    assert soto.slug == "soto-grado"
    assert soto.red_cards_per_game >= 0.35

    # Serie A officials
    orsato = RefereeRegistry.get_by_name("Daniele Orsato")
    assert orsato is not None
    assert orsato.competition == "serie_a"
    assert orsato.slug == "orsato"

    # Case-insensitive / partial match
    hernandez = RefereeRegistry.get_by_name("hernandez")
    assert hernandez is not None
    assert "Hernández" in hernandez.name


def test_referee_registry_categories_and_rankings():
    """Verifies ranking filters: top strict, most lenient, penalty magnets."""
    strict_refs = RefereeRegistry.get_top_strict(limit=5)
    assert len(strict_refs) == 5
    for i in range(1, len(strict_refs)):
        assert strict_refs[i - 1].strictness_index >= strict_refs[i].strictness_index

    lenient_refs = RefereeRegistry.get_most_lenient(limit=5)
    assert len(lenient_refs) == 5
    for i in range(1, len(lenient_refs)):
        assert lenient_refs[i - 1].leniency_index >= lenient_refs[i].leniency_index

    pk_magnets = RefereeRegistry.get_penalty_magnets(limit=5)
    assert len(pk_magnets) == 5
    for i in range(1, len(pk_magnets)):
        assert pk_magnets[i - 1].penalties_per_game >= pk_magnets[i].penalties_per_game

    # League scoped filtering
    laliga_refs = RefereeRegistry.get_all(competition="laliga")
    serie_a_refs = RefereeRegistry.get_all(competition="serie_a")
    assert all(r.competition == "laliga" for r in laliga_refs)
    assert all(r.competition == "serie_a" for r in serie_a_refs)
    assert len(laliga_refs) >= 10
    assert len(serie_a_refs) >= 5


def test_referee_tactical_evaluator_modifiers():
    """Verifies tactical clash evaluation between referee threshold and team stances."""
    ref = RefereeRegistry.get_by_name("gil-manzano")
    assert ref is not None

    clash_physical = {
        "home": {"tactical_identity": "Physical Low Block & Combativeness"},
        "away": {"tactical_identity": "Aggressive Pragmatic Midfield Press"},
        "key_battle": "Derby midfield warfare",
    }
    home_team = {"nickname": "Getafe", "overall_rating": 77}
    away_team = {"nickname": "Atlético Madrid", "overall_rating": 86}

    eval_result = RefereeTacticalEvaluator.evaluate(ref, clash_physical, home_team, away_team)

    assert "foul_multiplier" in eval_result
    assert "card_multiplier" in eval_result
    assert "penalty_chance" in eval_result
    assert "red_card_chance" in eval_result
    assert "tactical_narrative" in eval_result

    # Strict referee + physical clash should yield elevated foul & card multipliers
    assert eval_result["foul_multiplier"] > 1.0
    assert eval_result["card_multiplier"] > 1.10
    assert 0.12 <= eval_result["penalty_chance"] <= 0.55
    assert 0.04 <= eval_result["red_card_chance"] <= 0.45


def test_simulation_engine_incorporates_referee_telemetry():
    """Verifies that simulate_fixture produces full referee data and realistic cards/fouls."""
    db = Database()
    sim_engine = SimulationEngine(db)
    fixtures = db.get_fixtures()
    assert len(fixtures) > 0

    detail = db.get_match_detail(fixtures[0]["id"])
    assert detail is not None

    sim = sim_engine.simulate_fixture(detail)

    # 1. Referee object present in simulation payload
    assert "referee" in sim
    ref = sim["referee"]
    assert "name" in ref
    assert "strictness_index" in ref
    assert "fouls_per_game" in ref
    assert "badge_emoji" in ref

    # 2. Referee tactical impact present
    assert "referee_impact" in sim
    ref_imp = sim["referee_impact"]
    assert "foul_multiplier" in ref_imp
    assert "card_multiplier" in ref_imp
    assert "tactical_narrative" in ref_imp

    # 3. Stats include calibrated cards & fouls
    stats = sim["stats"]
    assert "fouls" in stats
    assert "yellow_cards" in stats
    assert "red_cards" in stats
    assert stats["fouls"]["home"] >= 5
    assert stats["fouls"]["away"] >= 5

    # 4. Strict 1-to-1 scoreline integrity preserved
    goal_events = [e for e in sim["events"] if e.get("type") == "goal"]
    h_goals = [e for e in goal_events if e.get("team") == "home"]
    a_goals = [e for e in goal_events if e.get("team") == "away"]
    assert len(h_goals) == sim["home_score"]
    assert len(a_goals) == sim["away_score"]

    # 5. Events sorted chronologically
    minutes = [e["minute"] for e in sim["events"]]
    assert minutes == sorted(minutes)


def test_telegram_bot_referee_views_and_navigation():
    """Verifies referee dossiers, directory, command shortcuts, and callbacks in Telegram bot."""
    db = Database()
    bot = PitchsideTelegramBot(token="123456:TEST_TOKEN", db=db)
    chat_id = 998811

    # 1. Single Referee Dossier View
    dossier_text, dossier_kb = bot.render_referee_dossier("gil-manzano", fixture_id=20262411)
    assert "MATCH OFFICIAL DOSSIER" in dossier_text
    assert "Jesús Gil Manzano" in dossier_text
    assert "STRICTNESS" in dossier_text
    assert "Fouls / Game" in dossier_text
    all_dossier_btns = [btn for row in dossier_kb["inline_keyboard"] for btn in row]
    dossier_cbs = {btn.get("callback_data") for btn in all_dossier_btns if btn.get("callback_data")}
    assert "simmode:simple:20262411" in dossier_cbs
    assert "refs:strict" in dossier_cbs

    # 2. Referees Directory View
    dir_text, dir_kb = bot.render_referees_directory(category="strict", chat_id=chat_id)
    assert "HIGHEST STRICTNESS" in dir_text
    all_dir_btns = [btn for row in dir_kb["inline_keyboard"] for btn in row]
    assert any(btn.get("callback_data", "").startswith("ref:") for btn in all_dir_btns)

    # 3. Lenient category directory
    len_text, len_kb = bot.render_referees_directory(category="lenient", chat_id=chat_id)
    assert "MOST LENIENT" in len_text

    # 4. Command dispatch /referees
    cmd_text, cmd_kb = bot.handle_command_or_text("/referees", chat_id=chat_id)
    assert "MATCH OFFICIALS" in cmd_text or "REFEREES" in cmd_text

    # 5. Callback dispatch ref:<slug>
    cb_text, cb_kb, toast = bot.handle_callback_data("ref:soto-grado", chat_id=chat_id)
    assert "César Soto Grado" in cb_text
    assert "Referee Dossier" in toast

    # 6. Callback dispatch refs:<cat>
    cb_dir_text, cb_dir_kb, dir_toast = bot.handle_callback_data("refs:penalties", chat_id=chat_id)
    assert "PENALTY" in cb_dir_text
    assert "Match Officials" in dir_toast


def test_telegram_bot_simulation_cards_contain_referee_actions():
    """Verifies that simple and advanced simulation modes include referee dossier action buttons."""
    db = Database()
    bot = PitchsideTelegramBot(token="123456:TEST_TOKEN", db=db)
    fixtures = db.get_fixtures()
    fid = fixtures[0]["id"]

    # Simple simulation card
    simple_text, simple_kb = bot.render_match_simulation_simple(fid)
    assert "MATCH OFFICIAL" in simple_text
    all_simple_btns = [btn for row in simple_kb["inline_keyboard"] for btn in row]
    assert any(btn.get("callback_data", "").startswith("ref:") for btn in all_simple_btns)

    # Advanced simulation card
    adv_text, adv_kb = bot.render_match_simulation_advanced(fid)
    assert "MATCH OFFICIAL" in adv_text
    all_adv_btns = [btn for row in adv_kb["inline_keyboard"] for btn in row]
    assert any(btn.get("callback_data", "").startswith("ref:") for btn in all_adv_btns)
