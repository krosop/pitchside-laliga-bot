"""
Main entry point for the La Liga Football Player Profiling System.
Boots the web dashboard server or delegates to CLI operations.
"""
import sys
import argparse
from pathlib import Path

from src.database import Database
from src.scraper import LaLigaScraper
from src.server import run_server
from src.telegram_bot import PitchsideTelegramBot, load_bot_token
import src.cli as cli


def check_and_bootstrap_db():
    db = Database()
    counts = db.get_total_counts()
    if counts["players"] == 0:
        print("[!] No player data found in database. Running initial sync from official La Liga feed...")
        scraper = LaLigaScraper()
        profiles = scraper.sync_all(use_cache=True, enrich_bios=False)
        clubs_seen = set()
        for club, profile in profiles:
            if club.id not in clubs_seen:
                db.upsert_club(club)
                clubs_seen.add(club.id)
            db.upsert_player_profile(profile)
        db.export_to_json()
        print(f"[+] Bootstrap complete! {len(profiles)} player profiles ready.")
    else:
        print(f"[+] Loaded existing database with {counts['players']} players across {counts['clubs']} clubs.")


def run_bot_demo():
    """Prints a live preview of the Telegram Bot screens & inline keyboards."""
    import re
    check_and_bootstrap_db()
    bot = PitchsideTelegramBot(token="DEMO")

    def show_screen(label: str, text: str, markup: dict):
        clean_text = re.sub(r"<[^>]+>", "", text)
        clean_text = clean_text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        print(f"\n╔══════════════════════════════════════════════════════════════════╗")
        print(f"║ TELEGRAM BOT PREVIEW: {label:<42} ║")
        print(f"╚══════════════════════════════════════════════════════════════════╝")
        print(clean_text)
        print("\n[INLINE KEYBOARD BUTTONS]:")
        for row in markup.get("inline_keyboard", []):
            row_str = "  ".join(f"[ {btn['text']} ({btn['callback_data']}) ]" for btn in row)
            print(f"  {row_str}")

    gif_url, caption, markup = bot.render_welcome_animation()
    show_screen(f"GIF Welcome & Features Guide (Animation: {gif_url})", caption, markup)
    show_screen("Today's Matches Hub (/today)", *bot.render_home_view())
    md = bot._get_active_matchday()
    show_screen(f"/matches (Matchday {md} Hub)", *bot.render_matchday_view(md))
    fxs = [f for f in bot._get_all_fixtures() if f.get("matchday") == md]
    if fxs:
        fid = fxs[0]["id"]
        show_screen(f"Match Center (m:{fid})", *bot.render_match_center(fid))
        show_screen(f"90' Match Simulation + Trends (sim:{fid})", *bot.render_match_simulation(fid))
    show_screen("/standings (Top 10 + Form)", *bot.render_standings_view("top"))
    show_screen("/club real-betis (Club Tactical DNA)", *bot.render_club_dossier("real-betis"))
    show_screen("/players (Top Scorers Leaderboard)", *bot.render_leaders_view("goals"))


def main():
    parser = argparse.ArgumentParser(description="La Liga Player Profiler System & Telegram Bot")
    parser.add_argument("--cli", nargs=argparse.REMAINDER, help="Run a CLI command (e.g. --cli search mbappe)")
    parser.add_argument("--sync", action="store_true", help="Sync latest official player statistics")
    parser.add_argument("--sync-data", action="store_true", dest="sync_data",
                        help="Refresh match data from the mirrors (football-data.co.uk + ESPN) and recompute Elo ratings")
    parser.add_argument("--enrich", action="store_true",
                        help="Run TheSportsDB imagery/bio enrichment only (badges, cutouts, DOB/height/birthplace)")
    parser.add_argument("--bot", action="store_true",
                        help="Run the interactive Pitchside La Liga Telegram Bot (long polling)")
    parser.add_argument("--bot-with-web", action="store_true", dest="bot_with_web",
                        help="Run both the Telegram Bot and the Web Dashboard Server simultaneously")
    parser.add_argument("--bot-demo", action="store_true", dest="bot_demo",
                        help="Preview all Telegram Bot screens, simulations & inline keyboards in the terminal")
    parser.add_argument("--daily-digest", action="store_true", dest="daily_digest",
                        help="Sync daily data and broadcast Matches of the Day to Telegram subscribers")
    parser.add_argument("--max-runtime", type=int, default=None, dest="max_runtime",
                        help="Optional max runtime in seconds for cloud/GitHub Actions bot polling")
    parser.add_argument("--token", default=None,
                        help="Telegram Bot Token from @BotFather (or set TELEGRAM_BOT_TOKEN in .env)")
    parser.add_argument("--host", default="127.0.0.1", help="Web dashboard host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Web dashboard port (default: 8080)")

    args = parser.parse_args()

    if args.cli:
        sys.argv = ["cli.py"] + args.cli
        cli.main()
        return

    if args.sync:
        sys.argv = ["cli.py", "sync"]
        cli.main()
        return

    if args.enrich:
        import json as _json
        from src.tsdb_feed import run_enrichment
        print(_json.dumps(run_enrichment(), indent=2, default=str))
        return

    if args.sync_data:
        import json as _json
        from src.data_pipeline import refresh
        report = refresh(with_timelines="--timelines" in sys.argv)
        print(_json.dumps(report, indent=2, default=str))
        return

    if args.bot_demo:
        run_bot_demo()
        return

    if args.daily_digest:
        import json as _json
        check_and_bootstrap_db()
        token = load_bot_token(args.token)
        bot = PitchsideTelegramBot(token=token)
        result = bot.send_daily_digest()
        print(_json.dumps(result, indent=2, default=str))
        return

    if args.bot:
        check_and_bootstrap_db()
        token = load_bot_token(args.token)
        bot = PitchsideTelegramBot(token=token)
        bot.run_polling(max_runtime_seconds=args.max_runtime)
        return

    # Default action: ensure DB has data, optionally start Telegram bot if token or --bot-with-web is present, then run web server
    check_and_bootstrap_db()
    token = load_bot_token(args.token)
    if args.bot_with_web or token:
        bot = PitchsideTelegramBot(token=token)
        if token:
            bot.start_background_thread()
        elif args.bot_with_web:
            bot.run_polling(max_runtime_seconds=args.max_runtime)  # Prints token setup guide

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

