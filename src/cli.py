"""
Command Line Interface for La Liga Football Profiler.
"""
import sys
import argparse
from typing import List

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from .database import Database
from .scraper import LaLigaScraper
from .comparator import PlayerComparator


def print_bar(val: int, max_val: int = 100, width: int = 24) -> str:
    filled = int((val / max_val) * width)
    return "█" * filled + "░" * (width - filled)


def cmd_sync(args):
    print("=" * 65)
    print(" ⚽ LA LIGA PROFILER - OFFICIAL OPTA DATA INGESTION")
    print("=" * 65)

    scraper = LaLigaScraper()
    db = Database()

    def progress(current, total, msg):
        pct = int((current / total) * 100)
        bar = print_bar(pct, 100, width=20)
        print(f"\r[{bar}] {pct}% | {msg}", end="", flush=True)

    print("\n[+] Initiating sync of 26 official ranking pages (~520 players)...")
    t0 = sys.platform
    profiles = scraper.sync_all(use_cache=not args.fresh, enrich_bios=not args.fast, progress_callback=progress)
    print("\n[+] Saving entities and intelligence profiles into SQLite...")

    clubs_seen = set()
    for club, profile in profiles:
        if club.id not in clubs_seen:
            db.upsert_club(club)
            clubs_seen.add(club.id)
        db.upsert_player_profile(profile)

    json_path = db.export_to_json()
    counts = db.get_total_counts()

    print("\n" + "=" * 65)
    print(f" ✨ SYNC COMPLETE!")
    print(f"   • Total Clubs Ingested:   {counts['clubs']}")
    print(f"   • Total Players Profiled: {counts['players']}")
    print(f"   • SQLite DB Path:         {db.db_path}")
    print(f"   • JSON Export:            {json_path}")
    print("=" * 65)


def cmd_search(args):
    db = Database()
    results = db.search_players(query=args.query, position=args.position, club_slug=args.club, limit=args.limit)

    print(f"\nFound {len(results)} player(s) matching '{args.query}':\n")
    header = f"{'NAME':<24} {'CLUB':<18} {'POS':<12} {'OVR':<5} {'ARCHETYPE':<28} {'G/A':<6}"
    print(header)
    print("-" * len(header))

    for p in results:
        name = p.get("nickname") or p.get("name", "Unknown")
        club = p.get("club_nickname") or "Free Agent"
        pos = p.get("position_name", "Unknown")
        ovr = p.get("overall_rating", 50)
        arch = p.get("archetype", "Unknown")
        stats = p.get("stats") or {}
        g = stats.get("goals", 0)
        a = stats.get("assists", 0)
        ga = f"{g}/{a}"
        print(f"{name:<24} {club:<18} {pos:<12} {ovr:<5} {arch:<28} {ga:<6}")


def cmd_profile(args):
    db = Database()
    profile = db.get_player_by_slug(args.player)

    if not profile:
        # Try search query
        results = db.search_players(query=args.player, limit=1)
        if results:
            profile = db.get_player_by_slug(results[0]["slug"])

    if not profile:
        print(f"Error: Player '{args.player}' not found in database. Try running 'python -m src.cli sync' first.")
        return

    bio = profile.get("bio", {})
    stats = profile.get("stats", {})
    scores = profile.get("scores", {})
    per90 = profile.get("per90", {})

    print("\n" + "=" * 68)
    name = bio.get("nickname") or bio.get("name", "Unknown")
    print(f" 📋 PLAYER DOSSIER: {name.upper()}")
    print("=" * 68)

    club = bio.get("club_name") or "La Liga"
    pos = bio.get("position_name") or "Unknown"
    num = f"#{bio.get('shirt_number')}" if bio.get("shirt_number") else ""
    country = bio.get("country_code") or "N/A"
    age = bio.get("date_of_birth")[:10] if bio.get("date_of_birth") else "N/A"
    height = f"{bio.get('height')} cm" if bio.get("height") else "N/A"

    print(f" Club:      {club:<22} Position:  {pos} {num}")
    print(f" Country:   {country:<22} Birth Date: {age}")
    print(f" Height:    {height:<22} Opta ID:   {bio.get('opta_id')}")
    print("-" * 68)
    print(f" TACTICAL ARCHETYPE: {profile.get('archetype', 'Unknown')}")
    if profile.get("secondary_archetype"):
        print(f" SECONDARY ROLE:    {profile.get('secondary_archetype')}")
    print("-" * 68)

    ovr = scores.get("overall_rating", 50)
    is_gk = scores.get("is_goalkeeper", False)
    print(f" 🌟 PERFORMANCE CARD STATS: [ {ovr} OVR ]")
    if is_gk:
        div = scores.get("gk_diving", 50)
        han = scores.get("gk_handling", 50)
        kic = scores.get("gk_kicking", 50)
        ref = scores.get("gk_reflexes", 50)
        spd = scores.get("gk_speed", 50)
        pos_st = scores.get("gk_positioning", 50)
        print(f"   DIV {div:>2} | HAN {han:>2} | KIC {kic:>2} | REF {ref:>2} | SPD {spd:>2} | POS {pos_st:>2}")
    else:
        pac = scores.get("pace", 50)
        sho = scores.get("shooting", 50)
        pas = scores.get("passing", 50)
        dri = scores.get("dribbling", 50)
        deff = scores.get("defending", 50)
        phy = scores.get("physical", 50)
        print(f"   PAC {pac:>2} | SHO {sho:>2} | PAS {pas:>2} | DRI {dri:>2} | DEF {deff:>2} | PHY {phy:>2}")
    print("-" * 68)

    print(" 📊 ATTRIBUTE PILLARS (0 - 100):")
    att = scores.get("attacking", 50)
    ply = scores.get("playmaking", 50)
    dfe = scores.get("defending", 50)
    phy_p = scores.get("physical_duels", 50)
    dsc = scores.get("discipline_reliability", 50)

    print(f"   OVERALL RATING:        [{print_bar(ovr, 100)}] {ovr:>3}")
    print(f"   Attacking Threat:      [{print_bar(att, 100)}] {att:>3}")
    print(f"   Playmaking & Passing:  [{print_bar(ply, 100)}] {ply:>3}")
    print(f"   Defensive Impact:      [{print_bar(dfe, 100)}] {dfe:>3}")
    print(f"   Physical & Duels:      [{print_bar(phy_p, 100)}] {phy_p:>3}")
    print(f"   Discipline & IQ:       [{print_bar(dsc, 100)}] {dsc:>3}")
    print("-" * 68)

    print(" 📈 CORE METRICS & PER-90 OUTPUT:")
    mins = stats.get("minutes_played", 0)
    apps = stats.get("games_played", 0)
    print(f"   Appearances: {apps} ({mins} mins)")
    print(f"   Goals:       {stats.get('goals', 0):<4} ({per90.get('goals_per90', 0)} / 90)   | Shots:      {stats.get('shots', 0):<4} ({stats.get('shots_on_target', 0)} on target)")
    print(f"   Assists:     {stats.get('assists', 0):<4} ({per90.get('assists_per90', 0)} / 90)   | Key Passes: {stats.get('key_passes', 0):<4} ({per90.get('key_passes_per90', 0)} / 90)")
    print(f"   Passes:      {stats.get('passes_accurate', 0)}/{stats.get('passes_total', 0):<4}           | Dribbles:   {stats.get('dribbles_won', 0)}/{stats.get('dribbles_attempted', 0)}")
    print(f"   Tackles Won: {stats.get('tackles_won', 0):<4} ({per90.get('tackles_per90', 0)} / 90)   | Intercepts: {stats.get('interceptions', 0)}")
    print(f"   Duels Won:   {stats.get('duels_won', 0):<4} ({stats.get('aerial_won', 0)} aerial)  | Yellows/Red:{stats.get('yellow_cards', 0)}/{stats.get('red_cards', 0)}")
    if stats.get("saves_total", 0) > 0:
        print(f"   Saves:       {stats.get('saves_total', 0):<4} ({stats.get('clean_sheets', 0)} clean sheets)")
    print("-" * 68)

    print(" 💡 SCOUT REPORT - STRENGTHS:")
    for s in profile.get("strengths", []):
        print(f"   ✔ {s}")
    print(" ⚠️ SCOUT REPORT - AREAS OF CAUTION:")
    for w in profile.get("weaknesses", []):
        print(f"   ✖ {w}")
    print("=" * 68 + "\n")


def cmd_compare(args):
    comp = PlayerComparator()
    res = comp.compare_players(args.player1, args.player2)

    if not res:
        print(f"Error: Could not compare players '{args.player1}' and '{args.player2}'. Ensure both exist in DB.")
        return

    b1 = res["player1"]["bio"]
    b2 = res["player2"]["bio"]
    n1 = b1.get("nickname") or b1.get("name")
    n2 = b2.get("nickname") or b2.get("name")

    print("\n" + "=" * 68)
    print(f" ⚔️ HEAD-TO-HEAD COMPARISON: {n1.upper()} vs {n2.upper()}")
    print("=" * 68)
    print(f"{n1:<32} vs {n2:<32}")
    print(f"{b1.get('club_name')} ({b1.get('position_name')}) {'':<12} {b2.get('club_name')} ({b2.get('position_name')})")
    print(" 🌟 PERFORMANCE CARD ATTRIBUTES:")
    for c in res.get("cards", []):
        abbr = c["abbr"]
        name = c["name"]
        s1 = c["player1_score"]
        s2 = c["player2_score"]
        adv1 = "★ " if c["advantage"] == "p1" else "  "
        adv2 = "★ " if c["advantage"] == "p2" else "  "
        print(f"   {adv1}{s1:>3}  {abbr} - {name:<23}  {s2:<3}{adv2}")
    print("-" * 68)

    print(" 📊 PILLAR SCORES:")
    for p in res["pillars"]:
        label = p["pillar"]
        s1 = p["player1_score"]
        s2 = p["player2_score"]
        adv1 = "★ " if p["advantage"] == "p1" else "  "
        adv2 = "★ " if p["advantage"] == "p2" else "  "
        print(f"   {adv1}{s1:>3}  {label:<28}  {s2:<3}{adv2}")
    print("-" * 68)

    print(" 📈 STATISTICAL COMPARISON:")
    for m in res["metrics"]:
        label = m["label"]
        v1 = m["player1_value"]
        v2 = m["player2_value"]
        adv1 = "★ " if m["advantage"] == "p1" else "  "
        adv2 = "★ " if m["advantage"] == "p2" else "  "
        print(f"   {adv1}{v1:>4}  {label:<32}  {v2:<4}{adv2}")
    print("-" * 68)

    print(" 📝 SCOUT VERDICT:")
    print(f"   {res['verdict']}")
    print("=" * 68 + "\n")


def cmd_leaders(args):
    db = Database()
    leaders = db.get_leaders(metric=args.stat, limit=args.limit)

    print(f"\n🏆 LA LIGA LEAGUE LEADERS - {args.stat.replace('_', ' ').upper()}:\n")
    header = f"{'#':<3} {'NAME':<24} {'CLUB':<20} {'POS':<12} {'VAL':<6}"
    print(header)
    print("-" * len(header))

    for idx, p in enumerate(leaders):
        name = p.get("nickname") or p.get("name", "Unknown")
        club = p.get("club_nickname") or "Free Agent"
        pos = p.get("position_name", "Unknown")
        if args.stat == "overall_rating":
            val = p.get("overall_rating", 50)
        else:
            val = p.get("stats", {}).get(args.stat, 0)
        print(f"{idx+1:<3} {name:<24} {club:<20} {pos:<12} {val:<6}")


def cmd_clubs(args):
    db = Database()
    clubs = db.get_all_club_profiles()
    print(f"\n🏆 LA LIGA CLUBS PROFILES & RATINGS ({len(clubs)} Clubs):\n")
    header = f"{'#':<3} {'CLUB':<22} {'W-D-L':<8} {'GF:GA':<8} {'PTS':<5} {'OVR':<5} {'ATT':<5} {'MID':<5} {'DEF':<5} {'TACTICAL ARCHETYPE'}"
    print(header)
    print("-" * 105)
    for c in clubs:
        meta = c.get("club", {})
        scores = c.get("scores", {})
        pos = meta.get("position") or "-"
        name = meta.get("nickname") or meta.get("name", "Unknown")
        rec = f"{meta.get('won', 0)}-{meta.get('drawn', 0)}-{meta.get('lost', 0)}"
        gf_ga = f"{meta.get('goals_for', 0)}:{meta.get('goals_against', 0)}"
        pts = meta.get("points", 0)
        ovr = scores.get("overall_rating", 50)
        att = scores.get("att_rating", 50)
        mid = scores.get("mid_rating", 50)
        defense = scores.get("def_rating", 50)
        arch = c.get("archetype", "Organized Tactical Unit")
        print(f"{pos:<3} {name:<22} {rec:<8} {gf_ga:<8} {pts:<5} {ovr:<5} {att:<5} {mid:<5} {defense:<5} {arch}")


def cmd_club_profile(args):
    db = Database()
    profile = db.get_club_profile(args.club)
    if not profile:
        print(f"Error: Club '{args.club}' not found. Try 'python run.py --cli clubs' to see all clubs.")
        return

    meta = profile.get("club", {})
    scores = profile.get("scores", {})
    stats = profile.get("stats", {})
    arch = profile.get("archetype", "Organized Tactical Unit")
    sec_arch = profile.get("secondary_style")

    name = meta.get("name", "Unknown")
    nickname = meta.get("nickname", name)
    stadium = meta.get("stadium_name") or meta.get("stadium") or "Unknown Ground"
    president = meta.get("president") or "N/A"
    founded = meta.get("foundation") or "N/A"
    if "T" in str(founded):
        founded = str(founded).split("T")[0]

    pos = meta.get("position") or "-"
    pts = meta.get("points", 0)
    w = meta.get("won", 0)
    d = meta.get("drawn", 0)
    l = meta.get("lost", 0)

    print("=" * 68)
    print(f" 🛡️ CLUB DOSSIER: {nickname.upper()} ({name})")
    print("=" * 68)
    print(f" Stadium:   {stadium:<22} President: {president}")
    print(f" Founded:   {founded:<22} Standing:  #{pos} ({pts} pts | {w}W-{d}D-{l}L)")
    print("-" * 68)
    print(f" TACTICAL ARCHETYPE: {arch}")
    if sec_arch:
        print(f" SECONDARY STYLE:    {sec_arch}")
    print("-" * 68)
    print(f" 🌟 PERFORMANCE CARD RATINGS: [ {scores.get('overall_rating', 50)} OVR ]")
    print(f"   ATT: {scores.get('att_rating', 50)} | MID: {scores.get('mid_rating', 50)} | DEF: {scores.get('def_rating', 50)}")
    print("-" * 68)
    print(" 📊 TACTICAL RADAR PILLARS (0 - 100):")
    pillars = [
        ("Possession & Control", scores.get("possession_control", 50)),
        ("Attacking Potency", scores.get("attacking_potency", 50)),
        ("Defensive Solidity", scores.get("defensive_solidity", 50)),
        ("Pressing & Workrate", scores.get("pressing_workrate", 50)),
        ("Physical Dominance", scores.get("physical_dominance", 50)),
    ]
    for label, val in pillars:
        print(f"   {label:<24} [{print_bar(val, 100, 20)}]  {val:>2}")
    print("-" * 68)
    print(" 📈 SQUAD AGGREGATE STATS:")
    m = stats.get("matches_played", meta.get("played", 4))
    g = stats.get("goals", meta.get("goals_for", 0))
    ga = stats.get("goals_conceded", meta.get("goals_against", 0))
    print(f"   Matches: {m} | Squad Size: {stats.get('squad_size', 0)} players")
    print(f"   Goals:   {g} ({stats.get('goals_per_game', 0.0)}/game) | Conceded: {ga} ({stats.get('goals_conceded_per_game', 0.0)}/game)")
    print(f"   Shots:   {stats.get('shots', 0)} ({stats.get('shot_accuracy_pct', 0.0)}% on target) | Conversion: {stats.get('conversion_rate_pct', 0.0)}%")
    print(f"   Passes:  {stats.get('passes_total', 0)} ({stats.get('pass_accuracy_pct', 0.0)}% acc) | Chances: {stats.get('key_passes', 0)}")
    print(f"   Tackles: {stats.get('tackles_won', 0)}/{stats.get('tackles_total', 0)} ({stats.get('tackle_pct', 0.0)}% win) | Clean Sheets: {stats.get('clean_sheets', 0)}")
    print("-" * 68)
    print(" 🌟 KEY SQUAD LEADERS:")
    scorer = profile.get("top_scorer")
    if scorer:
        print(f"   • Top Scorer:        {scorer['name']} ({scorer['stat_val']} goals, {scorer['overall_rating']} OVR)")
    assister = profile.get("top_assister")
    if assister:
        print(f"   • Primary Playmaker: {assister['name']} ({assister['stat_val']}, {assister['overall_rating']} OVR)")
    def_lead = profile.get("defensive_leader")
    if def_lead:
        print(f"   • Defensive Anchor:  {def_lead['name']} ({def_lead['stat_val']}, {def_lead['overall_rating']} OVR)")
    star = profile.get("star_player")
    if star:
        print(f"   • Star Player:       {star['name']} ({star['overall_rating']} OVR, #{star.get('shirt_number') or '-'})")
    print("-" * 68)
    print(" 💡 SCOUT REPORT - TACTICAL STRENGTHS:")
    for s in profile.get("strengths", []):
        print(f"   ✔ {s}")
    print(" ⚠️ SCOUT REPORT - AREAS OF CAUTION:")
    for w in profile.get("weaknesses", []):
        print(f"   ✖ {w}")
    print("=" * 68 + "\n")


def cmd_club_compare(args):
    comp = PlayerComparator()
    res = comp.compare_clubs(args.club1, args.club2)
    if not res:
        print(f"Error: Could not compare clubs '{args.club1}' and '{args.club2}'.")
        return

    c1 = res["club1"]["meta"]
    c2 = res["club2"]["meta"]
    name1 = c1.get("nickname") or c1.get("name", "Club 1")
    name2 = c2.get("nickname") or c2.get("name", "Club 2")

    print("=" * 68)
    print(f" ⚔️ HEAD-TO-HEAD CLUB COMPARISON: {name1.upper()} vs {name2.upper()}")
    print("=" * 68)
    pos1 = f"#{c1.get('position', '-')} ({c1.get('points', 0)} pts)"
    pos2 = f"#{c2.get('position', '-')} ({c2.get('points', 0)} pts)"
    print(f"{name1:<32} vs {name2}")
    print(f"{pos1:<32}    {pos2}")
    print("-" * 68)

    print(" 🌟 PERFORMANCE CARD RATINGS:")
    for r in res.get("ratings", []):
        abbr = r["abbr"]
        label = r["label"]
        s1 = r["club1_score"]
        s2 = r["club2_score"]
        adv1 = "★ " if r["advantage"] == "c1" else "  "
        adv2 = "★ " if r["advantage"] == "c2" else "  "
        print(f"   {adv1}{s1:>3}  {abbr} - {label:<23}  {s2:<3}{adv2}")
    print("-" * 68)

    print(" 📊 TACTICAL RADAR PILLARS:")
    for p in res.get("pillars", []):
        label = p["label"]
        s1 = p["club1_score"]
        s2 = p["club2_score"]
        adv1 = "★ " if p["advantage"] == "c1" else "  "
        adv2 = "★ " if p["advantage"] == "c2" else "  "
        print(f"   {adv1}{s1:>3}  {label:<28}  {s2:<3}{adv2}")
    print("-" * 68)

    print(" 📈 SQUAD & LEAGUE METRICS:")
    for m in res.get("metrics", []):
        label = m["label"]
        v1 = m["club1_value"]
        v2 = m["club2_value"]
        adv1 = "★ " if m["advantage"] == "c1" else "  "
        adv2 = "★ " if m["advantage"] == "c2" else "  "
        print(f"   {adv1}{v1:>4}  {label:<32}  {v2:<4}{adv2}")
    print("-" * 68)

    print(" 📝 TACTICAL SCOUT VERDICT:")
    print(f"   {res['verdict']}")
    print("=" * 68 + "\n")


def cmd_standings(args):
    db = Database()
    standings = db.get_standings()
    print(f"\n🏆 OFFICIAL LA LIGA EASPORTS TABLE ({len(standings)} Teams):\n")
    header = f"{'#':<3} {'CLUB':<22} {'P':<3} {'W':<3} {'D':<3} {'L':<3} {'GF':<4} {'GA':<4} {'GD':<5} {'PTS':<4} {'OVR':<4} {'ZONE'}"
    print(header)
    print("-" * 90)
    for s in standings:
        pos = s.get("position") or "-"
        name = s.get("nickname") or s.get("name", "Unknown")
        p = s.get("played", 0)
        w = s.get("won", 0)
        d = s.get("drawn", 0)
        l = s.get("lost", 0)
        gf = s.get("goals_for", 0)
        ga = s.get("goals_against", 0)
        gd = s.get("goal_difference", 0)
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        pts = s.get("points", 0)
        ovr = s.get("overall_rating", 50)
        q = s.get("qualification") or ""
        print(f"{pos:<3} {name:<22} {p:<3} {w:<3} {d:<3} {l:<3} {gf:<4} {ga:<4} {gd_str:<5} {pts:<4} {ovr:<4} {q}")


def main():
    parser = argparse.ArgumentParser(description="La Liga Football Player & Club Profiling System")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # sync
    sync_p = subparsers.add_parser("sync", help="Ingest official player and club data from La Liga")
    sync_p.add_argument("--fresh", action="store_true", help="Bypass local cache and re-fetch from web")
    sync_p.add_argument("--fast", action="store_true", help="Skip deep bio enrichment for faster sync")

    # search
    search_p = subparsers.add_parser("search", help="Search players by name, team, or position")
    search_p.add_argument("query", nargs="?", default="", help="Player or team name")
    search_p.add_argument("--position", default="", help="Filter by position (Forward, Midfielder, Defender, Goalkeeper)")
    search_p.add_argument("--club", default="", help="Filter by club slug or nickname")
    search_p.add_argument("--limit", type=int, default=30, help="Max results")

    # profile
    profile_p = subparsers.add_parser("profile", help="Show detailed player dossier")
    profile_p.add_argument("player", help="Player slug or nickname (e.g. mbappe, raphinha, camello)")

    # compare
    compare_p = subparsers.add_parser("compare", help="Compare two players head-to-head")
    compare_p.add_argument("player1", help="First player slug or nickname")
    compare_p.add_argument("player2", help="Second player slug or nickname")

    # leaders
    leaders_p = subparsers.add_parser("leaders", help="Show stat leaderboards")
    leaders_p.add_argument("--stat", default="goals", help="Stat name (goals, assists, shots, key_passes, tackles_won, clean_sheets, overall_rating)")
    leaders_p.add_argument("--limit", type=int, default=10, help="Max results")

    # clubs
    clubs_p = subparsers.add_parser("clubs", help="List all 20 clubs with ratings and tactical archetypes")

    # club-profile
    club_prof_p = subparsers.add_parser("club-profile", help="Show full tactical club dossier and squad breakdown")
    club_prof_p.add_argument("club", help="Club slug, nickname, or shortname (e.g. real-madrid, fc-barcelona, betis)")

    # club-compare
    club_comp_p = subparsers.add_parser("club-compare", help="Compare two clubs head-to-head")
    club_comp_p.add_argument("club1", help="First club slug or nickname")
    club_comp_p.add_argument("club2", help="Second club slug or nickname")

    # standings
    standings_p = subparsers.add_parser("standings", help="Show official La Liga standings table")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "sync":
        cmd_sync(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "profile":
        cmd_profile(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "leaders":
        cmd_leaders(args)
    elif args.command == "clubs":
        cmd_clubs(args)
    elif args.command == "club-profile":
        cmd_club_profile(args)
    elif args.command == "club-compare":
        cmd_club_compare(args)
    elif args.command == "standings":
        cmd_standings(args)



if __name__ == "__main__":
    main()
