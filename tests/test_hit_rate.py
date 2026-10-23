"""
Tests for Verified Hit Rate Telemetry, Dossier & Outcome Celebrations
======================================================================
Verifies:
  * get_hit_rate_telemetry calculation (all-time, high-confidence, ultra-confidence)
  * get_fixture_prediction_record retrieval and hit flag
  * PitchsideTelegramBot.render_hit_rate_view rendering and progress bars
  * /hitrate command dispatch and hitrate:* callbacks
  * Celebratory prediction hit badge in render_match_center
  * Hit rate telemetry lines in simulation modes
"""
import pytest
from src.database import Database
from src.predictions import get_hit_rate_telemetry, get_fixture_prediction_record
from src.telegram_bot import PitchsideTelegramBot


def test_hit_rate_telemetry_structure():
    db = Database()
    telemetry = get_hit_rate_telemetry(db)

    assert "all_time" in telemetry
    assert "high_confidence" in telemetry
    assert "ultra_confidence" in telemetry
    assert "season_2026" in telemetry
    assert "recent_streak" in telemetry
    assert "recent_hits" in telemetry

    all_t = telemetry["all_time"]
    assert all_t["settled"] >= 1000
    assert all_t["hits"] > 0
    assert 0.50 <= all_t["hit_rate"] <= 0.65
    assert all_t["hit_pct"] > 50.0

    hc = telemetry["high_confidence"]
    assert hc["settled"] > 0
    assert hc["hit_rate"] >= 0.65  # High-confidence picks must be >= 65%

    uc = telemetry["ultra_confidence"]
    assert uc["settled"] > 0
    assert uc["hit_rate"] >= 0.70  # Ultra-confidence picks must be >= 70%

    assert len(telemetry["recent_streak"]) > 0
    assert len(telemetry["recent_hits"]) > 0


def test_fixture_prediction_record():
    db = Database()
    # Check known settled hit fixture (20262489 Real Madrid vs Sevilla)
    rec = get_fixture_prediction_record(db, 20262489)
    assert rec is not None
    assert rec["fixture_id"] == 20262489
    assert rec["result"] == "H"
    assert rec["hit"] == 1
    assert rec["home_score"] == 4
    assert rec["away_score"] == 1


def test_render_hit_rate_view():
    db = Database()
    bot = PitchsideTelegramBot(token="dummy", db=db)
    msg, kb = bot.render_hit_rate_view()

    assert "VERIFIED PREDICTION HIT RATE" in msg
    assert "ALL-TIME 1X2 HIT RATE" in msg
    assert "HIGH-CONFIDENCE PICKS" in msg
    assert "ULTRA-LOCK PICKS" in msg
    assert "RECENT VERIFIED MATCH HITS" in msg

    inline_kb = kb.get("inline_keyboard", [])
    flat_texts = [btn["text"] for row in inline_kb for btn in row]
    assert any("Refresh Hit Rate" in t for t in flat_texts)
    assert any("Main Menu" in t for t in flat_texts)


def test_hit_rate_command_and_callbacks():
    db = Database()
    bot = PitchsideTelegramBot(token="dummy", db=db)

    # Command
    msg, kb = bot.handle_command_or_text("/hitrate", chat_id=123)
    assert "VERIFIED PREDICTION HIT RATE" in msg

    # Callback
    cb_msg, cb_kb, toast = bot.handle_callback_data("hitrate:all", chat_id=123)
    assert "VERIFIED PREDICTION HIT RATE" in cb_msg
    assert "Hit Rate" in toast


def test_match_center_prediction_hit_badge():
    db = Database()
    bot = PitchsideTelegramBot(token="dummy", db=db)
    # Match that was a verified hit (20262489 Real Madrid 4-1 Sevilla)
    msg, kb = bot.render_match_center(20262489)

    assert "PREDICTION HIT!" in msg
    assert "FT 4-1" in msg
    assert "880" in msg or "Verified Wins" in msg


def test_simulation_hit_rate_telemetry():
    db = Database()
    bot = PitchsideTelegramBot(token="dummy", db=db)

    msg_s, kb_s = bot.render_match_simulation_simple(20262489)
    assert "Verified Hit Rate:" in msg_s
    flat_s = [btn["callback_data"] for row in kb_s.get("inline_keyboard", []) for btn in row if "callback_data" in btn]
    assert "hitrate:all" in flat_s

    msg_a, kb_a = bot.render_match_simulation_advanced(20262489)
    assert "Verified Hit Rate:" in msg_a
    flat_a = [btn["callback_data"] for row in kb_a.get("inline_keyboard", []) for btn in row if "callback_data" in btn]
    assert "hitrate:all" in flat_a
