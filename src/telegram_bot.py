"""
PITCHSIDE — La Liga EA SPORTS Interactive Telegram Bot
======================================================
Transforms the entire La Liga Profiler & Match Simulation platform into a
rich, interactive Telegram Chat Bot with inline keyboards, visual ASCII/Unicode
charts, 90-minute tactical match simulation, live standings, club tactical DNA
dossiers, and player telemetry profiles.

Zero external pip dependencies required (uses standard library urllib.request).
"""
import html
import json
import math
import os
import sys
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .database import Database
from .comparator import PlayerComparator
from .simulation_engine import SimulationEngine
from .club_tactics import ClubTacticsRegistry, CLUB_TACTICAL_DNA


# Ensure UTF-8 output on Windows consoles
if sys.stdout and getattr(sys.stdout, "encoding", None) != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_bot_token(cli_token: Optional[str] = None) -> Optional[str]:
    """
    Loads the Telegram Bot Token from (in priority order):
    1. Explicit CLI --token argument
    2. Environment variables TELEGRAM_BOT_TOKEN or BOT_TOKEN
    3. .env file in project root
    4. config/telegram.json in project root
    """
    if cli_token and cli_token.strip():
        return cli_token.strip()

    for env_key in ("TELEGRAM_BOT_TOKEN", "BOT_TOKEN"):
        val = os.environ.get(env_key, "").strip()
        if val and val != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
            return val

    base_dir = Path(__file__).resolve().parent.parent

    # Check .env file
    env_file = base_dir / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k in ("TELEGRAM_BOT_TOKEN", "BOT_TOKEN") and v and v != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
                    return v
        except Exception:
            pass

    # Check config/telegram.json
    cfg_file = base_dir / "config" / "telegram.json"
    if cfg_file.exists():
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            tok = (data.get("bot_token") or data.get("token") or "").strip()
            if tok and tok != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
                return tok
        except Exception:
            pass

    return None


class PitchsideTelegramBot:
    """
    Full-featured Telegram Bot engine for La Liga EA SPORTS Analytics & Match Simulation.
    """

    WELCOME_GIF_URL: str = "https://media1.tenor.com/m/tgsrfDxv17MAAAAd/neyma.gif"

    CLUB_THEMES: Dict[str, Dict[str, str]] = {
        "barcelona": {"code": "FCB", "badge": "🔵🔴", "name": "Barcelona"},
        "real-madrid": {"code": "RMA", "badge": "⚪🟣", "name": "Real Madrid"},
        "atletico": {"code": "ATM", "badge": "🔴⚪", "name": "Atlético Madrid"},
        "betis": {"code": "BET", "badge": "🟢⚪", "name": "Real Betis"},
        "sociedad": {"code": "RSO", "badge": "⚪🔵", "name": "Real Sociedad"},
        "sevilla": {"code": "SEV", "badge": "⚪🔴", "name": "Sevilla"},
        "alaves": {"code": "ALV", "badge": "🔵⚪", "name": "Alavés"},
        "celta": {"code": "CEL", "badge": "🩵", "name": "Celta Vigo"},
        "deportivo": {"code": "DEP", "badge": "🔵⚪", "name": "Deportivo"},
        "osasuna": {"code": "OSA", "badge": "🔴🔵", "name": "Osasuna"},
        "athletic": {"code": "ATH", "badge": "🔴⚪", "name": "Athletic Club"},
        "villarreal": {"code": "VIL", "badge": "🟡", "name": "Villarreal"},
        "espanyol": {"code": "ESP", "badge": "⚪🔵", "name": "Espanyol"},
        "rayo": {"code": "RAY", "badge": "⚪⚡", "name": "Rayo Vallecano"},
        "getafe": {"code": "GET", "badge": "🔵", "name": "Getafe"},
        "racing": {"code": "RAC", "badge": "🟢⚪", "name": "Racing Santander"},
        "levante": {"code": "LEV", "badge": "🔴🔵", "name": "Levante"},
        "elche": {"code": "ELC", "badge": "🟢⚪", "name": "Elche"},
        "valencia": {"code": "VAL", "badge": "⚪🦇", "name": "Valencia"},
        "malaga": {"code": "MAL", "badge": "⚪🔵", "name": "Málaga"},
        "girona": {"code": "GIR", "badge": "🔴⚪", "name": "Girona"},
        "mallorca": {"code": "MLL", "badge": "🔴⚫", "name": "Mallorca"},
        "leganes": {"code": "LEG", "badge": "🔵⚪", "name": "Leganés"},
        "valladolid": {"code": "VLL", "badge": "🟣⚪", "name": "Real Valladolid"},
        "palmas": {"code": "LPA", "badge": "🟡🔵", "name": "Las Palmas"},
    }

    @classmethod
    def get_club_theme(cls, slug_or_name: str) -> Dict[str, str]:
        s = (slug_or_name or "").lower().replace(" ", "-")
        for k, v in cls.CLUB_THEMES.items():
            if k in s:
                return v
        code = "".join([part[0] for part in s.split("-") if part])[:3].upper() or "LAL"
        return {"code": code, "badge": "⚽", "name": slug_or_name}

    def __init__(
        self,
        token: Optional[str] = None,
        db: Optional[Database] = None,
        send_new_messages: Optional[bool] = None,
    ):
        self.token = token
        self.db = db or Database()
        self.sim_engine = SimulationEngine(self.db)
        self.comparator = PlayerComparator(self.db)
        self._detail_cache: Dict[int, Tuple[float, Dict[str, Any]]] = {}
        self._standings_cache: Optional[Tuple[float, List[Dict[str, Any]]]] = None
        self._fixtures_cache: Optional[Tuple[float, List[Dict[str, Any]]]] = None
        self._running = False
        self._offset = 0
        if send_new_messages is not None:
            self.send_new_messages: bool = bool(send_new_messages)
        else:
            env_val = os.environ.get("TELEGRAM_SEND_NEW_MESSAGES", "0").strip().lower()
            self.send_new_messages = env_val in ("1", "true", "yes", "new")

    # =========================================================================
    # TELEGRAM HTTP API HELPERS
    # =========================================================================
    @property
    def api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    def _api_call(self, method: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 35) -> Dict[str, Any]:
        if not self.token:
            raise RuntimeError("Telegram Bot token is not configured.")
        url = f"{self.api_base}/{method}"
        data_bytes = None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if payload is not None:
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST" if data_bytes else "GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            # Ignore harmless "message is not modified" error on editMessageText
            if "message is not modified" in err_body:
                return {"ok": True, "not_modified": True}
            print(f"[Telegram API Error] {method} -> HTTP {e.code}: {err_body}")
            return {"ok": False, "error_code": e.code, "description": err_body}
        except Exception as e:
            print(f"[Telegram Network Error] {method} -> {e}")
            return {"ok": False, "description": str(e)}

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        if len(text) > 4050:
            text = text[:4040] + "\n..."
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._api_call("sendMessage", payload)

    def send_animation(
        self,
        chat_id: int,
        animation: str,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        """
        Sends an animation/GIF to a Telegram chat via sendAnimation API.
        Respects Telegram's 1024-character caption limit and automatically
        falls back to sendMessage if animation delivery fails.
        """
        if caption and len(caption) > 1024:
            caption = caption[:1020] + "..."
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "animation": animation,
            "parse_mode": parse_mode,
        }
        if caption:
            payload["caption"] = caption
        if reply_markup:
            payload["reply_markup"] = reply_markup
        res = self._api_call("sendAnimation", payload)
        if not res.get("ok"):
            # Fallback to standard text message if animation dispatch fails
            return self.send_message(chat_id, caption or "", reply_markup=reply_markup, parse_mode=parse_mode)
        return res

    def edit_or_send(
        self,
        chat_id: int,
        message_id: Optional[int],
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        if len(text) > 4050:
            text = text[:4040] + "\n..."
        if message_id:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            res = self._api_call("editMessageText", payload)
            if res.get("ok"):
                return res
            # If editMessageText failed (e.g. previous message was an animation/photo),
            # delete the old message so the screen updates cleanly in-place!
            self.delete_message(chat_id, message_id)
        return self.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)

    def delete_message(self, chat_id: int, message_id: int) -> Dict[str, Any]:
        """Deletes a message from a chat via deleteMessage API."""
        return self._api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id}, timeout=10)

    def answer_callback(self, callback_query_id: str, text: Optional[str] = None, show_alert: bool = False):
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text[:190]
        self._api_call("answerCallbackQuery", payload, timeout=10)

    def register_commands(self):
        commands = [
            {"command": "start", "description": "🟢 Welcome & What This Bot Does (GIF Guide)"},
            {"command": "today", "description": "📅 Matches of the Day, Odds & Quick Sim"},
            {"command": "matches", "description": "⚽ All 38 Matchdays Schedule & Results"},
            {"command": "simulate", "description": "⚡ 90-Minute Match Simulator & Trends"},
            {"command": "standings", "description": "🏆 Live La Liga Table & Form Guide"},
            {"command": "clubs", "description": "🛡️ All 20 Club Tactical DNA Dossiers"},
            {"command": "players", "description": "🌟 Leaderboards, Ratings & Player Search"},
            {"command": "compare", "description": "⚔️ Compare 2 Players or Clubs Head-to-Head"},
            {"command": "msgmode", "description": "💬 Toggle New Messages vs In-Place Edits"},
            {"command": "help", "description": "ℹ️ Bot Guide & Features Overview"},
        ]
        try:
            self._api_call("setChatMenuButton", {"menu_button": {"type": "commands"}}, timeout=15)
        except Exception:
            pass
        return self._api_call("setMyCommands", {"commands": commands}, timeout=15)

    # =========================================================================
    # DATA & FORMATTING HELPERS
    # =========================================================================
    @staticmethod
    def _render_scoreboard_card(
        h_code: str,
        h_name: str,
        h_score: Any,
        a_code: str,
        a_name: str,
        a_score: Any,
        status_sub: str,
        width: int = 32,
    ) -> str:
        """
        Renders a clean, monospaced card frame for scores and fixtures in <pre><code>.
        """
        h_line = f"{h_code:<4} {h_name[:15]:<15} {str(h_score):>4}"
        a_line = f"{a_code:<4} {a_name[:15]:<15} {str(a_score):>4}"
        sub_line = (status_sub or "")[:width - 4]
        box = [
            "┌" + ("─" * (width - 2)) + "┐",
            f"│ {h_line:<{width - 4}} │",
            f"│ {a_line:<{width - 4}} │",
            "├" + ("─" * (width - 2)) + "┤",
            f"│ {sub_line:<{width - 4}} │",
            "└" + ("─" * (width - 2)) + "┘",
        ]
        return "<pre><code>" + "\n".join(box) + "</code></pre>"

    @staticmethod
    def _esc(val: Any) -> str:
        return html.escape(str(val if val is not None else ""))

    @staticmethod
    def _progress_bar(value: float, max_val: float = 100.0, width: int = 10, filled: str = "█", empty: str = "░") -> str:
        pct = max(0.0, min(1.0, float(value) / float(max_val or 1.0)))
        fill_cnt = int(round(pct * width))
        return (filled * fill_cnt) + (empty * (width - fill_cnt))

    @staticmethod
    def _dual_bar(home_pct: float, away_pct: float, width: int = 12) -> str:
        total = (home_pct + away_pct) or 100.0
        h_blocks = int(round((home_pct / total) * width))
        h_blocks = max(1, min(width - 1, h_blocks))
        a_blocks = width - h_blocks
        return ("🟩" * h_blocks) + ("🟦" * a_blocks)

    @staticmethod
    def _prob_bar(h_pct: float, d_pct: float, a_pct: float, width: int = 12) -> str:
        total = (h_pct + d_pct + a_pct) or 100.0
        h_b = max(1, int(round((h_pct / total) * width)))
        a_b = max(1, int(round((a_pct / total) * width)))
        d_b = max(1, width - h_b - a_b)
        if h_b + d_b + a_b > width:
            if h_b >= a_b and h_b > 1:
                h_b -= 1
            elif a_b > 1:
                a_b -= 1
        return ("🟩" * h_b) + ("⬜" * d_b) + ("🟥" * a_b)

    def _get_standings(self) -> List[Dict[str, Any]]:
        now = time.time()
        if self._standings_cache and now - self._standings_cache[0] < 30.0:
            return self._standings_cache[1]
        st = self.db.get_standings()
        self._standings_cache = (now, st)
        return st

    def _get_all_fixtures(self) -> List[Dict[str, Any]]:
        now = time.time()
        if self._fixtures_cache and now - self._fixtures_cache[0] < 30.0:
            return self._fixtures_cache[1]
        raw_fx = self.db.get_fixtures()
        status_prio = {"LIVE": 0, "FINISHED": 1, "SCHEDULED": 2}
        raw_fx.sort(
            key=lambda x: (
                (x.get("kickoff_time") or "")[:16],
                status_prio.get(x.get("status", "SCHEDULED"), 3),
                x.get("id") or 0,
            )
        )
        seen = set()
        fx = []
        for f in raw_fx:
            date_part = (f.get("kickoff_time") or "")[:10]
            key = (date_part, f.get("home_slug"), f.get("away_slug"))
            if key in seen:
                continue
            seen.add(key)
            fx.append(f)

        self._fixtures_cache = (now, fx)
        return fx

    def _get_match_dates(self) -> List[str]:
        fixtures = self._get_all_fixtures()
        dates = sorted({(f.get("kickoff_time") or "")[:10] for f in fixtures if (f.get("kickoff_time") or "")[:10]})
        return dates

    def _resolve_active_date(self, requested_date: Optional[str] = None) -> Tuple[str, str, bool]:
        """
        Returns (today_iso, resolved_match_date_iso, is_exact_today).
        If today has matches, resolved_match_date == today.
        Otherwise resolves to the closest upcoming match date (or latest available).
        """
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        dates = self._get_match_dates()
        if not dates:
            return today_str, today_str, True

        if requested_date and requested_date != "today":
            return today_str, requested_date, (requested_date == today_str)

        if today_str in dates:
            return today_str, today_str, True

        upcoming = [d for d in dates if d >= today_str]
        if upcoming:
            return today_str, upcoming[0], False
        return today_str, dates[-1], False

    def _get_active_matchday(self) -> int:
        """Finds the current active/upcoming matchday based on today's date."""
        _, active_date, _ = self._resolve_active_date("today")
        fixtures = self._get_all_fixtures()
        day_fxs = [f for f in fixtures if (f.get("kickoff_time") or "")[:10] == active_date]
        if day_fxs and day_fxs[0].get("matchday"):
            return int(day_fxs[0]["matchday"])
        return self.db.get_current_matchday()

    def _get_match_detail(self, fid: int) -> Optional[Dict[str, Any]]:
        now = time.time()
        hit = self._detail_cache.get(fid)
        if hit and now - hit[0] < 120.0:
            return dict(hit[1])
        detail = self.db.get_match_detail(fid)
        if not detail:
            return None
        h_slug = detail.get("home_team", {}).get("slug", "")
        a_slug = detail.get("away_team", {}).get("slug", "")
        h_pos = detail.get("home_team", {}).get("position") or 10
        a_pos = detail.get("away_team", {}).get("position") or 10
        detail["tactical_clash"] = ClubTacticsRegistry.evaluate_tactical_clash(h_slug, a_slug, h_pos, a_pos)
        detail["forecast"] = self.sim_engine.monte_carlo_forecast(detail)
        self._detail_cache[fid] = (now, detail)
        return dict(detail)

    def _get_club_form_emojis(self, slug: str, count: int = 5) -> str:
        fixtures = self._get_all_fixtures()
        finished = [
            f for f in fixtures
            if f.get("status") == "FINISHED" and (f.get("home_slug") == slug or f.get("away_slug") == slug)
        ]
        recent = finished[-count:]
        if not recent:
            return "⚪⚪⚪⚪⚪"
        dots = []
        for f in recent:
            is_home = f.get("home_slug") == slug
            hs = f.get("home_score") or 0
            as_ = f.get("away_score") or 0
            my_s = hs if is_home else as_
            op_s = as_ if is_home else hs
            if my_s > op_s:
                dots.append("🟢")
            elif my_s == op_s:
                dots.append("🟡")
            else:
                dots.append("🔴")
        return "".join(dots)

    def _compute_quick_odds(self, f: Dict[str, Any]) -> Tuple[str, str, str]:
        """Computes realistic 3-way decimal odds (1, X, 2) for a fixture row."""
        standings = {c["slug"]: c for c in self._get_standings()}
        hc = standings.get(f.get("home_slug"), {})
        ac = standings.get(f.get("away_slug"), {})
        h_ovr = (hc.get("overall_rating") or 76) + 3.0  # Home pitch edge
        a_ovr = float(ac.get("overall_rating") or 75)
        diff = h_ovr - a_ovr
        p_h = max(0.15, min(0.76, 0.44 + diff * 0.018))
        p_d = max(0.16, min(0.32, 0.27 - abs(diff) * 0.005))
        p_a = max(0.10, 1.0 - p_h - p_d)
        margin = 1.05
        o1 = max(1.18, round(1.0 / (p_h * margin), 2))
        ox = max(2.80, round(1.0 / (p_d * margin), 2))
        o2 = max(1.22, round(1.0 / (p_a * margin), 2))
        return f"{o1:.2f}", f"{ox:.2f}", f"{o2:.2f}"

    def _get_player_by_id_or_slug(self, identifier: str) -> Optional[Dict[str, Any]]:
        ident = str(identifier).strip()
        if ident.isdigit():
            with self.db.get_connection() as conn:
                row = conn.execute("SELECT slug FROM players WHERE id = ?", (int(ident),)).fetchone()
                if row and row["slug"]:
                    return self.db.get_player_by_slug(row["slug"])
        return self.db.get_player_by_slug(ident)

    # =========================================================================
    # VIEW 0: WELCOME & WHAT BOT DOES (GIF + CAPTION) (/start, /help, /about)
    # =========================================================================
    def render_welcome_animation(self) -> Tuple[str, str, Dict[str, Any]]:
        """
        Returns (gif_url, caption_html, reply_markup) explaining all bot capabilities.
        Caption is formatted in HTML and strictly within Telegram's 1024-char limit.
        """
        caption, markup = self.render_welcome_text()
        return self.WELCOME_GIF_URL, caption, markup

    def render_welcome_text(self) -> Tuple[str, Dict[str, Any]]:
        """
        Renders the comprehensive overview of what the bot does with interactive buttons.
        """
        caption = (
            "⚡ <b>WELCOME TO PITCHSIDE LA LIGA BOT!</b> ⚽\n\n"
            "Your elite real-time <b>La Liga tactical terminal &amp; match simulation engine</b> directly in Telegram!\n\n"
            "🔥 <b>What I Can Do For You:</b>\n"
            "• 📅 <b>Matches of the Day:</b> Daily schedule, real-time status &amp; betting odds\n"
            "• ⚡ <b>90' Tactical Match Simulator:</b> Dixon-Coles Poisson engine, club tactical DNA, player form &amp; European fatigue\n"
            "• 🚫 <b>Suspension &amp; Injury Tracking:</b> Automatic detection of red cards &amp; injuries, excluding sidelined players &amp; updating live ratings\n"
            "• 🌊 <b>Predictive Telemetry:</b> 6-phase match dominance, attack momentum wave, cumulative xG &amp; win probability flow\n"
            "• 🏆 <b>Live Standings &amp; Form Guide:</b> 20-club league table, UCL/UEL zones &amp; 5-match form dots\n"
            "• 🛡️ <b>Club Tactical DNA &amp; Scouting:</b> In-depth dossiers for all 20 clubs &amp; 500+ players\n"
            "• ⚔️ <b>Head-to-Head Compare:</b> Club vs Club &amp; Player vs Player duels\n\n"
            "<i>Select an option below to start exploring! 👇</i>"
        )
        current_md = self._get_active_matchday()
        kb = [
            [
                {"text": "📅 Matches of the Day", "callback_data": "day:today"},
                {"text": "⚡ Sim Today", "callback_data": "daysim:today"},
            ],
            [
                {"text": "⚽ All 38 Matchdays", "callback_data": f"md:{current_md}"},
                {"text": "🏆 Standings & Form", "callback_data": "st:all"},
            ],
            [
                {"text": "🛡️ 20 Clubs Tactical DNA", "callback_data": "clubs"},
                {"text": "🌟 Top Scorers & Scouting", "callback_data": "ldr:goals"},
            ],
            [
                {"text": "⚔️ Compare H2H", "callback_data": "cmp"},
                {"text": "🔄 Sync Live Data", "callback_data": "sync"},
            ],
        ]
        return caption, {"inline_keyboard": kb}

    def send_welcome(self, chat_id: int) -> Dict[str, Any]:
        """Sends the welcome Neymar animation and guide to a specific chat_id."""
        gif_url, caption, markup = self.render_welcome_animation()
        return self.send_animation(chat_id, gif_url, caption=caption, reply_markup=markup)

    def send_welcome_to_all_subscribers(self) -> int:
        """Broadcasts the welcome animation and guide to all registered subscribers."""
        subs = self.get_active_subscribers()
        gif_url, caption, markup = self.render_welcome_animation()
        sent = 0
        for cid in subs:
            if cid:
                res = self.send_animation(cid, gif_url, caption=caption, reply_markup=markup)
                if res.get("ok"):
                    sent += 1
        return sent

    def render_msgmode_view(self) -> Tuple[str, Dict[str, Any]]:
        """Renders the message delivery mode toggle card (In-Place Updates vs New Messages)."""
        mode_desc = (
            "✏️ <b>In-Place Updates (Default)</b> — Button clicks edit and update the current message in-place"
            if not self.send_new_messages
            else "🆕 <b>Fresh New Messages</b> — Button clicks send a new message into the chat"
        )
        next_action = "New Messages" if not self.send_new_messages else "In-Place Updates"
        resp = (
            f"💬 <b>NAVIGATION MESSAGE MODE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Current Mode: {mode_desc}\n\n"
            f"• <b>In-Place Updates (Default)</b>: Every button click cleanly updates the existing message without chat clutter.\n"
            f"• <b>New Messages</b>: Button clicks send fresh cards into the chat to preserve history.\n\n"
            f"<i>Tap the button below or type <code>/msgmode</code> to toggle anytime.</i>"
        )
        kb = [
            [{"text": f"🔄 Switch to {next_action}", "callback_data": "msgmode:toggle"}],
            [{"text": "📅 Matches of the Day", "callback_data": "day:today"}, {"text": "🏠 Main Menu", "callback_data": "menu:home"}],
        ]
        return resp, {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 1: DAILY MATCHES OF THE DAY & MAIN HUB (/today, day:<date>)
    # =========================================================================
    def render_home_view(self, requested_date: Optional[str] = None, chat_id: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
        from datetime import datetime
        today_str, active_date, is_exact_today = self._resolve_active_date(requested_date)
        all_dates = self._get_match_dates()
        fixtures = self._get_all_fixtures()
        day_fixtures = [f for f in fixtures if (f.get("kickoff_time") or "")[:10] == active_date]
        standings_map = {c["slug"]: c for c in self._get_standings()}

        try:
            dt_obj = datetime.strptime(active_date, "%Y-%m-%d")
            pretty_date = dt_obj.strftime("%A, %d %b %Y")
        except Exception:
            pretty_date = active_date

        if active_date == today_str:
            date_badge = f"🟢 <b>TODAY'S MATCHES · {self._esc(pretty_date.upper())}</b>"
        else:
            date_badge = (
                f"📅 <b>MATCHES FOR {self._esc(pretty_date.upper())}</b>\n"
                f"<i>(Today is {today_str})</i>"
            )

        lines = [
            "⚽ <b>PITCHSIDE · LA LIGA DAILY MATCH CENTER</b>",
            date_badge,
            "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        ]

        kb = []
        if not day_fixtures:
            lines.append("\n<i>No La Liga fixtures scheduled on this date. Use the date buttons below to browse match days!</i>")
        else:
            for idx, f in enumerate(day_fixtures, 1):
                h_name = f.get("home_nickname") or f.get("home_name") or "Home"
                a_name = f.get("away_nickname") or f.get("away_name") or "Away"
                h_theme = self.get_club_theme(f.get("home_slug") or h_name)
                a_theme = self.get_club_theme(f.get("away_slug") or a_name)
                h_rank = (standings_map.get(f.get("home_slug")) or {}).get("position") or "-"
                a_rank = (standings_map.get(f.get("away_slug")) or {}).get("position") or "-"
                st = f.get("status", "SCHEDULED")
                o1, ox, o2 = self._compute_quick_odds(f)
                ko_time = (f.get("kickoff_time") or "")[11:16] or "19:00"

                if st == "FINISHED":
                    hs, as_ = f.get("home_score", 0), f.get("away_score", 0)
                    goals = f.get("goals") or []
                    scorers = ", ".join(f"{g.get('scorer')} {g.get('minute')}'" for g in goals[:3])
                    scorer_line = f"\n   └ ⚽ <i>{self._esc(scorers)}</i>" if scorers else ""
                    lines.append(
                        f"\n🏁 <b>{idx}. {h_theme['badge']} {h_theme['code']}  <code>{hs} - {as_}</code>  {a_theme['code']} {a_theme['badge']}</b> (FT){scorer_line}"
                    )
                    btn_main = f"📊 {h_theme['code']} {hs}-{as_} {a_theme['code']}"
                elif st == "LIVE":
                    hs, as_ = f.get("home_score", 0), f.get("away_score", 0)
                    lines.append(
                        f"\n🔴 <b>{idx}. {h_theme['badge']} {h_theme['code']}  <code>{hs} - {as_}</code>  {a_theme['code']} {a_theme['badge']}</b> (LIVE)"
                    )
                    btn_main = f"🔴 {h_theme['code']} {hs}-{as_} {a_theme['code']}"
                else:
                    lines.append(
                        f"\n🕒 <b>{idx}. [{ko_time} UTC] {h_theme['badge']} {h_theme['code']} vs {a_theme['code']} {a_theme['badge']}</b>\n"
                        f"   └ 🎲 Odds: <code>1: {o1}</code> · <code>X: {ox}</code> · <code>2: {o2}</code>"
                    )
                    btn_main = f"🏟️ {h_theme['code']} vs {a_theme['code']}"

                kb.append([
                    {"text": btn_main, "callback_data": f"m:{f['id']}"},
                    {"text": "⚡ Sim 90'", "callback_data": f"sim:{f['id']}"},
                ])

            lines.append(
                f"\n👇 <b>Tap a match above to preview/simulate, or move to another section below:</b>"
            )
            kb.append([
                {"text": f"⚡ Simulate All {len(day_fixtures)} Matches on {active_date[5:]}", "callback_data": f"daysim:{active_date}"}
            ])

        # Date Navigation Bar (Prev Match Date / Today / Next Match Date)
        nav_dates = []
        if active_date in all_dates:
            cur_idx = all_dates.index(active_date)
            if cur_idx > 0:
                prev_d = all_dates[cur_idx - 1]
                nav_dates.append({"text": f"◀ {prev_d[5:]}", "callback_data": f"day:{prev_d}"})
            if active_date != today_str:
                nav_dates.append({"text": "📍 Today", "callback_data": "day:today"})
            if cur_idx + 1 < len(all_dates):
                next_d = all_dates[cur_idx + 1]
                nav_dates.append({"text": f"{next_d[5:]} ▶", "callback_data": f"day:{next_d}"})
        if nav_dates:
            kb.append(nav_dates)

        # "Move to Other Things" Navigation Hub
        current_md = self._get_active_matchday()
        is_sub = self.is_subscribed(chat_id) if chat_id else True
        sub_btn = {"text": "🔔 Daily Alerts: ON" if is_sub else "🔕 Daily Alerts: OFF", "callback_data": "sub:toggle"}
        kb.extend([
            [
                {"text": "🏆 Standings & Form", "callback_data": "st:all"},
                {"text": f"📅 All 38 Matchdays", "callback_data": f"md:{current_md}"},
            ],
            [
                {"text": "🛡️ 20 Clubs & DNA", "callback_data": "clubs:list"},
                {"text": "🌟 Top Scorers & Players", "callback_data": "ldr:goals"},
            ],
            [
                {"text": "⚔️ Compare H2H", "callback_data": "cmp:menu"},
                {"text": "🔄 Update Daily Data", "callback_data": "sync:now"},
            ],
            [
                sub_btn,
                {"text": "ℹ️ What Bot Does (GIF Guide)", "callback_data": "menu:welcome"},
            ],
        ])
        return "\n".join(lines), {"inline_keyboard": kb}

    def render_daily_simulation(self, date_str: str) -> Tuple[str, Dict[str, Any]]:
        """Simulates all matches scheduled on a specific calendar date (daysim:<YYYY-MM-DD>)."""
        fixtures = [f for f in self._get_all_fixtures() if (f.get("kickoff_time") or "")[:10] == date_str]
        if not fixtures:
            return self.render_home_view(date_str)

        lines = [
            f"⚡ <b>DAILY MATCHES SIMULATION · {self._esc(date_str)}</b>",
            "<i>Calibrated Dixon-Coles + Club Tactical DNA + Player Form</i>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        kb = []
        total_goals = 0
        for idx, f in enumerate(fixtures, 1):
            detail = self._get_match_detail(f["id"])
            if not detail:
                continue
            sim = self.sim_engine.simulate_fixture(detail)
            hs, as_ = sim["home_score"], sim["away_score"]
            total_goals += hs + as_
            h_name = f.get("home_nickname") or f.get("home_name")
            a_name = f.get("away_nickname") or f.get("away_name")
            stats = sim.get("stats", {})
            h_xg = stats.get("xg", {}).get("home", 0.0)
            a_xg = stats.get("xg", {}).get("away", 0.0)
            h_poss = stats.get("possession", {}).get("home", 50)
            a_poss = stats.get("possession", {}).get("away", 50)
            goal_events = [e for e in sim.get("events", []) if e.get("type") == "goal"]
            goal_str = ", ".join(f"{e.get('scorer')} {e.get('minute')}'" for e in goal_events[:4])

            lines.append(
                f"\n<b>{idx}. {self._esc(h_name)}  <code>{hs} - {as_}</code>  {self._esc(a_name)}</b>\n"
                f"   📊 xG: <code>{h_xg:.2f} - {a_xg:.2f}</code> · Poss: <code>{h_poss}%-{a_poss}%</code>"
                + (f"\n   ⚽ <i>{self._esc(goal_str)}</i>" if goal_str else "\n   🧤 <i>Tactical defensive deadlock</i>")
            )
            kb.append([
                {"text": f"🔍 Full 90' Report: {h_name[:10]} {hs}-{as_} {a_name[:10]}", "callback_data": f"sim:{f['id']}"}
            ])

        kb.append([
            {"text": f"◀ Back to {date_str[5:]} Matches", "callback_data": f"day:{date_str}"},
            {"text": "🏠 Today's Matches", "callback_data": "day:today"},
        ])
        return "\n".join(lines), {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 2: MATCHDAY FIXTURES HUB (/matches, md:<num>)
    # =========================================================================
    def render_matchday_view(self, matchday: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
        current_md = self._get_active_matchday()
        md = int(matchday) if matchday else current_md
        md = max(1, min(38, md))

        raw_md = [f for f in self._get_all_fixtures() if f.get("matchday") == md]
        # Keep up to 10 non-overlapping club fixtures for the selected round
        used_clubs = set()
        fixtures = []
        for f in raw_md:
            hs_slug, as_slug = f.get("home_slug"), f.get("away_slug")
            if hs_slug in used_clubs or as_slug in used_clubs:
                continue
            used_clubs.add(hs_slug)
            used_clubs.add(as_slug)
            fixtures.append(f)
        finished_cnt = sum(1 for f in fixtures if f.get("status") == "FINISHED")

        status_tag = "✅ COMPLETED ROUND" if finished_cnt == len(fixtures) and fixtures else (
            "🟢 CURRENT ACTIVE ROUND" if md == current_md else "📅 UPCOMING SCHEDULE"
        )

        lines = [
            f"⚽ <b>LA LIGA MATCHDAY {md} HUB</b>",
            f"<code>{status_tag}</code>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        match_buttons = []
        current_row = []

        for idx, f in enumerate(fixtures, 1):
            h_name = f.get("home_nickname") or f.get("home_name") or "Home"
            a_name = f.get("away_nickname") or f.get("away_name") or "Away"
            st = f.get("status", "SCHEDULED")
            o1, ox, o2 = self._compute_quick_odds(f)

            if st == "FINISHED":
                hs, as_ = f.get("home_score", 0), f.get("away_score", 0)
                goals = f.get("goals") or []
                scorers = ", ".join(f"{g.get('scorer')} {g.get('minute')}'" for g in goals[:3])
                scorer_line = f"\n   └ ⚽ <i>{self._esc(scorers)}</i>" if scorers else ""
                lines.append(
                    f"<b>{idx}. {self._esc(h_name)}  <code>{hs} - {as_}</code>  {self._esc(a_name)}</b> (FT){scorer_line}"
                )
                btn_label = f"📊 {h_name[:10]} {hs}-{as_} {a_name[:10]}"
            elif st == "LIVE":
                hs, as_ = f.get("home_score", 0), f.get("away_score", 0)
                lines.append(
                    f"🔴 <b>{idx}. {self._esc(h_name)}  <code>{hs} - {as_}</code>  {self._esc(a_name)}</b> (LIVE)"
                )
                btn_label = f"🔴 {h_name[:10]} {hs}-{as_} {a_name[:10]}"
            else:
                ko = (f.get("kickoff_time") or "TBD").replace("T", " ")[:16]
                lines.append(
                    f"🕒 <b>{idx}. {self._esc(h_name)} vs {self._esc(a_name)}</b>\n"
                    f"   └ 📅 <code>{self._esc(ko)}</code> · 🎲 <code>1:{o1} X:{ox} 2:{o2}</code>"
                )
                btn_label = f"⚽ {h_name[:11]} vs {a_name[:11]}"

            current_row.append({"text": btn_label, "callback_data": f"m:{f['id']}"})
            if len(current_row) == 2:
                match_buttons.append(current_row)
                current_row = []

        if current_row:
            match_buttons.append(current_row)

        lines.append("\n👇 <b>Tap any fixture below for Tactical Preview, Odds &amp; 90' Simulation:</b>")

        nav_row = []
        if md > 1:
            nav_row.append({"text": f"◀ MD {md - 1}", "callback_data": f"md:{md - 1}"})
        if md != current_md:
            nav_row.append({"text": f"📍 Current (MD {current_md})", "callback_data": f"md:{current_md}"})
        if md < 38:
            nav_row.append({"text": f"MD {md + 1} ▶", "callback_data": f"md:{md + 1}"})

        kb = [
            [{"text": f"⚡ Simulate All Matchday {md} Matches", "callback_data": f"mdsim:{md}"}],
            *match_buttons,
        ]
        if nav_row:
            kb.append(nav_row)
        kb.append([{"text": "🏠 Main Menu", "callback_data": "menu:home"}])

        return "\n".join(lines), {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 3: FULL MATCHDAY BATCH SIMULATION (mdsim:<md>)
    # =========================================================================
    def render_matchday_simulation(self, matchday: int) -> Tuple[str, Dict[str, Any]]:
        md = max(1, min(38, int(matchday)))
        fixtures = [f for f in self._get_all_fixtures() if f.get("matchday") == md]

        lines = [
            f"⚡ <b>MATCHDAY {md} — FULL ENGINE SIMULATION</b>",
            "<i>Calibrated Dixon-Coles + Club Tactical DNA + Player Form</i>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        total_goals = 0
        match_buttons = []
        row = []

        for idx, f in enumerate(fixtures, 1):
            detail = self._get_match_detail(f["id"])
            if not detail:
                continue
            sim = self.sim_engine.simulate_fixture(detail)
            hs = sim["home_score"]
            as_ = sim["away_score"]
            total_goals += hs + as_
            h_name = f.get("home_nickname") or f.get("home_name")
            a_name = f.get("away_nickname") or f.get("away_name")
            stats = sim.get("stats", {})
            h_xg = stats.get("xg", {}).get("home", 0.0)
            a_xg = stats.get("xg", {}).get("away", 0.0)
            h_poss = stats.get("possession", {}).get("home", 50)
            a_poss = stats.get("possession", {}).get("away", 50)

            goal_events = [e for e in sim.get("events", []) if e.get("type") == "goal"]
            goal_str = ", ".join(f"{e.get('scorer')} {e.get('minute')}'" for e in goal_events[:4])
            if len(goal_events) > 4:
                goal_str += f" (+{len(goal_events) - 4} more)"

            lines.append(
                f"<b>{idx}. {self._esc(h_name)}  <code>{hs} - {as_}</code>  {self._esc(a_name)}</b>\n"
                f"   📊 xG: <code>{h_xg:.2f} - {a_xg:.2f}</code> · Poss: <code>{h_poss}%-{a_poss}%</code>"
                + (f"\n   ⚽ <i>{self._esc(goal_str)}</i>" if goal_str else "\n   🧤 <i>Tactical defensive deadlock</i>")
            )

            row.append({"text": f"🔍 {h_name[:9]} {hs}-{as_} {a_name[:9]}", "callback_data": f"sim:{f['id']}"})
            if len(row) == 2:
                match_buttons.append(row)
                row = []

        if row:
            match_buttons.append(row)

        avg_goals = round(total_goals / max(1, len(fixtures)), 2)
        lines.append(
            f"\n📈 <b>Round Summary:</b> <code>{total_goals} total goals</code> (<code>{avg_goals}</code> goals/match)\n"
            f"👇 <i>Tap any match below to inspect its full 90' Momentum, 6-Phase Dominance &amp; xG Flow:</i>"
        )

        kb = [
            *match_buttons,
            [
                {"text": f"◀ Back to Matchday {md}", "callback_data": f"md:{md}"},
                {"text": "🏠 Main Menu", "callback_data": "menu:home"},
            ],
        ]
        return "\n".join(lines), {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 4: SINGLE MATCH CENTER & TACTICAL PREVIEW (m:<fid>)
    # =========================================================================
    def render_match_center(self, fixture_id: int, tab: str = "overview") -> Tuple[str, Dict[str, Any]]:
        detail = self._get_match_detail(fixture_id)
        if not detail:
            return "❌ Match not found.", {"inline_keyboard": [[{"text": "🏠 Main Menu", "callback_data": "menu:home"}]]}

        fx = detail["fixture"]
        home = detail["home_team"]
        away = detail["away_team"]
        clash = detail.get("tactical_clash") or {}
        forecast = detail.get("forecast") or {}

        h_name = home.get("nickname") or home.get("name")
        a_name = away.get("nickname") or away.get("name")
        h_theme = self.get_club_theme(home.get("slug") or h_name)
        a_theme = self.get_club_theme(away.get("slug") or a_name)
        h_pos = home.get("position") or "-"
        a_pos = away.get("position") or "-"
        h_form = self._get_club_form_emojis(home.get("slug", ""), 5)
        a_form = self._get_club_form_emojis(away.get("slug", ""), 5)
        stadium = home.get("stadium") or "Estadio Oficial"

        st = fx.get("status", "SCHEDULED")
        hs = fx.get("home_score", 0)
        as_ = fx.get("away_score", 0)

        if st == "FINISHED":
            card_sub = f"FT · {stadium}"
        elif st == "LIVE":
            card_sub = f"LIVE · {stadium}"
        else:
            ko_time = (fx.get("kickoff_time") or "19:00 UTC").replace("T", " ")[:16]
            card_sub = f"KO {ko_time} · {stadium}"

        scoreboard_card = self._render_scoreboard_card(
            h_theme["code"], h_name, hs if st in ("FINISHED", "LIVE") else "-",
            a_theme["code"], a_name, as_ if st in ("FINISHED", "LIVE") else "-",
            card_sub
        )

        # Missing Players block (Injuries & Suspensions)
        h_missing = (home.get("tactics") or {}).get("missing_players") or []
        a_missing = (away.get("tactics") or {}).get("missing_players") or []
        missing_lines = []
        if h_missing:
            hm_str = ", ".join(f"{m.get('status_icon', '🚫')} {m.get('nickname') or m.get('name')} ({m.get('availability_reason', 'Out')})" for m in h_missing[:4])
            missing_lines.append(f"• <b>{self._esc(h_name)} Out:</b> {self._esc(hm_str)}")
        if a_missing:
            am_str = ", ".join(f"{m.get('status_icon', '🚫')} {m.get('nickname') or m.get('name')} ({m.get('availability_reason', 'Out')})" for m in a_missing[:4])
            missing_lines.append(f"• <b>{self._esc(a_name)} Out:</b> {self._esc(am_str)}")
        missing_block = ("\n🚫 <b>SUSPENSIONS &amp; INJURIES</b>\n" + "\n".join(missing_lines) + "\n") if missing_lines else ""

        # Forecast probabilities & implied odds
        h_prob = forecast.get("home_win_pct", 45.0)
        d_prob = forecast.get("draw_pct", 25.0)
        a_prob = forecast.get("away_win_pct", 30.0)
        prob_bar = self._prob_bar(h_prob, d_prob, a_prob, width=12)

        o1 = round(100.0 / max(5.0, h_prob * 1.05), 2)
        ox = round(100.0 / max(5.0, d_prob * 1.05), 2)
        o2 = round(100.0 / max(5.0, a_prob * 1.05), 2)

        proj_xg = forecast.get("projected_xg") or {}
        xg_h = proj_xg.get("home", 1.35)
        xg_a = proj_xg.get("away", 1.10)
        o25 = forecast.get("over_2_5_pct", 50.0)
        btts = forecast.get("btts_yes_pct", 52.0)
        top_scores = forecast.get("top_scorelines") or []
        top_scores_str = " · ".join(f"<code>{s['score']}</code> ({s['probability']}%)" for s in top_scores[:3])

        h_tac = clash.get("home") or {}
        a_tac = clash.get("away") or {}
        exp_poss = clash.get("expected_possession") or {"home": 50, "away": 50}
        tac_narrative = clash.get("key_battle") or clash.get("verdict") or ""

        h_fat = (home.get("fatigue") or {}).get("freshness_badge", "⚡ Rested")
        a_fat = (away.get("fatigue") or {}).get("freshness_badge", "⚡ Rested")

        if tab == "lineups":
            h_formation = (home.get("tactics") or {}).get("formation", "4-3-3")
            a_formation = (away.get("tactics") or {}).get("formation", "4-3-3")
            h_xi = (home.get("tactics") or {}).get("starting_xi", [])[:11]
            a_xi = (away.get("tactics") or {}).get("starting_xi", [])[:11]

            h_xi_lines = [f"  <code>{p.get('slot','POS'):<3}</code> #{p.get('shirt_number',99):<2} <b>{self._esc(p.get('nickname') or p.get('name'))}</b> ({p.get('overall_rating',75)})" for p in h_xi]
            a_xi_lines = [f"  <code>{p.get('slot','POS'):<3}</code> #{p.get('shirt_number',99):<2} <b>{self._esc(p.get('nickname') or p.get('name'))}</b> ({p.get('overall_rating',75)})" for p in a_xi]

            out_block = []
            if missing_lines:
                out_block.append("  🚫 <b>Unavailable / Out:</b>")
                for mp in h_missing + a_missing:
                    out_block.append(f"    {mp.get('status_icon','🚫')} <s>{self._esc(mp.get('nickname') or mp.get('name'))}</s> — <i>{self._esc(mp.get('availability_reason','Unavailable'))}</i>")

            text = (
                f"🏟️ <b>MATCH CENTER · STARTING XIs &amp; FORM</b>\n"
                f"{h_theme['badge']} <b>{self._esc(h_name)}</b> vs <b>{self._esc(a_name)}</b> {a_theme['badge']}\n"
                f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
                f"🛡️ <b>{h_theme['badge']} {self._esc(h_name)} ({h_formation})</b>\n"
                + "\n".join(h_xi_lines) + "\n\n"
                f"🛡️ <b>{a_theme['badge']} {self._esc(a_name)} ({a_formation})</b>\n"
                + "\n".join(a_xi_lines) + "\n"
                + ("\n".join(out_block) if out_block else "")
            )
        elif tab == "momentum":
            poss_split = self._dual_bar(exp_poss.get("home", 50), exp_poss.get("away", 50), 12)
            text = (
                f"🏟️ <b>MATCH CENTER · PREDICTIVE TELEMETRY</b>\n"
                f"{h_theme['badge']} <b>{self._esc(h_name)}</b> vs <b>{self._esc(a_name)}</b> {a_theme['badge']}\n"
                f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
                f"🌊 <b>PROJECTED POSSESSION SPLIT</b>\n"
                f"{poss_split}\n"
                f"• {h_theme['code']} <code>{exp_poss.get('home', 50)}%</code> vs <code>{exp_poss.get('away', 50)}%</code> {a_theme['code']}\n\n"
                f"📈 <b>EXPECTED GOALS &amp; MARKET METRICS</b>\n"
                f"• <b>Projected xG:</b> <code>{xg_h:.2f}</code> ({h_theme['code']}) vs <code>{xg_a:.2f}</code> ({a_theme['code']})\n"
                f"• <b>Over 2.5 Goals:</b> <code>{o25}%</code>\n"
                f"• <b>Both Teams to Score (BTTS):</b> <code>{btts}%</code>\n"
                f"• <b>Likeliest Scorelines:</b> {top_scores_str}\n\n"
                f"🎲 <b>DIXON-COLES PROBABILITY</b>\n"
                f"{prob_bar}\n"
                f"🟩 {h_theme['code']}: <code>{h_prob}%</code> · ⬜ Draw: <code>{d_prob}%</code> · 🟥 {a_theme['code']}: <code>{a_prob}%</code>"
            )
        elif tab == "tactics":
            text = (
                f"🏟️ <b>MATCH CENTER · TACTICAL CLASH</b>\n"
                f"{h_theme['badge']} <b>{self._esc(h_name)}</b> vs <b>{self._esc(a_name)}</b> {a_theme['badge']}\n"
                f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
                f"🧠 <b>MANAGERIAL DUEL</b>\n"
                f"• <b>{h_theme['code']}:</b> {self._esc(h_tac.get('manager', 'Manager'))}\n"
                f"  └ <i>{self._esc(h_tac.get('tactical_identity', 'Structured Football'))}</i>\n"
                f"• <b>{a_theme['code']}:</b> {self._esc(a_tac.get('manager', 'Manager'))}\n"
                f"  └ <i>{self._esc(a_tac.get('tactical_identity', 'Structured Football'))}</i>\n\n"
                f"⚔️ <b>TACTICAL KEY BATTLE</b>\n"
                f"💬 <i>{self._esc(tac_narrative)}</i>\n\n"
                f"• <b>{h_theme['code']} Strengths:</b> {self._esc(h_tac.get('key_strength', 'Technical midfield combinations'))}\n"
                f"• <b>{h_theme['code']} Vulnerabilities:</b> {self._esc(h_tac.get('key_weakness', 'High line space'))}\n"
                f"• <b>{a_theme['code']} Strengths:</b> {self._esc(a_tac.get('key_strength', 'Direct transition speed'))}\n"
                f"• <b>{a_theme['code']} Vulnerabilities:</b> {self._esc(a_tac.get('key_weakness', 'Set piece defending'))}"
            )
        else:  # overview
            goals = fx.get("goals") or []
            scorers_str = ", ".join(f"{g.get('scorer')} {g.get('minute')}'" for g in goals[:4])
            scorers_line = f"⚽ <b>Goals:</b> <i>{self._esc(scorers_str)}</i>\n" if scorers_str else ""
            text = (
                f"🏟️ <b>LA LIGA MATCH CENTER · ROUND {fx.get('matchday')}</b>\n"
                f"{h_theme['badge']} <b>{self._esc(h_name)}</b> (#{h_pos})  vs  <b>{self._esc(a_name)}</b> (#{a_pos}) {a_theme['badge']}\n"
                f"{scoreboard_card}\n"
                f"{scorers_line}"
                f"📊 <b>FORM &amp; CONDITION</b>\n"
                f"• <b>{h_theme['code']}:</b> {h_form} · {self._esc(h_fat)}\n"
                f"• <b>{a_theme['code']}:</b> {a_form} · {self._esc(a_fat)}\n"
                f"{missing_block}\n"
                f"🎲 <b>DIXON-COLES WIN PROBABILITY &amp; ODDS</b>\n"
                f"{prob_bar}\n"
                f"🟩 <b>{h_theme['code']}:</b> <code>{h_prob}%</code> (Odds <code>{o1:.2f}</code>)\n"
                f"⬜ <b>Draw:</b> <code>{d_prob}%</code> (Odds <code>{ox:.2f}</code>)\n"
                f"🟥 <b>{a_theme['code']}:</b> <code>{a_prob}%</code> (Odds <code>{o2:.2f}</code>)\n"
                f"• <b>Projected xG:</b> <code>{xg_h:.2f}</code> vs <code>{xg_a:.2f}</code> · <b>Likely:</b> {top_scores_str}"
            )

        tab_row = [
            {"text": "• 📊 Overview •" if tab == "overview" else "📊 Overview", "callback_data": f"m:{fixture_id}:overview"},
            {"text": "• 📋 XIs •" if tab == "lineups" else "📋 XIs", "callback_data": f"m:{fixture_id}:lineups"},
            {"text": "• 🌊 Momentum •" if tab == "momentum" else "🌊 Momentum", "callback_data": f"m:{fixture_id}:momentum"},
            {"text": "• 🧠 Tactics •" if tab == "tactics" else "🧠 Tactics", "callback_data": f"m:{fixture_id}:tactics"},
        ]

        kb = [
            tab_row,
            [{"text": "⚡ SIMULATE 90' MATCH + TRENDS ▶", "callback_data": f"sim:{fixture_id}"}],
            [
                {"text": f"🔄 Sub {h_theme['code']}", "callback_data": f"msub:{fixture_id}:h"},
                {"text": f"🔄 Sub {a_theme['code']}", "callback_data": f"msub:{fixture_id}:a"},
            ],
            [
                {"text": f"🛡️ {h_theme['code']} DNA", "callback_data": f"c:{home.get('id')}"},
                {"text": f"🛡️ {a_theme['code']} DNA", "callback_data": f"c:{away.get('id')}"},
            ],
            [
                {"text": f"◀ Matchday {fx.get('matchday')}", "callback_data": f"md:{fx.get('matchday')}"},
                {"text": "🏠 Today's Matches", "callback_data": "day:today"},
            ],
        ]
        return text, {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 5: 90-MINUTE SIMULATION REPORT + TRENDS (sim:<fid>)
    # =========================================================================
    def render_match_simulation(
        self,
        fixture_id: int,
        custom_subs: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        detail = self._get_match_detail(fixture_id)
        if not detail:
            return "❌ Match not found.", {"inline_keyboard": [[{"text": "🏠 Main Menu", "callback_data": "menu:home"}]]}

        sim = self.sim_engine.simulate_fixture(detail, custom_substitutions=custom_subs)
        fx = detail["fixture"]
        home = detail["home_team"]
        away = detail["away_team"]
        h_name = home.get("nickname") or home.get("name")
        a_name = away.get("nickname") or away.get("name")

        hs = sim["home_score"]
        as_ = sim["away_score"]
        stats = sim["stats"]
        trends = sim.get("trends") or {}
        narrative = trends.get("narrative") or {}
        phases = trends.get("phases") or []
        win_prob = trends.get("win_probability") or []

        # 1. Incident Timeline
        events_lines = []
        for ev in sim.get("events", []):
            m_str = f"<code>{ev.get('minute', 0):>2}'</code>"
            etype = ev.get("type")
            if etype == "goal":
                side_ico = "🏠" if ev.get("team") == "home" else "✈️"
                assist_str = f" <i>(ast. {self._esc(ev['assist'])})</i>" if ev.get("assist") else ""
                events_lines.append(f"{m_str} ⚽ <b>GOAL! {self._esc(ev.get('scorer'))}</b> {side_ico}{assist_str}")
            elif etype == "save":
                events_lines.append(f"{m_str} 🧤 Save by <b>{self._esc(ev.get('player'))}</b> ({self._esc(ev.get('team_name'))})")
            elif etype == "card":
                events_lines.append(f"{m_str} 🟨 Yellow Card: <b>{self._esc(ev.get('player'))}</b>")
            elif etype in ("game_management", "attacking_siege"):
                events_lines.append(f"{m_str} {self._esc(ev.get('description'))}")

        if not events_lines:
            events_lines.append("<i>0'–90' Tactical midfield battle with disciplined defensive structures.</i>")

        # 2. Match Statistics Visual Comparison
        h_poss = stats["possession"]["home"]
        a_poss = stats["possession"]["away"]
        poss_bar = self._dual_bar(h_poss, a_poss, 10)
        h_xg = stats["xg"]["home"]
        a_xg = stats["xg"]["away"]
        h_sh = stats["shots"]["home"]
        a_sh = stats["shots"]["away"]
        h_sot = stats["shots_on_target"]["home"]
        a_sot = stats["shots_on_target"]["away"]
        h_cor = stats["corners"]["home"]
        a_cor = stats["corners"]["away"]

        # 3. 6-Phase Dominance & Attack Momentum Chart
        phase_lines = []
        for p in phases:
            lbl = p.get("label", "")
            hp = p.get("home_pct", 50)
            ap = p.get("away_pct", 50)
            bar = self._dual_bar(hp, ap, 8)
            goals_tag = " " + " ".join(p.get("goals", [])) if p.get("goals") else ""
            phase_lines.append(
                f"<code>{lbl:<7}</code> {bar} <code>{hp:>2}%/{ap:<2}%</code>{self._esc(goals_tag)}"
            )

        # 4. Win Probability & xG Evolution (0', 45', 90')
        wp_lines = []
        for snap in win_prob:
            if snap.get("minute") in (0, 30, 45, 75, 90):
                m_lbl = f"{snap['minute']}'"
                wp_lines.append(
                    f"<code>{m_lbl:<4}</code> [{snap['score']}] → "
                    f"🏠<code>{snap['home_prob']:>4.1f}%</code> · 🤝<code>{snap['draw_prob']:>4.1f}%</code> · ✈️<code>{snap['away_prob']:>4.1f}%</code>"
                )

        h_theme = self.get_club_theme(home.get("slug") or h_name)
        a_theme = self.get_club_theme(away.get("slug") or a_name)
        stadium = home.get("stadium") or "Estadio Oficial"

        card = self._render_scoreboard_card(
            h_theme["code"], h_name, hs,
            a_theme["code"], a_name, as_,
            f"FT · {stadium}"
        )

        sub_banner = ""
        if custom_subs:
            sub_banner = "\n🔄 <i>Interactive Manager Substitution Applied!</i>"

        verdict_txt = narrative.get("flow_summary") or narrative.get("tactical_verdict") or ""

        text = (
            f"⚡ <b>90' FULL-TIME SIMULATION REPORT · MD {fx.get('matchday')}</b>{sub_banner}\n"
            f"{h_theme['badge']} <b>{h_theme['code']}  {hs} - {as_}  {a_theme['code']}</b> {a_theme['badge']}\n"
            f"{card}\n"
            f"⏱️ <b>MATCH INCIDENT TIMELINE</b>\n"
            + "\n".join(events_lines)
            + f"\n\n📊 <b>TELEMETRY &amp; EXPECTED GOALS (xG)</b>\n"
            f"🟩 {h_theme['code']} vs 🟦 {a_theme['code']}\n"
            f"{poss_bar}\n"
            f"• <b>Possession:</b> <code>{h_poss}%</code> vs <code>{a_poss}%</code>\n"
            f"• <b>Expected Goals (xG):</b> <code>{h_xg:.2f}</code> vs <code>{a_xg:.2f}</code>\n"
            f"• <b>Total Shots (On Target):</b> <code>{h_sh} ({h_sot})</code> vs <code>{a_sh} ({a_sot})</code>\n"
            f"• <b>Corners / Fouls:</b> <code>{h_cor}/{stats['fouls']['home']}</code> vs <code>{a_cor}/{stats['fouls']['away']}</code>\n\n"
            f"🌊 <b>6-PHASE ATTACK MOMENTUM &amp; DOMINANCE</b>\n"
            + "\n".join(phase_lines)
            + f"\n\n📈 <b>WIN PROBABILITY EVOLUTION</b>\n"
            + "\n".join(wp_lines)
            + f"\n\n🧠 <b>TACTICAL TREND NARRATIVE</b>\n"
            f"• <b>Headline:</b> <b>{self._esc(narrative.get('headline', ''))}</b>\n"
            f"• <b>Key Turning Point:</b> {self._esc(narrative.get('turning_point', ''))}\n"
            f"• <b>Match Flow:</b> <i>{self._esc(verdict_txt)}</i>"
        )

        share_url = f"https://t.me/share/url?url=https://t.me/xbetbetterbot&text=⚡+Pitchside+Simulated+{h_theme['code']}+{hs}-{as_}+{a_theme['code']}+on+La+Liga+EA+SPORTS!"

        kb = [
            [
                {"text": f"🔄 Sub {h_theme['code']} & Re-Sim", "callback_data": f"msub:{fixture_id}:h"},
                {"text": f"🔄 Sub {a_theme['code']} & Re-Sim", "callback_data": f"msub:{fixture_id}:a"},
            ],
            [
                {"text": "📋 Starting XIs & Form", "callback_data": f"mxi:{fixture_id}"},
                {"text": "📊 6-Axis Tactical Radar", "callback_data": f"mrad:{fixture_id}"},
            ],
            [
                {"text": "📤 Share Simulation to Chat", "url": share_url},
                {"text": "◀ Match Center", "callback_data": f"m:{fixture_id}"},
            ],
            [
                {"text": f"📅 Matchday {fx.get('matchday')}", "callback_data": f"md:{fx.get('matchday')}"},
                {"text": "🏠 Today's Matches", "callback_data": "day:today"},
            ],
        ]
        return text, {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 6: MATCH STARTING XIs & TACTICAL RADAR (mxi:<fid>, mrad:<fid>)
    # =========================================================================
    def render_match_lineups(self, fixture_id: int) -> Tuple[str, Dict[str, Any]]:
        detail = self._get_match_detail(fixture_id)
        if not detail:
            return "❌ Match not found.", {"inline_keyboard": [[{"text": "🏠 Main Menu", "callback_data": "menu:home"}]]}

        home = detail["home_team"]
        away = detail["away_team"]
        h_tac = home.get("tactics") or {}
        a_tac = away.get("tactics") or {}

        def fmt_xi(team_name: str, tac: Dict[str, Any]) -> str:
            out = [
                f"🛡️ <b>{self._esc(team_name)}</b> — <code>{self._esc(tac.get('formation', '4-3-3'))}</code> ({self._esc(tac.get('manager', 'Coach'))})"
            ]
            for p in tac.get("starting_xi", []):
                slot = p.get("slot", "POS")
                num = p.get("shirt_number", 99)
                name = p.get("nickname") or p.get("name")
                ovr = p.get("overall_rating", 75)
                mod = p.get("form_modifier", 0)
                mod_str = f"+{mod}" if mod > 0 else (str(mod) if mod < 0 else "")
                ico = p.get("streak_icon", "➡️")
                out.append(
                    f"  <code>{slot:<3}</code> #{num:<2} <b>{self._esc(name)}</b> — OVR <code>{ovr}{mod_str}</code> {ico}"
                )
            missing = tac.get("missing_players") or []
            if missing:
                out.append("  🚫 <b>Unavailable / Out:</b>")
                for mp in missing[:4]:
                    m_ico = mp.get("status_icon", "🚫")
                    m_name = mp.get("nickname") or mp.get("name")
                    m_rsn = mp.get("availability_reason", "Unavailable")
                    out.append(f"    {m_ico} <s>{self._esc(m_name)}</s> (OVR {mp.get('overall_rating', 75)}) — <i>{self._esc(m_rsn)}</i>")
            return "\n".join(out)

        text = (
            f"📋 <b>STARTING XIs &amp; LIVE PLAYER FORM</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            + fmt_xi(home.get("name", "Home"), h_tac)
            + "\n\n"
            + fmt_xi(away.get("name", "Away"), a_tac)
            + "\n\n💡 <i>🔥 Hot Streak (+4) · ⚡ In Form (+2) · 🟥 Suspended · 🏥 Injured</i>"
        )

        kb = [
            [{"text": "⚡ Simulate 90' Match", "callback_data": f"sim:{fixture_id}"}],
            [
                {"text": f"🔄 Make {home.get('nickname', 'Home')[:10]} Sub", "callback_data": f"msub:{fixture_id}:h"},
                {"text": f"🔄 Make {away.get('nickname', 'Away')[:10]} Sub", "callback_data": f"msub:{fixture_id}:a"},
            ],
            [{"text": "◀ Back to Match Center", "callback_data": f"m:{fixture_id}"}],
        ]
        return text, {"inline_keyboard": kb}

    def render_match_radar(self, fixture_id: int) -> Tuple[str, Dict[str, Any]]:
        detail = self._get_match_detail(fixture_id)
        if not detail:
            return "❌ Match not found.", {"inline_keyboard": [[{"text": "🏠 Main Menu", "callback_data": "menu:home"}]]}

        home = detail["home_team"]
        away = detail["away_team"]
        radar = detail.get("tactical_radar") or {}
        axes = radar.get("axes") or []
        h_vals = radar.get("home") or {}
        a_vals = radar.get("away") or {}

        h_name = home.get("nickname") or home.get("name")
        a_name = away.get("nickname") or away.get("name")

        lines = [
            f"📊 <b>6-AXIS TACTICAL RADAR COMPARISON</b>",
            f"🟩 <b>{self._esc(h_name)}</b>  vs  🟦 <b>{self._esc(a_name)}</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        for ax in axes:
            k = ax["key"]
            lbl = ax["label"]
            hv = h_vals.get(k, 70)
            av = a_vals.get(k, 70)
            edge = h_name if hv > av + 2 else (a_name if av > hv + 2 else "Even")
            lines.append(
                f"\n<b>{self._esc(lbl)}</b> (Edge: <i>{self._esc(edge)}</i>)\n"
                f"🟩 <code>{hv:>2}</code> {self._progress_bar(hv, 100, 10)} <b>{self._esc(h_name[:12])}</b>\n"
                f"🟦 <code>{av:>2}</code> {self._progress_bar(av, 100, 10)} <b>{self._esc(a_name[:12])}</b>"
            )

        kb = [
            [{"text": "⚡ Simulate 90' Match", "callback_data": f"sim:{fixture_id}"}],
            [
                {"text": "📋 Starting XIs", "callback_data": f"mxi:{fixture_id}"},
                {"text": "◀ Match Center", "callback_data": f"m:{fixture_id}"},
            ],
        ]
        return "\n".join(lines), {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 7: INTERACTIVE MANAGER SUBSTITUTION SIMULATOR (msub:<fid>:<side>)
    # =========================================================================
    def render_sub_menu(self, fixture_id: int, side: str) -> Tuple[str, Dict[str, Any]]:
        detail = self._get_match_detail(fixture_id)
        if not detail:
            return "❌ Match not found.", {"inline_keyboard": [[{"text": "🏠 Main Menu", "callback_data": "menu:home"}]]}

        team_key = "home_team" if side == "h" else "away_team"
        team = detail[team_key]
        tactics = team.get("tactics") or {}
        starters = tactics.get("starting_xi") or []
        bench = tactics.get("bench") or []

        if not starters or not bench:
            return "⚠️ No bench players available for substitution.", {
                "inline_keyboard": [[{"text": "◀ Back", "callback_data": f"m:{fixture_id}"}]]
            }

        top_bench = sorted(bench, key=lambda x: x.get("effective_rating", 0), reverse=True)[:4]
        field_starters = [p for p in starters if p.get("slot") != "GK"][:6]

        lines = [
            f"🔄 <b>INTERACTIVE MANAGER MODE · {self._esc(team.get('name'))}</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "Select a tactical substitution below to immediately re-run the 90-minute match simulation with the modified Starting XI:\n",
        ]

        kb = []
        for b_player in top_bench[:3]:
            b_name = (b_player.get("nickname") or b_player.get("name") or "Sub")[:13]
            b_pos = (b_player.get("position") or "")[:3].upper()
            b_ovr = b_player.get("effective_rating", b_player.get("overall_rating", 75))
            # Match bench player with a starter in similar or lowest rated slot
            target = field_starters[0]
            for st_p in field_starters:
                if (st_p.get("position") or "") == (b_player.get("position") or ""):
                    target = st_p
                    break
            t_name = (target.get("nickname") or target.get("name") or "Starter")[:13]
            t_slot = target.get("slot", "POS")
            lines.append(
                f"• 🟢 <b>IN:</b> {self._esc(b_player.get('name'))} ({b_pos}, OVR <code>{b_ovr}</code>)\n"
                f"  🔴 <b>OUT:</b> {self._esc(target.get('name'))} ({t_slot}, OVR <code>{target.get('effective_rating', 75)}</code>)"
            )
            kb.append([{
                "text": f"🔄 IN {b_name} ({b_ovr}) ⇄ OUT {t_name}",
                "callback_data": f"msw:{fixture_id}:{target['id']}:{b_player['id']}:{side}",
            }])

        kb.append([{"text": "◀ Back to Match Center", "callback_data": f"m:{fixture_id}"}])
        return "\n".join(lines), {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 8: LA LIGA STANDINGS & FORM TABLE (/standings, st:<mode>)
    # =========================================================================
    def render_standings_view(self, mode: str = "all") -> Tuple[str, Dict[str, Any]]:
        standings = self._get_standings()
        if mode == "top":
            subset = standings[:10]
            subtitle = "TOP 10 · CHAMPIONS LEAGUE &amp; EUROPEAN RACE"
        elif mode == "bot":
            subset = standings[10:]
            subtitle = "BOTTOM 10 · MID-TABLE &amp; RELEGATION BATTLE"
        else:
            subset = standings
            subtitle = "OFFICIAL 20-CLUB LEAGUE TABLE &amp; FORM"

        lines = [
            "🏆 <b>LA LIGA EA SPORTS STANDINGS</b>",
            f"<i>{subtitle}</i>",
            "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
            "<code> #  TAG CLUB        MP  GD PT</code>",
        ]

        club_buttons = []
        row_btns = []

        for c in subset:
            pos = c.get("position") or 0
            if pos <= 4:
                zone = "🟦"
            elif pos <= 6:
                zone = "🟧"
            elif pos == 7:
                zone = "🟩"
            elif pos >= 18:
                zone = "🟥"
            else:
                zone = "⬜"

            theme = self.get_club_theme(c.get("slug", "") or c.get("name", ""))
            tag = theme["code"]
            name = (c.get("nickname") or c.get("name") or "Club")[:11]
            mp = c.get("played", 0)
            gd = c.get("goal_difference", 0)
            gd_s = f"+{gd}" if gd > 0 else str(gd)
            pts = c.get("points", 0)
            form = self._get_club_form_emojis(c.get("slug", ""), 5)

            if mode in ("top", "bot"):
                lines.append(
                    f"{zone} <code>{pos:>2} {tag:<3} {name:<11} {mp:>2} {gd_s:>3} {pts:>2}</code> {form}"
                )
            else:
                lines.append(
                    f"{zone} <code>{pos:>2} {tag:<3} {name:<11} {mp:>2} {gd_s:>3} {pts:>2}</code>"
                )

            if len(club_buttons) < 4:
                row_btns.append({"text": f"#{pos} {theme['badge']} {name[:10]}", "callback_data": f"c:{c['id']}"})
                if len(row_btns) == 2:
                    club_buttons.append(row_btns)
                    row_btns = []

        if row_btns and len(club_buttons) < 4:
            club_buttons.append(row_btns)

        lines.append(
            "\n🟦 UCL (1-4) · 🟧 UEL (5-6) · 🟩 UECL (7) · 🟥 Relegation (18-20)"
        )

        kb = [
            [
                {"text": "📋 Full 20 Table" if mode != "all" else "• 📋 Full 20 Table •", "callback_data": "st:all"},
                {"text": "🏆 Top 10 + Form" if mode != "top" else "• 🏆 Top 10 + Form •", "callback_data": "st:top"},
                {"text": "⚠️ Bottom 10 + Form" if mode != "bot" else "• ⚠️ Bottom 10 •", "callback_data": "st:bot"},
            ],
            [{"text": "🛡️ Browse All 20 Club Tactical Dossiers", "callback_data": "clubs:list"}],
            [{"text": "🏠 Main Menu", "callback_data": "menu:home"}],
        ]
        return "\n".join(lines), {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 9: CLUBS DIRECTORY & TACTICAL DNA DOSSIER (/clubs, c:<id>)
    # =========================================================================
    def render_clubs_directory(self) -> Tuple[str, Dict[str, Any]]:
        standings = self._get_standings()
        lines = [
            "🛡️ <b>LA LIGA 20 CLUBS &amp; TACTICAL DNA DIRECTORY</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "Select any club below to inspect its <b>Managerial Philosophy, Tactical DNA Metrics, Starting XI Lineup, Form Guide &amp; Upcoming Schedule</b>:",
        ]

        kb = []
        row = []
        for c in standings:
            pos = c.get("position", 0)
            name = (c.get("nickname") or c.get("name") or "Club")[:12]
            theme = self.get_club_theme(c.get("slug") or c.get("name"))
            ovr = c.get("overall_rating", 75)
            row.append({"text": f"#{pos} {theme['badge']} {name}", "callback_data": f"c:{c['id']}"})
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        kb.append([{"text": "🏠 Main Menu", "callback_data": "menu:home"}])
        return "\n".join(lines), {"inline_keyboard": kb}

    def render_club_dossier(self, identifier: Any) -> Tuple[str, Dict[str, Any]]:
        profile = self.db.get_club_profile(identifier)
        if not profile:
            return "❌ Club not found.", {"inline_keyboard": [[{"text": "🛡️ All Clubs", "callback_data": "clubs:list"}]]}

        c = profile.get("club") or {}
        scores = profile.get("scores") or {}
        slug = c.get("slug", "")
        theme = self.get_club_theme(slug or c.get("name"))
        dna = ClubTacticsRegistry.get_profile(slug)
        metrics = dna.get("metrics") or {}
        form_dots = self._get_club_form_emojis(slug, 5)

        pos = c.get("position", "-")
        pts = c.get("points", 0)
        w, d, l = c.get("won", 0), c.get("drawn", 0), c.get("lost", 0)
        gf, ga, gd = c.get("goals_for", 0), c.get("goals_against", 0), c.get("goal_difference", 0)
        gd_str = f"+{gd}" if gd > 0 else str(gd)

        ovr = scores.get("overall_rating") or c.get("overall_rating", 75)
        att = scores.get("att_rating") or c.get("att_rating", 75)
        mid = scores.get("mid_rating") or c.get("mid_rating", 75)
        df = scores.get("def_rating") or c.get("def_rating", 75)

        text = (
            f"🛡️ {theme['badge']} <b>{self._esc(c.get('name') or c.get('nickname'))} — TACTICAL DOSSIER</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 <b>Rank:</b> <code>#{pos}</code> · <b>Points:</b> <code>{pts}</code> (<code>{w}W-{d}D-{l}L</code>)\n"
            f"⚽ <b>Goals:</b> <code>{gf} GF : {ga} GA</code> (GD <code>{gd_str}</code>)\n"
            f"🏟️ <b>Stadium:</b> {self._esc(c.get('stadium_name') or c.get('stadium') or 'Estadio Oficial')}\n"
            f"📈 <b>Recent Form:</b> {form_dots}\n"
            f"⭐ <b>Ratings:</b> OVR <code>{ovr}</code> (ATT <code>{att}</code> · MID <code>{mid}</code> · DEF <code>{df}</code>)\n\n"
            f"🧠 <b>MANAGER &amp; TACTICAL DNA</b>\n"
            f"• <b>Manager:</b> {self._esc(dna.get('manager'))} <i>(\"{self._esc(dna.get('manager_moniker', ''))}\")</i>\n"
            f"• <b>Base System:</b> <code>{self._esc(dna.get('formation'))}</code> — <b>{self._esc(dna.get('tactical_identity'))}</b>\n\n"
            f"📊 <b>TACTICAL METRICS (0–100)</b>\n"
            f"• Possession Target: <code>{metrics.get('possession_target', 50):>2}%</code> {self._progress_bar(metrics.get('possession_target', 50), 100, 8)}\n"
            f"• Pressing Intensity: <code>{metrics.get('pressing_intensity', 70):>2} </code> {self._progress_bar(metrics.get('pressing_intensity', 70), 100, 8)}\n"
            f"• Defensive Line:     <code>{metrics.get('defensive_line_height', 60):>2} </code> {self._progress_bar(metrics.get('defensive_line_height', 60), 100, 8)}\n"
            f"• Counter Threat:     <code>{metrics.get('counter_threat', 70):>2} </code> {self._progress_bar(metrics.get('counter_threat', 70), 100, 8)}\n"
            f"• Lead Preservation:  <code>{metrics.get('lead_preservation', 65):>2} </code> {self._progress_bar(metrics.get('lead_preservation', 65), 100, 8)}\n"
            f"• Late Siege Chase:   <code>{metrics.get('late_chase_intensity', 75):>2} </code> {self._progress_bar(metrics.get('late_chase_intensity', 75), 100, 8)}\n\n"
            f"⚔️ <b>SITUATIONAL GAMEPLAN</b>\n"
            f"• <b>Vs Big Clubs:</b> {self._esc(dna.get('vs_elite_tactics', ''))}\n"
            f"• <b>Vs Low Blocks:</b> {self._esc(dna.get('vs_underdog_tactics', ''))}\n"
            f"• <b>Key Strength:</b> ✅ {self._esc(dna.get('key_strength', ''))}\n"
            f"• <b>Vulnerability:</b> ⚠️ {self._esc(dna.get('vulnerability', ''))}"
        )

        cid = c.get("id")
        kb = [
            [
                {"text": "📋 Starting XI & Squad", "callback_data": f"cros:{cid}"},
                {"text": "📅 Club Fixtures & Sim", "callback_data": f"cfx:{cid}"},
            ],
            [
                {"text": "🛡️ All 20 Clubs", "callback_data": "clubs:list"},
                {"text": "🏆 Standings", "callback_data": "st:all"},
            ],
            [{"text": "🏠 Main Menu", "callback_data": "menu:home"}],
        ]
        return text, {"inline_keyboard": kb}

    def render_club_roster(self, club_id: int) -> Tuple[str, Dict[str, Any]]:
        club = self.db.get_club_by_id_or_slug(club_id)
        if not club:
            return "❌ Club not found.", {"inline_keyboard": [[{"text": "🛡️ All Clubs", "callback_data": "clubs:list"}]]}

        slug = club["slug"]
        players = self.db.search_players(club_slug=slug, limit=25)
        dna = ClubTacticsRegistry.get_profile(slug)

        lines = [
            f"📋 <b>{self._esc(club.get('name'))} — SQUAD &amp; KEY PLAYERS</b>",
            f"<i>System: {self._esc(dna.get('formation'))} · Manager: {self._esc(dna.get('manager'))}</i>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        kb = []
        row = []
        for idx, p in enumerate(players[:16], 1):
            num = p.get("shirt_number") or "-"
            name = p.get("nickname") or p.get("name")
            pos = (p.get("position_name") or "Player")[:3].upper()
            ovr = p.get("overall_rating", 75)
            st = p.get("stats") or {}
            g = st.get("goals", 0)
            a = st.get("assists", 0)
            stat_tag = f" · ⚽{g} 🎯{a}" if (g or a) else ""
            lines.append(
                f"<code>{idx:>2}.</code> <b>{self._esc(name)}</b> (#{num}, {pos}) — OVR <code>{ovr}</code>{stat_tag}"
            )
            if idx <= 10:
                row.append({"text": f"⭐ {name[:12]} ({ovr})", "callback_data": f"p:{p['id']}"})
                if len(row) == 2:
                    kb.append(row)
                    row = []
        if row:
            kb.append(row)

        kb.append([
            {"text": "◀ Back to Club Dossier", "callback_data": f"c:{club_id}"},
            {"text": "📅 Club Fixtures", "callback_data": f"cfx:{club_id}"},
        ])
        return "\n".join(lines), {"inline_keyboard": kb}

    def render_club_fixtures(self, club_id: int) -> Tuple[str, Dict[str, Any]]:
        club = self.db.get_club_by_id_or_slug(club_id)
        if not club:
            return "❌ Club not found.", {"inline_keyboard": [[{"text": "🛡️ All Clubs", "callback_data": "clubs:list"}]]}

        slug = club["slug"]
        all_fx = self.db.get_fixtures(club_slug=slug)
        finished = [f for f in all_fx if f.get("status") == "FINISHED"][-4:]
        upcoming = [f for f in all_fx if f.get("status") != "FINISHED"][:5]

        lines = [
            f"📅 <b>{self._esc(club.get('name'))} — RESULTS &amp; UPCOMING SCHEDULE</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "🏁 <b>RECENT RESULTS</b>",
        ]

        kb = []
        row = []

        if not finished:
            lines.append("<i>No completed matches yet.</i>")
        for f in finished:
            is_h = f.get("home_slug") == slug
            hs, as_ = f.get("home_score", 0), f.get("away_score", 0)
            my_s, op_s = (hs, as_) if is_h else (as_, hs)
            badge = "🟢 W" if my_s > op_s else ("🟡 D" if my_s == op_s else "🔴 L")
            opp = f.get("away_nickname") if is_h else f.get("home_nickname")
            venue = "H" if is_h else "A"
            lines.append(f"• MD {f['matchday']} ({venue}): {badge} <b>{my_s}-{op_s}</b> vs {self._esc(opp)}")

        lines.append("\n🕒 <b>UPCOMING FIXTURES (Tap to Simulate)</b>")
        for f in upcoming:
            is_h = f.get("home_slug") == slug
            opp = f.get("away_nickname") if is_h else f.get("home_nickname")
            venue = "Home" if is_h else "Away"
            o1, ox, o2 = self._compute_quick_odds(f)
            lines.append(
                f"• <b>MD {f['matchday']} ({venue}): vs {self._esc(opp)}</b> · 🎲 <code>1:{o1} X:{ox} 2:{o2}</code>"
            )
            row.append({"text": f"⚡ MD{f['matchday']}: vs {opp[:10]}", "callback_data": f"m:{f['id']}"})
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        kb.append([
            {"text": "◀ Back to Club Dossier", "callback_data": f"c:{club_id}"},
            {"text": "🏠 Main Menu", "callback_data": "menu:home"},
        ])
        return "\n".join(lines), {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 10: PLAYERS LEADERBOARDS & PLAYER DOSSIER (/players, ldr:<m>, p:<id>)
    # =========================================================================
    def render_leaders_view(self, metric: str = "goals") -> Tuple[str, Dict[str, Any]]:
        metric_titles = {
            "goals": ("⚽ TOP GOALSCORERS (PICHICHI RACE)", "goals", "Goals"),
            "assists": ("🎯 TOP PLAYMAKERS & ASSISTS", "assists", "Assists"),
            "overall_rating": ("⭐ HIGHEST RATED LA LIGA STARS (OVR)", "overall_rating", "OVR"),
            "pace": ("⚡ FASTEST PLAYERS (PACE RATING)", "pace", "PAC"),
            "passing": ("🎯 ELITE PASSERS (PASSING RATING)", "passing", "PAS"),
            "dribbling": ("🪄 TOP DRIBBLERS (DRIBBLING RATING)", "dribbling", "DRI"),
            "defending": ("🛡️ DEFENSIVE GIANTS (DEFENSE RATING)", "defending", "DEF"),
        }
        title, m_key, unit = metric_titles.get(metric, metric_titles["goals"])
        leaders = self.db.get_leaders(metric=m_key, limit=10)

        lines = [
            f"🌟 <b>{self._esc(title)}</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        kb = []
        row = []
        for idx, p in enumerate(leaders, 1):
            name = p.get("nickname") or p.get("name") or "Player"
            club = p.get("club_nickname") or p.get("club_name") or ""
            ovr = p.get("overall_rating", 75)
            if m_key == "overall_rating":
                val = ovr
            elif m_key in ("pace", "passing", "dribbling", "defending"):
                val = (p.get("scores") or {}).get(m_key, 0)
            else:
                val = (p.get("stats") or {}).get(m_key, 0)

            medal = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"<code>{idx:>2}.</code>"))
            lines.append(
                f"{medal} <b>{self._esc(name)}</b> ({self._esc(club)}) — <code>{val} {unit}</code> · OVR <code>{ovr}</code>"
            )
            if p.get("id"):
                row.append({"text": f"{idx}. {name[:13]} ({val})", "callback_data": f"p:{p['id']}"})
                if len(row) == 2:
                    kb.append(row)
                    row = []
        if row:
            kb.append(row)

        # Metric filter tabs
        kb.extend([
            [
                {"text": "⚽ Goals", "callback_data": "ldr:goals"},
                {"text": "🎯 Assists", "callback_data": "ldr:assists"},
                {"text": "⭐ Top OVR", "callback_data": "ldr:overall_rating"},
            ],
            [
                {"text": "⚡ Pace", "callback_data": "ldr:pace"},
                {"text": "🎯 Passing", "callback_data": "ldr:passing"},
                {"text": "🪄 Dribbling", "callback_data": "ldr:dribbling"},
                {"text": "🛡️ Defense", "callback_data": "ldr:defending"},
            ],
            [{"text": "🏠 Main Menu", "callback_data": "menu:home"}],
        ])
        lines.append("\n💡 <i>Tap any player above to open their full 6-Axis Attribute Radar &amp; Telemetry, or type any player name in chat!</i>")
        return "\n".join(lines), {"inline_keyboard": kb}

    def render_player_dossier(self, identifier: str) -> Tuple[str, Dict[str, Any]]:
        profile = self._get_player_by_id_or_slug(identifier)
        if not profile:
            return "❌ Player profile not found.", {"inline_keyboard": [[{"text": "🌟 Top Players", "callback_data": "ldr:goals"}]]}

        bio = profile.get("bio") or {}
        stats = profile.get("stats") or {}
        scores = profile.get("scores") or {}
        strengths = profile.get("strengths") or []
        weaknesses = profile.get("weaknesses") or []

        name = bio.get("name") or bio.get("nickname") or "Player"
        club_name = bio.get("club_name") or "La Liga Club"
        pos = bio.get("position") or "Player"
        shirt = bio.get("shirt_number") or "-"
        nation = bio.get("country") or "ESP"
        ovr = scores.get("overall_rating") or bio.get("overall_rating") or 75
        arch = profile.get("archetype") or "Complete Player"

        pac = scores.get("pace", 70)
        sho = scores.get("shooting", 70)
        pas = scores.get("passing", 70)
        dri = scores.get("dribbling", 70)
        df = scores.get("defending", 70)
        phy = scores.get("physical", 70)

        str_text = ", ".join(self._esc(s) for s in strengths[:4]) if strengths else " High Tactical Consistency"
        wk_text = ", ".join(self._esc(w) for w in weaknesses[:3]) if weaknesses else "Well-rounded profile"

        text = (
            f"🌟 <b>{self._esc(name)} — PLAYER TELEMETRY DOSSIER</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <b>Club:</b> {self._esc(club_name)} · <b>Pos:</b> {self._esc(pos)} (#{shirt})\n"
            f"🌍 <b>Nation:</b> {self._esc(nation)} · <b>Archetype:</b> <i>{self._esc(arch)}</i>\n"
            f"⭐ <b>OVERALL RATING (OVR):</b> <code> {ovr} / 99 </code>\n\n"
            f"📊 <b>6-AXIS ATTRIBUTE RADAR</b>\n"
            f"• <code>PAC {pac:>2}</code> {self._progress_bar(pac, 100, 10)}\n"
            f"• <code>SHO {sho:>2}</code> {self._progress_bar(sho, 100, 10)}\n"
            f"• <code>PAS {pas:>2}</code> {self._progress_bar(pas, 100, 10)}\n"
            f"• <code>DRI {dri:>2}</code> {self._progress_bar(dri, 100, 10)}\n"
            f"• <code>DEF {df:>2}</code> {self._progress_bar(df, 100, 10)}\n"
            f"• <code>PHY {phy:>2}</code> {self._progress_bar(phy, 100, 10)}\n\n"
            f"📈 <b>OFFICIAL SEASON STATISTICS</b>\n"
            f"• <b>Appearances (Minutes):</b> <code>{stats.get('appearances', 0)}</code> (<code>{stats.get('minutes_played', 0)}'</code>)\n"
            f"• <b>Goals / Assists:</b> ⚽ <code>{stats.get('goals', 0)}</code> · 🎯 <code>{stats.get('assists', 0)}</code>\n"
            f"• <b>Shots (On Target):</b> <code>{stats.get('shots', 0)} ({stats.get('shots_on_target', 0)})</code>\n"
            f"• <b>Key Passes / Total Passes:</b> <code>{stats.get('key_passes', 0)} / {stats.get('passes_total', 0)}</code>\n"
            f"• <b>Tackles Won / Interceptions:</b> <code>{stats.get('tackles_won', 0)} / {stats.get('interceptions', 0)}</code>\n"
            f"• <b>Dribbles Won / Duels Won:</b> <code>{stats.get('dribbles_won', 0)} / {stats.get('duels_won', 0)}</code>\n\n"
            f"✅ <b>Strengths:</b> {str_text}\n"
            f"⚠️ <b>Areas to Watch:</b> {wk_text}"
        )

        club_id = bio.get("club_id")
        kb = []
        if club_id:
            kb.append([{"text": f"🛡️ View {club_name[:18]} Dossier", "callback_data": f"c:{club_id}"}])
        kb.extend([
            [
                {"text": "🌟 Leaderboards", "callback_data": "ldr:goals"},
                {"text": "🏠 Main Menu", "callback_data": "menu:home"},
            ]
        ])
        return text, {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 11: HEAD-TO-HEAD COMPARISON (/compare, cmp:menu)
    # =========================================================================
    def render_compare_menu(self, query_str: str = "") -> Tuple[str, Dict[str, Any]]:
        if query_str and (" vs " in query_str.lower() or "," in query_str):
            sep = " vs " if " vs " in query_str.lower() else ","
            parts = [p.strip() for p in query_str.lower().split(sep, 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                # Try club comparison first
                c_cmp = self.comparator.compare_clubs(parts[0], parts[1])
                if c_cmp:
                    c1 = c_cmp["club1"]["meta"]
                    c2 = c_cmp["club2"]["meta"]
                    s1 = c_cmp["club1"]["scores"]
                    s2 = c_cmp["club2"]["scores"]
                    verdict = c_cmp.get("verdict", "")
                    text = (
                        f"⚔️ <b>CLUB HEAD-TO-HEAD COMPARISON</b>\n"
                        f"🏠 <b>{self._esc(c1['name'])}</b>  vs  ✈️ <b>{self._esc(c2['name'])}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"• <b>Rank:</b> <code>#{c1.get('position')}</code> vs <code>#{c2.get('position')}</code>\n"
                        f"• <b>Points:</b> <code>{c1.get('points')}</code> vs <code>{c2.get('points')}</code>\n"
                        f"• <b>Overall Rating:</b> <code>{s1.get('overall_rating')}</code> vs <code>{s2.get('overall_rating')}</code>\n"
                        f"• <b>Attack:</b> <code>{s1.get('att_rating')}</code> vs <code>{s2.get('att_rating')}</code>\n"
                        f"• <b>Midfield:</b> <code>{s1.get('mid_rating')}</code> vs <code>{s2.get('mid_rating')}</code>\n"
                        f"• <b>Defense:</b> <code>{s1.get('def_rating')}</code> vs <code>{s2.get('def_rating')}</code>\n\n"
                        f"🧠 <b>Verdict:</b> <i>{self._esc(verdict)}</i>"
                    )
                    return text, {
                        "inline_keyboard": [
                            [
                                {"text": f"🛡️ {c1['name'][:14]}", "callback_data": f"c:{c1['id']}"},
                                {"text": f"🛡️ {c2['name'][:14]}", "callback_data": f"c:{c2['id']}"},
                            ],
                            [{"text": "🏠 Main Menu", "callback_data": "menu:home"}],
                        ]
                    }
                # Try player comparison
                p_cmp = self.comparator.compare_players(parts[0], parts[1])
                if p_cmp:
                    p1 = p_cmp["player1"]
                    p2 = p_cmp["player2"]
                    b1, b2 = p1["bio"], p2["bio"]
                    sc1, sc2 = p1["scores"], p2["scores"]
                    verdict = p_cmp.get("verdict", "")
                    text = (
                        f"⚔️ <b>PLAYER HEAD-TO-HEAD COMPARISON</b>\n"
                        f"🌟 <b>{self._esc(b1['name'])}</b> ({self._esc(b1.get('club_name', ''))}) vs 🌟 <b>{self._esc(b2['name'])}</b> ({self._esc(b2.get('club_name', ''))})\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"• <b>OVERALL:</b> <code>{sc1.get('overall_rating')}</code> vs <code>{sc2.get('overall_rating')}</code>\n"
                        f"• <b>Pace (PAC):</b> <code>{sc1.get('pace')}</code> vs <code>{sc2.get('pace')}</code>\n"
                        f"• <b>Shooting (SHO):</b> <code>{sc1.get('shooting')}</code> vs <code>{sc2.get('shooting')}</code>\n"
                        f"• <b>Passing (PAS):</b> <code>{sc1.get('passing')}</code> vs <code>{sc2.get('passing')}</code>\n"
                        f"• <b>Dribbling (DRI):</b> <code>{sc1.get('dribbling')}</code> vs <code>{sc2.get('dribbling')}</code>\n"
                        f"• <b>Defense (DEF):</b> <code>{sc1.get('defending')}</code> vs <code>{sc2.get('defending')}</code>\n"
                        f"• <b>Physical (PHY):</b> <code>{sc1.get('physical')}</code> vs <code>{sc2.get('physical')}</code>\n\n"
                        f"🧠 <b>Scout Verdict:</b> <i>{self._esc(verdict)}</i>"
                    )
                    return text, {"inline_keyboard": [[{"text": "🏠 Main Menu", "callback_data": "menu:home"}]]}

        text = (
            "⚔️ <b>HEAD-TO-HEAD COMPARISON ENGINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Compare any two La Liga players or clubs!\n\n"
            "💡 <b>How to use:</b>\n"
            "• Send <code>/compare Yamal vs Mbappe</code>\n"
            "• Send <code>/compare Barcelona vs Real Madrid</code>\n"
            "• Or tap a featured preset clash below:"
        )
        kb = [
            [{"text": "⚔️ Lamine Yamal vs Kylian Mbappé", "callback_data": "qcmp:lamine-yamal:kylian-mbappe"}],
            [{"text": "⚔️ Jude Bellingham vs Pedri", "callback_data": "qcmp:jude-bellingham:pedri"}],
            [{"text": "⚔️ FC Barcelona vs Real Madrid", "callback_data": "qcmp:fc-barcelona:real-madrid"}],
            [{"text": "⚔️ Real Betis vs Atlético Madrid", "callback_data": "qcmp:real-betis:atletico-de-madrid"}],
            [{"text": "🏠 Main Menu", "callback_data": "menu:home"}],
        ]
        return text, {"inline_keyboard": kb}

    # =========================================================================
    # VIEW 12: SMART NATURAL LANGUAGE SEARCH
    # =========================================================================
    def render_smart_search(self, query: str) -> Tuple[str, Dict[str, Any]]:
        q = query.strip()
        if not q:
            return self.render_home_view()

        # Check if user typed "A vs B"
        if " vs " in q.lower():
            return self.render_compare_menu(q)

        # Check if user typed "matchday N" or "md N"
        ql = q.lower()
        if ql.startswith("matchday ") or ql.startswith("md "):
            digits = "".join(ch for ch in ql if ch.isdigit())
            if digits:
                return self.render_matchday_view(int(digits))

        # 1. Search Clubs
        club = self.db.get_club_by_id_or_slug(q)
        # 2. Search Players
        players = self.db.search_players(query=q, limit=8)

        # If exact single club match and no stronger player match, open club dossier directly
        if club and q.lower() in (club.get("name", "").lower(), club.get("nickname", "").lower(), club.get("slug", "").lower()):
            return self.render_club_dossier(club["id"])

        # If exact single player match
        if len(players) == 1 and not club:
            return self.render_player_dossier(str(players[0]["id"]))

        lines = [
            f"🔍 <b>SEARCH RESULTS FOR: \"{self._esc(q)}\"</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]
        kb = []

        if club:
            lines.append(
                f"\n🛡️ <b>MATCHING CLUB</b>\n"
                f"• <b>{self._esc(club.get('name'))}</b> (#{club.get('position')}, OVR <code>{club.get('overall_rating')}</code>)"
            )
            kb.append([{"text": f"🛡️ Open {club.get('nickname') or club.get('name')} Dossier", "callback_data": f"c:{club['id']}"}])

        if players:
            lines.append("\n🌟 <b>MATCHING PLAYERS</b>")
            row = []
            for p in players[:6]:
                pname = p.get("nickname") or p.get("name")
                pclub = p.get("club_nickname") or p.get("club_name") or ""
                povr = p.get("overall_rating", 75)
                lines.append(f"• <b>{self._esc(pname)}</b> ({self._esc(pclub)}) — OVR <code>{povr}</code>")
                row.append({"text": f"🌟 {pname[:13]} ({povr})", "callback_data": f"p:{p['id']}"})
                if len(row) == 2:
                    kb.append(row)
                    row = []
            if row:
                kb.append(row)

        if not club and not players:
            lines.append(
                "\n⚠️ No exact club or player found.\n"
                "Try searching for a team (e.g. <code>Barcelona</code>, <code>Real Betis</code>, <code>Madrid</code>) "
                "or player (e.g. <code>Yamal</code>, <code>Mbappe</code>, <code>Isco</code>)."
            )

        kb.append([{"text": "🏠 Main Menu", "callback_data": "menu:home"}])
        return "\n".join(lines), {"inline_keyboard": kb}

    # =========================================================================
    # DAILY UPDATE, SUBSCRIBERS & DATA REFRESH
    # =========================================================================
    def _ensure_subscribers_table(self):
        with self.db.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_subscribers (
                    chat_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    subscribed INTEGER DEFAULT 1,
                    last_active TEXT
                )
                """
            )
            conn.commit()

    def register_subscriber(self, chat_id: int, username: str = "", first_name: str = ""):
        try:
            from datetime import datetime, timezone
            self._ensure_subscribers_table()
            now_iso = datetime.now(timezone.utc).isoformat()
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO bot_subscribers (chat_id, username, first_name, subscribed, last_active)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        username = COALESCE(NULLIF(excluded.username, ''), bot_subscribers.username),
                        first_name = COALESCE(NULLIF(excluded.first_name, ''), bot_subscribers.first_name),
                        last_active = excluded.last_active
                    """,
                    (int(chat_id), username or "", first_name or "", now_iso),
                )
                conn.commit()
        except Exception:
            pass

    def get_active_subscribers(self) -> List[int]:
        self._ensure_subscribers_table()
        subs = set()
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute("SELECT chat_id FROM bot_subscribers WHERE subscribed = 1").fetchall()
                for r in rows:
                    if r[0]:
                        subs.add(int(r[0]))
        except Exception:
            pass
        env_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if env_chat and env_chat.lstrip("-").isdigit():
            subs.add(int(env_chat))
        return sorted(subs)

    def is_subscribed(self, chat_id: int) -> bool:
        """Returns True if the user has daily match alerts enabled."""
        self._ensure_subscribers_table()
        try:
            with self.db.get_connection() as conn:
                row = conn.execute("SELECT subscribed FROM bot_subscribers WHERE chat_id = ?", (int(chat_id),)).fetchone()
                if row is not None:
                    return bool(row["subscribed"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])
        except Exception:
            pass
        return True

    def toggle_subscription(self, chat_id: int) -> bool:
        """Toggles daily matchday alert subscription on/off for a user."""
        self._ensure_subscribers_table()
        cur = self.is_subscribed(chat_id)
        new_val = 0 if cur else 1
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "UPDATE bot_subscribers SET subscribed = ? WHERE chat_id = ?",
                    (new_val, int(chat_id)),
                )
                conn.commit()
        except Exception:
            pass
        return bool(new_val)

    def refresh_daily_data(self) -> Dict[str, Any]:
        """Runs the full data pipeline (football-data + ESPN + Standings + Elo + Odds) and clears caches."""
        try:
            from .data_pipeline import refresh as _pipeline_refresh
            report = _pipeline_refresh(with_timelines=False, backup=False)
        except Exception as e:
            report = {"status": "error", "error": str(e)}
        self._detail_cache.clear()
        self._standings_cache = None
        self._fixtures_cache = None
        return report

    def send_daily_digest(self) -> Dict[str, Any]:
        """Refreshes data and sends the daily 'Matches of the Day' digest to all subscribers."""
        sync_report = self.refresh_daily_data()
        subscribers = self.get_active_subscribers()
        text, markup = self.render_home_view("today")
        digest_header = "🔔 <b>DAILY LA LIGA UPDATE — MATCHES OF THE DAY</b>\n"
        full_text = digest_header + text
        sent = 0
        for cid in subscribers:
            res = self.send_message(cid, full_text, reply_markup=markup)
            if res.get("ok"):
                sent += 1
        return {"sync_status": sync_report.get("status", "ok"), "subscribers": len(subscribers), "sent": sent}

    # =========================================================================
    # DISPATCHERS (COMMANDS, TEXT & CALLBACK QUERIES)
    # =========================================================================
    def handle_command_or_text(self, text: str, chat_id: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
        raw = (text or "").strip()
        if not raw:
            return self.render_home_view("today", chat_id=chat_id)

        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower().split("@")[0]  # strip @bot_username if in group chat
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/start", "/help", "/about", "/welcome", "/guide"):
            return self.render_welcome_text()
        if cmd in ("/today", "/menu"):
            return self.render_home_view(arg if arg else "today", chat_id=chat_id)
        if cmd in ("/matches", "/fixtures", "/schedule"):
            md = int(arg) if arg.isdigit() else None
            return self.render_matchday_view(md)
        if cmd in ("/simulate", "/sim"):
            if arg.isdigit():
                num = int(arg)
                if num <= 38:
                    return self.render_matchday_simulation(num)
                return self.render_match_simulation(num)
            _, active_date, _ = self._resolve_active_date("today")
            return self.render_daily_simulation(active_date)
        if cmd in ("/standings", "/table"):
            return self.render_standings_view("all")
        if cmd in ("/clubs", "/teams"):
            if arg:
                return self.render_club_dossier(arg)
            return self.render_clubs_directory()
        if cmd == "/club":
            return self.render_club_dossier(arg) if arg else self.render_clubs_directory()
        if cmd in ("/players", "/leaders", "/scorers"):
            if arg:
                return self.render_smart_search(arg)
            return self.render_leaders_view("goals")
        if cmd == "/player":
            return self.render_smart_search(arg) if arg else self.render_leaders_view("overall_rating")
        if cmd == "/compare":
            return self.render_compare_menu(arg)
        if cmd in ("/msgmode", "/mode"):
            if arg in ("new", "fresh", "send", "messages"):
                self.send_new_messages = True
            elif arg in ("edit", "inplace", "compact", "update"):
                self.send_new_messages = False
            else:
                self.send_new_messages = not self.send_new_messages
            return self.render_msgmode_view()

        # Free-text search
        return self.render_smart_search(raw)

    def handle_callback_data(self, data: str, chat_id: Optional[int] = None) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Processes inline button callback_data and returns:
        (message_html, reply_markup, toast_notification)
        """
        parts = (data or "").split(":")
        prefix = parts[0]

        if prefix == "msgmode":
            target = parts[1] if len(parts) >= 2 else "toggle"
            if target in ("new", "fresh", "send"):
                self.send_new_messages = True
            elif target in ("edit", "inplace", "compact"):
                self.send_new_messages = False
            else:
                self.send_new_messages = not self.send_new_messages
            toast = "💬 Now sending fresh new messages!" if self.send_new_messages else "✏️ Now updating messages in-place!"
            return (*self.render_msgmode_view(), toast)
        if prefix == "sub":
            cid = chat_id or (self.get_active_subscribers()[-1] if self.get_active_subscribers() else 0)
            new_state = self.toggle_subscription(cid) if cid else True
            toast = "🔔 Daily Match Alerts Enabled!" if new_state else "🔕 Daily Match Alerts Paused."
            return (*self.render_home_view("today", chat_id=cid), toast)
        if prefix in ("welcome", "about") or data in ("menu:welcome", "menu:about"):
            return (*self.render_welcome_text(), "ℹ️ Pitchside Features & Guide")
        if prefix == "menu":
            return (*self.render_home_view("today", chat_id=chat_id), None)
        if prefix == "day" and len(parts) >= 2:
            return (*self.render_home_view(parts[1], chat_id=chat_id), f"📅 Date: {parts[1]}")
        if prefix == "daysim" and len(parts) >= 2:
            return (*self.render_daily_simulation(parts[1]), f"⚡ Simulated {parts[1]} Matches!")
        if prefix == "sync":
            self.refresh_daily_data()
            return (*self.render_home_view("today", chat_id=chat_id), "✅ Daily Matches & Standings Updated!")
        if prefix == "md" and len(parts) >= 2:
            md_val = self._get_active_matchday() if parts[1] == "current" else int(parts[1])
            return (*self.render_matchday_view(md_val), f"Matchday {md_val}")
        if prefix == "mdsim" and len(parts) >= 2:
            return (*self.render_matchday_simulation(int(parts[1])), f"⚡ Simulated Matchday {parts[1]}!")
        if prefix == "m" and len(parts) >= 2:
            tab = parts[2] if len(parts) >= 3 else "overview"
            return (*self.render_match_center(int(parts[1]), tab=tab), None)
        if prefix == "sim" and len(parts) >= 2:
            return (*self.render_match_simulation(int(parts[1])), "⚡ 90' Match Simulation Complete!")
        if prefix == "mxi" and len(parts) >= 2:
            return (*self.render_match_lineups(int(parts[1])), "Starting XIs & Live Form")
        if prefix == "mrad" and len(parts) >= 2:
            return (*self.render_match_radar(int(parts[1])), "6-Axis Tactical Radar")
        if prefix == "msub" and len(parts) >= 3:
            return (*self.render_sub_menu(int(parts[1]), parts[2]), "Select Tactical Substitution")
        if prefix == "msw" and len(parts) >= 5:
            fid = int(parts[1])
            out_id = int(parts[2])
            in_id = int(parts[3])
            side = "home" if parts[4] == "h" else "away"
            subs = [{"team": side, "side": side, "out_id": out_id, "in_id": in_id}]
            return (*self.render_match_simulation(fid, custom_subs=subs), "🔄 Substitution Applied & Match Re-Simulated!")
        if prefix == "st" and len(parts) >= 2:
            return (*self.render_standings_view(parts[1]), None)
        if prefix == "clubs":
            return (*self.render_clubs_directory(), None)
        if prefix == "c" and len(parts) >= 2:
            return (*self.render_club_dossier(parts[1]), None)
        if prefix == "cros" and len(parts) >= 2:
            return (*self.render_club_roster(int(parts[1])), None)
        if prefix == "cfx" and len(parts) >= 2:
            return (*self.render_club_fixtures(int(parts[1])), None)
        if prefix == "ldr" and len(parts) >= 2:
            return (*self.render_leaders_view(parts[1]), None)
        if prefix == "p" and len(parts) >= 2:
            return (*self.render_player_dossier(parts[1]), None)
        if prefix == "cmp":
            return (*self.render_compare_menu(), None)
        if prefix == "qcmp" and len(parts) >= 3:
            return (*self.render_compare_menu(f"{parts[1]} vs {parts[2]}"), None)

        return (*self.render_home_view("today", chat_id=chat_id), None)

    # =========================================================================
    # LONG-POLLING LOOP (WITH DAILY AUTO-UPDATE & GITHUB ACTIONS RUNTIME CAP)
    # =========================================================================
    def process_update(self, update: Dict[str, Any]):
        if "message" in update:
            msg = update["message"]
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            text = msg.get("text", "")
            if chat_id:
                self.register_subscriber(
                    chat_id,
                    username=chat.get("username", ""),
                    first_name=chat.get("first_name", ""),
                )
            if chat_id and text:
                raw_cmd = text.strip().split()[0].lower().split("@")[0] if text.strip() else ""
                if raw_cmd in ("/start", "/help", "/about", "/welcome", "/guide"):
                    gif_url, caption, markup = self.render_welcome_animation()
                    self.send_animation(chat_id, gif_url, caption=caption, reply_markup=markup)
                else:
                    resp_text, markup = self.handle_command_or_text(text, chat_id=chat_id)
                    self.send_message(chat_id, resp_text, reply_markup=markup)

        elif "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb.get("id")
            data = cb.get("data", "")
            msg = cb.get("message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            message_id = msg.get("message_id")

            if chat_id:
                self.register_subscriber(
                    chat_id,
                    username=chat.get("username", ""),
                    first_name=chat.get("first_name", ""),
                )
            if chat_id and data:
                if data in ("welcome", "about", "menu:welcome", "menu:about"):
                    if cb_id:
                        self.answer_callback(cb_id, text="ℹ️ Pitchside Features & Guide")
                    gif_url, caption, markup = self.render_welcome_animation()
                    if self.send_new_messages:
                        self.send_animation(chat_id, gif_url, caption=caption, reply_markup=markup)
                    else:
                        resp_text, markup_w = self.render_welcome_text()
                        self.edit_or_send(chat_id, message_id, resp_text, reply_markup=markup_w)
                else:
                    resp_text, markup, toast = self.handle_callback_data(data, chat_id=chat_id)
                    if cb_id:
                        self.answer_callback(cb_id, text=toast)
                    if self.send_new_messages:
                        self.send_message(chat_id, resp_text, reply_markup=markup)
                    else:
                        self.edit_or_send(chat_id, message_id, resp_text, reply_markup=markup)

    def run_polling(self, max_runtime_seconds: Optional[int] = None):
        if not self.token:
            print("\n" + "=" * 70)
            print(" ⚠️  TELEGRAM BOT TOKEN NOT CONFIGURED YET")
            print("=" * 70)
            print(" To connect this bot to Telegram:")
            print(" 1. Open Telegram and message @BotFather -> /newbot")
            print(" 2. Copy your token (e.g. 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ)")
            print(" 3. Either:")
            print("    • Put it in `.env` as:  TELEGRAM_BOT_TOKEN=your_token_here")
            print("    • Or run:               python run.py --bot --token YOUR_TOKEN")
            print("=" * 70 + "\n")
            return

        me = self._api_call("getMe", timeout=15)
        if not me.get("ok"):
            print(f"[!] Invalid Telegram Bot Token or connection error: {me.get('description')}")
            return

        bot_info = me.get("result", {})
        bot_username = bot_info.get("username", "PitchsideBot")
        self.register_commands()

        print("\n" + "=" * 68)
        print(" 🤖 PITCHSIDE LA LIGA TELEGRAM BOT RUNNING (DAILY AUTO-SYNC)")
        print(f" 🔗 Bot Username: @{bot_username} (https://t.me/{bot_username})")
        print(" 📅 Default View: Matches of the Day + 1-Click 90' Sim + Navigation")
        if max_runtime_seconds:
            print(f" ⏱️ Max Runtime: {max_runtime_seconds}s (GitHub Actions Cloud Mode)")
        print(" 🛑 Press Ctrl+C to stop the bot")
        print("=" * 68 + "\n")

        from datetime import datetime
        start_ts = time.time()
        last_sync_date = datetime.now().strftime("%Y-%m-%d")

        self._running = True
        while self._running:
            if max_runtime_seconds and (time.time() - start_ts) >= max_runtime_seconds:
                print(f"[+] Reached max runtime ({max_runtime_seconds}s). Exiting cleanly for next scheduled workflow.")
                self._running = False
                break

            # Automatic daily rollover check: sync data & push daily matches digest when date changes
            cur_date = datetime.now().strftime("%Y-%m-%d")
            if cur_date != last_sync_date:
                last_sync_date = cur_date
                try:
                    print(f"[+] New day detected ({cur_date}). Running automatic daily sync & digest...")
                    self.send_daily_digest()
                except Exception as e:
                    print(f"[!] Daily rollover sync error: {e}")

            try:
                res = self._api_call(
                    "getUpdates",
                    {"offset": self._offset, "timeout": 25, "allowed_updates": ["message", "callback_query"]},
                    timeout=35,
                )
                if not res.get("ok"):
                    time.sleep(3)
                    continue
                for upd in res.get("result", []):
                    self._offset = max(self._offset, upd["update_id"] + 1)
                    try:
                        self.process_update(upd)
                    except Exception as err:
                        print(f"[!] Error processing update {upd.get('update_id')}: {err}")
            except KeyboardInterrupt:
                print("\n[!] Stopping Telegram Bot...")
                self._running = False
                break
            except Exception as e:
                print(f"[!] Polling error: {e}")
                time.sleep(3)

    def start_background_thread(self) -> Optional[threading.Thread]:
        if not self.token:
            return None
        t = threading.Thread(target=self.run_polling, daemon=True, name="TelegramBotThread")
        t.start()
        return t
