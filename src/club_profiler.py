"""
Club Profiler and Tactical Intelligence Engine.
Aggregates squad player metrics, calculates 0-99 team card ratings (ATT, MID, DEF, OVR),
5-axis tactical pillars, playstyle archetypes, and automated scout dossiers.
"""
from typing import List, Dict, Any, Optional, Tuple
from .models import Club, ClubStats, ClubScores, ClubProfile, PlayerProfile


class ClubProfiler:
    """Calculates team ratings, tactical identity, and scout reports for football clubs."""

    @staticmethod
    def _clamp(val: float, low: float = 30.0, high: float = 99.0) -> int:
        return int(round(max(low, min(high, val))))

    @classmethod
    def aggregate_squad_stats(cls, club: Club, player_profiles: List[PlayerProfile]) -> ClubStats:
        """Aggregates all player match statistics for a club."""
        squad_size = len(player_profiles)
        matches = club.played if club.played > 0 else 4

        total_mins = sum(p.stats.minutes_played for p in player_profiles)
        goals = club.goals_for if club.goals_for > 0 else sum(p.stats.goals for p in player_profiles)
        shots = sum(p.stats.shots for p in player_profiles)
        shots_ot = sum(p.stats.shots_on_target for p in player_profiles)
        shot_acc = (shots_ot / shots * 100.0) if shots > 0 else 0.0
        goals_pg = round(goals / matches, 2) if matches > 0 else 0.0
        shots_pg = round(shots / matches, 1) if matches > 0 else 0.0
        conv_rate = round((goals / shots * 100.0), 1) if shots > 0 else 0.0

        passes_tot = sum(p.stats.passes_total for p in player_profiles)
        passes_acc = sum(p.stats.passes_accurate for p in player_profiles)
        pass_acc = round((passes_acc / passes_tot * 100.0), 1) if passes_tot > 0 else 0.0
        passes_pg = round(passes_tot / matches, 1) if matches > 0 else 0.0
        assists = sum(p.stats.assists for p in player_profiles)
        key_passes = sum(p.stats.key_passes for p in player_profiles)
        crosses = sum(p.stats.crosses for p in player_profiles)

        drib_att = sum(p.stats.dribbles_attempted for p in player_profiles)
        drib_won = sum(p.stats.dribbles_won for p in player_profiles)
        drib_acc = round((drib_won / drib_att * 100.0), 1) if drib_att > 0 else 0.0

        tackles_tot = sum(p.stats.tackles_total for p in player_profiles)
        tackles_won = sum(p.stats.tackles_won for p in player_profiles)
        tackle_pct = round((tackles_won / tackles_tot * 100.0), 1) if tackles_tot > 0 else 0.0
        interceptions = sum(p.stats.interceptions for p in player_profiles)
        clearances = sum(p.stats.clearances for p in player_profiles)

        # Goalkeepers clean sheets & saves
        clean_sheets = sum(p.stats.clean_sheets for p in player_profiles if p.bio.position_name == "Goalkeeper")
        saves = sum(p.stats.saves_total for p in player_profiles if p.bio.position_name == "Goalkeeper")
        goals_against = club.goals_against
        ga_pg = round(goals_against / matches, 2) if matches > 0 else 0.0

        duels_won = sum(p.stats.duels_won for p in player_profiles)
        duels_lost = sum(p.stats.duels_lost for p in player_profiles)
        tot_duels = duels_won + duels_lost
        duel_pct = round((duels_won / tot_duels * 100.0), 1) if tot_duels > 0 else 0.0

        aerial_won = sum(p.stats.aerial_won for p in player_profiles)
        aerial_lost = sum(p.stats.aerial_lost for p in player_profiles)
        tot_aerial = aerial_won + aerial_lost
        aerial_pct = round((aerial_won / tot_aerial * 100.0), 1) if tot_aerial > 0 else 0.0

        fouls = sum(p.stats.fouls_conceded for p in player_profiles)
        yellows = sum(p.stats.yellow_cards for p in player_profiles)
        reds = sum(p.stats.red_cards for p in player_profiles)

        return ClubStats(
            squad_size=squad_size,
            matches_played=matches,
            total_minutes=total_mins,
            goals=goals,
            goals_per_game=goals_pg,
            shots=shots,
            shots_on_target=shots_ot,
            shot_accuracy_pct=round(shot_acc, 1),
            shots_per_game=shots_pg,
            conversion_rate_pct=conv_rate,
            passes_total=passes_tot,
            passes_accurate=passes_acc,
            pass_accuracy_pct=pass_acc,
            passes_per_game=passes_pg,
            assists=assists,
            key_passes=key_passes,
            crosses=crosses,
            dribbles_attempted=drib_att,
            dribbles_won=drib_won,
            dribble_accuracy_pct=drib_acc,
            tackles_total=tackles_tot,
            tackles_won=tackles_won,
            tackle_pct=tackle_pct,
            interceptions=interceptions,
            clearances=clearances,
            clean_sheets=clean_sheets,
            saves=saves,
            goals_conceded=goals_against,
            goals_conceded_per_game=ga_pg,
            duels_won=duels_won,
            duels_lost=duels_lost,
            duel_win_pct=duel_pct,
            aerial_won=aerial_won,
            aerial_lost=aerial_lost,
            aerial_win_pct=aerial_pct,
            fouls_conceded=fouls,
            yellow_cards=yellows,
            red_cards=reds,
        )

    @classmethod
    def calculate_scores(cls, stats: ClubStats, player_profiles: List[PlayerProfile]) -> ClubScores:
        """
        Calculates 0-99 card ratings (ATT, MID, DEF, OVR) and 0-100 tactical pillars.
        """
        # Separate players by position
        forwards = [p for p in player_profiles if p.bio.position_name == "Forward"]
        midfielders = [p for p in player_profiles if p.bio.position_name == "Midfielder"]
        defenders = [p for p in player_profiles if p.bio.position_name == "Defender"]
        keepers = [p for p in player_profiles if p.bio.position_name == "Goalkeeper"]

        # Sort each unit by overall_rating descending
        forwards.sort(key=lambda p: p.scores.overall_rating, reverse=True)
        midfielders.sort(key=lambda p: p.scores.overall_rating, reverse=True)
        defenders.sort(key=lambda p: p.scores.overall_rating, reverse=True)
        keepers.sort(key=lambda p: p.scores.overall_rating, reverse=True)

        # Average top players per position
        fwd_rating = sum(p.scores.overall_rating for p in forwards[:3]) / max(1, len(forwards[:3])) if forwards else 65.0
        mid_rating = sum(p.scores.overall_rating for p in midfielders[:4]) / max(1, len(midfielders[:4])) if midfielders else 65.0
        def_rating_unit = sum(p.scores.overall_rating for p in defenders[:4]) / max(1, len(defenders[:4])) if defenders else 65.0
        gk_rating = keepers[0].scores.overall_rating if keepers else 70.0

        # --- 1. ATT RATING (0-99) ---
        goals_factor = min(99.0, 60.0 + stats.goals_per_game * 11.0)
        shot_factor = min(95.0, max(55.0, stats.shot_accuracy_pct * 1.5))
        stat_att = (goals_factor * 0.7) + (shot_factor * 0.3)
        att = cls._clamp((fwd_rating * 0.45) + (stat_att * 0.55), low=55, high=97)

        # --- 2. MID RATING (0-99) ---
        pass_acc_factor = min(98.0, max(50.0, 50.0 + (stats.pass_accuracy_pct - 70.0) * 2.2))
        chances_factor = min(95.0, max(55.0, 60.0 + (stats.key_passes / max(1, stats.matches_played)) * 4.0))
        stat_mid = (pass_acc_factor * 0.6) + (chances_factor * 0.4)
        mid = cls._clamp((mid_rating * 0.45) + (stat_mid * 0.55), low=55, high=96)

        # --- 3. DEF RATING (0-99) ---
        ga_factor = min(96.0, max(52.0, 94.0 - (stats.goals_conceded_per_game * 14.0)))
        clean_sheet_bonus = min(6.0, stats.clean_sheets * 2.0)
        tackle_factor = min(92.0, max(55.0, stats.tackle_pct * 1.2))
        stat_def = ga_factor + clean_sheet_bonus * 0.5 + (tackle_factor - 70.0) * 0.1
        blended_def_unit = (def_rating_unit * 0.7) + (gk_rating * 0.3)
        defense = cls._clamp((blended_def_unit * 0.45) + (stat_def * 0.55), low=55, high=96)

        # --- 4. OVERALL RATING (0-99) ---
        overall = int(round((att * 0.35) + (mid * 0.35) + (defense * 0.30)))

        # --- 5. TACTICAL RADAR PILLARS (0-100) ---
        p_acc = min(99.0, max(45.0, stats.pass_accuracy_pct * 1.1))
        p_vol = min(98.0, max(40.0, 45.0 + (stats.passes_per_game - 250.0) * 0.15))
        possession = cls._clamp((p_acc * 0.6) + (p_vol * 0.4), low=40, high=99)

        attack_potency = cls._clamp((att * 0.9) + (stats.conversion_rate_pct * 0.6), low=40, high=99)
        def_solidity = cls._clamp(defense, low=40, high=99)

        tackles_pg = stats.tackles_won / max(1, stats.matches_played)
        press_val = min(98.0, max(45.0, 50.0 + (tackles_pg * 3.5) + (stats.interceptions / max(1, stats.matches_played) * 2.0)))
        pressing = cls._clamp(press_val, low=40, high=98)

        phys_val = min(98.0, max(45.0, (stats.duel_win_pct * 0.5) + (stats.aerial_win_pct * 0.5) + 5.0))
        physical = cls._clamp(phys_val, low=40, high=98)

        return ClubScores(
            att_rating=att,
            mid_rating=mid,
            def_rating=defense,
            overall_rating=overall,
            possession_control=possession,
            attacking_potency=attack_potency,
            defensive_solidity=def_solidity,
            pressing_workrate=pressing,
            physical_dominance=physical,
        )

    @classmethod
    def determine_archetype(cls, scores: ClubScores, stats: ClubStats) -> Tuple[str, Optional[str]]:
        """Determines the primary and secondary tactical playstyle archetype."""
        p = scores.possession_control
        a = scores.attacking_potency
        d = scores.defensive_solidity
        pr = scores.pressing_workrate
        ph = scores.physical_dominance

        if p >= 85 and a >= 85:
            primary = "High-Press Possession Dominator"
            secondary = "Total Football Attacking System"
        elif a >= 84 and p < 75:
            primary = "Vertical Counter-Attacking Force"
            secondary = "Rapid Transition Specialists"
        elif d >= 84 and a < 75:
            primary = "Defensive Fortress & Low Block"
            secondary = "Resilient Defensive Unit"
        elif pr >= 82 and ph >= 78:
            primary = "High-Intensity Pressing Engine"
            secondary = "Aggressive Midfield Stiflers"
        elif ph >= 82 and stats.crosses >= 50:
            primary = "Direct Aerial & Cross Heavyweight"
            secondary = "Physical Box Presence"
        elif p >= 80:
            primary = "Technical Ball-Circulation Unit"
            secondary = "Control-Oriented Possession"
        elif a >= 78:
            primary = "Dynamic Attacking Unit"
            secondary = "Multi-Threat Direct Offense"
        else:
            primary = "Balanced Pragmatic Unit"
            secondary = "Organized Tactical Framework"

        return primary, secondary

    @classmethod
    def generate_scout_report(cls, club: Club, stats: ClubStats, scores: ClubScores) -> Tuple[List[str], List[str]]:
        """Generates automated strengths and areas of caution."""
        strengths = []
        weaknesses = []

        # Strengths
        if stats.goals_per_game >= 2.0:
            strengths.append(f"Lethal attacking potency: averaging {stats.goals_per_game} goals per game ({stats.goals} goals total).")
        elif stats.goals >= 5:
            strengths.append(f"Proven scoring productivity with {stats.goals} goals scored.")

        if stats.pass_accuracy_pct >= 85.0:
            strengths.append(f"Elite ball circulation: {stats.pass_accuracy_pct}% pass completion rate ({stats.passes_accurate}/{stats.passes_total}).")

        if stats.goals_conceded_per_game <= 0.75:
            strengths.append(f"Stifling defensive organization: conceding only {stats.goals_conceded_per_game} goals per match.")

        if stats.clean_sheets >= 2:
            strengths.append(f"Exceptional defensive security with {stats.clean_sheets} clean sheets logged.")

        if stats.shot_accuracy_pct >= 50.0:
            strengths.append(f"Sharp shooting calibration with {stats.shot_accuracy_pct}% of attempts testing the goalkeeper.")

        if stats.tackle_pct >= 65.0:
            strengths.append(f"Tenacious ball recovery: winning {stats.tackle_pct}% of contested tackles.")

        if stats.aerial_win_pct >= 55.0:
            strengths.append(f"Dominant aerial presence winning {stats.aerial_win_pct}% of aerial duels.")

        if not strengths:
            strengths.append(f"Solid tactical cohesion and squad depth across all match phases.")

        # Weaknesses / Caution
        if stats.goals_conceded_per_game >= 1.75:
            weaknesses.append(f"High defensive vulnerability: conceding {stats.goals_conceded_per_game} goals per game.")

        if stats.conversion_rate_pct < 10.0 and stats.shots > 20:
            weaknesses.append(f"Finishing inefficiency: converting only {stats.conversion_rate_pct}% of {stats.shots} total shots.")

        if stats.pass_accuracy_pct < 75.0:
            weaknesses.append(f"Susceptible to ball turnover under pressure ({stats.pass_accuracy_pct}% pass accuracy).")

        if stats.fouls_conceded >= 55:
            weaknesses.append(f"High foul accumulation: conceded {stats.fouls_conceded} fouls ({stats.yellow_cards} bookings).")

        if stats.clean_sheets == 0 and stats.matches_played >= 3:
            weaknesses.append(f"Inability to preserve a clean sheet across {stats.matches_played} matches.")

        if not weaknesses:
            weaknesses.append(f"Maintaining consistency against high-pressing, elite opposition.")

        return strengths[:4], weaknesses[:2]

    @classmethod
    def identify_leaders(cls, player_profiles: List[PlayerProfile]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Identifies top scorer, playmaker, defensive leader, and star player."""
        if not player_profiles:
            return {"top_scorer": None, "top_assister": None, "defensive_leader": None, "star_player": None}

        def _fmt(p: PlayerProfile, stat_label: str, stat_val: Any) -> Dict[str, Any]:
            return {
                "name": p.bio.nickname or p.bio.name,
                "slug": p.bio.slug,
                "position": p.bio.position_name,
                "shirt_number": p.bio.shirt_number,
                "photo_url": p.bio.photo_url,
                "overall_rating": p.scores.overall_rating,
                "stat_label": stat_label,
                "stat_val": stat_val,
            }

        # Top Scorer
        by_goals = sorted(player_profiles, key=lambda p: (p.stats.goals, p.stats.shots_on_target), reverse=True)
        top_scorer = _fmt(by_goals[0], "Goals", by_goals[0].stats.goals) if by_goals else None

        # Top Assister / Chance Creator
        by_assists = sorted(player_profiles, key=lambda p: (p.stats.assists, p.stats.key_passes), reverse=True)
        top_assister = _fmt(by_assists[0], "Assists (KP)", f"{by_assists[0].stats.assists} ({by_assists[0].stats.key_passes})") if by_assists else None

        # Defensive Leader
        by_defense = sorted(player_profiles, key=lambda p: (p.stats.tackles_won + p.stats.interceptions), reverse=True)
        defensive_leader = _fmt(by_defense[0], "Tackles + Int", by_defense[0].stats.tackles_won + by_defense[0].stats.interceptions) if by_defense else None

        # Star Player (highest OVR)
        by_ovr = sorted(player_profiles, key=lambda p: p.scores.overall_rating, reverse=True)
        star_player = _fmt(by_ovr[0], "OVR Rating", by_ovr[0].scores.overall_rating) if by_ovr else None

        return {
            "top_scorer": top_scorer,
            "top_assister": top_assister,
            "defensive_leader": defensive_leader,
            "star_player": star_player,
        }

    @classmethod
    def profile_club(cls, club: Club, player_profiles: List[PlayerProfile]) -> ClubProfile:
        """Constructs a complete ClubProfile object."""
        stats = cls.aggregate_squad_stats(club, player_profiles)
        scores = cls.calculate_scores(stats, player_profiles)
        primary_arch, sec_arch = cls.determine_archetype(scores, stats)
        strengths, weaknesses = cls.generate_scout_report(club, stats, scores)
        leaders = cls.identify_leaders(player_profiles)

        roster_summary = {
            "goalkeepers": len([p for p in player_profiles if p.bio.position_name == "Goalkeeper"]),
            "defenders": len([p for p in player_profiles if p.bio.position_name == "Defender"]),
            "midfielders": len([p for p in player_profiles if p.bio.position_name == "Midfielder"]),
            "forwards": len([p for p in player_profiles if p.bio.position_name == "Forward"]),
            "total": len(player_profiles),
        }

        roster = [
            {
                "id": p.bio.id,
                "name": p.bio.nickname or p.bio.name,
                "slug": p.bio.slug,
                "position": p.bio.position_name,
                "shirt_number": p.bio.shirt_number,
                "photo_url": p.bio.photo_url,
                "overall_rating": p.scores.overall_rating,
                "archetype": p.archetype,
                "card_stats": {
                    "pac": p.scores.pace,
                    "sho": p.scores.shooting,
                    "pas": p.scores.passing,
                    "dri": p.scores.dribbling,
                    "def": p.scores.defending,
                    "phy": p.scores.physical,
                } if not p.scores.is_goalkeeper else {
                    "div": p.scores.gk_diving,
                    "han": p.scores.gk_handling,
                    "kic": p.scores.gk_kicking,
                    "ref": p.scores.gk_reflexes,
                    "spd": p.scores.gk_speed,
                    "pos": p.scores.gk_positioning,
                }
            }
            for p in sorted(player_profiles, key=lambda x: x.scores.overall_rating, reverse=True)
        ]

        return ClubProfile(
            club=club,
            stats=stats,
            scores=scores,
            archetype=primary_arch,
            secondary_style=sec_arch,
            strengths=strengths,
            weaknesses=weaknesses,
            top_scorer=leaders["top_scorer"],
            top_assister=leaders["top_assister"],
            defensive_leader=leaders["defensive_leader"],
            star_player=leaders["star_player"],
            squad_breakdown=roster_summary,
            roster=roster,
        )
