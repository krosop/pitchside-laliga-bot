# ⚽ La Liga Football Player Profiling & Intelligence System

A comprehensive, production-grade football player profiling and statistical analysis platform for **La Liga (Spanish Primera División)**, powered by 100% accurate, official match and season data directly from La Liga's official Opta data feed.

The system ingests and processes all 520 players across all 20 La Liga clubs, calculating tactical archetypes, 5-pillar composite attribute ratings (0–100), league-wide percentile rankings, automated scout dossiers, and head-to-head tactical comparisons.

---

## 🌟 Key Features

- **100% Official Data**: Directly extracted from La Liga's official Opta statistics feed across 26 pages covering all 520 registered players and 20 clubs.
- **60+ Granular Metrics**: Goals (inside/outside box, foot/head), shots, shots on target, expected finishing, key passes, total/accurate passes, long balls, crosses, take-ons, tackles won, interceptions, clearances, duels won/lost, aerial duels, clean sheets, saves, discipline cards.
- **Tactical Archetype Classification**: Automatically determines each player's specific tactical role (e.g. *Clinical Finisher / Poacher*, *Creative Playmaker / Maestro*, *Inverted Winger*, *Ball-Playing Centre-Back*, *Box-to-Box Engine*, *Sweeper Keeper*).
- **5-Pillar Attribute Radar (0–100)**: Normalized ratings across *Attacking Threat*, *Playmaking & Passing*, *Defensive Impact*, *Physical & Duels*, and *Discipline & Reliability*.
- **AI Scout Dossier**: Synthesizes statistical outliers into actionable bullet points (strengths, tactical cautions, per-90 rates, shot conversion).
- **Head-to-Head Comparison Engine**: Direct side-by-side comparison between any two players with dual SVG radar overlay, metric advantage flags, and tactical verdict.
- **Modern Dark-Mode Web Dashboard**: High-speed interactive web application with instant client-side filtering, SVG radar charts, and detailed player dossier modals.
- **Full CLI Suite**: Complete terminal interface for searching players, inspecting scout dossiers, generating H2H comparisons, and viewing leaderboards.
- **Zero External Dependencies**: Runs entirely on Python 3.12 standard library (`sqlite3`, `http.server`, `urllib`, `json`, `dataclasses`).

---

## 🚀 Quick Start

### 1. Launch the Interactive Web Dashboard

To launch the web interface:

```bash
python run.py
```

Then open your browser at **`http://localhost:8080`**.

### 2. Command Line Interface (CLI)

#### Search Players:
```bash
python -m src.cli search "Mbappe"
python -m src.cli search --position Forward
python -m src.cli search --club "real-madrid"
```

#### View Complete Player Dossier:
```bash
python -m src.cli profile "mbappe"
python -m src.cli profile "raphinha"
python -m src.cli profile "bellingham"
python -m src.cli profile "lamine-yamal"
```

#### Head-to-Head Player Comparison:
```bash
python -m src.cli compare "mbappe" "raphinha"
python -m src.cli compare "bellingham" "pedri"
```

#### League Leaderboards:
```bash
python -m src.cli leaders --stat goals
python -m src.cli leaders --stat assists
python -m src.cli leaders --stat key_passes
python -m src.cli leaders --stat tackles_won
python -m src.cli leaders --stat overall_rating
```

#### Club Profiling & Head-to-Head Comparisons:
```bash
# List all 20 clubs with ratings and tactical archetypes
python -m src.cli clubs

# Inspect full club dossier (stadium, leaders, scout report, squad roster)
python -m src.cli club-profile "real-madrid"
python -m src.cli club-profile "fc-barcelona"

# Head-to-head club battle with ratings, radar, and scout verdict
python -m src.cli club-compare "real-madrid" "fc-barcelona"

# View official league table with qualification zones
python -m src.cli standings
```

#### Re-Sync Latest Data:
```bash
python -m src.cli sync
```

---

## 🏛️ System Architecture

```
gambeling/
├── data/
│   ├── laliga_profiles.db       # SQLite database (clubs, club_profiles, players, player_profiles)
│   ├── laliga_players.json      # Structured JSON export of all 520 player profiles
│   ├── laliga_clubs.json        # Structured JSON export of all 20 club profiles
│   └── cache/                   # Cached official raw page responses, standings & club pages
├── src/
│   ├── __init__.py              # Package init
│   ├── models.py                # Data classes (Club, PlayerBio, Stats, Profile, ClubProfile)
│   ├── scraper.py               # Official La Liga Opta crawler, standings & club metadata
│   ├── database.py              # SQLite storage, queries, indexing & JSON export
│   ├── profiler.py              # Player archetype classification, 0-100 radar & card ratings
│   ├── club_profiler.py         # Club squad aggregation, ATT/MID/DEF/OVR ratings & scout reports
│   ├── comparator.py            # Head-to-head comparison engine (Players & Clubs)
│   ├── server.py                # Lightweight REST API & static file server
│   └── cli.py                   # Terminal interface with ASCII bars & colored tables
├── web/
│   ├── index.html               # Responsive multi-view dashboard (Players, Clubs, Standings)
│   ├── styles.css               # Elite dark theme UI with neon accents & card styling
│   └── app.js                   # Interactive UI logic, SVG radar generation & comparisons
├── run.py                       # Root launcher script
└── README.md                    # System documentation
```

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/players` | `GET` | Search & filter players (`?q=`, `?pos=`, `?club=`, `?limit=`) |
| `/api/players/<slug>` | `GET` | Complete player dossier (card stats, radar scores, scout report) |
| `/api/clubs` | `GET` | All 20 club profiles with ratings (ATT, MID, DEF, OVR) & standings |
| `/api/clubs/<slug>` | `GET` | Detailed club dossier (stadium, president, leaders, roster, radar) |
| `/api/standings` | `GET` | Official league table with goal difference & qualification zones |
| `/api/compare` | `GET` | Head-to-head player comparison (`?p1=slug1&p2=slug2`) |
| `/api/compare-clubs` | `GET` | Head-to-head club comparison (`?c1=slug1&c2=slug2`) |
| `/api/leaders` | `GET` | Top 10 leaders for any metric (`?stat=goals\|assists\|tackles_won...`) |
| `/api/summary` | `GET` | League overview (counts, top scorers, top rated, top clubs) |

---

## 📊 Tactical Profiling Methodology

### 1. Player Attribute Pillars & Card Ratings (0–99 Scale)
- **PAC / Transition**: Sprint acceleration, off-the-ball threat, carrying rate.
- **SHO / Attacking**: Goals/90, shot accuracy %, shots on target, box conversion.
- **PAS / Playmaking**: Official assists, key passes (chances created), pass completion %.
- **DRI / Dribbling**: Successful take-ons, ball-retention under pressure.
- **DEF / Defending**: Tackles won, tackle win %, interceptions, clearances, disruption.
- **PHY / Physicality**: Total duels won, aerial duels won, stamina durability.
- **OVR / Overall**: Position-weighted composite performance score.

### 2. Club Profiling & Tactical Ratings (0–99 Scale)
- **ATT (Attack Rating)**: Squad finishing efficiency, goals/match, shots on target, forward unit caliber.
- **MID (Midfield Rating)**: Pass accuracy %, chances created, ball circulation, midfield unit caliber.
- **DEF (Defense Rating)**: Conceded goals rate, clean sheets, tackle success, defender and goalkeeper ratings.
- **OVR (Overall Rating)**: Weighted balance ($0.35 \times \text{ATT} + 0.35 \times \text{MID} + 0.30 \times \text{DEF}$).
- **Tactical Archetypes**: *High-Press Possession Dominator*, *Vertical Counter-Attacking Force*, *Defensive Fortress & Low Block*, *Technical Ball-Circulation Unit*, *Direct Aerial Heavyweight*.

