"""
Comprehensive tests for:
1. Full 90-minute Simulation Engine mathematical & logical accuracy
2. Predictive Trends (Momentum 1'-90', 6-Phase Dominance, Cumulative xG Ladder, Win Probability)
3. Red Card (Suspension) & Injury tracking across Database, Lineup Builder, Simulation Engine, and Telegram Bot
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import Database
from src.simulation_engine import SimulationEngine
from src.telegram_bot import PitchsideTelegramBot

_TMPDIR = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
_DB_COUNTER = 0


def _build_squad_test_db() -> Database:
    """
    Creates an isolated SQLite test database with 2 clubs, 3 fixtures across
    Matchdays 1, 2, and 3, and full 16-player squads per club so lineup building,
    bench promotion, red card suspensions, and injuries can be tested deterministically.
    """
    global _DB_COUNTER
    _DB_COUNTER += 1
    db_path = str(Path(_TMPDIR.name) / f"sim_avail_{_DB_COUNTER}.db")
    db = Database(db_path=db_path)
    conn = db.get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fixtures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matchday INTEGER, home_team_id INTEGER, away_team_id INTEGER,
                home_score INTEGER, away_score INTEGER, status TEXT,
                kickoff_time TEXT, goals_json TEXT, cards_json TEXT, season INTEGER
            )
        """)
        conn.execute(
            "INSERT INTO clubs (id, slug, name, nickname, position, overall_rating) "
            "VALUES (1, 'real-madrid', 'Real Madrid', 'Real Madrid', 1, 88)"
        )
        conn.execute(
            "INSERT INTO clubs (id, slug, name, nickname, position, overall_rating) "
            "VALUES (2, 'fc-barcelona', 'FC Barcelona', 'Barcelona', 2, 87)"
        )

        # Insert 16 players for Real Madrid (club_id=1):
        # 2 GKs, 5 Defenders, 5 Midfielders, 4 Forwards
        rm_players = [
            (101, "thibaut-courtois", "Thibaut Courtois", "Courtois", 1, "Goalkeeper", 90),
            (102, "andriy-lunin", "Andriy Lunin", "Lunin", 13, "Goalkeeper", 81),
            (103, "dani-carvajal", "Dani Carvajal", "Carvajal", 2, "Defender", 86),
            (104, "antonio-rudiger", "Antonio Rüdiger", "Rüdiger", 22, "Defender", 88),
            (105, "eder-militao", "Éder Militão", "Militão", 3, "Defender", 86),
            (106, "ferland-mendy", "Ferland Mendy", "Mendy", 23, "Defender", 83),
            (107, "lucas-vazquez", "Lucas Vázquez", "Vázquez", 17, "Defender", 79),
            (108, "jude-bellingham", "Jude Bellingham", "Bellingham", 5, "Midfielder", 91),
            (109, "federico-valverde", "Federico Valverde", "Valverde", 8, "Midfielder", 89),
            (110, "aurelien-tchouameni", "Aurélien Tchouaméni", "Tchouaméni", 14, "Midfielder", 85),
            (111, "eduardo-camavinga", "Eduardo Camavinga", "Camavinga", 6, "Midfielder", 84),
            (112, "luka-modric", "Luka Modrić", "Modrić", 10, "Midfielder", 82),
            (113, "kylian-mbappe", "Kylian Mbappé", "Mbappé", 9, "Forward", 92),
            (114, "vinicius-junior", "Vinícius Júnior", "Vinícius Jr", 7, "Forward", 91),
            (115, "rodrygo", "Rodrygo Goes", "Rodrygo", 11, "Forward", 87),
            (116, "brahim-diaz", "Brahim Díaz", "Brahim", 21, "Forward", 81),
        ]
        for pid, slug, name, nick, num, pos, ovr in rm_players:
            conn.execute(
                "INSERT INTO players (id, slug, name, nickname, shirt_number, club_id, position_name, overall_rating) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (pid, slug, name, nick, num, pos, ovr),
            )

        # Insert 16 players for FC Barcelona (club_id=2):
        fcb_players = [
            (201, "marc-andre-ter-stegen", "Marc-André ter Stegen", "Ter Stegen", 1, "Goalkeeper", 88),
            (202, "inaki-pena", "Iñaki Peña", "Iñaki Peña", 13, "Goalkeeper", 78),
            (203, "jules-kounde", "Jules Koundé", "Koundé", 23, "Defender", 86),
            (204, "ronald-araujo", "Ronald Araújo", "Araújo", 4, "Defender", 87),
            (205, "pau-cubarsi", "Pau Cubarsí", "Cubarsí", 2, "Defender", 83),
            (206, "alejandro-balde", "Alejandro Balde", "Balde", 3, "Defender", 83),
            (207, "inigo-martinez", "Iñigo Martínez", "Iñigo", 5, "Defender", 81),
            (208, "pedri", "Pedri González", "Pedri", 8, "Midfielder", 88),
            (209, "gavi", "Pablo Gavi", "Gavi", 6, "Midfielder", 85),
            (210, "frenkie-de-jong", "Frenkie de Jong", "De Jong", 21, "Midfielder", 86),
            (211, "dani-olmo", "Dani Olmo", "Olmo", 20, "Midfielder", 85),
            (212, "fermin-lopez", "Fermín López", "Fermín", 16, "Midfielder", 80),
            (213, "robert-lewandowski", "Robert Lewandowski", "Lewandowski", 9, "Forward", 89),
            (214, "lamine-yamal", "Lamine Yamal", "Lamine Yamal", 19, "Forward", 89),
            (215, "raphinha", "Raphinha", "Raphinha", 11, "Forward", 86),
            (216, "ferran-torres", "Ferran Torres", "Ferran", 7, "Forward", 80),
        ]
        for pid, slug, name, nick, num, pos, ovr in fcb_players:
            conn.execute(
                "INSERT INTO players (id, slug, name, nickname, shirt_number, club_id, position_name, overall_rating) "
                "VALUES (?, ?, ?, ?, ?, 2, ?, ?)",
                (pid, slug, name, nick, num, pos, ovr),
            )

        # Fixture 1: Matchday 1 (FINISHED)
        conn.execute(
            "INSERT INTO fixtures (id, matchday, home_team_id, away_team_id, home_score, away_score, "
            "status, kickoff_time, season) VALUES (1, 1, 1, 2, 2, 1, 'FINISHED', '2026-08-20 20:00:00', 2026)"
        )
        # Fixture 2: Matchday 2 (SCHEDULED - next match after MD 1)
        conn.execute(
            "INSERT INTO fixtures (id, matchday, home_team_id, away_team_id, status, kickoff_time, season) "
            "VALUES (2, 2, 2, 1, 'SCHEDULED', '2026-08-27 20:00:00', 2026)"
        )
        # Fixture 3: Matchday 3 (SCHEDULED)
        conn.execute(
            "INSERT INTO fixtures (id, matchday, home_team_id, away_team_id, status, kickoff_time, season) "
            "VALUES (3, 3, 1, 2, 'SCHEDULED', '2026-09-03 20:00:00', 2026)"
        )
        conn.commit()
    finally:
        conn.close()
    return db


def test_simulation_score_event_1_to_1_integrity():
    """
    Verifies that across real database fixtures, `simulate_fixture`:
    - Produces a 1-to-1 match between `home_score`/`away_score` and goal events
    - Is 100% deterministic across repeated calls
    - Produces valid possession, shots, shots on target, and xG
    """
    real_db = Database()
    engine = SimulationEngine(real_db)
    fixtures = real_db.get_fixtures()[:8]
    assert len(fixtures) > 0, "Expected fixtures in main DB"

    for fx in fixtures:
        detail = real_db.get_match_detail(fx["id"])
        assert detail is not None
        sim1 = engine.simulate_fixture(detail)
        sim2 = engine.simulate_fixture(detail)

        # Determinism check
        assert sim1["home_score"] == sim2["home_score"]
        assert sim1["away_score"] == sim2["away_score"]
        assert sim1["events"] == sim2["events"]

        # 1-to-1 scoreline vs goal events check
        h_goals = [e for e in sim1["events"] if e.get("type") == "goal" and e.get("team") == "home"]
        a_goals = [e for e in sim1["events"] if e.get("type") == "goal" and e.get("team") == "away"]
        assert len(h_goals) == sim1["home_score"], f"Home score {sim1['home_score']} != goal events {len(h_goals)}"
        assert len(a_goals) == sim1["away_score"], f"Away score {sim1['away_score']} != goal events {len(a_goals)}"

        # Result type consistency
        if sim1["home_score"] > sim1["away_score"]:
            assert sim1["result_type"] == "home_win"
        elif sim1["away_score"] > sim1["home_score"]:
            assert sim1["result_type"] == "away_win"
        else:
            assert sim1["result_type"] == "draw"

        # Telemetry & statistical bounds
        stats = sim1["stats"]
        assert stats["possession"]["home"] + stats["possession"]["away"] == 100
        assert stats["shots"]["home"] >= stats["shots_on_target"]["home"] >= sim1["home_score"]
        assert stats["shots"]["away"] >= stats["shots_on_target"]["away"] >= sim1["away_score"]
        assert stats["xg"]["home"] > 0 and stats["xg"]["away"] > 0

        # Events must be sorted chronologically by minute
        minutes = [e["minute"] for e in sim1["events"]]
        assert minutes == sorted(minutes), "Match events must be sorted chronologically"


def test_simulation_trends_momentum_phases_xg_winprob():
    """
    Verifies all predictive trends generated by the simulation engine:
    - 90-minute momentum wave (1'..90')
    - 6-phase match dominance (sum to 100% per phase)
    - Cumulative xG flow step-ladder (monotonic 0'..90')
    - Win probability evolution (7 snapshots summing to 100.0%)
    """
    db = _build_squad_test_db()
    engine = SimulationEngine(db)
    detail = db.get_match_detail(2)
    sim = engine.simulate_fixture(detail)
    trends = sim["trends"]

    # 1. Momentum (90 minutes)
    mom = trends["momentum"]
    assert len(mom) == 90
    assert [m["minute"] for m in mom] == list(range(1, 91))
    assert all(-95.0 <= m["value"] <= 95.0 for m in mom)

    # 2. 6-Phase Dominance
    phases = trends["phases"]
    assert len(phases) == 6
    for p in phases:
        assert p["home_pct"] + p["away_pct"] == 100
        assert 20 <= p["home_pct"] <= 80

    # 3. Cumulative xG Flow (0'..90' monotonic step-ladder)
    xg_flow = trends["xg_flow"]
    assert len(xg_flow) == 91
    for i in range(1, len(xg_flow)):
        assert xg_flow[i]["home_xg"] >= xg_flow[i - 1]["home_xg"]
        assert xg_flow[i]["away_xg"] >= xg_flow[i - 1]["away_xg"]
    assert xg_flow[-1]["home_xg"] == sim["stats"]["xg"]["home"]
    assert xg_flow[-1]["away_xg"] == sim["stats"]["xg"]["away"]

    # 4. Win Probability Trend
    wp = trends["win_probability"]
    assert [s["minute"] for s in wp] == [0, 15, 30, 45, 60, 75, 90]
    for s in wp:
        tot = round(s["home_prob"] + s["draw_prob"] + s["away_prob"], 1)
        assert abs(tot - 100.0) <= 0.2, f"Win prob at {s['minute']}' summed to {tot}"


def test_injured_player_excluded_and_replaced():
    """
    Verifies that when a starting player is marked as injured:
    - They are automatically removed from `starting_xi` and `bench`
    - They are placed in `missing_players` with `status == 'injured'` and `🏥`
    - The next highest-rated available player at their position is promoted into `starting_xi`
    - Team strength (`avg_ovr`) and expected goals decrease
    - The injured player NEVER scores, assists, gets a card, or makes a save in the simulation
    """
    db = _build_squad_test_db()
    engine = SimulationEngine(db)

    # Baseline before injury (Fixture 2: Barcelona Home vs Real Madrid Away)
    detail_healthy = db.get_match_detail(2)
    rm_xi_healthy = detail_healthy["away_team"]["tactics"]["starting_xi"]
    rm_starter_ids_healthy = {p["id"] for p in rm_xi_healthy}
    assert 113 in rm_starter_ids_healthy, "Kylian Mbappé (id=113, OVR 92) should start when healthy"
    assert 116 not in rm_starter_ids_healthy, "Brahim Díaz (id=116, OVR 81) should be on bench when Mbappé is healthy"

    forecast_healthy = engine.monte_carlo_forecast(detail_healthy)

    # Mark Kylian Mbappé (id=113) as INJURED
    ok = db.set_player_availability(113, status="injured", reason="Hamstring Muscle Injury")
    assert ok is True

    detail_injured = db.get_match_detail(2)
    rm_tactics_inj = detail_injured["away_team"]["tactics"]
    rm_xi_inj = rm_tactics_inj["starting_xi"]
    rm_bench_inj = rm_tactics_inj["bench"]
    rm_missing_inj = rm_tactics_inj["missing_players"]

    # 1. Mbappé is NOT in starting_xi or bench
    assert len(rm_xi_inj) == 11, "Starting XI must still have 11 players"
    assert all(p["id"] != 113 for p in rm_xi_inj), "Injured Mbappé must not be in starting_xi"
    assert all(p["id"] != 113 for p in rm_bench_inj), "Injured Mbappé must not be on the bench"

    # 2. Brahim Díaz (id=116, backup Forward) was automatically promoted into starting_xi
    assert any(p["id"] == 116 for p in rm_xi_inj), "Backup forward Brahim Díaz must be promoted into starting_xi"

    # 3. Mbappé is listed in missing_players with 🏥 and reason
    assert len(rm_missing_inj) == 1
    assert rm_missing_inj[0]["id"] == 113
    assert rm_missing_inj[0]["availability_status"] == "injured"
    assert rm_missing_inj[0]["status_icon"] == "🏥"
    assert "Hamstring" in rm_missing_inj[0]["availability_reason"]

    # 4. Team strength & projected xG drop when a 92-OVR star is out injured
    forecast_injured = engine.monte_carlo_forecast(detail_injured)
    assert forecast_injured["projected_xg"]["away"] < forecast_healthy["projected_xg"]["away"], (
        "Projected xG must decrease when 92-OVR star striker is injured"
    )
    assert forecast_injured["availability_analysis"]["away_absence_penalty"] > 0

    # 5. Simulate fixture and confirm injured player never appears in any match event
    sim = engine.simulate_fixture(detail_injured)
    for ev in sim["events"]:
        assert ev.get("scorer_id") != 113
        assert "Mbappé" not in (ev.get("scorer") or "")
        assert "Mbappé" not in (ev.get("assist") or "")
        assert "Mbappé" not in (ev.get("player") or "")


def test_red_card_in_previous_match_suspends_player():
    """
    Verifies automatic Red Card suspension tracking:
    - Recording a red card for a starter in Matchday 1 (FINISHED) automatically
      suspends them for Matchday 2!
    - In Matchday 2, they are excluded from `starting_xi` and `bench`, and listed
      in `missing_players` with `🟥` and `Red Card Suspension (MD 1)`.
    - Once Matchday 2 finishes without a red card for that player, they are
      automatically eligible again in Matchday 3!
    """
    db = _build_squad_test_db()
    engine = SimulationEngine(db)

    # Record a Red Card for Jude Bellingham (id=108, OVR 91) and Ronald Araújo (id=204, OVR 87) in Matchday 1 (fixture_id=1)
    assert db.record_match_red_card(fixture_id=1, player_id_or_slug=108, minute=72) is True
    assert db.record_match_red_card(fixture_id=1, player_id_or_slug="ronald-araujo", minute=84) is True

    # Inspect Matchday 2 (fixture_id=2: Barcelona vs Real Madrid)
    detail_md2 = db.get_match_detail(2)
    fcb_tactics = detail_md2["home_team"]["tactics"]
    rm_tactics = detail_md2["away_team"]["tactics"]

    # Jude Bellingham (108) must be excluded from Real Madrid's Starting XI & Bench in MD 2
    assert all(p["id"] != 108 for p in rm_tactics["starting_xi"]), "Red-carded Bellingham must be excluded from MD 2 XI"
    assert all(p["id"] != 108 for p in rm_tactics["bench"]), "Red-carded Bellingham must be excluded from MD 2 bench"
    assert any(m["id"] == 108 and m["availability_status"] == "suspended" and m["status_icon"] == "🟥" for m in rm_tactics["missing_players"])

    # Ronald Araújo (204) must be excluded from Barcelona's Starting XI & Bench in MD 2
    assert all(p["id"] != 204 for p in fcb_tactics["starting_xi"]), "Red-carded Araújo must be excluded from MD 2 XI"
    assert all(p["id"] != 204 for p in fcb_tactics["bench"]), "Red-carded Araújo must be excluded from MD 2 bench"
    assert any(m["id"] == 204 and m["availability_status"] == "suspended" and m["status_icon"] == "🟥" for m in fcb_tactics["missing_players"])

    # Simulate MD 2 and verify neither suspended player participates in any event
    sim_md2 = engine.simulate_fixture(detail_md2)
    for ev in sim_md2["events"]:
        assert ev.get("scorer_id") not in (108, 204)
        for name_tok in ("Bellingham", "Araújo"):
            assert name_tok not in (ev.get("scorer") or "")
            assert name_tok not in (ev.get("assist") or "")
            assert name_tok not in (ev.get("player") or "")

    # Now mark Matchday 2 (fixture_id=2) as FINISHED with no red cards, and check Matchday 3 (fixture_id=3)
    with db.get_connection() as conn:
        conn.execute("UPDATE fixtures SET status='FINISHED', home_score=1, away_score=1 WHERE id=2")
        conn.commit()

    detail_md3 = db.get_match_detail(3)
    rm_xi_md3 = {p["id"] for p in detail_md3["home_team"]["tactics"]["starting_xi"]}
    fcb_xi_md3 = {p["id"] for p in detail_md3["away_team"]["tactics"]["starting_xi"]}
    assert 108 in rm_xi_md3, "Bellingham must return to Starting XI in MD 3 after serving MD 2 suspension"
    assert 204 in fcb_xi_md3, "Araújo must return to Starting XI in MD 3 after serving MD 2 suspension"


def test_simulation_engine_sanitizes_unfiltered_lineup():
    """
    Verifies that even if a caller passes a raw `match_detail_data` dictionary
    into `SimulationEngine.simulate_fixture()` where a player inside `starting_xi`
    has `red_card=True` or `availability_status='suspended'`, the engine sanitizes
    the lineup, promotes a bench player, and prevents the unavailable player from playing.
    """
    db = _build_squad_test_db()
    engine = SimulationEngine(db)
    detail = db.get_match_detail(2)

    # Manually inject a red card flag onto Barcelona's top striker (Lewandowski, id=213) in the dict
    for p in detail["home_team"]["tactics"]["starting_xi"]:
        if p["id"] == 213:
            p["red_card"] = True
            p["availability_status"] = "suspended"
            p["availability_reason"] = "Direct Red Card"

    sim = engine.simulate_fixture(detail)
    home_missing = sim["availability_analysis"]["home_missing"]
    assert any(m["id"] == 213 and m["availability_status"] == "suspended" for m in home_missing)

    for ev in sim["events"]:
        assert ev.get("scorer_id") != 213
        assert "Lewandowski" not in (ev.get("scorer") or "")
        assert "Lewandowski" not in (ev.get("assist") or "")


def test_telegram_bot_renders_missing_players():
    """
    Verifies that the Telegram Bot's Match Center (`render_match_center`) and
    Starting XI (`render_match_lineups`) views display suspended (🟥) and injured (🏥)
    players clearly to the user.
    """
    db = _build_squad_test_db()
    db.record_match_red_card(fixture_id=1, player_id_or_slug=108, minute=65)  # Bellingham 🟥
    db.set_player_availability(213, status="injured", reason="Knee Injury")   # Lewandowski 🏥

    bot = PitchsideTelegramBot(token="123456:TEST_TOKEN", db=db)
    mc_text, _ = bot.render_match_center(2)
    xi_text, _ = bot.render_match_lineups(2)

    assert "SUSPENSIONS &amp; INJURIES" in mc_text
    assert "Bellingham" in mc_text and "🟥" in mc_text
    assert "Lewandowski" in mc_text and "🏥" in mc_text

    assert "Unavailable / Out:" in xi_text
    assert "Bellingham" in xi_text and "Red Card Suspension" in xi_text
    assert "Lewandowski" in xi_text and "Knee Injury" in xi_text


def test_telegram_bot_welcome_animation_and_features_guide():
    """
    Verifies that:
    1. WELCOME_GIF_URL matches the Neymar GIF requested by the user.
    2. render_welcome_animation() produces a valid GIF URL, HTML caption, and keyboard.
    3. Caption length is strictly <= 1024 characters (Telegram sendAnimation limit).
    4. Caption explicitly explains what the bot does:
       - Matches of the Day
       - 90' Match Simulator
       - Suspension & Injury Tracking
       - Predictive Telemetry
       - Standings & Form Guide
       - Club Tactical DNA & Scouting
       - Head-to-Head Compare
    5. Commands /start, /help, /about, /welcome trigger the welcome explanation.
    6. Callback data 'menu:welcome' returns the welcome view.
    7. process_update() dispatches send_animation() with the Neymar GIF for /start.
    """
    db = _build_squad_test_db()
    bot = PitchsideTelegramBot(token="123456:TEST_TOKEN", db=db)

    # 1. Verify GIF URL
    expected_gif = "https://media1.tenor.com/m/tgsrfDxv17MAAAAd/neyma.gif"
    assert bot.WELCOME_GIF_URL == expected_gif

    # 2. Verify render_welcome_animation
    gif_url, caption, markup = bot.render_welcome_animation()
    assert gif_url == expected_gif

    # 3. Caption length must be <= 1024 characters
    assert len(caption) <= 1024, f"Caption length {len(caption)} exceeds Telegram limit of 1024"
    assert len(caption) > 200

    # 4. Verify feature explanations
    assert "Matches of the Day" in caption
    assert "Simulator" in caption
    assert "Suspension" in caption
    assert "Telemetry" in caption or "Predictive" in caption
    assert "Standings" in caption
    assert "Tactical DNA" in caption
    assert "Head-to-Head" in caption

    # 5. Verify inline keyboard buttons
    all_buttons = [btn for row in markup["inline_keyboard"] for btn in row]
    cb_datas = {btn["callback_data"] for btn in all_buttons}
    assert "day:today" in cb_datas
    assert "daysim:today" in cb_datas
    assert "st:all" in cb_datas
    assert "clubs" in cb_datas

    # 6. Verify command handling
    for cmd in ("/start", "/help", "/about", "/welcome", "/guide"):
        text, kb = bot.handle_command_or_text(cmd)
        assert "WELCOME TO PITCHSIDE LA LIGA BOT" in text
        assert len(text) <= 1024

    # 7. Verify callback handling
    cb_text, cb_kb, toast = bot.handle_callback_data("menu:welcome")
    assert "WELCOME TO PITCHSIDE LA LIGA BOT" in cb_text
    assert toast is not None

    # 8. Verify process_update dispatches animation for /start
    sent_animations = []
    def mock_send_animation(chat_id, animation, caption=None, reply_markup=None, parse_mode="HTML"):
        sent_animations.append((chat_id, animation, caption, reply_markup))
        return {"ok": True, "result": {"message_id": 999}}

    bot.send_animation = mock_send_animation
    bot.process_update({
        "update_id": 100,
        "message": {
            "message_id": 50,
            "chat": {"id": 987654321, "username": "testuser"},
            "text": "/start"
        }
    })
    assert len(sent_animations) == 1
    assert sent_animations[0][0] == 987654321
    assert sent_animations[0][1] == expected_gif
    assert "WELCOME TO PITCHSIDE" in sent_animations[0][2]


def test_telegram_bot_automated_theme_cards_and_tabs():
    """
    Verifies that:
    1. CLUB_THEMES accurately maps club slugs/names to 3-letter codes and emoji badges.
    2. _render_scoreboard_card() generates a monospaced frame in <pre><code>.
    3. render_match_center() accurately renders all 4 tabs: overview, lineups, momentum, tactics.
    4. render_match_simulation() includes the scoreboard card and share link.
    5. render_standings_view() includes 3-letter club codes in columns.
    6. Daily Alerts toggle works automatically in the database (toggle_subscription & is_subscribed).
    """
    db = _build_squad_test_db()
    bot = PitchsideTelegramBot(token="123456:TEST_TOKEN", db=db)

    # 1. Club theme mappings
    rma = bot.get_club_theme("real-madrid")
    fcb = bot.get_club_theme("fc-barcelona")
    atm = bot.get_club_theme("atletico-madrid")
    assert rma["code"] == "RMA" and "⚪" in rma["badge"]
    assert fcb["code"] == "FCB" and "🔵" in fcb["badge"]
    assert atm["code"] == "ATM" and "🔴" in atm["badge"]

    # 2. Scoreboard card
    card = bot._render_scoreboard_card("RMA", "Real Madrid", 2, "FCB", "Barcelona", 1, "FT · Santiago Bernabéu")
    assert "<pre><code>" in card and "</code></pre>" in card
    assert "RMA" in card and "FCB" in card and "2" in card and "1" in card
    assert "┌" in card and "└" in card

    # 3. Match Center 4 Tabs
    # Tab 1: Overview
    t_over, kb_over = bot.render_match_center(2, tab="overview")
    assert "<pre><code>" in t_over
    assert "• 📊 Overview •" in str(kb_over)
    assert "DIXON-COLES" in t_over

    # Tab 2: Lineups
    t_line, kb_line = bot.render_match_center(2, tab="lineups")
    assert "• 📋 XIs •" in str(kb_line)
    assert "STARTING XIs" in t_line or "XI" in t_line

    # Tab 3: Momentum
    t_mom, kb_mom = bot.render_match_center(2, tab="momentum")
    assert "• 🌊 Momentum •" in str(kb_mom)
    assert "PROJECTED POSSESSION" in t_mom

    # Tab 4: Tactics
    t_tac, kb_tac = bot.render_match_center(2, tab="tactics")
    assert "• 🧠 Tactics •" in str(kb_tac)
    assert "MANAGERIAL DUEL" in t_tac

    # 4. Simulation report with scoreboard card and share link
    sim_text, sim_kb = bot.render_match_simulation(2)
    assert "<pre><code>" in sim_text
    assert any("Share" in btn.get("text", "") for row in sim_kb["inline_keyboard"] for btn in row)

    # 5. Standings with 3-letter codes
    st_text, _ = bot.render_standings_view("all")
    assert "TAG" in st_text or any(code in st_text for code in ("FCB", "ATM", "RMA"))

    # 6. Automated alerts toggle
    test_chat = 777888999
    bot.register_subscriber(test_chat, username="football_fan", first_name="Fan")
    assert bot.is_subscribed(test_chat) is True

    # Toggle off
    new_state = bot.toggle_subscription(test_chat)
    assert new_state is False
    assert bot.is_subscribed(test_chat) is False

    # Toggle on
    new_state = bot.toggle_subscription(test_chat)
    assert new_state is True
    assert bot.is_subscribed(test_chat) is True

    # Callback toggle
    cb_text, cb_kb, toast = bot.handle_callback_data("sub:toggle", chat_id=test_chat)
    assert toast is not None
    assert any("Daily Alerts" in btn.get("text", "") for row in cb_kb["inline_keyboard"] for btn in row)


def test_telegram_bot_send_new_messages_on_callback():
    """
    Verifies that:
    1. PitchsideTelegramBot defaults to send_new_messages = True.
    2. Clicking inline buttons (callback_query) sends a fresh new message via send_message
       rather than editing in-place via edit_or_send (fixing the issue where users didn't
       see a new message in chat).
    3. Clicking 'menu:welcome' sends the full Neymar GIF animation via send_animation.
    4. Answering callback queries clears the Telegram button loading spinner.
    5. /msgmode and 'msgmode:toggle' properly toggle between New Messages and In-Place Edits.
    6. When in-place edits mode is selected, callback queries route to edit_or_send.
    """
    db = _build_squad_test_db()
    bot = PitchsideTelegramBot(token="123456:TEST_TOKEN", db=db)

    # 1. Default configuration check
    assert bot.send_new_messages is True

    # Call recording arrays
    sent_messages = []
    sent_animations = []
    edited_messages = []
    answered_callbacks = []

    def mock_send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
        sent_messages.append({"chat_id": chat_id, "text": text, "markup": reply_markup})
        return {"ok": True, "result": {"message_id": 1001}}

    def mock_send_animation(chat_id, animation, caption=None, reply_markup=None, parse_mode="HTML"):
        sent_animations.append({"chat_id": chat_id, "animation": animation, "caption": caption, "markup": reply_markup})
        return {"ok": True, "result": {"message_id": 1002}}

    def mock_edit_or_send(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
        edited_messages.append({"chat_id": chat_id, "message_id": message_id, "text": text, "markup": reply_markup})
        return {"ok": True, "result": {"message_id": message_id}}

    def mock_answer_callback(callback_query_id, text=None, show_alert=False):
        answered_callbacks.append({"id": callback_query_id, "text": text})
        return {"ok": True}

    bot.send_message = mock_send_message
    bot.send_animation = mock_send_animation
    bot.edit_or_send = mock_edit_or_send
    bot.answer_callback = mock_answer_callback

    # 2. Test standard button click (e.g. today's fixtures or match selection)
    sample_update = {
        "update_id": 101,
        "callback_query": {
            "id": "cb_query_123",
            "data": "day:today",
            "message": {"message_id": 555, "chat": {"id": 99999, "first_name": "TestUser"}},
        },
    }
    bot.process_update(sample_update)

    # Must send a fresh new message, NOT edit existing message
    assert len(sent_messages) == 1, "Expected send_message to be called to show a fresh new message"
    assert len(edited_messages) == 0, "edit_or_send should NOT be called when send_new_messages is True"
    assert sent_messages[0]["chat_id"] == 99999
    assert len(answered_callbacks) == 1
    assert answered_callbacks[0]["id"] == "cb_query_123"

    # 3. Test welcome guide button click
    welcome_update = {
        "update_id": 102,
        "callback_query": {
            "id": "cb_query_456",
            "data": "menu:welcome",
            "message": {"message_id": 556, "chat": {"id": 99999, "first_name": "TestUser"}},
        },
    }
    bot.process_update(welcome_update)
    assert len(sent_animations) == 1, "Expected send_animation to be called for welcome callback"
    assert sent_animations[0]["animation"] == bot.WELCOME_GIF_URL
    assert "PITCHSIDE" in sent_animations[0]["caption"]

    # 4. Test /msgmode command toggling
    resp_text, kb = bot.handle_command_or_text("/msgmode")
    assert bot.send_new_messages is False
    assert "In-Place Edits" in resp_text

    # 5. In-Place Edit Mode: callback queries should now edit existing message
    sent_messages.clear()
    edited_messages.clear()
    bot.process_update(sample_update)
    assert len(sent_messages) == 0, "send_message should NOT be called in in-place edit mode"
    assert len(edited_messages) == 1, "edit_or_send SHOULD be called in in-place edit mode"
    assert edited_messages[0]["message_id"] == 555

    # 6. Switch back to New Messages Mode via callback
    mode_switch_cb = {
        "update_id": 103,
        "callback_query": {
            "id": "cb_query_789",
            "data": "msgmode:new",
            "message": {"message_id": 557, "chat": {"id": 99999, "first_name": "TestUser"}},
        },
    }
    bot.process_update(mode_switch_cb)
    assert bot.send_new_messages is True
