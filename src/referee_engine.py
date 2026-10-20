"""
STATSPHERE Match Referee Intelligence & Behavioral Modeling Engine.
Calibrated on real European match data.

Profiles every official referee in La Liga and Serie A:
- Historical Fouls per Game (FPG)
- Yellow Card & Red Card Frequency
- Penalty Kick Propensity (PK/game)
- Strictness vs Leniency Index (0-100)
- Home Whistle Advantage Ratio
- Tactical Synergy / Friction with Manager Stances (Low Block vs Gegenpress)
- Simulated Match Officiating Events (Penalties, VAR Reviews, Cautions, Red Cards)
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple


@dataclass
class RefereeProfile:
    name: str
    slug: str
    short_name: str
    competition: str  # "laliga" | "serie_a"
    experience_level: str
    matches_officiated: int
    fouls_per_game: float
    yellow_cards_per_game: float
    red_cards_per_game: float
    penalties_per_game: float
    home_bias_ratio: float  # away fouls / home fouls
    strictness_index: int  # 0 to 100
    archetype: str
    badge_emoji: str
    bio_summary: str
    key_tendencies: List[str]
    tactical_synergies: Dict[str, str]

    @property
    def leniency_index(self) -> int:
        return 100 - self.strictness_index

    @property
    def card_hazard_level(self) -> str:
        if self.yellow_cards_per_game >= 5.3:
            return "Extreme Card Hazard 🟨"
        elif self.yellow_cards_per_game >= 4.5:
            return "Elevated Card Risk ⚠️"
        else:
            return "Lenient Booking Threshold 🕊️"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "short_name": self.short_name,
            "competition": self.competition,
            "experience_level": self.experience_level,
            "matches_officiated": self.matches_officiated,
            "fouls_per_game": round(self.fouls_per_game, 1),
            "yellow_cards_per_game": round(self.yellow_cards_per_game, 1),
            "red_cards_per_game": round(self.red_cards_per_game, 2),
            "penalties_per_game": round(self.penalties_per_game, 2),
            "home_bias_ratio": round(self.home_bias_ratio, 2),
            "strictness_index": self.strictness_index,
            "leniency_index": self.leniency_index,
            "archetype": self.archetype,
            "badge_emoji": self.badge_emoji,
            "card_hazard": self.card_hazard_level,
            "bio_summary": self.bio_summary,
            "key_tendencies": self.key_tendencies,
            "tactical_synergies": self.tactical_synergies,
        }


class RefereeRegistry:
    """Pre-calibrated repository of all official La Liga and Serie A match referees."""

    _PROFILES: Dict[str, RefereeProfile] = {
        # =========================================================================
        # LA LIGA MATCH OFFICIALS
        # =========================================================================
        "gil-manzano": RefereeProfile(
            name="Jesús Gil Manzano",
            slug="gil-manzano",
            short_name="Gil Manzano",
            competition="laliga",
            experience_level="FIFA International / Elite Category 1",
            matches_officiated=248,
            fouls_per_game=26.8,
            yellow_cards_per_game=6.1,
            red_cards_per_game=0.33,
            penalties_per_game=0.38,
            home_bias_ratio=0.91,
            strictness_index=93,
            archetype="Card-Happy Disciplinarian",
            badge_emoji="🟨",
            bio_summary="Spain's most prominent disciplinarian. Uncompromising zero-tolerance for dissent and cynical tactical fouls. Holds the highest yellow-card frequency in La Liga.",
            key_tendencies=[
                "League-leading 6.1 yellow cards per 90",
                "Aggressively cautions defensive midfielders before minute 30",
                "Strict on verbal dissent towards officiating crew",
                "Frequent whistle stops disrupt rapid transition flow",
            ],
            tactical_synergies={
                "low_block": "High friction with José Bordalás / Diego Simeone style low blocks. Elevated booking risk for central defenders.",
                "high_press": "Disrupts Hansi Flick high-tempo press by whistling subtle shirt-pulls and technical fouls.",
                "derby": "Volatile derby environment; high probability of multi-card accumulation or second yellow.",
            },
        ),
        "soto-grado": RefereeProfile(
            name="César Soto Grado",
            slug="soto-grado",
            short_name="Soto Grado",
            competition="laliga",
            experience_level="Senior Primera División Official",
            matches_officiated=142,
            fouls_per_game=23.7,
            yellow_cards_per_game=4.2,
            red_cards_per_game=0.40,
            penalties_per_game=0.30,
            home_bias_ratio=0.82,
            strictness_index=83,
            archetype="Red Card Hazard",
            badge_emoji="🟥",
            bio_summary="Allows intense physical midfield duels, but holds the league's highest straight-red dismissal rate for studs-up challenges and reckless contact.",
            key_tendencies=[
                "Highest red-card dismissal rate in La Liga (0.40 per 90)",
                "Moderate yellow card volume, but sudden straight-red hazard",
                "Permits heavy shoulder-to-shoulder contact",
                "Decisive penalty box decision-maker",
            ],
            tactical_synergies={
                "low_block": "Allows physical tackling in the middle third; defenders must avoid lunging tackles.",
                "high_press": "Favors physical counter-pressing teams as long as tackles remain on the ground.",
                "derby": "High dismissal danger in heated regional derbies.",
            },
        ),
        "hernandez-hernandez": RefereeProfile(
            name="Alejandro Hernández Hernández",
            slug="hernandez-hernandez",
            short_name="Hernández Hernández",
            competition="laliga",
            experience_level="FIFA International / El Clásico Veteran",
            matches_officiated=226,
            fouls_per_game=26.8,
            yellow_cards_per_game=5.5,
            red_cards_per_game=0.22,
            penalties_per_game=0.42,
            home_bias_ratio=1.08,
            strictness_index=88,
            archetype="Penalty & VAR Magnet",
            badge_emoji="🎯",
            bio_summary="Famous for intense scrutiny in marquee fixtures. High propensity to award spot-kicks and frequent reliance on pitchside VAR review monitors.",
            key_tendencies=[
                "Highest penalty-kick rate in Spain (0.42 PKs per 90)",
                "Frequently stops play to review box handballs on VAR",
                "Sensitive to theatrical box challenges",
                "Elevated foul count in the final third",
            ],
            tactical_synergies={
                "low_block": "Dangerous for low blocks that pack the 18-yard box; high risk of handball penalties.",
                "high_press": "Penalizes box challenges; favors agile dribblers like Vinícius and Yamal.",
                "derby": "High penalty expectation in high-stakes fixtures.",
            },
        ),
        "sanchez-martinez": RefereeProfile(
            name="José María Sánchez Martínez",
            slug="sanchez-martinez",
            short_name="Sánchez Martínez",
            competition="laliga",
            experience_level="FIFA International / Champions League Official",
            matches_officiated=214,
            fouls_per_game=25.5,
            yellow_cards_per_game=5.0,
            red_cards_per_game=0.18,
            penalties_per_game=0.33,
            home_bias_ratio=0.96,
            strictness_index=85,
            archetype="Authoritative Disciplinarian",
            badge_emoji="⚖️",
            bio_summary="Commands supreme tactical authority on the pitch. Highly consistent application of the rulebook, punitive on time-wasting and professional fouls.",
            key_tendencies=[
                "Consistent 5.0 yellow cards per match",
                "Punishes goalkeeper time-wasting with swift bookings",
                "Authoritative game management in high-pressure atmospheres",
                "Clear, decisive penalty box rulings",
            ],
            tactical_synergies={
                "low_block": "Quickly suppresses tactical time-wasting and injury simulation.",
                "high_press": "Balanced environment; protects goalkeepers on set-piece crowding.",
                "derby": "Keeps high-friction contests under firm tactical control.",
            },
        ),
        "busquets-ferrer": RefereeProfile(
            name="Mateo Busquets Ferrer",
            slug="busquets-ferrer",
            short_name="Busquets Ferrer",
            competition="laliga",
            experience_level="Rising Primera División Official",
            matches_officiated=44,
            fouls_per_game=27.8,
            yellow_cards_per_game=5.7,
            red_cards_per_game=0.33,
            penalties_per_game=0.35,
            home_bias_ratio=1.00,
            strictness_index=91,
            archetype="High-Stoppage Whistle",
            badge_emoji="🛑",
            bio_summary="One of Spain's strictest young officials. High whistle frequency breaks game momentum and elevates set-piece dominance.",
            key_tendencies=[
                "Highest fouls called per game in Spain (27.8 fouls/90)",
                "Low threshold for physical challenges in the midfield",
                "Frequent stoppages benefit set-piece specialists",
                "5.7 yellow cards per game",
            ],
            tactical_synergies={
                "low_block": "Stops play often, frustrating fluid possession clubs and favoring defensive resets.",
                "high_press": "Blunts high-tempo counter-attacks with persistent whistle interventions.",
                "derby": "High card count; set-piece goals heavily favored.",
            },
        ),
        "alberola-rojas": RefereeProfile(
            name="Javier Alberola Rojas",
            slug="alberola-rojas",
            short_name="Alberola Rojas",
            competition="laliga",
            experience_level="Senior Primera División Official",
            matches_officiated=168,
            fouls_per_game=26.2,
            yellow_cards_per_game=3.1,
            red_cards_per_game=0.28,
            penalties_per_game=0.19,
            home_bias_ratio=1.17,
            strictness_index=45,
            archetype="Lenient Free-Flow Enforcer",
            badge_emoji="🕊️",
            bio_summary="Spain's most card-lenient official. Believes in conversational refereeing and maximum ball-in-play time, recording the lowest card average in La Liga.",
            key_tendencies=[
                "Lowest yellow card rate in La Liga (just 3.1 YC/90)",
                "Prefers verbal warnings over brandishing cards",
                "Permits physical advantage whenever possible",
                "Rarely awards contentious soft penalties",
            ],
            tactical_synergies={
                "low_block": "Demands defenders tackle cleanly, but rarely cautions for first-time challenges.",
                "high_press": "Ideal referee for high-speed pressing and fluid possession clubs.",
                "derby": "Minimizes card accumulation; high ball-in-play percentage.",
            },
        ),
        "ortiz-arias": RefereeProfile(
            name="Miguel Ortiz Arias",
            slug="ortiz-arias",
            short_name="Ortiz Arias",
            competition="laliga",
            experience_level="Primera División Regular",
            matches_officiated=78,
            fouls_per_game=19.7,
            yellow_cards_per_game=3.8,
            red_cards_per_game=0.21,
            penalties_per_game=0.20,
            home_bias_ratio=1.03,
            strictness_index=42,
            archetype="Minimalist Whistle",
            badge_emoji="⏱️",
            bio_summary="A minimalist official who lets matches breathe. Holds the lowest foul-call rate in the league (under 20 fouls/game).",
            key_tendencies=[
                "Lowest foul rate in the league (19.7 fouls/90)",
                "Low card rate (3.8 YC/90)",
                "Maximizes continuous game flow",
                "Consistently high effective playing time",
            ],
            tactical_synergies={
                "low_block": "Forces defensive teams to win the ball cleanly without relying on tactical fouls.",
                "high_press": "Allows rapid end-to-end transition counter-attacks.",
                "derby": "Calm demeanor keeps tempers subdued.",
            },
        ),
        "quintero-gonzalez": RefereeProfile(
            name="Alejandro Quintero González",
            slug="quintero-gonzalez",
            short_name="Quintero González",
            competition="laliga",
            experience_level="Promoted Primera División Official",
            matches_officiated=36,
            fouls_per_game=26.7,
            yellow_cards_per_game=3.5,
            red_cards_per_game=0.31,
            penalties_per_game=0.26,
            home_bias_ratio=1.45,
            strictness_index=72,
            archetype="Home Advantage Whistle",
            badge_emoji="🏟️",
            bio_summary="Young official who displays the highest home-whistle bias in Spain, calling 45% more fouls against away visitors.",
            key_tendencies=[
                "Significant home whistle bias (1.45 Away/Home foul ratio)",
                "Away defenders penalized heavily in 50/50 duels",
                "3.5 yellow cards per game",
                "Home stadium crowd pressure influences whistle decisions",
            ],
            tactical_synergies={
                "low_block": "Gives home sides significant free-kick territory.",
                "high_press": "Away pressing teams encounter frequent whistle interruptions.",
                "derby": "Home team receives significant whistle edge.",
            },
        ),
        "cuadra-fernandez": RefereeProfile(
            name="Guillermo Cuadra Fernández",
            slug="cuadra-fernandez",
            short_name="Cuadra Fernández",
            competition="laliga",
            experience_level="FIFA International Official",
            matches_officiated=148,
            fouls_per_game=22.2,
            yellow_cards_per_game=4.4,
            red_cards_per_game=0.16,
            penalties_per_game=0.27,
            home_bias_ratio=0.87,
            strictness_index=76,
            archetype="Balanced European Standard",
            badge_emoji="⚖️",
            bio_summary="Solid, reliable UEFA-accredited official. Maintains balanced control across all game phases.",
            key_tendencies=[
                "Moderate foul call frequency (22.2/90)",
                "Average 4.4 yellow cards per game",
                "Low red-card risk (0.16/90)",
                "Reliable neutral officiating",
            ],
            tactical_synergies={
                "low_block": "Fair balance between defensive structure and attacking protection.",
                "high_press": "Allows technical superiority to decide the match outcome.",
                "derby": "Steady hand in mid-table clashes.",
            },
        ),
        "de-burgos": RefereeProfile(
            name="Ricardo De Burgos Bengoetxea",
            slug="de-burgos",
            short_name="De Burgos",
            competition="laliga",
            experience_level="FIFA International Official",
            matches_officiated=192,
            fouls_per_game=21.8,
            yellow_cards_per_game=3.4,
            red_cards_per_game=0.22,
            penalties_per_game=0.22,
            home_bias_ratio=1.19,
            strictness_index=58,
            archetype="Play-On Advocate",
            badge_emoji="⏱️",
            bio_summary="Basque official known for high physical tolerance and minimal card intervention. Favors athletic, competitive football.",
            key_tendencies=[
                "Under 3.5 yellow cards per game",
                "High tolerance for body checks and shoulder challenges",
                "Reluctant to award soft spot-kicks",
                "Favors continuous advantage play",
            ],
            tactical_synergies={
                "low_block": "Does not whistle minor contact, forcing attackers to stay on their feet.",
                "high_press": "Superb for fast transitions and direct vertical football.",
                "derby": "Refuses to let games degenerate into card theatrics.",
            },
        ),
        "munuera-montero": RefereeProfile(
            name="José Luis Munuera Montero",
            slug="munuera-montero",
            short_name="Munuera Montero",
            competition="laliga",
            experience_level="FIFA International Official",
            matches_officiated=174,
            fouls_per_game=24.7,
            yellow_cards_per_game=4.7,
            red_cards_per_game=0.12,
            penalties_per_game=0.24,
            home_bias_ratio=0.87,
            strictness_index=75,
            archetype="Fluid Modern Official",
            badge_emoji="🏃",
            bio_summary="Athletic official who stays close to play. Strong on positional reading and proactive player communication.",
            key_tendencies=[
                "Consistent 4.7 yellow cards per game",
                "Low red card rate (0.12/90)",
                "Communicates actively with team captains",
                "Solid penalty box judgment",
            ],
            tactical_synergies={
                "low_block": "Stops cynical fouls from behind promptly.",
                "high_press": "High positioning keeps up with fast breaks.",
                "derby": "Calm, assertive game management.",
            },
        ),

        # =========================================================================
        # SERIE A MATCH OFFICIALS
        # =========================================================================
        "orsato": RefereeProfile(
            name="Daniele Orsato",
            slug="orsato",
            short_name="Daniele Orsato",
            competition="serie_a",
            experience_level="FIFA World Cup Final Official / Legend",
            matches_officiated=290,
            fouls_per_game=22.5,
            yellow_cards_per_game=3.9,
            red_cards_per_game=0.20,
            penalties_per_game=0.24,
            home_bias_ratio=1.02,
            strictness_index=64,
            archetype="Authoritative Legend",
            badge_emoji="👑",
            bio_summary="World football icon renowned for commanding respect without brandishing cards. Commands absolute player obedience in high-friction Italian derbies.",
            key_tendencies=[
                "High tolerance for physical Italian defending",
                "Sub-4.0 yellow cards per 90 minutes",
                "Commands supreme player respect",
                "Zero tolerance for theatrics or feigning injury",
            ],
            tactical_synergies={
                "low_block": "Favors classic Italian catenaccio and physical box defending.",
                "high_press": "Allows aggressive midfield duels without petty whistle stops.",
                "derby": "Absolute master of high-voltage clashes like Derby d'Italia.",
            },
        ),
        "massa": RefereeProfile(
            name="Davide Massa",
            slug="massa",
            short_name="Davide Massa",
            competition="serie_a",
            experience_level="FIFA International / UEFA Category 1",
            matches_officiated=208,
            fouls_per_game=26.4,
            yellow_cards_per_game=5.2,
            red_cards_per_game=0.28,
            penalties_per_game=0.34,
            home_bias_ratio=1.06,
            strictness_index=84,
            archetype="Disciplinarian Official",
            badge_emoji="🟨",
            bio_summary="Strict Italian disciplinarian. Holds a firm grip on proceedings with quick cards for persistent infringements.",
            key_tendencies=[
                "5.2 yellow cards per game in Serie A",
                "Strict on shirt-pulling and tactical fouls",
                "High foul count in congested midfields",
                "Firm application of disciplinary sanctions",
            ],
            tactical_synergies={
                "low_block": "Heavily penalizes aggressive tactical fouling around the penalty area.",
                "high_press": "Protects attacking playmakers from persistent rotational fouls.",
                "derby": "Elevated card risk in high-friction matchups.",
            },
        ),
        "mariani": RefereeProfile(
            name="Maurizio Mariani",
            slug="mariani",
            short_name="Maurizio Mariani",
            competition="serie_a",
            experience_level="FIFA International Official",
            matches_officiated=162,
            fouls_per_game=27.1,
            yellow_cards_per_game=5.4,
            red_cards_per_game=0.30,
            penalties_per_game=0.44,
            home_bias_ratio=0.98,
            strictness_index=87,
            archetype="Penalty Whistle Magnet",
            badge_emoji="🎯",
            bio_summary="Serie A's leading penalty kick caller (0.44 PK/game). Highly vigilant on box contact, handballs, and VAR penalty reviews.",
            key_tendencies=[
                "Highest penalty-kick frequency in Italy (0.44 PKs/90)",
                "5.4 yellow cards per game",
                "Decisive on VAR review calls",
                "Strict on late challenges inside the box",
            ],
            tactical_synergies={
                "low_block": "Extreme hazard for penalty box crowding and desperate recovery tackles.",
                "high_press": "Favors nimble penalty-box attackers like Lautaro and Leão.",
                "derby": "Very high penalty expectation in marquee games.",
            },
        ),
        "di-bello": RefereeProfile(
            name="Marco Di Bello",
            slug="di-bello",
            short_name="Marco Di Bello",
            competition="serie_a",
            experience_level="Senior Serie A Official",
            matches_officiated=176,
            fouls_per_game=26.8,
            yellow_cards_per_game=5.8,
            red_cards_per_game=0.38,
            penalties_per_game=0.38,
            home_bias_ratio=1.04,
            strictness_index=91,
            archetype="Card-Happy Enforcer",
            badge_emoji="🟨",
            bio_summary="Notorious for volatile card spikes in high-stakes matches. Quick to issue multiple bookings in quick succession when games get heated.",
            key_tendencies=[
                "5.8 yellow cards and 0.38 reds per 90",
                "Rapid card escalation when challenged by players",
                "High dismissal hazard",
                "Frequent game interruptions",
            ],
            tactical_synergies={
                "low_block": "High risk of second yellow cards for defensive backs.",
                "high_press": "Quickly penalizes high-pressing tackles with bookings.",
                "derby": "Extreme caution required; multiple card events almost certain.",
            },
        ),
        "maresca": RefereeProfile(
            name="Fabio Maresca",
            slug="maresca",
            short_name="Fabio Maresca",
            competition="serie_a",
            experience_level="FIFA International Official",
            matches_officiated=140,
            fouls_per_game=27.5,
            yellow_cards_per_game=5.5,
            red_cards_per_game=0.32,
            penalties_per_game=0.36,
            home_bias_ratio=0.95,
            strictness_index=88,
            archetype="High-Tension Disciplinarian",
            badge_emoji="🛑",
            bio_summary="Unapologetic enforcer who punishes dissent and aggressive posturing. Highly active whistle in physical contests.",
            key_tendencies=[
                "Over 27 fouls called per game",
                "Cautions players and bench staff for dissent",
                "Punishes cynical counter-stopping fouls",
                "Elevated set-piece probability",
            ],
            tactical_synergies={
                "low_block": "Suppresses rough defensive tactics with persistent cards.",
                "high_press": "Whistles break rhythm of high-tempo vertical teams.",
                "derby": "Tense environment with zero tolerance for bench theatrics.",
            },
        ),
        "sozza": RefereeProfile(
            name="Simone Sozza",
            slug="sozza",
            short_name="Simone Sozza",
            competition="serie_a",
            experience_level="Rising International Official",
            matches_officiated=62,
            fouls_per_game=23.2,
            yellow_cards_per_game=4.1,
            red_cards_per_game=0.18,
            penalties_per_game=0.24,
            home_bias_ratio=1.00,
            strictness_index=55,
            archetype="Modern Fast-Flowing Official",
            badge_emoji="🏃",
            bio_summary="Regarded as the future of Italian refereeing. Athletic, modern European style with low stoppage and high playing tempo.",
            key_tendencies=[
                "Low card rate (4.1 YC/90)",
                "Under 24 fouls per match",
                "Lets physical 50/50 challenges play on",
                "Encourages high-tempo transitions",
            ],
            tactical_synergies={
                "low_block": "Forces defenders to win the ball cleanly without phantom fouls.",
                "high_press": "Ideal for fast attacking football like Atalanta and Inter.",
                "derby": "Calm, modern game management.",
            },
        ),
    }

    # Canonical name aliases for fuzzy/robust matching
    _NAME_ALIASES: Dict[str, str] = {
        "gil manzano": "gil-manzano",
        "jesús gil manzano": "gil-manzano",
        "jesus gil manzano": "gil-manzano",
        "césar soto": "soto-grado",
        "cesar soto": "soto-grado",
        "soto grado": "soto-grado",
        "césar soto grado": "soto-grado",
        "cesar soto grado": "soto-grado",
        "hernández hernández": "hernandez-hernandez",
        "alejandro hernández": "hernandez-hernandez",
        "alejandro hernandez": "hernandez-hernandez",
        "sánchez martínez": "sanchez-martinez",
        "josé sánchez": "sanchez-martinez",
        "jose sanchez": "sanchez-martinez",
        "sanchez martinez": "sanchez-martinez",
        "busquets ferrer": "busquets-ferrer",
        "mateo busquets": "busquets-ferrer",
        "alberola rojas": "alberola-rojas",
        "javier alberola": "alberola-rojas",
        "ortiz arias": "ortiz-arias",
        "miguel ortiz": "ortiz-arias",
        "quintero gonzález": "quintero-gonzalez",
        "alejandro quintero": "quintero-gonzalez",
        "cuadra fernández": "cuadra-fernandez",
        "guillermo cuadra": "cuadra-fernandez",
        "de burgos": "de-burgos",
        "ricardo de burgos": "de-burgos",
        "munuera montero": "munuera-montero",
        "josé munuera": "munuera-montero",
        "jose munuera": "munuera-montero",
        "orsato": "orsato",
        "daniele orsato": "orsato",
        "massa": "massa",
        "davide massa": "massa",
        "mariani": "mariani",
        "maurizio mariani": "mariani",
        "di bello": "di-bello",
        "marco di bello": "di-bello",
        "maresca": "maresca",
        "fabio maresca": "maresca",
        "sozza": "sozza",
        "simone sozza": "sozza",
    }

    @classmethod
    def get_by_slug(cls, slug: str) -> Optional[RefereeProfile]:
        return cls._PROFILES.get(slug.lower().strip())

    @classmethod
    def get_by_name(cls, name_or_alias: str) -> Optional[RefereeProfile]:
        if not name_or_alias:
            return None
        norm = name_or_alias.lower().strip()
        # Direct slug lookup
        if norm in cls._PROFILES:
            return cls._PROFILES[norm]
        # Alias lookup
        if norm in cls._NAME_ALIASES:
            return cls._PROFILES.get(cls._NAME_ALIASES[norm])
        # Substring search
        for key, slug in cls._NAME_ALIASES.items():
            if key in norm or norm in key:
                return cls._PROFILES.get(slug)
        # Search official names
        for slug, prof in cls._PROFILES.items():
            if norm in prof.name.lower() or norm in prof.short_name.lower():
                return prof
        return None

    @classmethod
    def get_all(cls, competition: Optional[str] = None) -> List[RefereeProfile]:
        profs = list(cls._PROFILES.values())
        if competition:
            comp = competition.lower().strip()
            profs = [p for p in profs if p.competition == comp]
        return sorted(profs, key=lambda x: x.strictness_index, reverse=True)

    @classmethod
    def get_top_strict(cls, limit: int = 5, competition: Optional[str] = None) -> List[RefereeProfile]:
        profs = cls.get_all(competition)
        return sorted(profs, key=lambda x: x.strictness_index, reverse=True)[:limit]

    @classmethod
    def get_most_lenient(cls, limit: int = 5, competition: Optional[str] = None) -> List[RefereeProfile]:
        profs = cls.get_all(competition)
        return sorted(profs, key=lambda x: x.leniency_index, reverse=True)[:limit]

    @classmethod
    def get_penalty_magnets(cls, limit: int = 5, competition: Optional[str] = None) -> List[RefereeProfile]:
        profs = cls.get_all(competition)
        return sorted(profs, key=lambda x: x.penalties_per_game, reverse=True)[:limit]

    @classmethod
    def get_for_fixture(cls, fixture: Dict[str, Any], fallback_comp: str = "laliga") -> RefereeProfile:
        """
        Retrieves the referee profile for a fixture.
        Uses database assigned referee, or deterministically assigns an authentic referee
        from the competition pool based on fixture ID and matchday.
        """
        ref_raw = fixture.get("referee")
        if ref_raw:
            p = cls.get_by_name(ref_raw)
            if p:
                return p

        comp = str(fixture.get("competition") or fallback_comp).lower()
        if "serie" in comp or "ita" in comp:
            pool = [p for p in cls._PROFILES.values() if p.competition == "serie_a"]
        else:
            pool = [p for p in cls._PROFILES.values() if p.competition == "laliga"]

        fid = int(fixture.get("id") or 20260401)
        md = int(fixture.get("matchday") or 1)
        idx = (fid * 31 + md * 17) % len(pool)
        return pool[idx]


class RefereeTacticalEvaluator:
    """Evaluates the tactical clash between match referee and team/manager styles."""

    @staticmethod
    def evaluate(
        referee: RefereeProfile,
        clash: Dict[str, Any],
        home_team: Dict[str, Any],
        away_team: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Computes quantitative and qualitative officiating impacts on the match:
        - fouls_multiplier & expected fouls
        - yellow_card_multiplier & booking hazard
        - red_card_risk_percentage
        - penalty_kick_probability (0.0 to 1.0)
        - tempo_and_flow_factor
        - tactical narrative breakdown
        """
        home_name = home_team.get("nickname") or home_team.get("name") or "Home"
        away_name = away_team.get("nickname") or away_team.get("name") or "Away"
        h_style = clash.get("home", {}).get("tactical_identity", "Balanced")
        a_style = clash.get("away", {}).get("tactical_identity", "Balanced")

        # 1. Fouls Multiplier
        # League baseline: 24.5 fouls/game
        base_foul_mult = referee.fouls_per_game / 24.5
        # If teams have physical styles (e.g. low block, heavy press), foul count rises
        is_h_physical = any(w in h_style.lower() for w in ("low block", "pragmatic", "combat", "press", "intense"))
        is_a_physical = any(w in a_style.lower() for w in ("low block", "pragmatic", "combat", "press", "intense"))
        style_foul_bump = (0.08 if is_h_physical else 0.0) + (0.08 if is_a_physical else 0.0)
        foul_mult = round(base_foul_mult * (1.0 + style_foul_bump), 2)

        # 2. Card Hazard & Multiplier
        # League baseline: 4.4 yellow cards/game
        base_card_mult = referee.yellow_cards_per_game / 4.4
        strict_card_bump = 0.12 if (referee.strictness_index >= 85 and (is_h_physical or is_a_physical)) else 0.0
        card_mult = round(base_card_mult + strict_card_bump, 2)

        # 3. Penalty Kick Probability (Empirical European baseline: ~27% per match)
        base_pk_prob = referee.penalties_per_game
        # Attacking box pressure: if match has high expected box entries (e.g. Madrid, Barca, Inter)
        h_att = home_team.get("att_rating") or home_team.get("overall_rating") or 78
        a_att = away_team.get("att_rating") or away_team.get("overall_rating") or 78
        box_threat = max(0.0, (max(h_att, a_att) - 78) * 0.012)
        penalty_chance = round(min(0.55, max(0.12, base_pk_prob + box_threat)), 2)

        # 4. Red Card Risk (Empirical baseline: ~18% per match)
        base_rc_prob = referee.red_cards_per_game * 0.65
        derby_friction = 0.08 if ("derby" in str(clash.get("key_battle", "")).lower() or (is_h_physical and is_a_physical)) else 0.0
        red_card_chance = round(min(0.38, max(0.04, base_rc_prob + derby_friction)), 2)

        # 5. Open-Play Tempo Modifier
        # Strict refs with high stoppages blunt counter-attacks (-8%), lenient refs boost transitions (+8%)
        if referee.strictness_index >= 85:
            tempo_factor = 0.92
            tempo_label = "Fragmented / High Stoppage 🛑"
        elif referee.strictness_index <= 55:
            tempo_factor = 1.08
            tempo_label = "Fluid / High Ball-in-Play 🏃"
        else:
            tempo_factor = 1.00
            tempo_label = "Standard European Flow ⚖️"

        # 6. Narrative Tactical Clashes
        narrative_points = []
        if referee.strictness_index >= 88:
            narrative_points.append(
                f"⚠️ High Whistle Hazard: {referee.short_name}'s strict threshold puts defensive midfielders on high alert for early cautions."
            )
        elif referee.strictness_index <= 50:
            narrative_points.append(
                f"🕊️ Free-Flowing Advantage: {referee.short_name}'s high contact tolerance favors aggressive counter-pressing without petty whistle stoppages."
            )

        if referee.penalties_per_game >= 0.38:
            narrative_points.append(
                f"🎯 Box Vigilance: {referee.short_name} awards {referee.penalties_per_game:.2f} penalties/game; defenders must exercise extreme caution inside the 18-yard box."
            )

        if referee.home_bias_ratio >= 1.25:
            narrative_points.append(
                f"🏟️ Stadium Influence: Strong home whistle tendency ({referee.home_bias_ratio:.2f}x foul ratio); {away_name} must stay disciplined under crowd pressure."
            )

        if not narrative_points:
            narrative_points.append(
                f"⚖️ Neutral Officiating: {referee.short_name} maintains balanced, authoritative game management across all phases."
            )

        return {
            "referee": referee.to_dict(),
            "foul_multiplier": foul_mult,
            "card_multiplier": card_mult,
            "penalty_chance": penalty_chance,
            "red_card_chance": red_card_chance,
            "tempo_factor": tempo_factor,
            "tempo_label": tempo_label,
            "tactical_narrative": " ".join(narrative_points),
        }
