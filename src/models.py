"""
Data models for the Football Player Profiling System.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class Club:
    id: int
    slug: str
    name: str
    nickname: str
    shortname: str
    foundation: Optional[str] = None
    shield_url: Optional[str] = None
    color: Optional[str] = None
    color_secondary: Optional[str] = None
    stadium: Optional[str] = None
    stadium_name: Optional[str] = None
    stadium_image_url: Optional[str] = None
    president: Optional[str] = None
    address: Optional[str] = None
    web_url: Optional[str] = None
    position: Optional[int] = None
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    points: int = 0
    qualification: Optional[str] = None
    formation: Optional[str] = '4-3-3'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlayerBio:
    id: int
    opta_id: str
    slug: str
    name: str
    nickname: str
    shirt_number: Optional[int] = None
    position_name: str = "Unknown"  # Forward, Midfielder, Defender, Goalkeeper
    position_slug: str = "unknown"
    country_code: Optional[str] = None
    photo_url: Optional[str] = None
    club_id: Optional[int] = None
    club_name: Optional[str] = None
    club_shield: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    height: Optional[int] = None  # in cm
    weight: Optional[int] = None  # in kg

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlayerStats:
    # Match participation
    games_played: int = 0
    starts: int = 0
    sub_on: int = 0
    sub_off: int = 0
    minutes_played: int = 0

    # Scoring & Attacking
    goals: int = 0
    home_goals: int = 0
    away_goals: int = 0
    goals_ibox: int = 0
    goals_obox: int = 0
    shots: int = 0
    shots_on_target: int = 0
    shots_ibox: int = 0
    shots_obox: int = 0
    blocked_shots: int = 0
    freekick_goals: int = 0
    penalty_goals: int = 0
    penalties_taken: int = 0

    # Passing & Playmaking
    assists: int = 0
    key_passes: int = 0  # att_assist
    passes_total: int = 0
    passes_accurate: int = 0
    forward_passes: int = 0
    long_balls: int = 0
    crosses: int = 0

    # Dribbling & Possession
    dribbles_attempted: int = 0
    dribbles_won: int = 0
    touches_in_box: int = 0
    fouls_drawn: int = 0  # was_fouled

    # Defending
    tackles_total: int = 0
    tackles_won: int = 0
    tackle_pct: float = 0.0
    interceptions: int = 0
    clearances: int = 0
    blocked_attempts: int = 0

    # Duels
    duels_won: int = 0
    duels_lost: int = 0
    aerial_won: int = 0
    aerial_lost: int = 0
    challenges_lost: int = 0

    # Discipline
    fouls_conceded: int = 0
    yellow_cards: int = 0
    second_yellows: int = 0
    red_cards: int = 0
    offsides: int = 0

    # Goalkeeping
    saves_total: int = 0
    saves_ibox: int = 0
    saves_obox: int = 0
    clean_sheets: int = 0
    goals_conceded: int = 0
    high_claims: int = 0
    punches: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlayerRankings:
    """Official La Liga league rank for each metric (1 = #1 in league)"""
    rankings: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, int]:
        return self.rankings


@dataclass
class ProfileScores:
    """Standard 0-99 performance card ratings & tactical attribute pillars"""
    overall_rating: int = 50

    # Standard Football Card Stats (Outfield: PAC, SHO, PAS, DRI, DEF, PHY)
    pace: int = 65
    shooting: int = 50
    passing: int = 55
    dribbling: int = 55
    defending: int = 50
    physical: int = 55

    # Goalkeeper Card Stats (DIV, HAN, KIC, REF, SPD, POS)
    is_goalkeeper: bool = False
    gk_diving: Optional[int] = None
    gk_handling: Optional[int] = None
    gk_kicking: Optional[int] = None
    gk_reflexes: Optional[int] = None
    gk_speed: Optional[int] = None
    gk_positioning: Optional[int] = None

    # Tactical Radar Pillars (0-100)
    attacking: int = 50
    playmaking: int = 50
    discipline_reliability: int = 50
    physical_duels: int = 50


    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class PlayerProfile:
    bio: PlayerBio
    stats: PlayerStats
    rankings: Dict[str, int]
    scores: ProfileScores
    archetype: str
    secondary_archetype: Optional[str] = None
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    per90: Dict[str, float] = field(default_factory=dict)
    percentiles: Dict[str, int] = field(default_factory=dict)  # 0-99 percentile rank

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bio": self.bio.to_dict(),
            "stats": self.stats.to_dict(),
            "rankings": self.rankings,
            "scores": self.scores.to_dict(),
            "archetype": self.archetype,
            "secondary_archetype": self.secondary_archetype,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "per90": self.per90,
            "percentiles": self.percentiles,
        }


@dataclass
class ClubStats:
    # Squad structure & match totals
    squad_size: int = 0
    matches_played: int = 0
    total_minutes: int = 0

    # Attacking
    goals: int = 0
    goals_per_game: float = 0.0
    shots: int = 0
    shots_on_target: int = 0
    shot_accuracy_pct: float = 0.0
    shots_per_game: float = 0.0
    conversion_rate_pct: float = 0.0

    # Passing & Control
    passes_total: int = 0
    passes_accurate: int = 0
    pass_accuracy_pct: float = 0.0
    passes_per_game: float = 0.0
    assists: int = 0
    key_passes: int = 0
    crosses: int = 0

    # Dribbling & Transition
    dribbles_attempted: int = 0
    dribbles_won: int = 0
    dribble_accuracy_pct: float = 0.0

    # Defending
    tackles_total: int = 0
    tackles_won: int = 0
    tackle_pct: float = 0.0
    interceptions: int = 0
    clearances: int = 0
    clean_sheets: int = 0
    saves: int = 0
    goals_conceded: int = 0
    goals_conceded_per_game: float = 0.0

    # Duels & Physicality
    duels_won: int = 0
    duels_lost: int = 0
    duel_win_pct: float = 0.0
    aerial_won: int = 0
    aerial_lost: int = 0
    aerial_win_pct: float = 0.0

    # Discipline
    fouls_conceded: int = 0
    yellow_cards: int = 0
    red_cards: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClubScores:
    # 0-99 Card Ratings (EA FC / FIFA Style)
    att_rating: int = 50
    mid_rating: int = 50
    def_rating: int = 50
    overall_rating: int = 50

    # Tactical Radar Pillars (0-100)
    possession_control: int = 50
    attacking_potency: int = 50
    defensive_solidity: int = 50
    pressing_workrate: int = 50
    physical_dominance: int = 50

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class ClubProfile:
    club: Club
    stats: ClubStats
    scores: ClubScores
    archetype: str
    secondary_style: Optional[str] = None
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    top_scorer: Optional[Dict[str, Any]] = None
    top_assister: Optional[Dict[str, Any]] = None
    defensive_leader: Optional[Dict[str, Any]] = None
    star_player: Optional[Dict[str, Any]] = None
    squad_breakdown: Dict[str, Any] = field(default_factory=dict)
    roster: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "club": self.club.to_dict(),
            "stats": self.stats.to_dict(),
            "scores": self.scores.to_dict(),
            "archetype": self.archetype,
            "secondary_style": self.secondary_style,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "top_scorer": self.top_scorer,
            "top_assister": self.top_assister,
            "defensive_leader": self.defensive_leader,
            "star_player": self.star_player,
            "squad_breakdown": self.squad_breakdown,
            "roster": self.roster,
        }

