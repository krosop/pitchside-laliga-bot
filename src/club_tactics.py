"""
Club Tactical DNA Registry & Managerial Philosophy Engine for La Liga.
Researched real-world tactical profiles for Spanish football clubs:
- Real managers & tactical formations
- Pressing intensity & defensive line height
- Build-up tempo & counter-attack lethality
- Tactical adjustments vs Big Clubs (Top 4) vs Lower/Relegation teams
- Game-state tendencies: Result preservation (protecting a lead, time-wasting) vs Chasing deficits
- Tactical Clash Evaluator for matchup-specific simulation modifiers
"""
from typing import Dict, Any, Tuple, Optional


CLUB_TACTICAL_DNA: Dict[str, Dict[str, Any]] = {
    # 1. Real Betis Balompie
    "real-betis": {
        "club_name": "Real Betis Balompié",
        "nickname": "Real Betis",
        "manager": "Manuel Pellegrini",
        "manager_moniker": "El Ingeniero",
        "formation": "4-2-3-1",
        "tactical_identity": "Fluid Positional Overload & High Press",
        "style_category": "possession_heavy",
        "metrics": {
            "possession_target": 58,
            "pressing_intensity": 84,
            "defensive_line_height": 82,
            "build_up_tempo": 68,
            "counter_threat": 66,
            "tactical_fouls_rate": 52,
            "lead_preservation": 62,      # Retains ball in midfield to control game
            "late_chase_intensity": 88    # High-intensity overload when behind
        },
        "vs_elite_tactics": "Brave high-pressing & wide full-back overlaps; creates chances but leaves space behind.",
        "vs_underdog_tactics": "Dominant possession carousel; patient perimeter circulation to break down low blocks.",
        "key_strength": "Technical midfield combination play and creative 1v1 wingers.",
        "vulnerability": "Susceptible to rapid vertical counters behind high-pushing full-backs."
    },

    # 2. Real Madrid CF
    "real-madrid": {
        "club_name": "Real Madrid CF",
        "nickname": "Real Madrid",
        "manager": "Carlo Ancelotti",
        "manager_moniker": "Il Maestro",
        "formation": "4-3-3",
        "tactical_identity": "Positional Pragmatism & Lethal Vertical Transition",
        "style_category": "pragmatic_transitional",
        "metrics": {
            "possession_target": 57,
            "pressing_intensity": 72,
            "defensive_line_height": 64,
            "build_up_tempo": 84,
            "counter_threat": 98,
            "tactical_fouls_rate": 48,
            "lead_preservation": 84,      # Controlled rest defense; lethal on break
            "late_chase_intensity": 96    # Legendary 'Remontada' all-out late pressure
        },
        "vs_elite_tactics": "Absorbs early pressure in structured mid-block, then unleashes world-class vertical transition.",
        "vs_underdog_tactics": "Relentless 1v1 isolation on flanks; high cross volume and box overloads.",
        "key_strength": "Unrivaled transition speed and elite clinical finishing.",
        "vulnerability": "Occasional midfield disconnect when fullbacks commit forward simultaneously."
    },

    # 3. FC Barcelona
    "fc-barcelona": {
        "club_name": "FC Barcelona",
        "nickname": "Barcelona",
        "manager": "Hansi Flick",
        "manager_moniker": "The High-Line Architect",
        "formation": "4-2-3-1",
        "tactical_identity": "Flick-Ball Ultra-High Line & Suffocating Gegenpress",
        "style_category": "high_press_vertical",
        "metrics": {
            "possession_target": 64,
            "pressing_intensity": 96,
            "defensive_line_height": 96,
            "build_up_tempo": 86,
            "counter_threat": 74,
            "tactical_fouls_rate": 42,
            "lead_preservation": 28,      # Never sits back; relentlessly pushes for 3-0, 4-0
            "late_chase_intensity": 95    # Ultra-compressed high line, suffocating box siege
        },
        "vs_elite_tactics": "Fearless ultra-high offside trap and 5-second counter-pressing regardless of opponent stature.",
        "vs_underdog_tactics": "Total territory stranglehold; choking opponent build-up inside their own third.",
        "key_strength": "Suffocating territory compression and rapid turnover-to-shot execution.",
        "vulnerability": "Extreme exposure to well-timed direct passes behind the high defensive line."
    },

    # 4. Atletico de Madrid
    "atletico-de-madrid": {
        "club_name": "Atlético de Madrid",
        "nickname": "Atlético Madrid",
        "manager": "Diego Simeone",
        "manager_moniker": "El Cholo",
        "formation": "5-3-2",
        "tactical_identity": "Cholismo Compact Low-Block & Devastating Counter-Strike",
        "style_category": "compact_low_block",
        "metrics": {
            "possession_target": 47,
            "pressing_intensity": 68,
            "defensive_line_height": 34,
            "build_up_tempo": 80,
            "counter_threat": 92,
            "tactical_fouls_rate": 84,
            "lead_preservation": 96,      # Master of the 1-0 lockdown; impenetrable double wall
            "late_chase_intensity": 82    # Direct aerial switches and aggressive physical duels
        },
        "vs_elite_tactics": "Impenetrable 5-3-2 low-block bunker; denies all central space and strikes ruthlessly on counters.",
        "vs_underdog_tactics": "Direct vertical progression through wing-backs; physical dominance in penalty box.",
        "key_strength": "World-class box defending, physical intimidation, and ruthless transition efficiency.",
        "vulnerability": "Can struggle to create breakthroughs when forced to break down ultra-passive low blocks."
    },
    "atletico-madrid": {
        "club_name": "Atlético de Madrid",
        "nickname": "Atlético Madrid",
        "manager": "Diego Simeone",
        "manager_moniker": "El Cholo",
        "formation": "5-3-2",
        "tactical_identity": "Cholismo Compact Low-Block & Devastating Counter-Strike",
        "style_category": "compact_low_block",
        "metrics": {
            "possession_target": 47,
            "pressing_intensity": 68,
            "defensive_line_height": 34,
            "build_up_tempo": 80,
            "counter_threat": 92,
            "tactical_fouls_rate": 84,
            "lead_preservation": 96,
            "late_chase_intensity": 82
        },
        "vs_elite_tactics": "Impenetrable 5-3-2 low-block bunker; denies all central space and strikes ruthlessly on counters.",
        "vs_underdog_tactics": "Direct vertical progression through wing-backs; physical dominance in penalty box.",
        "key_strength": "World-class box defending, physical intimidation, and ruthless transition efficiency.",
        "vulnerability": "Can struggle to create breakthroughs when forced to break down ultra-passive low blocks."
    },

    # 5. Athletic Club
    "athletic-club": {
        "club_name": "Athletic Club",
        "nickname": "Athletic Club",
        "manager": "Ernesto Valverde",
        "manager_moniker": "Txingurri",
        "formation": "4-2-3-1",
        "tactical_identity": "San Mamés High-Octane Press & Wing Sprints",
        "style_category": "high_press_vertical",
        "metrics": {
            "possession_target": 52,
            "pressing_intensity": 92,
            "defensive_line_height": 78,
            "build_up_tempo": 88,
            "counter_threat": 86,
            "tactical_fouls_rate": 66,
            "lead_preservation": 76,
            "late_chase_intensity": 92
        },
        "vs_elite_tactics": "Suffocating man-to-man pressing at San Mamés; relentless wing pace through Williams brothers.",
        "vs_underdog_tactics": "Fast vertical deliveries, high corner counts, and ferocious second-ball recovery.",
        "key_strength": "Blistering wing pace, aerial threat, and unmatched home stadium intensity.",
        "vulnerability": "High physical expenditure can lead to late fatigue in compressed match weeks."
    },

    # 6. Villarreal CF
    "villarreal-cf": {
        "club_name": "Villarreal CF",
        "nickname": "Villarreal",
        "manager": "Marcelino García Toral",
        "manager_moniker": "The Transition Master",
        "formation": "4-4-2",
        "tactical_identity": "Compact 4-4-2 Rapid Vertical Transitions",
        "style_category": "pragmatic_transitional",
        "metrics": {
            "possession_target": 49,
            "pressing_intensity": 74,
            "defensive_line_height": 55,
            "build_up_tempo": 88,
            "counter_threat": 94,
            "tactical_fouls_rate": 62,
            "lead_preservation": 82,
            "late_chase_intensity": 84
        },
        "vs_elite_tactics": "Narrow two-bank defensive block that traps central play and breaks with vertical precision.",
        "vs_underdog_tactics": "Fast combinations between strikers and wide midfielders to unbalance backlines.",
        "key_strength": "Lethal direct vertical counter-attacks and disciplined defensive spacing.",
        "vulnerability": "Can be vulnerable if opposing wingers stretch their narrow 4-4-2 horizontally."
    },

    # 7. Real Sociedad
    "real-sociedad": {
        "club_name": "Real Sociedad",
        "nickname": "Real Sociedad",
        "manager": "Imanol Alguacil",
        "manager_moniker": "The Basque Tactician",
        "formation": "4-3-3",
        "tactical_identity": "Intricate Midfield Circulation & Pressing Traps",
        "style_category": "possession_heavy",
        "metrics": {
            "possession_target": 56,
            "pressing_intensity": 86,
            "defensive_line_height": 76,
            "build_up_tempo": 64,
            "counter_threat": 70,
            "tactical_fouls_rate": 58,
            "lead_preservation": 74,
            "late_chase_intensity": 85
        },
        "vs_elite_tactics": "Intense midfield pressing traps; disrupts rhythm with patient, technical ball retention.",
        "vs_underdog_tactics": "Patient positional dissection; working overloads to free wingers inside the box.",
        "key_strength": "Midfield technical quality and structured pressing triggers.",
        "vulnerability": "Can lack raw finishing edge against ultra-deep defensive blocks."
    },

    # 8. Getafe CF
    "getafe-cf": {
        "club_name": "Getafe CF",
        "nickname": "Getafe",
        "manager": "José Bordalás",
        "manager_moniker": "El Comandante",
        "formation": "4-4-2",
        "tactical_identity": "Bordalismo Aggressive Combat, Low-Block & Gamesmanship",
        "style_category": "direct_aerial_combat",
        "metrics": {
            "possession_target": 38,
            "pressing_intensity": 88,
            "defensive_line_height": 24,
            "build_up_tempo": 45,
            "counter_threat": 76,
            "tactical_fouls_rate": 98,
            "lead_preservation": 98,
            "late_chase_intensity": 78
        },
        "vs_elite_tactics": "Extreme physical warfare; breaks flow with tactical fouls, ultra-deep block, and zero space.",
        "vs_underdog_tactics": "Set-piece bombardment, second-ball battles, and aggressive direct duels.",
        "key_strength": "Disruptive psychological edge, set-piece threat, and unmatched low-block resilience.",
        "vulnerability": "High card and suspension frequency; limited open-play creative flair."
    },

    # 9. Sevilla FC
    "sevilla-fc": {
        "club_name": "Sevilla FC",
        "nickname": "Sevilla",
        "manager": "García Pimienta",
        "manager_moniker": "The Build-Up Purist",
        "formation": "4-3-3",
        "tactical_identity": "Progressive Build-Up from the Back & Wide Overloads",
        "style_category": "possession_heavy",
        "metrics": {
            "possession_target": 56,
            "pressing_intensity": 72,
            "defensive_line_height": 68,
            "build_up_tempo": 62,
            "counter_threat": 65,
            "tactical_fouls_rate": 60,
            "lead_preservation": 68,
            "late_chase_intensity": 82
        },
        "vs_elite_tactics": "Cautious possession progression; seeks to take the sting out of high-intensity opponents.",
        "vs_underdog_tactics": "High territorial occupation; switches play to dynamic wingers in 1v1 situations.",
        "key_strength": "Patient ball progression and structured positional play.",
        "vulnerability": "High risk of costly turnovers when playing out under coordinated press."
    },

    # 10. CA Osasuna
    "c-a-osasuna": {
        "club_name": "CA Osasuna",
        "nickname": "Osasuna",
        "manager": "Vicente Moreno",
        "manager_moniker": "The Pragmatist",
        "formation": "4-3-3",
        "tactical_identity": "Combative Direct Verticality & Aerial Crossing",
        "style_category": "direct_aerial_combat",
        "metrics": {
            "possession_target": 46,
            "pressing_intensity": 80,
            "defensive_line_height": 48,
            "build_up_tempo": 78,
            "counter_threat": 76,
            "tactical_fouls_rate": 82,
            "lead_preservation": 85,
            "late_chase_intensity": 86
        },
        "vs_elite_tactics": "High-intensity physical harassment in midfield; direct aerial balls to bypass opposition press.",
        "vs_underdog_tactics": "Relentless crossing from both flanks; physical battles on the second ball.",
        "key_strength": "Aerial dominance in both boxes and fierce home ground tenacity.",
        "vulnerability": "Susceptible to quick passing combinations through the half-spaces."
    },

    # 11. Rayo Vallecano
    "rayo-vallecano": {
        "club_name": "Rayo Vallecano",
        "nickname": "Rayo Vallecano",
        "manager": "Iñigo Pérez",
        "manager_moniker": "The High-Voltage Coach",
        "formation": "4-2-3-1",
        "tactical_identity": "Guerrilla High Press & Lightning Flank Invasions",
        "style_category": "high_press_vertical",
        "metrics": {
            "possession_target": 48,
            "pressing_intensity": 90,
            "defensive_line_height": 75,
            "build_up_tempo": 86,
            "counter_threat": 82,
            "tactical_fouls_rate": 74,
            "lead_preservation": 64,
            "late_chase_intensity": 90
        },
        "vs_elite_tactics": "Aggressive, fearless man-to-man high press; turns games into wild end-to-end chaos.",
        "vs_underdog_tactics": "Fast vertical transitions; relentless wing deliveries and long-range shooting.",
        "key_strength": "Fierce pressing tempo and chaotic transitions that unnerve technical giants.",
        "vulnerability": "Leaves massive pockets of space in transition if initial press is broken."
    },

    # 12. Valencia CF
    "valencia-cf": {
        "club_name": "Valencia CF",
        "nickname": "Valencia",
        "manager": "Rubén Baraja",
        "manager_moniker": "El Pipo",
        "formation": "4-4-2",
        "tactical_identity": "Disciplined Mid-Block & Energetic Youth Counter",
        "style_category": "pragmatic_transitional",
        "metrics": {
            "possession_target": 44,
            "pressing_intensity": 72,
            "defensive_line_height": 42,
            "build_up_tempo": 80,
            "counter_threat": 82,
            "tactical_fouls_rate": 70,
            "lead_preservation": 82,
            "late_chase_intensity": 80
        },
        "vs_elite_tactics": "Deep, structured 4-4-2 block at Mestalla; launches fast wing counter-attacks.",
        "vs_underdog_tactics": "Organized direct transitions; feeds strikers with early balls into channels.",
        "key_strength": "Youthful energy, defensive solidarity in deep zones, and spirited home support.",
        "vulnerability": "Lack of depth and experience can cause lapses in concentration late in games."
    },

    # 13. Deportivo Alaves
    "d-alaves": {
        "club_name": "Deportivo Alavés",
        "nickname": "Alavés",
        "manager": "Luis García Plaza",
        "manager_moniker": "The Fort Builder",
        "formation": "4-2-3-1",
        "tactical_identity": "Resilient Home Fortress & Direct Physical Combat",
        "style_category": "direct_aerial_combat",
        "metrics": {
            "possession_target": 43,
            "pressing_intensity": 76,
            "defensive_line_height": 45,
            "build_up_tempo": 76,
            "counter_threat": 78,
            "tactical_fouls_rate": 78,
            "lead_preservation": 84,
            "late_chase_intensity": 82
        },
        "vs_elite_tactics": "Compact central blockade; denies through-balls and forces play into contested wide zones.",
        "vs_underdog_tactics": "Direct physical hold-up play; strong set-piece emphasis and second-phase pressure.",
        "key_strength": "Mendizorrotza home atmosphere, physical duels, and defensive work-rate.",
        "vulnerability": "Limited technical creativity when chasing games against set defenses."
    },

    # 14. RC Celta de Vigo
    "rc-celta": {
        "club_name": "RC Celta de Vigo",
        "nickname": "Celta Vigo",
        "manager": "Claudio Giráldez",
        "manager_moniker": "The Academy Visionary",
        "formation": "3-4-3",
        "tactical_identity": "Dynamic Positional Fluidity & Bravery on the Ball",
        "style_category": "possession_heavy",
        "metrics": {
            "possession_target": 55,
            "pressing_intensity": 82,
            "defensive_line_height": 72,
            "build_up_tempo": 76,
            "counter_threat": 74,
            "tactical_fouls_rate": 54,
            "lead_preservation": 58,
            "late_chase_intensity": 88
        },
        "vs_elite_tactics": "Refuses to abandon possession; plays through high presses with bold passing out from the back.",
        "vs_underdog_tactics": "Overloads the wide channels with overlapping wing-backs and inverted playmakers.",
        "key_strength": "High technical bravery, fluid combinations, and vertical passing corridors.",
        "vulnerability": "Can be caught in high-risk possession turnovers inside defensive third."
    },
    "celta-vigo": {
        "club_name": "RC Celta de Vigo",
        "nickname": "Celta Vigo",
        "manager": "Claudio Giráldez",
        "manager_moniker": "The Academy Visionary",
        "formation": "3-4-3",
        "tactical_identity": "Dynamic Positional Fluidity & Bravery on the Ball",
        "style_category": "possession_heavy",
        "metrics": {
            "possession_target": 55,
            "pressing_intensity": 82,
            "defensive_line_height": 72,
            "build_up_tempo": 76,
            "counter_threat": 74,
            "tactical_fouls_rate": 54,
            "lead_preservation": 58,
            "late_chase_intensity": 88
        },
        "vs_elite_tactics": "Refuses to abandon possession; plays through high presses with bold passing out from the back.",
        "vs_underdog_tactics": "Overloads the wide channels with overlapping wing-backs and inverted playmakers.",
        "key_strength": "High technical bravery, fluid combinations, and vertical passing corridors.",
        "vulnerability": "Can be caught in high-risk possession turnovers inside defensive third."
    },

    # 15. RCD Espanyol
    "rcd-espanyol": {
        "club_name": "RCD Espanyol",
        "nickname": "Espanyol",
        "manager": "Manolo González",
        "manager_moniker": "The Battle Strategist",
        "formation": "4-4-2",
        "tactical_identity": "Pragmatic Compact Mid-Block & Direct Counters",
        "style_category": "pragmatic_transitional",
        "metrics": {
            "possession_target": 42,
            "pressing_intensity": 74,
            "defensive_line_height": 40,
            "build_up_tempo": 76,
            "counter_threat": 78,
            "tactical_fouls_rate": 78,
            "lead_preservation": 84,
            "late_chase_intensity": 80
        },
        "vs_elite_tactics": "Disciplined low-to-mid block; restricts central passing lanes and strikes with direct balls.",
        "vs_underdog_tactics": "Organized direct transitions and strong emphasis on set-piece delivery.",
        "key_strength": "Structured defensive discipline and physical battle-tested spirit.",
        "vulnerability": "Low passing volume can leave forwards isolated for long spells."
    },

    # 16. RC Deportivo de La Coruna
    "rc-deportivo": {
        "club_name": "RC Deportivo de La Coruña",
        "nickname": "Deportivo",
        "manager": "Imanol Idiakez",
        "manager_moniker": "The Riazor General",
        "formation": "4-2-3-1",
        "tactical_identity": "Historic Pride, Fast Flank Transitions & Resilient Defense",
        "style_category": "pragmatic_transitional",
        "metrics": {
            "possession_target": 50,
            "pressing_intensity": 75,
            "defensive_line_height": 55,
            "build_up_tempo": 78,
            "counter_threat": 80,
            "tactical_fouls_rate": 66,
            "lead_preservation": 80,
            "late_chase_intensity": 85
        },
        "vs_elite_tactics": "Passionate Riazor fortress defense; compact double pivot and explosive counter-attacks.",
        "vs_underdog_tactics": "Assertive forward passing; feeds mobile strikers in central channel.",
        "key_strength": "Spirited tactical unity, passionate fan base, and clinical transition finishing.",
        "vulnerability": "Occasional defensive lapses against intricate wide combinations."
    },

    # 17. Levante UD
    "levante-ud": {
        "club_name": "Levante UD",
        "nickname": "Levante",
        "manager": "Julián Calero",
        "manager_moniker": "The Tactical Pragmatist",
        "formation": "4-4-2",
        "tactical_identity": "Organized Defensive Spine & Fast Wing Breaks",
        "style_category": "pragmatic_transitional",
        "metrics": {
            "possession_target": 46,
            "pressing_intensity": 72,
            "defensive_line_height": 48,
            "build_up_tempo": 80,
            "counter_threat": 82,
            "tactical_fouls_rate": 72,
            "lead_preservation": 82,
            "late_chase_intensity": 80
        },
        "vs_elite_tactics": "Deep defensive discipline, compact lines, fast wing breaks via wide midfielders.",
        "vs_underdog_tactics": "Controlled possession tempo, utilizing striker combinations to penetrate box.",
        "key_strength": "Defensive organization and direct counter-attacking speed.",
        "vulnerability": "Vulnerable to high sustained pressing against their backline."
    },

    # 18. Racing Santander
    "r-racing-club": {
        "club_name": "Racing Santander",
        "nickname": "Racing Santander",
        "manager": "José Alberto López",
        "manager_moniker": "The High-Tempo Coach",
        "formation": "4-2-3-1",
        "tactical_identity": "Fast-Paced Attacking Transition & Flank Overload",
        "style_category": "high_press_vertical",
        "metrics": {
            "possession_target": 48,
            "pressing_intensity": 82,
            "defensive_line_height": 62,
            "build_up_tempo": 86,
            "counter_threat": 84,
            "tactical_fouls_rate": 68,
            "lead_preservation": 72,
            "late_chase_intensity": 88
        },
        "vs_elite_tactics": "Brave forward pressing; tries to disrupt build-up with sudden high-tempo surges.",
        "vs_underdog_tactics": "High cross volume and fast combination play in the final third.",
        "key_strength": "Fearless attacking intent, pace on wings, and high vertical speed.",
        "vulnerability": "Can concede counter opportunities when overcommitting players forward."
    },

    # 19. Malaga CF
    "malaga-cf": {
        "club_name": "Málaga CF",
        "nickname": "Málaga",
        "manager": "Sergio Pellicer",
        "manager_moniker": "The Rosaleda Tactician",
        "formation": "4-2-3-1",
        "tactical_identity": "Resilient Mid-Block & Rosaleda Electric Counter",
        "style_category": "pragmatic_transitional",
        "metrics": {
            "possession_target": 46,
            "pressing_intensity": 74,
            "defensive_line_height": 48,
            "build_up_tempo": 76,
            "counter_threat": 78,
            "tactical_fouls_rate": 72,
            "lead_preservation": 82,
            "late_chase_intensity": 82
        },
        "vs_elite_tactics": "Solid mid-block; feeds off intense Rosaleda home support to launch swift counters.",
        "vs_underdog_tactics": "Organized direct build-up with heavy reliance on wide delivery.",
        "key_strength": "Passionate home backing and solid collective defensive cohesion.",
        "vulnerability": "Difficulty breaking down well-organized low blocks."
    },

    # 20. Elche CF
    "elche-c-f": {
        "club_name": "Elche CF",
        "nickname": "Elche",
        "manager": "Eder Sarabia",
        "manager_moniker": "The Possession Devotee",
        "formation": "4-3-3",
        "tactical_identity": "Extreme Possession Football & High Defensive Risk",
        "style_category": "possession_heavy",
        "metrics": {
            "possession_target": 60,
            "pressing_intensity": 80,
            "defensive_line_height": 78,
            "build_up_tempo": 60,
            "counter_threat": 62,
            "tactical_fouls_rate": 58,
            "lead_preservation": 64,
            "late_chase_intensity": 86
        },
        "vs_elite_tactics": "Insists on dominating possession even against giants; creates overloads but risks huge turnovers.",
        "vs_underdog_tactics": "Smothering possession game; circulates until openings appear in central zones.",
        "key_strength": "Total ball domination and high short-passing volume.",
        "vulnerability": "Excessive possession obsession can lead to fatal counter-attack concessions."
    },

    # Promoted / Alternative Spanish clubs
    "girona": {
        "club_name": "Girona FC",
        "nickname": "Girona",
        "manager": "Míchel Sánchez",
        "manager_moniker": "The Fluid Revolutionary",
        "formation": "4-3-3",
        "tactical_identity": "Inverted Full-Backs & Expansive Positional Fluidity",
        "style_category": "possession_heavy",
        "metrics": {
            "possession_target": 60,
            "pressing_intensity": 85,
            "defensive_line_height": 82,
            "build_up_tempo": 82,
            "counter_threat": 80,
            "tactical_fouls_rate": 50,
            "lead_preservation": 55,
            "late_chase_intensity": 92
        },
        "vs_elite_tactics": "Fearless positional rotation; attacks elite clubs with high numerical overloads.",
        "vs_underdog_tactics": "Total territory dominance; overlapping center-backs and inverted wing-backs.",
        "key_strength": "Unpredictable positional movement and clinical wide crossing.",
        "vulnerability": "High defensive line vulnerable to direct through-balls."
    },
    "mallorca": {
        "club_name": "RCD Mallorca",
        "nickname": "Mallorca",
        "manager": "Jagoba Arrasate",
        "manager_moniker": "The Island Fortress Master",
        "formation": "5-3-2",
        "tactical_identity": "Solid Low-Block, Set-Piece Threat & Aerial Power",
        "style_category": "compact_low_block",
        "metrics": {
            "possession_target": 42,
            "pressing_intensity": 70,
            "defensive_line_height": 35,
            "build_up_tempo": 74,
            "counter_threat": 76,
            "tactical_fouls_rate": 86,
            "lead_preservation": 90,
            "late_chase_intensity": 80
        },
        "vs_elite_tactics": "Deep 5-3-2 barricade; aggressive physical duels and lethal set-piece delivery.",
        "vs_underdog_tactics": "Direct aerial football and aggressive second-ball contesting.",
        "key_strength": "Imposing physical size, set-piece efficiency, and disciplined low-block.",
        "vulnerability": "Low possession can wear down defenders over 90 minutes."
    },
    "las-palmas": {
        "club_name": "UD Las Palmas",
        "nickname": "Las Palmas",
        "manager": "Diego Martínez",
        "manager_moniker": "The Tactical Balancer",
        "formation": "4-3-3",
        "tactical_identity": "Canarian Technical Touch & Measured Build-Up",
        "style_category": "possession_heavy",
        "metrics": {
            "possession_target": 56,
            "pressing_intensity": 72,
            "defensive_line_height": 60,
            "build_up_tempo": 62,
            "counter_threat": 65,
            "tactical_fouls_rate": 55,
            "lead_preservation": 70,
            "late_chase_intensity": 80
        },
        "vs_elite_tactics": "High passing density to frustrate press; patient retention to lower tempo.",
        "vs_underdog_tactics": "Intricate technical passing through midfield to create central overloads.",
        "key_strength": "Exceptional first-touch technique and close-control ball retention.",
        "vulnerability": "Lacks physical power in defensive transition."
    },
    "leganes": {
        "club_name": "CD Leganés",
        "nickname": "Leganés",
        "manager": "Borja Jiménez",
        "manager_moniker": "The Defensive Craftsman",
        "formation": "4-2-3-1",
        "tactical_identity": "Compact Low-Block & Fast Counters",
        "style_category": "compact_low_block",
        "metrics": {
            "possession_target": 40,
            "pressing_intensity": 74,
            "defensive_line_height": 36,
            "build_up_tempo": 78,
            "counter_threat": 80,
            "tactical_fouls_rate": 82,
            "lead_preservation": 92,
            "late_chase_intensity": 78
        },
        "vs_elite_tactics": "Ultra-compact low block; limits opposition to speculative long shots.",
        "vs_underdog_tactics": "Pragmatic mid-block with sharp counter-attacking spikes.",
        "key_strength": "Rock-solid defensive discipline and high work-rate.",
        "vulnerability": "Low goal-scoring output in open play."
    },
    "valladolid": {
        "club_name": "Real Valladolid",
        "nickname": "Valladolid",
        "manager": "Paulo Pezzolano",
        "manager_moniker": "The Aggressive Competitor",
        "formation": "4-3-3",
        "tactical_identity": "Combative Midfield Duels & Fast Flank Breaks",
        "style_category": "pragmatic_transitional",
        "metrics": {
            "possession_target": 45,
            "pressing_intensity": 76,
            "defensive_line_height": 50,
            "build_up_tempo": 78,
            "counter_threat": 76,
            "tactical_fouls_rate": 78,
            "lead_preservation": 80,
            "late_chase_intensity": 82
        },
        "vs_elite_tactics": "Physical battle in central zones; quick switches to wide attackers.",
        "vs_underdog_tactics": "Direct attacking transitions with heavy cross volume.",
        "key_strength": "Combative physical spirit and direct crossing.",
        "vulnerability": "Can be drawn out of defensive shape by patient positional play."
    }
}


DEFAULT_TACTICAL_DNA: Dict[str, Any] = {
    "club_name": "La Liga Club",
    "nickname": "Club",
    "manager": "Head Coach",
    "manager_moniker": "The Strategist",
    "formation": "4-2-3-1",
    "tactical_identity": "Balanced Spanish Tactical System",
    "style_category": "pragmatic_transitional",
    "metrics": {
        "possession_target": 50,
        "pressing_intensity": 75,
        "defensive_line_height": 55,
        "build_up_tempo": 75,
        "counter_threat": 75,
        "tactical_fouls_rate": 65,
        "lead_preservation": 75,
        "late_chase_intensity": 80
    },
    "vs_elite_tactics": "Disciplined mid-block and opportunistic counter-attacks.",
    "vs_underdog_tactics": "Assertive possession build-up with structured wing play.",
    "key_strength": "Tactical discipline and balanced squad structure.",
    "vulnerability": "Balanced style can lack extreme specialization."
}


class ClubTacticsRegistry:
    """Registry and matchup analysis engine for authentic club & manager tactical identities."""

    @staticmethod
    def get_profile(club_slug: Optional[str]) -> Dict[str, Any]:
        """Fetches the authentic tactical DNA profile for a club slug with default fallback."""
        if not club_slug:
            return dict(DEFAULT_TACTICAL_DNA)
        slug_clean = club_slug.lower().strip()
        if slug_clean in CLUB_TACTICAL_DNA:
            return dict(CLUB_TACTICAL_DNA[slug_clean])
        for k, v in CLUB_TACTICAL_DNA.items():
            if k in slug_clean or slug_clean in k:
                return dict(v)
        return dict(DEFAULT_TACTICAL_DNA)

    @classmethod
    def evaluate_tactical_clash(
        cls,
        home_slug: str,
        away_slug: str,
        home_rank: int = 10,
        away_rank: int = 10
    ) -> Dict[str, Any]:
        """
        Calculates the authentic tactical clash dynamics between Home Club DNA and Away Club DNA.
        Models:
        - Style synergy: High Line vs Fast Counter, Possession vs Low Block
        - Opponent Tier Context: How each team adapts when facing a Big Club vs Underdog
        - Tactical xG multipliers: Real football tactical adjustments
        - Expected possession split & match flow
        """
        h = cls.get_profile(home_slug)
        a = cls.get_profile(away_slug)

        h_metrics = h["metrics"]
        a_metrics = a["metrics"]

        # Opponent Tier determination (Top 4 / elite)
        is_h_elite = home_rank <= 4 or home_slug in ["real-madrid", "fc-barcelona", "atletico-de-madrid", "atletico-madrid"]
        is_a_elite = away_rank <= 4 or away_slug in ["real-madrid", "fc-barcelona", "atletico-de-madrid", "atletico-madrid"]

        h_approach = h["vs_elite_tactics"] if is_a_elite else h["vs_underdog_tactics"]
        a_approach = a["vs_elite_tactics"] if is_h_elite else a["vs_underdog_tactics"]

        # 1. Base tactical xG multipliers
        h_mult = 1.0
        a_mult = 1.0

        # High Line vs Fast Counter
        if h_metrics["defensive_line_height"] >= 75 and a_metrics["counter_threat"] >= 80:
            a_mult += 0.12
            h_mult += 0.06

        if a_metrics["defensive_line_height"] >= 75 and h_metrics["counter_threat"] >= 80:
            h_mult += 0.14
            a_mult += 0.05

        # Possession vs Compact Low-Block
        if h["style_category"] == "possession_heavy" and a["style_category"] in ["compact_low_block", "direct_aerial_combat"]:
            h_mult -= 0.08
            a_mult += 0.04

        # High Press Duel (Both teams pressing >80)
        if h_metrics["pressing_intensity"] >= 82 and a_metrics["pressing_intensity"] >= 82:
            h_mult += 0.10
            a_mult += 0.10

        # 2. Possession calculation
        base_h_poss = h_metrics["possession_target"] + 3.0
        base_a_poss = a_metrics["possession_target"]
        total_p = base_h_poss + base_a_poss
        expected_h_poss = int(round((base_h_poss / total_p) * 100))
        expected_h_poss = max(35, min(70, expected_h_poss))
        expected_a_poss = 100 - expected_h_poss

        # 3. Tactical clash narrative synthesis
        verdict = f"{h['manager']}'s {h['tactical_identity']} collides with {a['manager']}'s {a['tactical_identity']}."
        if h_metrics["defensive_line_height"] >= 78 and a_metrics["counter_threat"] >= 85:
            key_battle = f"Key Clash: {h['nickname']}'s aggressive high defensive line will be tested by {a['nickname']}'s lethal vertical counter-strike."
        elif a["style_category"] in ["compact_low_block", "direct_aerial_combat"]:
            key_battle = f"Key Clash: {h['nickname']} must patiently break down {a['manager']}'s stubborn low block without getting caught on the break."
        elif h_metrics["pressing_intensity"] >= 80 and a_metrics["pressing_intensity"] >= 80:
            key_battle = f"Key Clash: A fierce midfield war of attrition with both managers demanding relentless pressing and fast transitions."
        else:
            key_battle = f"Key Clash: Tactical battle of tempo and space — {h['manager']}'s home game plan against {a['manager']}'s organized shape."

        return {
            "home": {
                "manager": h["manager"],
                "manager_moniker": h.get("manager_moniker", ""),
                "formation": h["formation"],
                "tactical_identity": h["tactical_identity"],
                "style_category": h["style_category"],
                "pressing_intensity": h_metrics["pressing_intensity"],
                "defensive_line_height": h_metrics["defensive_line_height"],
                "lead_preservation": h_metrics["lead_preservation"],
                "late_chase_intensity": h_metrics["late_chase_intensity"],
                "tactical_approach": h_approach,
                "key_strength": h["key_strength"],
                "vulnerability": h["vulnerability"],
                "xg_modifier": round(h_mult, 3)
            },
            "away": {
                "manager": a["manager"],
                "manager_moniker": a.get("manager_moniker", ""),
                "formation": a["formation"],
                "tactical_identity": a["tactical_identity"],
                "style_category": a["style_category"],
                "pressing_intensity": a_metrics["pressing_intensity"],
                "defensive_line_height": a_metrics["defensive_line_height"],
                "lead_preservation": a_metrics["lead_preservation"],
                "late_chase_intensity": a_metrics["late_chase_intensity"],
                "tactical_approach": a_approach,
                "key_strength": a["key_strength"],
                "vulnerability": a["vulnerability"],
                "xg_modifier": round(a_mult, 3)
            },
            "expected_possession": {
                "home": expected_h_poss,
                "away": expected_a_poss
            },
            "verdict": verdict,
            "key_battle": key_battle
        }
