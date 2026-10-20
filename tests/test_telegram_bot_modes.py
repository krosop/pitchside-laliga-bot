"""
Automated unit tests for the upgraded Telegram Bot (@xbetbetterbot):
- Simple Mode (clean 5-second check, club crests, scorers, 10,000-draw Gut Feeling probabilities & fair odds)
- Advanced Mode (deep telemetry, 6-phase momentum, incident timeline, Gut Feeling math engine)
- Gut Feeling 10k Prediction Dossier & /gut command
- Welcome GIF animation (<1024 char caption) & sendPhoto support
"""
import pytest
from src.telegram_bot import PitchsideTelegramBot
from src.database import Database


@pytest.fixture(scope="module")
def bot():
    db = Database()
    return PitchsideTelegramBot(token="123456:dummy_test_token", db=db)


def test_welcome_animation_under_telegram_limits(bot):
    gif_url, caption, markup = bot.render_welcome_animation()
    assert gif_url.startswith("http"), "Invalid GIF URL"
    assert len(caption) < 1024, f"Caption exceeds Telegram's 1024-char limit: {len(caption)}"
    assert "<b>" in caption and "</b>" in caption, "Caption should be formatted in valid HTML"
    assert "inline_keyboard" in markup, "Missing inline keyboard markup"


def test_welcome_text_content(bot):
    text, markup = bot.render_welcome_text()
    assert "Simple Mode" in text
    assert "Advanced Mode" in text
    assert "Gut Feeling AI" in text
    assert "/gut" in text


def test_simple_simulation_mode_with_gut_feeling(bot):
    fixtures = bot._get_all_fixtures()
    assert len(fixtures) > 0, "No fixtures available"
    fid = fixtures[0]["id"]

    text, markup = bot.render_match_simulation_simple(fid)
    assert "SIMPLE MODE" in text
    assert "GUT FEELING 10,000-DRAW SIMULATION" in text
    assert "Fair Decimal Odds:" in text
    assert "Expected Goals:" in text

    buttons = [b["text"] for row in markup.get("inline_keyboard", []) for b in row]
    assert any("Switch to Advanced" in b for b in buttons)
    assert any("Gut Feeling Dossier" in b for b in buttons)


def test_advanced_simulation_mode_with_mathematical_engine(bot):
    fixtures = bot._get_all_fixtures()
    fid = fixtures[0]["id"]

    text, markup = bot.render_match_simulation_advanced(fid)
    assert "ADVANCED MODE" in text
    assert "GUT FEELING MATHEMATICAL ENGINE" in text
    assert "Elo Anchor:" in text
    assert "3-Match Form:" in text
    assert "10,000 Draws:" in text
    assert "Fair Decimal Odds:" in text

    buttons = [b["text"] for row in markup.get("inline_keyboard", []) for b in row]
    assert any("Switch to Simple" in b for b in buttons)
    assert any("Gut Feeling Dossier" in b for b in buttons)


def test_gut_feeling_view_and_command(bot):
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


def test_send_photo_method(bot):
    assert hasattr(bot, "send_photo"), "send_photo method should exist on bot"
