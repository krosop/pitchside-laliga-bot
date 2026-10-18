"""
Official API-Football (API-Sports) Integration Client.
Provides real-time in-play data, official 2024/25 La Liga fixtures,
20-team standings, team metadata, and top scorer leaderboards.
Includes intelligent caching to respect the 100 requests/day quota.
"""
import urllib.request
import urllib.error
import json
import time
import ssl
from pathlib import Path
from typing import Optional, Dict, Any, List

API_KEY = "ad8279c482baa8bb4b5117e0f1b26d14"
BASE_URL = "https://v3.football.api-sports.io"
LA_LIGA_LEAGUE_ID = 140
CURRENT_SEASON = 2024

class APIFootballClient:
    def __init__(self, api_key: str = API_KEY, cache_dir: Optional[Path] = None):
        self.api_key = api_key
        if cache_dir is None:
            self.cache_dir = Path(__file__).resolve().parent.parent / "data" / "cache" / "api_football"
        else:
            self.cache_dir = Path(cache_dir)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Read-only bundle FS (e.g. Vercel serverless): fall back to tmp.
            import tempfile
            self.cache_dir = Path(tempfile.gettempdir()) / "statsphere_cache" / "api_football"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for live polling (60s TTL)
        self._memory_cache = {}
        self._memory_cache_timestamps = {}
        
        # SSL context
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-apisports-key": self.api_key,
            "User-Agent": "STATSPHERE-Engine/2.0"
        }

    def _fetch_from_api(self, endpoint: str) -> Dict[str, Any]:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        req = urllib.request.Request(url, headers=self._get_headers())
        with urllib.request.urlopen(req, timeout=12, context=self.ctx) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data

    def _get_cached_or_fetch(self, endpoint: str, cache_file_name: str, ttl_seconds: int = 3600) -> Dict[str, Any]:
        cache_path = self.cache_dir / cache_file_name
        now = time.time()
        
        # Check disk cache
        if cache_path.exists():
            mtime = cache_path.stat().st_mtime
            if (now - mtime) < ttl_seconds:
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
        
        # Fetch fresh
        data = self._fetch_from_api(endpoint)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return data

    def get_live_matches(self, league_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetches in-play live matches with 60-second in-memory cache
        to avoid burning daily rate limits.
        """
        cache_key = f"live_{league_id or 'all'}"
        now = time.time()
        
        if cache_key in self._memory_cache:
            ts = self._memory_cache_timestamps.get(cache_key, 0)
            if now - ts < 60:
                return self._memory_cache[cache_key]
        
        endpoint = "fixtures?live=all" if not league_id else f"fixtures?live={league_id}"
        try:
            raw = self._fetch_from_api(endpoint)
            matches = raw.get("response", [])
            self._memory_cache[cache_key] = matches
            self._memory_cache_timestamps[cache_key] = now
            return matches
        except Exception as e:
            print(f"[!] API-Football live fetch error: {e}")
            return self._memory_cache.get(cache_key, [])

    def get_standings(self, league_id: int = LA_LIGA_LEAGUE_ID, season: int = CURRENT_SEASON) -> List[Dict[str, Any]]:
        """Fetches official 20-team standings (cached 2 hours)."""
        cache_file = f"standings_{league_id}_{season}.json"
        raw = self._get_cached_or_fetch(f"standings?league={league_id}&season={season}", cache_file, ttl_seconds=7200)
        try:
            return raw.get("response", [])[0]["league"]["standings"][0]
        except (IndexError, KeyError):
            return []

    def get_teams(self, league_id: int = LA_LIGA_LEAGUE_ID, season: int = CURRENT_SEASON) -> List[Dict[str, Any]]:
        """Fetches official 20 clubs (cached 24 hours)."""
        cache_file = f"teams_{league_id}_{season}.json"
        raw = self._get_cached_or_fetch(f"teams?league={league_id}&season={season}", cache_file, ttl_seconds=86400)
        return raw.get("response", [])

    def get_fixtures(self, league_id: int = LA_LIGA_LEAGUE_ID, season: int = CURRENT_SEASON) -> List[Dict[str, Any]]:
        """Fetches all 380 official fixtures (cached 2 hours)."""
        cache_file = f"fixtures_{league_id}_{season}.json"
        raw = self._get_cached_or_fetch(f"fixtures?league={league_id}&season={season}", cache_file, ttl_seconds=7200)
        return raw.get("response", [])

    def get_top_scorers(self, league_id: int = LA_LIGA_LEAGUE_ID, season: int = CURRENT_SEASON) -> List[Dict[str, Any]]:
        """Fetches top scorers leaderboard (cached 2 hours)."""
        cache_file = f"topscorers_{league_id}_{season}.json"
        raw = self._get_cached_or_fetch(f"players/topscorers?league={league_id}&season={season}", cache_file, ttl_seconds=7200)
        return raw.get("response", [])

    def get_top_assists(self, league_id: int = LA_LIGA_LEAGUE_ID, season: int = CURRENT_SEASON) -> List[Dict[str, Any]]:
        """Fetches top assists leaderboard (cached 2 hours)."""
        cache_file = f"topassists_{league_id}_{season}.json"
        raw = self._get_cached_or_fetch(f"players/topassists?league={league_id}&season={season}", cache_file, ttl_seconds=7200)
        return raw.get("response", [])

    def get_status(self) -> Dict[str, Any]:
        """Checks API quota and account status."""
        return self._fetch_from_api("status").get("response", {})
