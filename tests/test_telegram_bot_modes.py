"""
Automated unit tests for the upgraded Telegram Bot (@xbetbetterbot):
- Simple Mode (clean 5-second check, club crests, scorers, 10,000-draw Gut Feeling probabilities & fair odds)
- Advanced Mode (deep telemetry, 6-phase momentum, incident timeline, Gut Feeling math engine)
- Gut Feeling 10k Prediction Dossier & /gut command
- Welcome GIF animation (<1024 char caption) & sendPhoto support
"""
from src.telegram_bot import PitchsideTelegramBot
from src.database import Database

def _get_bot():
    db = Database()
    return PitchsideTelegramBot(token="123456:dummy_test_token", db=db)

def test_welcome_animation_under_telegram_limits():
    bot = _get_bot()
    gif_url, caption, markup = bot.render_welcome_animation()
    assert gif_url.startswith("http"), "Invalid GIF URL"
    assert len(caption) <= 1024, f"Caption exceeds Telegram's 1024-char limit: {len(caption)}"
    assert "<b>" in caption and "</b>" in caption, "Caption should be formatted in valid HTML"
    assert "inline_keyboard" in markup, "Missing inline keyboard markup"

def test_welcome_text_content():
    bot = _get_bot()
    text, markup = bot.render_welcome_text()
    assert "Simple" in text
    assert "Advanced" in text
    assert "Gut Feeling AI" in text
    assert "/gut" in text

def test_simple_simulation_mode_with_gut_feeling():
    bot = _get_bot()
    fixtures = bot._get_all_fixtures()
    assert len(fixtures) > 0, "No fixtures available"
    fid = fixtures[0]["id"]

    text, markup = bot.render_match_simulation_simple(fid)
    assert "SIMPLE MODE" in text
    assert "WIN PROBABILITY &amp; xG" in text
    assert "GUT FEELING 10,000-DRAW SIMULATION" in text
    assert "Fair Decimal Odds:" in text
    assert "Expected Goals:" in text

    buttons = [b["text"] for row in markup.get("inline_keyboard", []) for b in row]
    assert any("Switch to Advanced" in b for b in buttons)
    assert any("Gut Feeling Dossier" in b for b in buttons)
    assert any("Share Simulation" in b for b in buttons)

def test_advanced_simulation_mode_with_mathematical_engine():
    bot = _get_bot()
    fixtures = bot._get_all_fixtures()
    fid = fixtures[0]["id"]

    text, markup = bot.render_match_simulation_advanced(fid)
    assert "ADVANCED MODE" in text
    assert "6-PHASE ATTACK MOMENTUM" in text
    assert "WIN PROBABILITY EVOLUTION" in text
    assert "TACTICAL TREND NARRATIVE" in text
    assert "Elo Anchor:" in text
    assert "3-Match Form:" in text
    assert "10,000 Draws:" in text
    assert "Fair Decimal Odds:" in text

    buttons = [b["text"] for row in markup.get("inline_keyboard", []) for b in row]
    assert any("Switch to Simple" in b for b in buttons)
    assert any("Gut Feeling Dossier" in b for b in buttons)
    assert any("Share Simulation" in b for b in buttons)

def test_gut_feeling_view_and_command():
    bot = _get_bot()
    fixtures = bot._get_all_fixtures()
    fid = fixtures[0]["id"]

    # Today's overview
    today_txt, today_markup = bot.render_gut_feeling_view("today")
    assert "GUT FEELING 10,000-DRAW PREDICTIONS" in today_txt

    # Single fixture dossier
    dossier_txt, dossier_markup = bot.render_gut_feeling_view(str(fid))
    assert "GUT FEELING PREDICTION DOSSIER" in dossier_txt
    assert "DECISION VERDICT:" in dossier_txt
    assert "10,000-DRAW SIMULATION PROBABILITIES" in dossier_txt

    # Command dispatch
    cmd_txt, _ = bot.handle_command_or_text("/gut")
    assert "GUT FEELING" in cmd_txt.upper()

    cmd_txt2, _ = bot.handle_command_or_text(f"/gut {fid}")
    assert "GUT FEELING PREDICTION DOSSIER" in cmd_txt2

def test_send_photo_method():
    bot = _get_bot()
    assert hasattr(bot, "send_photo"), "send_photo method should exist on bot"

def test_engine_selection_preference():
    bot = _get_bot()
    chat_id = 998877
    assert bot.get_chat_prediction_engine(chat_id) == "gut"

    assert bot.set_chat_prediction_engine(chat_id, "dixon") == "dixon"
    assert bot.get_chat_prediction_engine(chat_id) == "dixon"

    assert bot.set_chat_prediction_engine(chat_id, "old") == "dixon"
    assert bot.get_chat_prediction_engine(chat_id) == "dixon"

    assert bot.set_chat_prediction_engine(chat_id, "gut") == "gut"
    assert bot.get_chat_prediction_engine(chat_id) == "gut"

    assert bot.set_chat_prediction_engine(chat_id, "new") == "gut"
    assert bot.get_chat_prediction_engine(chat_id) == "gut"

def test_engine_switcher_view():
    bot = _get_bot()
    chat_id = 998877
    text, markup = bot.render_engine_switcher(chat_id)
    assert "PREDICTION ENGINE SELECTOR" in text
    assert "NEW ENGINE: GUT FEELING 10,000-DRAW SIMULATION" in text
    assert "OLD ENGINE: CLASSIC DIXON-COLES" in text
    assert "(Active ✅)" in text

    buttons = [b["text"] for row in markup.get("inline_keyboard", []) for b in row]
    cbs = [b.get("callback_data") for row in markup.get("inline_keyboard", []) for b in row if b.get("callback_data")]
    assert any("New Engine" in b for b in buttons)
    assert any("Old Engine" in b for b in buttons)
    assert "engine:gut" in cbs
    assert "engine:dixon" in cbs
    assert "menu:mode" in cbs
    assert "menu:home" in cbs

def test_engine_command_and_shortcuts():
    bot = _get_bot()
    chat_id = 998877

    # /engine opens switcher
    txt, _ = bot.handle_command_or_text("/engine", chat_id=chat_id)
    assert "PREDICTION ENGINE SELECTOR" in txt

    # /engine old sets to dixon
    bot.handle_command_or_text("/engine old", chat_id=chat_id)
    assert bot.get_chat_prediction_engine(chat_id) == "dixon"

    # /engine new sets to gut
    bot.handle_command_or_text("/engine new", chat_id=chat_id)
    assert bot.get_chat_prediction_engine(chat_id) == "gut"

    # /oldengine shortcut
    bot.handle_command_or_text("/oldengine", chat_id=chat_id)
    assert bot.get_chat_prediction_engine(chat_id) == "dixon"

    # /newengine shortcut
    bot.handle_command_or_text("/newengine", chat_id=chat_id)
    assert bot.get_chat_prediction_engine(chat_id) == "gut"

def test_engine_toggle_on_simulation_cards():
    bot = _get_bot()
    fixtures = bot._get_all_fixtures()
    fid = fixtures[0]["id"]
    chat_id = 998877

    # Simple mode - New Engine (Gut)
    txt_s_gut, mk_s_gut = bot.render_match_simulation_simple(fid, engine="gut")
    assert "GUT FEELING 10,000-DRAW SIMULATION" in txt_s_gut
    cbs_s_gut = [b.get("callback_data") for row in mk_s_gut.get("inline_keyboard", []) for b in row]
    assert f"simengine:dixon:{fid}" in cbs_s_gut

    # Simple mode - Old Engine (Dixon)
    txt_s_dix, mk_s_dix = bot.render_match_simulation_simple(fid, engine="dixon")
    assert "CLASSIC DIXON-COLES ENGINE (OLD)" in txt_s_dix
    cbs_s_dix = [b.get("callback_data") for row in mk_s_dix.get("inline_keyboard", []) for b in row]
    assert f"simengine:gut:{fid}" in cbs_s_dix

    # Advanced mode - New Engine (Gut)
    txt_a_gut, mk_a_gut = bot.render_match_simulation_advanced(fid, engine="gut")
    assert "GUT FEELING ENGINE" in txt_a_gut
    cbs_a_gut = [b.get("callback_data") for row in mk_a_gut.get("inline_keyboard", []) for b in row]
    assert f"simengine:dixon:{fid}" in cbs_a_gut

    # Advanced mode - Old Engine (Dixon)
    txt_a_dix, mk_a_dix = bot.render_match_simulation_advanced(fid, engine="dixon")
    assert "DIXON-COLES ENGINE (OLD)" in txt_a_dix
    cbs_a_dix = [b.get("callback_data") for row in mk_a_dix.get("inline_keyboard", []) for b in row]
    assert f"simengine:gut:{fid}" in cbs_a_dix

def test_engine_callbacks_and_mode_switcher_integration():
    bot = _get_bot()
    chat_id = 998877
    fixtures = bot._get_all_fixtures()
    fid = fixtures[0]["id"]

    # Callback engine:dixon
    txt, mk, toast = bot.handle_callback_data("engine:dixon", chat_id=chat_id)
    assert bot.get_chat_prediction_engine(chat_id) == "dixon"
    assert "Old Engine" in toast

    # Callback engine:gut
    txt2, mk2, toast2 = bot.handle_callback_data("engine:gut", chat_id=chat_id)
    assert bot.get_chat_prediction_engine(chat_id) == "gut"
    assert "New Engine" in toast2

    # Callback simengine:dixon:<fid>
    sim_dix, _, toast_sim_dix = bot.handle_callback_data(f"simengine:dixon:{fid}", chat_id=chat_id)
    assert "CLASSIC DIXON-COLES ENGINE (OLD)" in sim_dix
    assert "Old Engine" in toast_sim_dix

    # Callback simengine:gut:<fid>
    sim_gut, _, toast_sim_gut = bot.handle_callback_data(f"simengine:gut:{fid}", chat_id=chat_id)
    assert "GUT FEELING 10,000-DRAW SIMULATION" in sim_gut
    assert "New Engine" in toast_sim_gut

    # menu:engine callback
    m_txt, m_mk, _ = bot.handle_callback_data("menu:engine", chat_id=chat_id)
    assert "PREDICTION ENGINE SELECTOR" in m_txt

    # Mode switcher view includes prediction engine indicator
    mode_txt, mode_mk = bot.render_mode_switcher(chat_id)
    assert "Active Prediction Engine:" in mode_txt
    mode_cbs = [b.get("callback_data") for row in mode_mk.get("inline_keyboard", []) for b in row]
    assert "menu:engine" in mode_cbs

def test_server_engine_switching():
    from src.server import ProfilerHTTPRequestHandler
    from gut_feeling.model import GutFeelingEngine
    from src.simulation_engine import SimulationEngine
    db = Database()
    fixtures = db.get_fixtures()
    assert len(fixtures) > 0
    fid = fixtures[0]["id"]
    detail = db.get_match_detail(fid)
    assert detail is not None

    handler = ProfilerHTTPRequestHandler.__new__(ProfilerHTTPRequestHandler)
    handler.db = db
    handler.simulation_engine = SimulationEngine(db)
    handler.gut_engine = GutFeelingEngine(
        w_elo=0.9, w_form=0.1, k_goal=0.35, sigma_noise=0.05, n_sim=10000
    )

    gf = handler._compute_gut_feeling(detail)
    assert gf["method"] == "gut_feeling_10k_monte_carlo"
    assert "home_win_pct" in gf
    assert "fair_odds" in gf
    assert "projected_xg" in gf
    assert "confidence_verdict" in gf

def test_register_commands_includes_engine_and_gut():
    bot = _get_bot()
    captured_calls = []
    def fake_api_call(method, payload=None, timeout=35):
        captured_calls.append((method, payload))
        return {"ok": True, "result": True}
    bot._api_call = fake_api_call
    bot.register_commands()

    methods = [c[0] for c in captured_calls]
    assert "setMyCommands" in methods
    assert "setMyDescription" in methods
    assert "setMyShortDescription" in methods
    assert "setChatMenuButton" in methods

    cmd_payload = next(c[1] for c in captured_calls if c[0] == "setMyCommands")
    registered_cmds = [cmd["command"] for cmd in cmd_payload["commands"]]
    assert "engine" in registered_cmds
    assert "gut" in registered_cmds
    assert "start" in registered_cmds
    assert "mode" in registered_cmds


def test_gut_feeling_simulation_engine_distinct_results():
    bot = _get_bot()
    fixtures = bot._get_all_fixtures()
    assert len(fixtures) > 0
    fid = fixtures[0]["id"]
    detail = bot._get_match_detail(fid)
    assert detail is not None

    # Test SimulationEngine directly
    sim_dixon = bot.sim_engine.simulate_fixture(detail, engine="dixon")
    sim_gut = bot.sim_engine.simulate_fixture(detail, engine="gut")

    assert sim_dixon["engine"] == "dixon"
    assert sim_gut["engine"] == "gut"

    # Both must have valid integer scores and exact 1-to-1 event count
    assert isinstance(sim_dixon["home_score"], int)
    assert isinstance(sim_gut["home_score"], int)
    dix_goals = [e for e in sim_dixon["events"] if e.get("type") == "goal"]
    assert len([e for e in dix_goals if e["team"] == "home"]) == sim_dixon["home_score"]
    assert len([e for e in dix_goals if e["team"] == "away"]) == sim_dixon["away_score"]

    gut_goals = [e for e in sim_gut["events"] if e.get("type") == "goal"]
    assert len([e for e in gut_goals if e["team"] == "home"]) == sim_gut["home_score"]
    assert len([e for e in gut_goals if e["team"] == "away"]) == sim_gut["away_score"]

    # Test rendering via Telegram Bot methods
    txt_dix, _ = bot.render_match_simulation_simple(fid, engine="dixon")
    assert "CLASSIC DIXON-COLES ENGINE (OLD)" in txt_dix

    txt_gut, _ = bot.render_match_simulation_simple(fid, engine="gut")
    assert "GUT FEELING 10,000-DRAW SIMULATION" in txt_gut




