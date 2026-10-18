"""
Lightweight REST API & Web Dashboard Server for La Liga Football Profiler.
Uses standard library http.server (no external dependencies needed).
"""
import http.server
import json
import time
import urllib.parse
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from .database import Database
from .comparator import PlayerComparator
from .api_football import APIFootballClient
from .simulation_engine import SimulationEngine
from .club_tactics import ClubTacticsRegistry
from .live_sync import LiveSyncEngine

# TTL cache for expensive match-detail payloads (lineup building runs two
# full squad searches per request). Finished matches are immutable; scheduled
# ones refresh quickly so form/position changes flow through.
_detail_cache = {}
DETAIL_TTL_FINISHED = 3600.0
DETAIL_TTL_PENDING = 60.0


def _cached_match_detail(db, fid):
    now = time.time()
    hit = _detail_cache.get(fid)
    if hit and now - hit[0] < hit[2]:
        return dict(hit[1])
    detail = db.get_match_detail(fid)
    if detail is None:
        return None
    status = (detail.get("fixture") or {}).get("status")
    ttl = DETAIL_TTL_FINISHED if status == "FINISHED" else DETAIL_TTL_PENDING
    _detail_cache[fid] = (now, detail, ttl)
    return dict(detail)


def clear_detail_cache():
    """Invalidates match-detail TTL cache (called after data refreshes)."""
    _detail_cache.clear()


class ProfilerHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.web_dir = Path(__file__).resolve().parent.parent / "web"
        self.db = Database()
        self.comparator = PlayerComparator(self.db)
        self.api_football = APIFootballClient()
        self.simulation_engine = SimulationEngine(self.db)
        self.live_sync = LiveSyncEngine(self.db)
        super().__init__(*args, directory=str(self.web_dir), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def _send_json(self, data: dict or list, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 404):
        self._send_json({"error": message, "status": status}, status=status)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API: Search Players
        if path == "/api/players":
            q = query.get("q", [""])[0]
            pos = query.get("pos", [""])[0]
            club = query.get("club", [""])[0]
            limit = int(query.get("limit", [100])[0])
            results = self.db.search_players(query=q, position=pos, club_slug=club, limit=limit)
            self._send_json({"count": len(results), "players": results})
            return

        # 2. API: Single Player Profile (/api/players/<slug>)
        if path.startswith("/api/players/"):
            slug = path[len("/api/players/"):]
            if not slug:
                self._send_error("Player slug required")
                return
            profile = self.db.get_player_by_slug(slug)
            if profile:
                self._send_json(profile)
            else:
                self._send_error(f"Player '{slug}' not found", status=404)
            return

        
        # API: Real-Time Live Matches (/api/live)
        if path == "/api/live":
            all_param = query.get("all", ["false"])[0].lower() == "true"
            league_id = None if all_param else 140
            raw_live = self.api_football.get_live_matches(league_id=league_id)
            
            live_matches = []
            for m in raw_live:
                fix = m.get("fixture", {})
                lg = m.get("league", {})
                teams = m.get("teams", {})
                goals = m.get("goals", {})
                st = fix.get("status", {})
                events = m.get("events", [])
                
                live_matches.append({
                    "id": fix.get("id"),
                    "league": lg.get("name"),
                    "country": lg.get("country"),
                    "round": lg.get("round"),
                    "home_name": teams.get("home", {}).get("name"),
                    "home_logo": teams.get("home", {}).get("logo"),
                    "home_score": goals.get("home", 0),
                    "away_name": teams.get("away", {}).get("name"),
                    "away_logo": teams.get("away", {}).get("logo"),
                    "away_score": goals.get("away", 0),
                    "status_short": st.get("short"),
                    "status_long": st.get("long"),
                    "elapsed": st.get("elapsed", 0),
                    "events": [
                        {
                            "time": ev.get("time", {}).get("elapsed"),
                            "team": ev.get("team", {}).get("name"),
                            "player": ev.get("player", {}).get("name"),
                            "type": ev.get("type"),
                            "detail": ev.get("detail"),
                        } for ev in events
                    ]
                })
            
            self._send_json({
                "count": len(live_matches),
                "live_matches": live_matches,
                "provider": "API-Football (Verified Official Live Feed)"
            })
            return

        # API: Fixtures
        if path == "/api/fixtures":
            md = query.get("matchday", [None])[0]
            slug = query.get("club", [None])[0]
            if md:
                md = int(md)
            fixtures = self.db.get_fixtures(matchday=md, club_slug=slug)
            current_md = self.db.get_current_matchday()

            # Check if any match is currently live in La Liga
            try:
                live_laliga = self.api_football.get_live_matches(league_id=140)
            except Exception:
                live_laliga = []

            if live_laliga:
                live_map = {}
                for lm in live_laliga:
                    hname = lm.get("teams", {}).get("home", {}).get("name", "").lower()
                    aname = lm.get("teams", {}).get("away", {}).get("name", "").lower()
                    live_map[(hname, aname)] = lm

                for f in fixtures:
                    fh = (f.get("home_name") or f.get("home_nickname") or "").lower()
                    fa = (f.get("away_name") or f.get("away_nickname") or "").lower()
                    for (lh, la), lm in live_map.items():
                        if (lh in fh or fh in lh) and (la in fa or fa in la):
                            f["status"] = "LIVE"
                            f["home_score"] = lm.get("goals", {}).get("home", 0)
                            f["away_score"] = lm.get("goals", {}).get("away", 0)
                            f["elapsed"] = lm.get("fixture", {}).get("status", {}).get("elapsed", 0)

            self._send_json({
                "fixtures": fixtures,
                "current_matchday": current_md,
                "live_count": len(live_laliga)
            })
            return

        # API: Single Match Tactical Preview (/api/match/<fixture_id>)
        if path.startswith("/api/match/"):
            fid_str = path[len("/api/match/"):]
            try:
                fid = int(fid_str)
                detail = _cached_match_detail(self.db, fid)
                if detail:
                    # Enrich with authentic Club & Manager Tactical Clash
                    h_slug = detail.get("home_team", {}).get("slug", "")
                    a_slug = detail.get("away_team", {}).get("slug", "")
                    h_pos = detail.get("home_team", {}).get("position") or 10
                    a_pos = detail.get("away_team", {}).get("position") or 10
                    detail["tactical_clash"] = ClubTacticsRegistry.evaluate_tactical_clash(h_slug, a_slug, h_pos, a_pos)
                    detail["forecast"] = self.simulation_engine.monte_carlo_forecast(detail)
                    self._send_json(detail)
                else:
                    self._send_error(f"Match with ID {fid} not found", status=404)
            except ValueError:
                self._send_error("Invalid fixture ID", status=400)
            return

        # API: Live Data Ingestion Health & Sync Status (/api/sync-status)
        if path == "/api/sync-status":
            self._send_json(self.live_sync.get_sync_status())
            return

        # API: Data pipeline status (mirror + live feeds + Elo ratings)
        if path == "/api/data-status":
            from .data_pipeline import sync_status as _pipeline_status
            self._send_json(_pipeline_status())
            return

        # API: Prediction ledger — hit-or-miss feed (/api/predictions?status=hits|misses|upcoming|all&limit=120)
        if path == "/api/predictions":
            from .predictions import get_feed, get_stats
            status = query.get("status", ["all"])[0]
            limit = int(query.get("limit", [120])[0])
            feed = get_feed(self.db, status=status, limit=limit)
            feed["stats"] = get_stats(self.db)
            self._send_json(feed)
            return

        # API: Pre-Match Probability Forecast (/api/forecast/<fixture_id>)
        if path.startswith("/api/forecast/"):
            fid_str = path[len("/api/forecast/"):]
            try:
                fid = int(fid_str)
                detail = _cached_match_detail(self.db, fid)
                if not detail:
                    self._send_error(f"Match with ID {fid} not found", status=404)
                    return
                forecast = self.simulation_engine.monte_carlo_forecast(detail)
                self._send_json(forecast)
            except ValueError:
                self._send_error("Invalid fixture ID", status=400)
            return

        # API: Calibrated Match Simulation with Dynamic Player Form (/api/simulate-match/<fixture_id>)
        if path.startswith("/api/simulate-match/"):
            fid_str = path[len("/api/simulate-match/"):]
            try:
                fid = int(fid_str)
                detail = _cached_match_detail(self.db, fid)
                if not detail:
                    self._send_error(f"Match with ID {fid} not found", status=404)
                    return
                sim_result = self.simulation_engine.simulate_fixture(detail)
                self._send_json(sim_result)
            except ValueError:
                self._send_error("Invalid fixture ID", status=400)
            return

        # 3. API: All Teams / Clubs
        if path == "/api/teams":
            clubs = self.db.get_all_clubs()
            self._send_json({"count": len(clubs), "teams": clubs})
            return

        # 4. API: Leaderboards (/api/leaders?stat=goals&limit=10)
        if path == "/api/leaders":
            stat = query.get("stat", ["goals"])[0]
            limit = int(query.get("limit", [10])[0])
            if stat == "goals":
                try:
                    ts = self.api_football.get_top_scorers()
                    if ts:
                        leaders = []
                        for s in ts[:limit]:
                            p = s.get("player", {})
                            st = s.get("statistics", [{}])[0]
                            leaders.append({
                                "name": p.get("name"),
                                "nickname": p.get("name"),
                                "club_nickname": st.get("team", {}).get("name"),
                                "club_shield": st.get("team", {}).get("logo"),
                                "photo_url": p.get("photo"),
                                "overall_rating": int(float(st.get("games", {}).get("rating") or 7.0) * 11.5),
                                "stat_name": "goals",
                                "stat_value": st.get("goals", {}).get("total", 0),
                                "assists": st.get("goals", {}).get("assists", 0)
                            })
                        self._send_json({"stat": stat, "count": len(leaders), "leaders": leaders})
                        return
                except Exception:
                    pass
            leaders = self.db.get_leaders(metric=stat, limit=limit)
            self._send_json({"stat": stat, "count": len(leaders), "leaders": leaders})
            return

        # 5. API: Head-to-Head Compare (/api/compare?p1=slug1&p2=slug2)
        if path == "/api/compare":
            p1 = query.get("p1", [""])[0]
            p2 = query.get("p2", [""])[0]
            if not p1 or not p2:
                self._send_error("Both p1 and p2 query parameters are required", status=400)
                return
            comparison = self.comparator.compare_players(p1, p2)
            if comparison:
                self._send_json(comparison)
            else:
                self._send_error(f"Could not compare players '{p1}' and '{p2}'", status=404)
            return

        # 6. API: All Club Profiles (/api/clubs)
        if path == "/api/clubs":
            clubs = self.db.get_all_club_profiles()
            self._send_json({"count": len(clubs), "clubs": clubs})
            return

        # 7. API: Single Club Profile (/api/clubs/<slug>)
        if path.startswith("/api/clubs/"):
            slug = path[len("/api/clubs/"):]
            if not slug:
                self._send_error("Club slug required")
                return
            profile = self.db.get_club_profile(slug)
            if profile:
                self._send_json(profile)
            else:
                self._send_error(f"Club '{slug}' not found", status=404)
            return

        # 8. API: Official Standings (/api/standings)
        if path == "/api/standings":
            standings = self.db.get_standings()
            self._send_json({"count": len(standings), "standings": standings})
            return

        # 9. API: Compare Clubs (/api/compare-clubs?c1=slug1&c2=slug2)
        if path == "/api/compare-clubs":
            c1 = query.get("c1", [""])[0]
            c2 = query.get("c2", [""])[0]
            if not c1 or not c2:
                self._send_error("Both c1 and c2 query parameters are required", status=400)
                return
            comparison = self.comparator.compare_clubs(c1, c2)
            if comparison:
                self._send_json(comparison)
            else:
                self._send_error(f"Could not compare clubs '{c1}' and '{c2}'", status=404)
            return

        # 10. API: Summary (/api/summary)
        if path == "/api/summary":
            counts = self.db.get_total_counts()
            top_scorers = self.db.get_leaders("goals", limit=5)
            top_assists = self.db.get_leaders("assists", limit=5)
            top_overall = self.db.get_leaders("overall_rating", limit=5)
            top_clubs = self.db.get_standings()[:5]
            self._send_json({
                "counts": counts,
                "top_scorers": top_scorers,
                "top_assists": top_assists,
                "top_rated": top_overall,
                "top_clubs": top_clubs,
            })
            return

        # Static file handling (HTML, CSS, JS)
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Guarded data refresh from the mirrors (football-data.co.uk + ESPN + Elo recompute)
        if path == "/api/refresh-data":
            try:
                from .data_pipeline import refresh as _pipeline_refresh
                report = _pipeline_refresh(with_timelines=False, backup=False)
                clear_detail_cache()
                self._send_json(report, status=200 if report.get("status") == "ok" else 500)
            except Exception as e:
                self._send_error(f"Refresh failed: {e}", status=500)
            return

        # Interactive Simulation with Manager Mode Substitutions
        if path.startswith("/api/simulate-match/"):
            fid_str = path[len("/api/simulate-match/"):]
            try:
                fid = int(fid_str)
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len) if content_len > 0 else b"{}"
                payload = json.loads(body.decode("utf-8")) if body else {}

                subs = payload.get("substitutions", [])

                detail = self.db.get_match_detail(fid)
                if not detail:
                    self._send_error(f"Match with ID {fid} not found", status=404)
                    return
                sim_result = self.simulation_engine.simulate_fixture(detail, custom_substitutions=subs)
                self._send_json(sim_result)
            except Exception as e:
                self._send_error(f"Simulation error: {str(e)}", status=400)
            return

        self._send_error("Endpoint not found", status=404)


def run_server(host: str = "127.0.0.1", port: int = 8080):
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, ProfilerHTTPRequestHandler)
    print(f"\n" + "=" * 65)
    print(f" 🚀 LA LIGA PROFILER WEB DASHBOARD RUNNING")
    print(f" 🌐 Access at: http://{host}:{port}")
    print(f" 🛑 Press Ctrl+C to terminate server")
    print("=" * 65 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
