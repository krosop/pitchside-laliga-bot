"""
Tests for Bot Visuals, Club Stadium Banners & Multi-League Switcher
===================================================================
Verifies:
  * ClubBannersRegistry profiles (La Liga, Serie A, Champions League)
  * Resolution of slugs including 'ucl-' prefixes
  * Stadium specs, mottos, anthems, and atmosphere ratings
  * Monospaced scoreboard card double-line box rendering (╔═╤═╗)
  * High-res media header embedding (<a href="...">&#8205;</a>)
  * render_club_banner_card and render_banners_directory layouts
  * Multi-competition switching (/league, /ucl, lg:champions_league)
"""

import pytest
from src.club_banners import ClubBannersRegistry, ClubBannerProfile
from src.telegram_bot import PitchsideTelegramBot
from src.database import Database
from src.champions_league import seed_champions_league_clubs


@pytest.fixture
def bot():
    db = Database()
    seed_champions_league_clubs(db)
    return PitchsideTelegramBot(token="dummy")


def test_club_banners_registry_coverage():
    """Verifies that all major clubs have high-res stadium & spirit profiles."""
    all_banners = ClubBannersRegistry.get_all()
    assert len(all_banners) >= 20

    laliga_banners = ClubBannersRegistry.get_all("laliga")
    assert len(laliga_banners) >= 8

    seriea_banners = ClubBannersRegistry.get_all("serie_a")
    assert len(seriea_banners) >= 5

    ucl_banners = ClubBannersRegistry.get_all("champions_league")
    assert len(ucl_banners) >= 7


def test_club_banners_slug_resolution():
    """Verifies retrieval by exact slug, name substring, and ucl- prefix."""
    # Exact slug
    rm = ClubBannersRegistry.get_by_slug("real-madrid")
    assert rm is not None
    assert "Bernab" in rm.stadium_name
    assert rm.atmosphere_rating >= 95
    assert rm.capacity >= 80000

    # Prefix stripping (ucl-psg -> psg)
    psg = ClubBannersRegistry.get_by_slug("ucl-psg")
    assert psg is not None
    assert "Parc des Princes" in psg.stadium_name
    assert psg.badge_emoji != ""

    # European giant
    liv = ClubBannersRegistry.get_by_slug("ucl-liverpool")
    assert liv is not None
    assert "Anfield" in liv.stadium_name
    assert "You'll Never Walk Alone" in liv.anthem or "Never Walk Alone" in liv.anthem


def test_scoreboard_card_double_line_framing():
    """Verifies that _render_scoreboard_card renders clean double-line Unicode framing."""
    card = PitchsideTelegramBot._render_scoreboard_card(
        h_code="RMA",
        h_name="Real Madrid CF",
        h_score=2,
        a_code="FCB",
        a_name="FC Barcelona",
        a_score=1,
        status_sub="FT · Santiago Bernabéu",
    )
    assert "<pre><code>" in card
    assert "</code></pre>" in card
    assert "╔" in card
    assert "╗" in card
    assert "╠" in card
    assert "╣" in card
    assert "╚" in card
    assert "╝" in card
    assert "RMA" in card
    assert "FCB" in card
    assert "[2]" in card
    assert "[1]" in card


def test_media_header_embedding():
    """Verifies zero-width hidden anchor embedding for Telegram media previews."""
    hdr = PitchsideTelegramBot._render_media_header("https://assets.laliga.com/stadium.png")
    assert hdr == '<a href="https://assets.laliga.com/stadium.png">&#8205;</a>'

    # Fallback to slug banner
    hdr_slug = PitchsideTelegramBot._render_media_header(None, fallback_slug="real-madrid")
    assert "assets.laliga.com" in hdr_slug or "media.api-sports.io" in hdr_slug

    # Empty for invalid/missing
    assert PitchsideTelegramBot._render_media_header(None) == ""


def test_render_club_banner_card(bot):
    """Verifies the layout of the rich Club Stadium & Spirit card."""
    msg, kb = bot.render_club_banner_card("real-madrid")
    assert "ESTADIO SANTIAGO BERNAB" in msg
    assert "Capacity:" in msg
    assert "Atmosphere Rating:" in msg
    assert "Motto:" in msg
    assert "Anthem:" in msg

    inline_kb = kb.get("inline_keyboard", [])
    assert len(inline_kb) >= 2


def test_render_banners_directory(bot):
    """Verifies the stadium directory selector view."""
    msg, kb = bot.render_banners_directory()
    assert "OFFICIAL CLUB STADIUMS" in msg and "SPIRIT DIRECTORY" in msg

    inline_kb = kb.get("inline_keyboard", [])
    assert len(inline_kb) >= 3
    # Check that competition filter buttons exist
    flat_btns = [btn["text"] for row in inline_kb for btn in row]
    assert any("La Liga" in t for t in flat_btns)
    assert any("Serie A" in t for t in flat_btns)
    assert any("UCL" in t for t in flat_btns)


def test_multi_league_switcher(bot):
    """Verifies switching between La Liga, Serie A, and Champions League."""
    # Test setting leagues
    assert bot.set_chat_league(101, "laliga") == "laliga"
    assert bot.get_chat_league(101) == "laliga"

    assert bot.set_chat_league(101, "serie_a") == "serie_a"
    assert bot.get_chat_league(101) == "serie_a"

    assert bot.set_chat_league(101, "champions_league") == "champions_league"
    assert bot.get_chat_league(101) == "champions_league"

    assert bot.set_chat_league(101, "ucl") == "champions_league"
    assert bot.get_chat_league(101) == "champions_league"


def test_bot_ucl_command_and_callbacks(bot):
    """Verifies that /ucl command and callbacks switch league and render correctly."""
    # /ucl command
    msg, kb = bot.handle_command_or_text("/ucl", chat_id=202)
    assert bot.get_chat_league(202) == "champions_league"
    assert "UEFA CHAMPIONS LEAGUE" in msg

    # lg:champions_league callback
    msg, kb, toast = bot.handle_callback_data("lg:champions_league", chat_id=202)
    assert "UEFA Champions League" in toast
    assert "UEFA CHAMPIONS LEAGUE" in msg

    # ucl:standings callback
    st_msg, st_kb, toast = bot.handle_callback_data("ucl:standings", chat_id=202)
    assert "UEFA CHAMPIONS LEAGUE STANDINGS" in st_msg
    assert "36-CLUB" in st_msg or "STANDINGS" in st_msg


def test_psg_theme_and_naming_not_up(bot):
    """Verifies that PSG is never labeled as 'UP' and has official code PSG and badge."""
    theme_slug = bot.get_club_theme("ucl-psg")
    assert theme_slug["code"] == "PSG", f"Expected PSG but got {theme_slug['code']}"
    assert "Paris" in theme_slug["name"]
    assert theme_slug["badge"] == "🔵🔴"

    theme_clean = bot.get_club_theme("psg")
    assert theme_clean["code"] == "PSG"

    # Verify other UCL clubs don't have broken prefixes
    theme_liv = bot.get_club_theme("ucl-liverpool")
    assert theme_liv["code"] == "LIV"

    theme_mci = bot.get_club_theme("ucl-manchester-city")
    assert theme_mci["code"] == "MCI"

    theme_ars = bot.get_club_theme("ucl-arsenal")
    assert theme_ars["code"] == "ARS"


def test_simulation_victory_banner_rendering(bot):
    """Verifies that simulated match winner gets a victory banner and stadium button."""
    db = Database()
    fixtures = db.get_fixtures()
    assert len(fixtures) > 0
    fx = fixtures[0]

    # Simple simulation
    msg, kb = bot.render_match_simulation_simple(fx["id"])
    assert "SIMULATION WINNER" in msg or "Draw" in msg
    if "SIMULATION WINNER" in msg:
        assert "Venue:" in msg
        assert "Capacity:" in msg
        assert "Atmosphere Roar:" in msg
        # Check victory banner button in inline keyboard
        flat_callbacks = [btn["callback_data"] for row in kb.get("inline_keyboard", []) for btn in row if "callback_data" in btn]
        assert any(cb.startswith("cbanner:") for cb in flat_callbacks)

    # Advanced simulation
    adv_msg, adv_kb = bot.render_match_simulation_advanced(fx["id"])
    assert "SIMULATION WINNER" in adv_msg or "Draw" in adv_msg
    if "SIMULATION WINNER" in adv_msg:
        assert "Venue:" in adv_msg
        flat_adv_callbacks = [btn["callback_data"] for row in adv_kb.get("inline_keyboard", []) for btn in row if "callback_data" in btn]
        assert any(cb.startswith("cbanner:") for cb in flat_adv_callbacks)

