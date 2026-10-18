"""
Official La Liga Data Scraper & Ingestion Pipeline.
Extracts 100% accurate player statistics and official Opta rankings directly from La Liga.
"""
import urllib.request
import urllib.error
import json
import re
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable

from .models import Club, PlayerBio, PlayerStats, ProfileScores, PlayerProfile, ClubProfile, ClubStats, ClubScores
from .profiler import Profiler
from .club_profiler import ClubProfiler


class LaLigaScraper:
    BASE_URL = "https://www.laliga.com/en-ES/stats/laliga-easports/scorers"
    PLAYER_URL_TEMPLATE = "https://www.laliga.com/en-ES/player/{slug}"
    STANDINGS_URL = "https://www.laliga.com/en-ES/laliga-easports/standing"
    CLUB_URL_TEMPLATE = "https://www.laliga.com/en-ES/clubs/{slug}"
    TOTAL_PAGES = 26  # 520 players / 20 per page

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
            self.cache_dir = base_dir / "data" / "cache"
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "players").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "clubs").mkdir(parents=True, exist_ok=True)

    def _fetch_html(self, url: str, retries: int = 3, delay: float = 0.5) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as res:
                    return res.read().decode("utf-8")
            except (urllib.error.URLError, urllib.error.HTTPError) as e:
                if attempt == retries - 1:
                    raise e
                time.sleep(delay * (attempt + 1))
        return ""

    def _extract_next_data(self, html: str) -> Dict[str, Any]:
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if not match:
            raise ValueError("Could not find __NEXT_DATA__ payload in page HTML")
        return json.loads(match.group(1))

    def fetch_rankings_page(self, page: int, use_cache: bool = True) -> List[Dict[str, Any]]:
        cache_file = self.cache_dir / f"page_{page}.json"
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        url = f"{self.BASE_URL}/page/{page}" if page > 1 else self.BASE_URL
        html = self._fetch_html(url)
        data = self._extract_next_data(html)

        stats_data = data.get("props", {}).get("pageProps", {}).get("statsData", {})
        rankings = stats_data.get("player_rankings", [])

        # Cache page data
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(rankings, f, indent=2, ensure_ascii=False)

        return rankings

    def fetch_player_bio(self, slug: str, use_cache: bool = True) -> Dict[str, Any]:
        cache_file = self.cache_dir / "players" / f"{slug}.json"
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        url = self.PLAYER_URL_TEMPLATE.format(slug=slug)
        try:
            html = self._fetch_html(url, retries=2, delay=0.3)
            data = self._extract_next_data(html)
            player_info = data.get("props", {}).get("pageProps", {}).get("player", {})
            bio_data = {
                "date_of_birth": player_info.get("date_of_birth"),
                "place_of_birth": player_info.get("place_of_birth"),
                "height": player_info.get("height"),
                "weight": player_info.get("weight"),
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(bio_data, f, indent=2, ensure_ascii=False)
            return bio_data
        except Exception:
            return {}

    def fetch_standings(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Fetches official La Liga standings table."""
        cache_file = self.cache_dir / "standings.json"
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        try:
            html = self._fetch_html(self.STANDINGS_URL)
            data = self._extract_next_data(html)
            standings_raw = data.get("props", {}).get("pageProps", {}).get("standings", [])
            standings_list = []
            for row in standings_raw:
                t = row.get("team") or {}
                q = row.get("qualify") or {}
                gd_raw = str(row.get("goal_difference", 0))
                try:
                    gd = int(gd_raw.replace("+", ""))
                except Exception:
                    gd = 0

                standings_list.append({
                    "position": row.get("position", 0),
                    "club_id": t.get("id", 0),
                    "club_slug": t.get("slug", ""),
                    "club_name": t.get("name", ""),
                    "club_nickname": t.get("nickname", ""),
                    "club_shortname": t.get("shortname", ""),
                    "played": row.get("played", 0),
                    "won": row.get("won", 0),
                    "drawn": row.get("drawn", 0),
                    "lost": row.get("lost", 0),
                    "goals_for": row.get("goals_for", 0),
                    "goals_against": row.get("goals_against", 0),
                    "goal_difference": gd,
                    "points": row.get("points", 0),
                    "qualification": q.get("name") if isinstance(q, dict) else None,
                })

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(standings_list, f, indent=2, ensure_ascii=False)

            return standings_list
        except Exception as e:
            print(f"Warning: Failed to fetch live standings ({e}).")
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []

    def fetch_club_details(self, slug: str, use_cache: bool = True) -> Dict[str, Any]:
        """Fetches venue, president, and address for a club."""
        cache_file = self.cache_dir / "clubs" / f"{slug}.json"
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        url = self.CLUB_URL_TEMPLATE.format(slug=slug)
        try:
            html = self._fetch_html(url, retries=2, delay=0.3)
            data = self._extract_next_data(html)
            club_data = data.get("props", {}).get("pageProps", {}).get("club", {})
            venue_data = club_data.get("venue") or {}
            venue_img = venue_data.get("image") or {}
            venue_resizes = venue_img.get("resizes") or {}
            venue_url = venue_resizes.get("large") or venue_resizes.get("medium") or venue_img.get("url")

            inner_club = club_data.get("club") or {}
            president = inner_club.get("president") or club_data.get("president")

            details = {
                "stadium_name": venue_data.get("name"),
                "stadium_image_url": venue_url,
                "president": president,
                "address": club_data.get("address"),
                "web_url": club_data.get("web"),
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(details, f, indent=2, ensure_ascii=False)
            return details
        except Exception:
            return {}

    def parse_player_data(self, raw_player: Dict[str, Any]) -> Tuple[Club, PlayerBio, PlayerStats, Dict[str, int]]:
        # 1. Parse Club
        team_data = raw_player.get("team") or {}
        shield_dict = team_data.get("shield") or {}
        shield_resizes = shield_dict.get("resizes") or {}
        shield_url = shield_resizes.get("medium") or shield_dict.get("url")

        club = Club(
            id=team_data.get("id", 0),
            slug=team_data.get("slug", "unknown"),
            name=team_data.get("name", "Unknown Club"),
            nickname=team_data.get("nickname", "Unknown"),
            shortname=team_data.get("shortname", ""),
            foundation=team_data.get("foundation"),
            shield_url=shield_url,
            color=team_data.get("color"),
            color_secondary=team_data.get("color_secondary")
        )

        # 2. Parse Player Bio
        pos_data = raw_player.get("position") or {}
        pos_name = pos_data.get("name", "Forward") if isinstance(pos_data, dict) else "Forward"
        pos_slug = pos_data.get("slug", "forward") if isinstance(pos_data, dict) else "forward"

        photos = raw_player.get("photos") or {}
        photo_url = None
        if isinstance(photos, dict) and "001" in photos:
            p001 = photos["001"]
            if isinstance(p001, dict):
                photo_url = p001.get("512x556") or p001.get("256x278") or p001.get("1024x1113")

        country_data = raw_player.get("country") or {}
        country_code = country_data.get("id") if isinstance(country_data, dict) else str(country_data)

        bio = PlayerBio(
            id=raw_player.get("id", 0),
            opta_id=raw_player.get("opta_id", ""),
            slug=raw_player.get("slug", ""),
            name=raw_player.get("name", "Unknown"),
            nickname=raw_player.get("nickname") or raw_player.get("name", "Unknown"),
            shirt_number=raw_player.get("shirt_number"),
            position_name=pos_name,
            position_slug=pos_slug,
            country_code=country_code,
            photo_url=photo_url,
            club_id=club.id,
            club_name=club.nickname,
            club_shield=club.shield_url
        )

        # 3. Parse Stats and Rankings
        stats_list = raw_player.get("stats") or []
        stat_map = {}
        ranking_map = {}

        for item in stats_list:
            name = item.get("name", "")
            val = item.get("stat", 0)
            if name.endswith("_ranking"):
                ranking_map[name] = int(val)
            else:
                stat_map[name] = val

        stats = PlayerStats(
            games_played=int(stat_map.get("total_games", 0)),
            starts=int(stat_map.get("total_games", 0)) - int(stat_map.get("total_sub_on", 0)),
            sub_on=int(stat_map.get("total_sub_on", 0)),
            sub_off=int(stat_map.get("total_sub_off", 0)),
            minutes_played=int(stat_map.get("total_mins_played", 0)),

            goals=int(stat_map.get("total_goals", 0)),
            home_goals=int(stat_map.get("total_home_goals", 0)),
            away_goals=int(stat_map.get("total_away_goals", 0)),
            goals_ibox=int(stat_map.get("total_att_ibox_goal", 0)),
            goals_obox=int(stat_map.get("total_att_obox_goal", 0)),
            shots=int(stat_map.get("total_scoring_att", 0)),
            shots_on_target=int(stat_map.get("total_ontarget_attempt", 0)),
            shots_ibox=int(stat_map.get("total_attempts_ibox", 0)),
            shots_obox=int(stat_map.get("total_attempts_obox", 0)),
            blocked_shots=int(stat_map.get("total_blocked_scoring_att", 0)),
            freekick_goals=int(stat_map.get("total_att_freekick_goal", 0)),
            penalty_goals=int(stat_map.get("total_att_pen_goal", 0)),
            penalties_taken=int(stat_map.get("total_att_pen_target", 0)),

            assists=int(stat_map.get("total_assists", 0)),
            key_passes=int(stat_map.get("total_att_assist", 0)),
            passes_total=int(stat_map.get("total_pass", 0)),
            passes_accurate=int(stat_map.get("total_accurate_pass", 0)),
            forward_passes=int(stat_map.get("total_fwd_zone_pass", 0)),
            long_balls=int(stat_map.get("total_long_balls", 0)),
            crosses=int(stat_map.get("total_crosses", 0)),

            dribbles_attempted=int(stat_map.get("total_dribbles_attempted", 0)),
            dribbles_won=int(stat_map.get("total_won_contest", 0)),
            touches_in_box=int(stat_map.get("total_touches_in_opposition_box", 0)),
            fouls_drawn=int(stat_map.get("total_was_fouled", 0)),

            tackles_total=int(stat_map.get("total_tackle", 0)),
            tackles_won=int(stat_map.get("total_won_tackle", 0)),
            tackle_pct=float(stat_map.get("total_tackle_pct", 0.0)),
            interceptions=int(stat_map.get("total_interception", 0)),
            clearances=int(stat_map.get("total_clearance", 0)),
            blocked_attempts=int(stat_map.get("total_effective_clearance", 0)),

            duels_won=int(stat_map.get("total_duels_won", 0)),
            duels_lost=int(stat_map.get("total_duels_lost", 0)),
            aerial_won=int(stat_map.get("total_aerial_won", 0)),
            aerial_lost=int(stat_map.get("total_aerial_lost", 0)),
            challenges_lost=int(stat_map.get("total_challenge_lost", 0)),

            fouls_conceded=int(stat_map.get("total_fouls", 0)),
            yellow_cards=int(stat_map.get("total_yellow_card", 0)),
            second_yellows=int(stat_map.get("total_second_yellow", 0)),
            red_cards=int(stat_map.get("total_red_card", 0)),
            offsides=int(stat_map.get("total_offside", 0)),

            saves_total=int(stat_map.get("total_saves", 0)),
            saves_ibox=int(stat_map.get("total_saved_ibox", 0)),
            saves_obox=int(stat_map.get("total_saved_obox", 0)),
            clean_sheets=int(stat_map.get("total_clean_sheet", 0)),
            goals_conceded=int(stat_map.get("total_goals_conceded", 0)),
            high_claims=int(stat_map.get("total_high_claim", 0)),
            punches=int(stat_map.get("total_punches", 0))
        )

        return club, bio, stats, ranking_map

    def sync_all(self, use_cache: bool = True, enrich_bios: bool = True,
                 progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[PlayerProfile]:
        """
        Synchronizes all 26 pages of La Liga player statistics from the official source.
        Returns a list of complete PlayerProfile objects.
        """
        all_profiles = []
        clubs_dict = {}

        total_pages = self.TOTAL_PAGES

        for page in range(1, total_pages + 1):
            if progress_callback:
                progress_callback(page, total_pages, f"Ingesting rankings page {page}/{total_pages}...")

            rankings = self.fetch_rankings_page(page, use_cache=use_cache)
            for raw_player in rankings:
                club, bio, stats, ranking_map = self.parse_player_data(raw_player)
                clubs_dict[club.id] = club

                # Build profile intelligence
                profile = Profiler.build_profile(bio, stats, ranking_map)
                all_profiles.append((club, profile))

            # Small courtesy throttle when fetching uncached pages
            if not use_cache and page < total_pages:
                time.sleep(0.3)

        # Enrich top 50 active players with bio data if requested
        if enrich_bios:
            # Sort by minutes played or goals to get notable players
            sorted_for_bio = sorted(all_profiles, key=lambda x: (x[1].stats.minutes_played, x[1].stats.goals), reverse=True)
            to_enrich = sorted_for_bio[:40]

            for idx, (club, profile) in enumerate(to_enrich):
                if progress_callback and idx % 10 == 0:
                    progress_callback(idx + 1, len(to_enrich), f"Enriching player bio {idx+1}/{len(to_enrich)}...")
                bio_info = self.fetch_player_bio(profile.bio.slug, use_cache=use_cache)
                if bio_info:
                    profile.bio.date_of_birth = bio_info.get("date_of_birth")
                    profile.bio.place_of_birth = bio_info.get("place_of_birth")
                    profile.bio.height = bio_info.get("height")
                    profile.bio.weight = bio_info.get("weight")

        return all_profiles

    def sync_clubs(self, db, use_cache: bool = True,
                   progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[ClubProfile]:
        """
        Synchronizes official standings, fetches club venue metadata, aggregates squad stats,
        builds full ClubProfiles, and saves them to the database and JSON export.
        """
        if progress_callback:
            progress_callback(1, 4, "Fetching official La Liga standings table...")

        standings = self.fetch_standings(use_cache=use_cache)
        standings_by_slug = {s["club_slug"]: s for s in standings if s.get("club_slug")}
        standings_by_id = {s["club_id"]: s for s in standings if s.get("club_id")}

        # Get existing clubs from database
        all_clubs = db.get_all_clubs()
        total_clubs = len(all_clubs)
        club_profiles = []

        for idx, club_data in enumerate(all_clubs):
            c_slug = club_data["slug"]
            c_id = club_data["id"]

            if progress_callback:
                progress_callback(idx + 1, total_clubs, f"Profiling club {idx+1}/{total_clubs}: {club_data.get('nickname')}...")

            # Match standing info
            std = standings_by_slug.get(c_slug) or standings_by_id.get(c_id) or {}

            # Fetch venue and metadata
            meta = self.fetch_club_details(c_slug, use_cache=use_cache)

            # Create updated Club object
            club_obj = Club(
                id=c_id,
                slug=c_slug,
                name=club_data.get("name", ""),
                nickname=club_data.get("nickname", ""),
                shortname=club_data.get("shortname", ""),
                foundation=club_data.get("foundation"),
                shield_url=club_data.get("shield_url"),
                color=club_data.get("color"),
                color_secondary=club_data.get("color_secondary"),
                stadium=meta.get("stadium_name") or club_data.get("stadium"),
                stadium_name=meta.get("stadium_name") or club_data.get("stadium_name"),
                stadium_image_url=meta.get("stadium_image_url") or club_data.get("stadium_image_url"),
                president=meta.get("president") or club_data.get("president"),
                address=meta.get("address") or club_data.get("address"),
                web_url=meta.get("web_url") or club_data.get("web_url"),
                position=std.get("position") or club_data.get("position"),
                played=std.get("played", club_data.get("played") or 0),
                won=std.get("won", club_data.get("won") or 0),
                drawn=std.get("drawn", club_data.get("drawn") or 0),
                lost=std.get("lost", club_data.get("lost") or 0),
                goals_for=std.get("goals_for", club_data.get("goals_for") or 0),
                goals_against=std.get("goals_against", club_data.get("goals_against") or 0),
                goal_difference=std.get("goal_difference", club_data.get("goal_difference") or 0),
                points=std.get("points", club_data.get("points") or 0),
                qualification=std.get("qualification") or club_data.get("qualification"),
            )

            # Upsert updated club basic info
            db.upsert_club(club_obj)

            # Load squad players from database
            raw_players = db.search_players(club_slug=c_slug, limit=100)
            player_profiles = []
            for rp in raw_players:
                bio = PlayerBio(
                    id=rp["id"],
                    opta_id=rp.get("opta_id", ""),
                    slug=rp["slug"],
                    name=rp["name"],
                    nickname=rp.get("nickname", rp["name"]),
                    shirt_number=rp.get("shirt_number"),
                    position_name=rp.get("position_name", "Forward"),
                    position_slug=rp.get("position_slug", "forward"),
                    country_code=rp.get("country_code"),
                    photo_url=rp.get("photo_url"),
                    club_id=c_id,
                    club_name=club_obj.nickname,
                    club_shield=club_obj.shield_url,
                    date_of_birth=rp.get("date_of_birth"),
                    place_of_birth=rp.get("place_of_birth"),
                    height=rp.get("height"),
                    weight=rp.get("weight"),
                )

                s_dict = rp.get("stats") or {}
                stats = PlayerStats(**{k: s_dict[k] for k in s_dict if hasattr(PlayerStats, k)})

                sc_dict = rp.get("scores") or {}
                scores = ProfileScores(**{k: sc_dict[k] for k in sc_dict if hasattr(ProfileScores, k)})

                player_profiles.append(PlayerProfile(
                    bio=bio,
                    stats=stats,
                    rankings={},
                    scores=scores,
                    archetype=rp.get("archetype", "Standard Player"),
                    strengths=[],
                    weaknesses=[]
                ))

            # Run Club Profiler
            profile = ClubProfiler.profile_club(club_obj, player_profiles)
            club_profiles.append(profile)

            # Persist to database
            db.upsert_club_profile(profile)

        # Export to JSON
        db.export_clubs_to_json()

        return club_profiles

