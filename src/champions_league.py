"""
PITCHSIDE — UEFA Champions League (uefa.champions) Integration Engine
====================================================================
End-to-end integration for the 36-team UEFA Champions League Phase:
  * 36 authentic European club profiles, tactical DNA, stadiums, crests, and ratings
  * Database seeding & Elo ratings calibration for European competition
  * Real-time sync with official ESPN UCL feeds for 36-club single table
  * Full 144 league phase fixtures ingestion across all 8 matchdays
  * Seamless multi-competition integration with Pitchside's Dixon-Coles simulation engine
"""

import json
import logging
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .database import Database
from .models import Club

logger = logging.getLogger(__name__)

ESPN_UCL_STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer/uefa.champions/standings"
ESPN_UCL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"
UA = {"User-Agent": "curl/8.4.0", "Accept": "application/json"}

# The 36 official Champions League clubs
CHAMPIONS_LEAGUE_CLUBS: List[Dict[str, Any]] = [
    {
        "id": 301,
        "slug": "ucl-psg",
        "name": "Paris Saint-Germain",
        "nickname": "Paris Saint-Germain",
        "shortname": "PSG",
        "espn_id": "160",
        "stadium_name": "Parc des Princes",
        "color": "#004170",
        "color_secondary": "#DA291C",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/160.png",
        "formation": "4-3-3",
        "att_rating": 89,
        "mid_rating": 86,
        "def_rating": 84,
        "overall_rating": 86,
        "elo": 1780.0,
        "position": 1,
    },
    {
        "id": 302,
        "slug": "ucl-barcelona",
        "name": "FC Barcelona",
        "nickname": "FC Barcelona",
        "shortname": "BAR",
        "espn_id": "83",
        "stadium_name": "Spotify Camp Nou / Estadi Olímpic",
        "color": "#004D98",
        "color_secondary": "#A50044",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/83.png",
        "formation": "4-2-3-1",
        "att_rating": 89,
        "mid_rating": 87,
        "def_rating": 83,
        "overall_rating": 87,
        "elo": 1790.0,
        "position": 2,
    },
    {
        "id": 303,
        "slug": "ucl-aston-villa",
        "name": "Aston Villa FC",
        "nickname": "Aston Villa",
        "shortname": "AVL",
        "espn_id": "362",
        "stadium_name": "Villa Park",
        "color": "#95BFE5",
        "color_secondary": "#670E36",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/362.png",
        "formation": "4-4-2",
        "att_rating": 83,
        "mid_rating": 82,
        "def_rating": 81,
        "overall_rating": 82,
        "elo": 1640.0,
        "position": 3,
    },
    {
        "id": 304,
        "slug": "ucl-vfb-stuttgart",
        "name": "VfB Stuttgart",
        "nickname": "VfB Stuttgart",
        "shortname": "VFB",
        "espn_id": "134",
        "stadium_name": "MHPArena",
        "color": "#E30613",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/134.png",
        "formation": "4-2-3-1",
        "att_rating": 81,
        "mid_rating": 80,
        "def_rating": 79,
        "overall_rating": 80,
        "elo": 1600.0,
        "position": 4,
    },
    {
        "id": 305,
        "slug": "ucl-liverpool",
        "name": "Liverpool FC",
        "nickname": "Liverpool",
        "shortname": "LIV",
        "espn_id": "364",
        "stadium_name": "Anfield",
        "color": "#C8102E",
        "color_secondary": "#00B2A9",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/364.png",
        "formation": "4-3-3",
        "att_rating": 88,
        "mid_rating": 86,
        "def_rating": 86,
        "overall_rating": 87,
        "elo": 1785.0,
        "position": 5,
    },
    {
        "id": 306,
        "slug": "ucl-sporting-cp",
        "name": "Sporting Clube de Portugal",
        "nickname": "Sporting CP",
        "shortname": "SCP",
        "espn_id": "2250",
        "stadium_name": "Estádio José Alvalade",
        "color": "#008050",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/2250.png",
        "formation": "3-4-2-1",
        "att_rating": 84,
        "mid_rating": 82,
        "def_rating": 81,
        "overall_rating": 82,
        "elo": 1650.0,
        "position": 6,
    },
    {
        "id": 307,
        "slug": "ucl-arsenal",
        "name": "Arsenal FC",
        "nickname": "Arsenal",
        "shortname": "ARS",
        "espn_id": "359",
        "stadium_name": "Emirates Stadium",
        "color": "#EF0107",
        "color_secondary": "#063672",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/359.png",
        "formation": "4-3-3",
        "att_rating": 87,
        "mid_rating": 87,
        "def_rating": 87,
        "overall_rating": 87,
        "elo": 1775.0,
        "position": 7,
    },
    {
        "id": 308,
        "slug": "ucl-real-madrid",
        "name": "Real Madrid CF",
        "nickname": "Real Madrid",
        "shortname": "RMA",
        "espn_id": "86",
        "stadium_name": "Estadio Santiago Bernabéu",
        "color": "#FFFFFF",
        "color_secondary": "#00529F",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/86.png",
        "formation": "4-3-1-2",
        "att_rating": 91,
        "mid_rating": 89,
        "def_rating": 86,
        "overall_rating": 89,
        "elo": 1820.0,
        "position": 8,
    },
    {
        "id": 309,
        "slug": "ucl-real-betis",
        "name": "Real Betis Balompié",
        "nickname": "Real Betis",
        "shortname": "BET",
        "espn_id": "244",
        "stadium_name": "Estadio Benito Villamarín",
        "color": "#008850",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/244.png",
        "formation": "4-2-3-1",
        "att_rating": 81,
        "mid_rating": 80,
        "def_rating": 79,
        "overall_rating": 80,
        "elo": 1590.0,
        "position": 9,
    },
    {
        "id": 310,
        "slug": "ucl-bayern-munich",
        "name": "FC Bayern München",
        "nickname": "Bayern Munich",
        "shortname": "BAY",
        "espn_id": "132",
        "stadium_name": "Allianz Arena",
        "color": "#DC052D",
        "color_secondary": "#0066B2",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/132.png",
        "formation": "4-2-3-1",
        "att_rating": 90,
        "mid_rating": 87,
        "def_rating": 85,
        "overall_rating": 88,
        "elo": 1795.0,
        "position": 10,
    },
    {
        "id": 311,
        "slug": "ucl-shakhtar-donetsk",
        "name": "FC Shakhtar Donetsk",
        "nickname": "Shakhtar Donetsk",
        "shortname": "SHK",
        "espn_id": "493",
        "stadium_name": "Volksparkstadion (Hamburg / Interim)",
        "color": "#FF7500",
        "color_secondary": "#000000",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/493.png",
        "formation": "4-3-3",
        "att_rating": 77,
        "mid_rating": 76,
        "def_rating": 75,
        "overall_rating": 76,
        "elo": 1530.0,
        "position": 11,
    },
    {
        "id": 312,
        "slug": "ucl-como",
        "name": "Como 1907",
        "nickname": "Como",
        "shortname": "COM",
        "espn_id": "2572",
        "stadium_name": "Stadio Giuseppe Sinigaglia",
        "color": "#003DA5",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/2572.png",
        "formation": "4-2-3-1",
        "att_rating": 78,
        "mid_rating": 77,
        "def_rating": 75,
        "overall_rating": 77,
        "elo": 1510.0,
        "position": 12,
    },
    {
        "id": 313,
        "slug": "ucl-manchester-united",
        "name": "Manchester United FC",
        "nickname": "Manchester United",
        "shortname": "MUN",
        "espn_id": "360",
        "stadium_name": "Old Trafford",
        "color": "#DA291C",
        "color_secondary": "#FBE122",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
        "formation": "4-2-3-1",
        "att_rating": 84,
        "mid_rating": 83,
        "def_rating": 82,
        "overall_rating": 83,
        "elo": 1660.0,
        "position": 13,
    },
    {
        "id": 314,
        "slug": "ucl-villarreal",
        "name": "Villarreal CF",
        "nickname": "Villarreal",
        "shortname": "VIL",
        "espn_id": "102",
        "stadium_name": "Estadio de la Cerámica",
        "color": "#FFE600",
        "color_secondary": "#0055A5",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/102.png",
        "formation": "4-4-2",
        "att_rating": 82,
        "mid_rating": 81,
        "def_rating": 80,
        "overall_rating": 81,
        "elo": 1620.0,
        "position": 14,
    },
    {
        "id": 315,
        "slug": "ucl-atletico-madrid",
        "name": "Club Atlético de Madrid",
        "nickname": "Atlético Madrid",
        "shortname": "ATM",
        "espn_id": "1068",
        "stadium_name": "Riyadh Air Metropolitano",
        "color": "#CB3524",
        "color_secondary": "#0A2240",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/1068.png",
        "formation": "5-3-2",
        "att_rating": 86,
        "mid_rating": 85,
        "def_rating": 85,
        "overall_rating": 85,
        "elo": 1730.0,
        "position": 15,
    },
    {
        "id": 316,
        "slug": "ucl-club-brugge",
        "name": "Club Brugge KV",
        "nickname": "Club Brugge",
        "shortname": "BRU",
        "espn_id": "570",
        "stadium_name": "Jan Breydel Stadium",
        "color": "#0055A5",
        "color_secondary": "#000000",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/570.png",
        "formation": "4-3-3",
        "att_rating": 78,
        "mid_rating": 77,
        "def_rating": 76,
        "overall_rating": 77,
        "elo": 1540.0,
        "position": 16,
    },
    {
        "id": 317,
        "slug": "ucl-manchester-city",
        "name": "Manchester City FC",
        "nickname": "Manchester City",
        "shortname": "MCI",
        "espn_id": "382",
        "stadium_name": "Etihad Stadium",
        "color": "#6CABDD",
        "color_secondary": "#1C2C5B",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/382.png",
        "formation": "4-3-3",
        "att_rating": 91,
        "mid_rating": 90,
        "def_rating": 87,
        "overall_rating": 90,
        "elo": 1835.0,
        "position": 17,
    },
    {
        "id": 318,
        "slug": "ucl-borussia-dortmund",
        "name": "Borussia Dortmund",
        "nickname": "Borussia Dortmund",
        "shortname": "BVB",
        "espn_id": "124",
        "stadium_name": "Signal Iduna Park (Westfalenstadion)",
        "color": "#FDE100",
        "color_secondary": "#000000",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/124.png",
        "formation": "4-2-3-1",
        "att_rating": 85,
        "mid_rating": 83,
        "def_rating": 82,
        "overall_rating": 84,
        "elo": 1690.0,
        "position": 18,
    },
    {
        "id": 319,
        "slug": "ucl-lens",
        "name": "RC Lens",
        "nickname": "RC Lens",
        "shortname": "RCL",
        "espn_id": "175",
        "stadium_name": "Stade Bollaert-Delelis",
        "color": "#ED1C24",
        "color_secondary": "#FFF200",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/175.png",
        "formation": "3-4-2-1",
        "att_rating": 78,
        "mid_rating": 77,
        "def_rating": 78,
        "overall_rating": 78,
        "elo": 1550.0,
        "position": 19,
    },
    {
        "id": 320,
        "slug": "ucl-aek-athens",
        "name": "AEK Athens FC",
        "nickname": "AEK Athens",
        "shortname": "AEK",
        "espn_id": "887",
        "stadium_name": "OPAP Arena (Agia Sophia)",
        "color": "#FFCC00",
        "color_secondary": "#000000",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/887.png",
        "formation": "4-4-1-1",
        "att_rating": 76,
        "mid_rating": 75,
        "def_rating": 75,
        "overall_rating": 75,
        "elo": 1490.0,
        "position": 20,
    },
    {
        "id": 321,
        "slug": "ucl-rb-leipzig",
        "name": "RB Leipzig",
        "nickname": "RB Leipzig",
        "shortname": "RBL",
        "espn_id": "11420",
        "stadium_name": "Red Bull Arena (Leipzig)",
        "color": "#ED1C24",
        "color_secondary": "#0A2240",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/11420.png",
        "formation": "4-2-2-2",
        "att_rating": 84,
        "mid_rating": 83,
        "def_rating": 82,
        "overall_rating": 83,
        "elo": 1680.0,
        "position": 21,
    },
    {
        "id": 322,
        "slug": "ucl-sabah-fk",
        "name": "Sabah FC",
        "nickname": "Sabah FK",
        "shortname": "SAB",
        "espn_id": "21922",
        "stadium_name": "Bank Respublika Arena",
        "color": "#003399",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/21922.png",
        "formation": "4-3-3",
        "att_rating": 72,
        "mid_rating": 71,
        "def_rating": 70,
        "overall_rating": 71,
        "elo": 1440.0,
        "position": 22,
    },
    {
        "id": 323,
        "slug": "ucl-feyenoord",
        "name": "Feyenoord Rotterdam",
        "nickname": "Feyenoord",
        "shortname": "FEY",
        "espn_id": "142",
        "stadium_name": "Stadion Feijenoord (De Kuip)",
        "color": "#ED1C24",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/142.png",
        "formation": "4-3-3",
        "att_rating": 81,
        "mid_rating": 80,
        "def_rating": 79,
        "overall_rating": 80,
        "elo": 1610.0,
        "position": 23,
    },
    {
        "id": 324,
        "slug": "ucl-bodo-glimt",
        "name": "FK Bodø/Glimt",
        "nickname": "Bodø/Glimt",
        "shortname": "BOD",
        "espn_id": "2980",
        "stadium_name": "Aspmyra Stadion",
        "color": "#FFF200",
        "color_secondary": "#000000",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/2980.png",
        "formation": "4-3-3",
        "att_rating": 76,
        "mid_rating": 75,
        "def_rating": 74,
        "overall_rating": 75,
        "elo": 1500.0,
        "position": 24,
    },
    {
        "id": 325,
        "slug": "ucl-as-roma",
        "name": "AS Roma",
        "nickname": "AS Roma",
        "shortname": "ROM",
        "espn_id": "104",
        "stadium_name": "Stadio Olimpico",
        "color": "#8E1F2F",
        "color_secondary": "#F0BC42",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/104.png",
        "formation": "4-3-3",
        "att_rating": 82,
        "mid_rating": 81,
        "def_rating": 80,
        "overall_rating": 81,
        "elo": 1610.0,
        "position": 25,
    },
    {
        "id": 326,
        "slug": "ucl-psv-eindhoven",
        "name": "PSV Eindhoven",
        "nickname": "PSV Eindhoven",
        "shortname": "PSV",
        "espn_id": "148",
        "stadium_name": "Philips Stadion",
        "color": "#EE1C25",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/148.png",
        "formation": "4-3-3",
        "att_rating": 82,
        "mid_rating": 81,
        "def_rating": 80,
        "overall_rating": 81,
        "elo": 1620.0,
        "position": 26,
    },
    {
        "id": 327,
        "slug": "ucl-viking-fk",
        "name": "Viking FK",
        "nickname": "Viking FK",
        "shortname": "VIK",
        "espn_id": "510",
        "stadium_name": "SR-Bank Arena",
        "color": "#00205B",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/510.png",
        "formation": "4-3-3",
        "att_rating": 73,
        "mid_rating": 72,
        "def_rating": 72,
        "overall_rating": 72,
        "elo": 1450.0,
        "position": 27,
    },
    {
        "id": 328,
        "slug": "ucl-fenerbahce",
        "name": "Fenerbahçe SK",
        "nickname": "Fenerbahçe",
        "shortname": "FEN",
        "espn_id": "436",
        "stadium_name": "Şükrü Saracoğlu Stadium",
        "color": "#002D72",
        "color_secondary": "#FFF200",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/436.png",
        "formation": "4-2-3-1",
        "att_rating": 81,
        "mid_rating": 80,
        "def_rating": 79,
        "overall_rating": 80,
        "elo": 1590.0,
        "position": 28,
    },
    {
        "id": 329,
        "slug": "ucl-inter",
        "name": "FC Internazionale Milano",
        "nickname": "Inter Milan",
        "shortname": "INT",
        "espn_id": "110",
        "stadium_name": "San Siro (Stadio Giuseppe Meazza)",
        "color": "#0068A8",
        "color_secondary": "#000000",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/110.png",
        "formation": "3-5-2",
        "att_rating": 87,
        "mid_rating": 86,
        "def_rating": 85,
        "overall_rating": 86,
        "elo": 1740.0,
        "position": 29,
    },
    {
        "id": 330,
        "slug": "ucl-fc-porto",
        "name": "FC Porto",
        "nickname": "FC Porto",
        "shortname": "POR",
        "espn_id": "437",
        "stadium_name": "Estádio do Dragão",
        "color": "#003399",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/437.png",
        "formation": "4-2-3-1",
        "att_rating": 81,
        "mid_rating": 80,
        "def_rating": 80,
        "overall_rating": 80,
        "elo": 1620.0,
        "position": 30,
    },
    {
        "id": 331,
        "slug": "ucl-slavia-prague",
        "name": "SK Slavia Prague",
        "nickname": "Slavia Prague",
        "shortname": "SLA",
        "espn_id": "494",
        "stadium_name": "Fortuna Arena (Eden)",
        "color": "#E30613",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/494.png",
        "formation": "3-4-2-1",
        "att_rating": 77,
        "mid_rating": 76,
        "def_rating": 76,
        "overall_rating": 76,
        "elo": 1520.0,
        "position": 31,
    },
    {
        "id": 332,
        "slug": "ucl-napoli",
        "name": "SSC Napoli",
        "nickname": "SSC Napoli",
        "shortname": "NAP",
        "espn_id": "114",
        "stadium_name": "Stadio Diego Armando Maradona",
        "color": "#0080FF",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/114.png",
        "formation": "3-4-2-1",
        "att_rating": 85,
        "mid_rating": 83,
        "def_rating": 82,
        "overall_rating": 83,
        "elo": 1660.0,
        "position": 32,
    },
    {
        "id": 333,
        "slug": "ucl-lask-linz",
        "name": "LASK",
        "nickname": "LASK Linz",
        "shortname": "LASK",
        "espn_id": "4411",
        "stadium_name": "Raiffeisen Arena",
        "color": "#000000",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/4411.png",
        "formation": "4-2-3-1",
        "att_rating": 74,
        "mid_rating": 73,
        "def_rating": 73,
        "overall_rating": 73,
        "elo": 1470.0,
        "position": 33,
    },
    {
        "id": 334,
        "slug": "ucl-lille",
        "name": "LOSC Lille",
        "nickname": "LOSC Lille",
        "shortname": "LIL",
        "espn_id": "166",
        "stadium_name": "Decathlon Arena Stade Pierre-Mauroy",
        "color": "#EE2737",
        "color_secondary": "#1E2B47",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/166.png",
        "formation": "4-2-3-1",
        "att_rating": 80,
        "mid_rating": 79,
        "def_rating": 79,
        "overall_rating": 79,
        "elo": 1580.0,
        "position": 34,
    },
    {
        "id": 335,
        "slug": "ucl-galatasaray",
        "name": "Galatasaray SK",
        "nickname": "Galatasaray",
        "shortname": "GAL",
        "espn_id": "432",
        "stadium_name": "Rams Park",
        "color": "#A90432",
        "color_secondary": "#FDB913",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/432.png",
        "formation": "4-2-3-1",
        "att_rating": 82,
        "mid_rating": 80,
        "def_rating": 79,
        "overall_rating": 80,
        "elo": 1600.0,
        "position": 35,
    },
    {
        "id": 336,
        "slug": "ucl-slovan-bratislava",
        "name": "ŠK Slovan Bratislava",
        "nickname": "Slovan Bratislava",
        "shortname": "SLO",
        "espn_id": "521",
        "stadium_name": "Tehelné pole",
        "color": "#5BB5E8",
        "color_secondary": "#FFFFFF",
        "shield_url": "https://a.espncdn.com/i/teamlogos/soccer/500/521.png",
        "formation": "4-3-3",
        "att_rating": 72,
        "mid_rating": 71,
        "def_rating": 70,
        "overall_rating": 71,
        "elo": 1440.0,
        "position": 36,
    },
]

# Quick mapping from ESPN identifiers / names to canonical UCL slug
ESPN_UCL_ALIAS: Dict[str, str] = {
    "160": "ucl-psg",
    "Paris Saint-Germain": "ucl-psg",
    "PSG": "ucl-psg",
    "83": "ucl-barcelona",
    "Barcelona": "ucl-barcelona",
    "FC Barcelona": "ucl-barcelona",
    "362": "ucl-aston-villa",
    "Aston Villa": "ucl-aston-villa",
    "134": "ucl-vfb-stuttgart",
    "VfB Stuttgart": "ucl-vfb-stuttgart",
    "Stuttgart": "ucl-vfb-stuttgart",
    "364": "ucl-liverpool",
    "Liverpool": "ucl-liverpool",
    "2250": "ucl-sporting-cp",
    "Sporting CP": "ucl-sporting-cp",
    "Sporting Lisbon": "ucl-sporting-cp",
    "359": "ucl-arsenal",
    "Arsenal": "ucl-arsenal",
    "86": "ucl-real-madrid",
    "Real Madrid": "ucl-real-madrid",
    "244": "ucl-real-betis",
    "Real Betis": "ucl-real-betis",
    "Betis": "ucl-real-betis",
    "132": "ucl-bayern-munich",
    "Bayern Munich": "ucl-bayern-munich",
    "Bayern": "ucl-bayern-munich",
    "FC Bayern München": "ucl-bayern-munich",
    "493": "ucl-shakhtar-donetsk",
    "Shakhtar Donetsk": "ucl-shakhtar-donetsk",
    "Shakhtar": "ucl-shakhtar-donetsk",
    "2572": "ucl-como",
    "Como": "ucl-como",
    "Como 1907": "ucl-como",
    "360": "ucl-manchester-united",
    "Manchester United": "ucl-manchester-united",
    "Man United": "ucl-manchester-united",
    "102": "ucl-villarreal",
    "Villarreal": "ucl-villarreal",
    "1068": "ucl-atletico-madrid",
    "Atlético Madrid": "ucl-atletico-madrid",
    "Atletico Madrid": "ucl-atletico-madrid",
    "570": "ucl-club-brugge",
    "Club Brugge": "ucl-club-brugge",
    "Brugge": "ucl-club-brugge",
    "382": "ucl-manchester-city",
    "Manchester City": "ucl-manchester-city",
    "Man City": "ucl-manchester-city",
    "124": "ucl-borussia-dortmund",
    "Borussia Dortmund": "ucl-borussia-dortmund",
    "Dortmund": "ucl-borussia-dortmund",
    "175": "ucl-lens",
    "Lens": "ucl-lens",
    "RC Lens": "ucl-lens",
    "887": "ucl-aek-athens",
    "AEK Athens": "ucl-aek-athens",
    "AEK": "ucl-aek-athens",
    "11420": "ucl-rb-leipzig",
    "RB Leipzig": "ucl-rb-leipzig",
    "Leipzig": "ucl-rb-leipzig",
    "21922": "ucl-sabah-fk",
    "Sabah FK": "ucl-sabah-fk",
    "Sabah": "ucl-sabah-fk",
    "142": "ucl-feyenoord",
    "Feyenoord": "ucl-feyenoord",
    "Feyenoord Rotterdam": "ucl-feyenoord",
    "2980": "ucl-bodo-glimt",
    "Bodo/Glimt": "ucl-bodo-glimt",
    "Bodø/Glimt": "ucl-bodo-glimt",
    "104": "ucl-as-roma",
    "AS Roma": "ucl-as-roma",
    "Roma": "ucl-as-roma",
    "148": "ucl-psv-eindhoven",
    "PSV Eindhoven": "ucl-psv-eindhoven",
    "PSV": "ucl-psv-eindhoven",
    "510": "ucl-viking-fk",
    "Viking FK": "ucl-viking-fk",
    "Viking": "ucl-viking-fk",
    "436": "ucl-fenerbahce",
    "Fenerbahce": "ucl-fenerbahce",
    "Fenerbahçe": "ucl-fenerbahce",
    "110": "ucl-inter",
    "Internazionale": "ucl-inter",
    "Inter Milan": "ucl-inter",
    "Inter": "ucl-inter",
    "437": "ucl-fc-porto",
    "FC Porto": "ucl-fc-porto",
    "Porto": "ucl-fc-porto",
    "494": "ucl-slavia-prague",
    "Slavia Prague": "ucl-slavia-prague",
    "114": "ucl-napoli",
    "Napoli": "ucl-napoli",
    "SSC Napoli": "ucl-napoli",
    "4411": "ucl-lask-linz",
    "LASK Linz": "ucl-lask-linz",
    "LASK": "ucl-lask-linz",
    "166": "ucl-lille",
    "Lille": "ucl-lille",
    "LOSC Lille": "ucl-lille",
    "432": "ucl-galatasaray",
    "Galatasaray": "ucl-galatasaray",
    "521": "ucl-slovan-bratislava",
    "Slovan Bratislava": "ucl-slovan-bratislava",
}


def _resolve_ucl_slug(team_info: Dict[str, Any]) -> Optional[str]:
    tid = str(team_info.get("id") or "").strip()
    if tid in ESPN_UCL_ALIAS:
        return ESPN_UCL_ALIAS[tid]
    name = (team_info.get("displayName") or team_info.get("name") or "").strip()
    if name in ESPN_UCL_ALIAS:
        return ESPN_UCL_ALIAS[name]
    short = (team_info.get("shortDisplayName") or team_info.get("abbreviation") or "").strip()
    if short in ESPN_UCL_ALIAS:
        return ESPN_UCL_ALIAS[short]
    for key, slug in ESPN_UCL_ALIAS.items():
        if key.lower() in name.lower() or name.lower() in key.lower():
            return slug
    return None


def _get_json(url: str, retries: int = 2) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except Exception as e:
            last_err = e
            time.sleep(1.0)
    raise last_err or RuntimeError(f"Failed to fetch {url}")


def seed_champions_league_clubs(db: Optional[Database] = None) -> int:
    """
    Seeds baseline metadata, stadiums, and calibrated Elo ratings
    for the 36 UEFA Champions League clubs in SQLite.
    """
    database = db or Database()
    seeded = 0
    for club_data in CHAMPIONS_LEAGUE_CLUBS:
        c = Club(
            id=club_data["id"],
            slug=club_data["slug"],
            name=club_data["name"],
            nickname=club_data["nickname"],
            shortname=club_data["shortname"],
            shield_url=club_data["shield_url"],
            color=club_data["color"],
            color_secondary=club_data["color_secondary"],
            stadium=club_data["stadium_name"],
            stadium_name=club_data["stadium_name"],
            position=club_data["position"],
            formation=club_data["formation"],
            competition="champions_league",
            att_rating=club_data["att_rating"],
            mid_rating=club_data["mid_rating"],
            def_rating=club_data["def_rating"],
            overall_rating=club_data["overall_rating"],
        )
        database.upsert_club(c)
        seeded += 1

    with database.get_connection() as conn:
        cursor = conn.cursor()
        for club_data in CHAMPIONS_LEAGUE_CLUBS:
            cursor.execute(
                """
                INSERT INTO club_ratings (club_id, elo, difficulty, rank, matches_counted, updated_at)
                VALUES (?, ?, 2.5, ?, 36, ?)
                ON CONFLICT(club_id) DO UPDATE SET
                    elo=excluded.elo,
                    rank=excluded.rank,
                    updated_at=excluded.updated_at
                """,
                (club_data["id"], club_data["elo"], club_data["position"], datetime.now().isoformat()),
            )
        conn.commit()
    return seeded


def sync_champions_league_standings(db: Optional[Database] = None) -> Dict[str, Any]:
    """
    Fetches real-time UEFA Champions League 36-team single table from ESPN (uefa.champions)
    and updates position, MP, W, D, L, GF, GA, GD, PTS, and qualification status.
    """
    database = db or Database()
    data = _get_json(ESPN_UCL_STANDINGS)
    children = data.get("children", [])
    if not children:
        return {"updated": 0, "status": "no_children"}

    entries = children[0].get("standings", {}).get("entries", [])
    updated = 0

    with database.get_connection() as conn:
        cursor = conn.cursor()
        for entry in entries:
            team = entry.get("team", {})
            slug = _resolve_ucl_slug(team)
            if not slug:
                continue

            stats = {s.get("name"): s.get("value") for s in entry.get("stats", [])}
            mp = int(stats.get("gamesPlayed") or 0)
            w = int(stats.get("wins") or 0)
            d = int(stats.get("ties") or 0)
            l = int(stats.get("losses") or 0)
            gf = int(stats.get("pointsFor") or 0)
            ga = int(stats.get("pointsAgainst") or 0)
            gd = int(stats.get("pointDifferential") or (gf - ga))
            pts = int(stats.get("points") or 0)
            pos = int(stats.get("rank") or 0)

            # Qualification status for official UCL single table:
            if pos <= 8:
                qual = "Direct Round of 16 (Seed 1-8)"
            elif pos <= 24:
                qual = "Knockout Play-offs (Seed 9-24)"
            else:
                qual = "Eliminated"

            cursor.execute(
                """
                UPDATE clubs
                SET position=?, played=?, won=?, drawn=?, lost=?,
                    goals_for=?, goals_against=?, goal_difference=?, points=?,
                    qualification=?, competition='champions_league'
                WHERE (slug=? OR espn_id=?) AND id >= 300
                """,
                (pos, mp, w, d, l, gf, ga, gd, pts, qual, slug, str(team.get("id"))),
            )
            if cursor.rowcount > 0:
                updated += 1

        conn.commit()

    return {"updated": updated, "total_entries": len(entries), "status": "success"}


def sync_champions_league_fixtures(
    db: Optional[Database] = None,
    months: Optional[List[str]] = None,
    season: int = 2026,
) -> Dict[str, Any]:
    """
    Fetches official UEFA Champions League fixtures and live scores from ESPN (uefa.champions),
    storing them with competition='champions_league'.
    """
    database = db or Database()
    if not months:
        # Full 2026/27 League Phase months: Sept, Oct, Nov, Dec, Jan
        months = ["202609", "202610", "202611", "202612", "202701"]

    counters = {"inserted": 0, "updated": 0, "total_events": 0}

    with database.get_connection() as conn:
        cursor = conn.cursor()
        # Create map of slug / espn_id -> club id for UCL
        club_map = {}
        for row in cursor.execute("SELECT id, slug, espn_id FROM clubs WHERE competition='champions_league'").fetchall():
            club_map[row["slug"]] = row["id"]
            if row["espn_id"]:
                club_map[str(row["espn_id"])] = row["id"]

        for ym in months:
            try:
                sb = _get_json(f"{ESPN_UCL_SCOREBOARD}?dates={ym}")
            except Exception as e:
                logger.warning(f"Error fetching UCL scoreboard for {ym}: {e}")
                continue

            events = sb.get("events", [])
            counters["total_events"] += len(events)

            for ev in events:
                comp_data = ev.get("competitions", [{}])[0]
                competitors = comp_data.get("competitors", [])
                if len(competitors) < 2:
                    continue

                home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

                h_id_raw = str(home_comp.get("id") or home_comp.get("team", {}).get("id") or "")
                a_id_raw = str(away_comp.get("id") or away_comp.get("team", {}).get("id") or "")

                h_slug = _resolve_ucl_slug(home_comp.get("team", {}))
                a_slug = _resolve_ucl_slug(away_comp.get("team", {}))

                h_id = club_map.get(h_slug) or club_map.get(h_id_raw)
                a_id = club_map.get(a_slug) or club_map.get(a_id_raw)

                if not h_id or not a_id:
                    continue

                state = (comp_data.get("status", {}).get("type", {}).get("name") or "").upper()
                if "FINAL" in state or "POST" in state:
                    status = "FINISHED"
                elif "IN" in state or "PROGRESS" in state:
                    status = "LIVE"
                else:
                    status = "SCHEDULED"

                hs_str = home_comp.get("score")
                as_str = away_comp.get("score")
                hs = int(hs_str) if hs_str is not None and str(hs_str).isdigit() else None
                as_ = int(as_str) if as_str is not None and str(as_str).isdigit() else None

                kickoff = ev.get("date")

                # Parse referee if available
                referee = None
                officials = comp_data.get("officials", [])
                if officials and isinstance(officials, list):
                    ref_item = next((o for o in officials if "referee" in str(o.get("position", "")).lower()), officials[0])
                    referee = ref_item.get("displayName") or ref_item.get("fullName")

                # Upsert fixture
                existing = cursor.execute(
                    """
                    SELECT id FROM fixtures
                    WHERE home_team_id=? AND away_team_id=? AND season=? AND competition='champions_league'
                    """,
                    (h_id, a_id, season),
                ).fetchone()

                if existing:
                    cursor.execute(
                        """
                        UPDATE fixtures
                        SET status=?, home_score=?, away_score=?, kickoff_time=?, referee=COALESCE(?, referee)
                        WHERE id=?
                        """,
                        (status, hs, as_, kickoff, referee, existing["id"]),
                    )
                    counters["updated"] += 1
                else:
                    cursor.execute(
                        """
                        INSERT INTO fixtures (
                            matchday, home_team_id, away_team_id, home_score, away_score,
                            status, kickoff_time, season, competition, referee
                        )
                        VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, 'champions_league', ?)
                        """,
                        (h_id, a_id, hs, as_, status, kickoff, season, referee),
                    )
                    counters["inserted"] += 1

        # Backfill chronological matchdays (1 to 8) for Champions League fixtures
        counts: Dict[int, int] = {}
        rows = cursor.execute(
            """
            SELECT id, home_team_id, away_team_id
            FROM fixtures
            WHERE season=? AND competition='champions_league' AND matchday IS NULL
            ORDER BY kickoff_time ASC, id ASC
            """,
            (season,),
        ).fetchall()
        for r in rows:
            h = counts.get(r["home_team_id"], 0)
            a = counts.get(r["away_team_id"], 0)
            md = max(h, a) + 1
            cursor.execute("UPDATE fixtures SET matchday=? WHERE id=?", (md, r["id"]))
            counts[r["home_team_id"]] = md
            counts[r["away_team_id"]] = md

        conn.commit()

    return counters
