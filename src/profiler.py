"""
Player Profiling and Intelligence Engine.
Calculates tactical archetypes, 0-100 attribute pillars, per-90 metrics,
percentile ranks, and scout notes.
"""
from typing import Dict, Any, List, Tuple, Optional
from .models import PlayerBio, PlayerStats, ProfileScores, PlayerProfile


class Profiler:
    @staticmethod
    def calculate_per90(stats: PlayerStats) -> Dict[str, float]:
        mins = max(1.0, float(stats.minutes_played))
        factor = 90.0 / mins

        return {
            "goals_per90": round(stats.goals * factor, 2),
            "assists_per90": round(stats.assists * factor, 2),
            "shots_per90": round(stats.shots * factor, 2),
            "shots_on_target_per90": round(stats.shots_on_target * factor, 2),
            "key_passes_per90": round(stats.key_passes * factor, 2),
            "passes_per90": round(stats.passes_total * factor, 2),
            "tackles_per90": round(stats.tackles_won * factor, 2),
            "interceptions_per90": round(stats.interceptions * factor, 2),
            "clearances_per90": round(stats.clearances * factor, 2),
            "dribbles_per90": round(stats.dribbles_won * factor, 2),
            "fouls_conceded_per90": round(stats.fouls_conceded * factor, 2),
            "fouls_drawn_per90": round(stats.fouls_drawn * factor, 2),
            "duels_won_per90": round(stats.duels_won * factor, 2),
            "aerial_won_per90": round(stats.aerial_won * factor, 2),
            "saves_per90": round(stats.saves_total * factor, 2),
        }

    @staticmethod
    def calculate_scores(bio: PlayerBio, stats: PlayerStats, rankings: Dict[str, int]) -> ProfileScores:
        pos = (bio.position_name or "").lower()
        mins = stats.minutes_played

        # If player hasn't played, assign baseline score
        if mins == 0:
            is_gk = "goalkeeper" in pos
            return ProfileScores(
                overall_rating=65,
                pace=65, shooting=50, passing=55, dribbling=55, defending=50, physical=55,
                is_goalkeeper=is_gk,
                gk_diving=65 if is_gk else None, gk_handling=65 if is_gk else None,
                gk_kicking=65 if is_gk else None, gk_reflexes=65 if is_gk else None,
                attacking=50, playmaking=55, physical_duels=55, discipline_reliability=70
            )

        games = max(1, stats.games_played)
        mins_f = max(1.0, float(mins))

        if "goalkeeper" in pos:
            saves = stats.saves_total
            saves_ibox = stats.saves_ibox
            clean_sheets = stats.clean_sheets
            goals_conceded = stats.goals_conceded
            passes_acc = stats.passes_accurate
            passes_tot = max(1, stats.passes_total)
            high_claims = stats.high_claims
            punches = stats.punches

            div = min(95, max(58, int(62 + min(22, saves * 1.4) + min(10, saves_ibox * 1.8))))
            han = min(94, max(58, int(62 + min(18, clean_sheets * 9.0) + min(12, high_claims * 4.0))))
            kic = min(92, max(55, int(60 + min(16, passes_acc * 0.22) + min(14, (passes_acc / passes_tot) * 16.0))))
            ref = min(96, max(58, int(64 + min(22, saves * 1.5) + min(10, saves_ibox * 1.8))))
            spd = min(85, max(50, int(52 + min(15, clean_sheets * 5.0) + min(10, punches * 3.0))))
            pos_stat = min(95, max(58, int(62 + min(18, clean_sheets * 8.0) + max(0, 12 - int((goals_conceded / games) * 4.0)))))

            ovr = int(div * 0.25 + ref * 0.25 + pos_stat * 0.20 + han * 0.15 + kic * 0.10 + spd * 0.05)
            ovr = min(94, max(66, ovr))

            return ProfileScores(
                overall_rating=ovr,
                is_goalkeeper=True,
                gk_diving=div,
                gk_handling=han,
                gk_kicking=kic,
                gk_reflexes=ref,
                gk_speed=spd,
                gk_positioning=pos_stat,
                pace=spd,
                shooting=40,
                passing=kic,
                dribbling=div,
                defending=ref,
                physical=han,
                attacking=45,
                playmaking=kic,
                discipline_reliability=80,
                physical_duels=han
            )

        # OUTFIELD PLAYERS
        # 1. SHOOTING (SHO)
        sho_base = 52.0
        sho_base += min(22.0, stats.goals * 4.5)
        sho_base += min(10.0, stats.shots_on_target * 1.2)
        sho_acc = (stats.shots_on_target / max(1, stats.shots)) if stats.shots > 0 else 0.0
        sho_base += (sho_acc * 8.0)
        if rankings.get("total_goals_ranking", 999) <= 5:
            sho_base += 8.0
        elif rankings.get("total_goals_ranking", 999) <= 15:
            sho_base += 4.0
        if "defender" in pos and stats.goals == 0 and stats.shots <= 1:
            sho = min(62, max(38, int(sho_base - 8.0)))
        else:
            sho = min(95, max(45, int(sho_base)))

        # 2. PASSING (PAS)
        pas_base = 58.0
        pass_acc_rate = (stats.passes_accurate / max(1, stats.passes_total)) if stats.passes_total > 0 else 0.75
        pas_base += (pass_acc_rate - 0.70) * 18.0
        pas_base += min(8.0, (stats.passes_accurate / mins_f) * 90 * 0.2)
        pas_base += min(16.0, stats.key_passes * 1.8)
        pas_base += min(12.0, stats.assists * 4.0)
        pas_base += min(6.0, stats.crosses * 0.8)
        if rankings.get("total_assists_ranking", 999) <= 5:
            pas_base += 7.0
        elif rankings.get("total_assists_ranking", 999) <= 15:
            pas_base += 4.0
        pas = min(95, max(50, int(pas_base)))

        # 3. DRIBBLING (DRI)
        dri_base = 58.0
        dri_base += min(18.0, stats.dribbles_won * 1.5)
        drib_acc = (stats.dribbles_won / max(1, stats.dribbles_attempted)) if stats.dribbles_attempted > 0 else 0.5
        dri_base += (drib_acc * 8.0)
        dri_base += min(8.0, (stats.touches_in_box / mins_f) * 90 * 1.5)
        dri_base += min(5.0, stats.fouls_drawn * 1.0)
        if "defender" in pos:
            dri = min(78, max(50, int(dri_base - 5.0)))
        else:
            dri = min(95, max(55, int(dri_base)))

        # 4. PACE (PAC)
        pac_base = 68.0
        pac_base += min(14.0, (stats.dribbles_attempted / mins_f) * 90 * 2.8)
        pac_base += min(8.0, stats.dribbles_won * 1.0)
        pac_base += min(6.0, (stats.fouls_drawn / mins_f) * 90 * 2.0)
        if "forward" in pos:
            pac_base += 6.0
        elif "defender" in pos:
            pac_base += 2.0 if stats.crosses >= 2 else -4.0
        pac = min(96, max(55, int(pac_base)))

        # 5. DEFENDING (DEF)
        def_base = 40.0
        def_base += min(18.0, stats.tackles_won * 4.0)
        def_base += min(14.0, stats.interceptions * 4.5)
        def_base += min(12.0, stats.clearances * 1.8)
        tackle_pct = stats.tackle_pct if stats.tackle_pct > 0 else (stats.tackles_won / max(1, stats.tackles_total) * 100)
        def_base += min(8.0, (tackle_pct / 100.0) * 8.0)
        if "defender" in pos:
            def_base += 15.0
        elif "midfield" in pos and (stats.tackles_won >= 2 or stats.interceptions >= 2):
            def_base += 8.0
        if "forward" in pos:
            deff = min(55, max(32, int(def_base * 0.75)))
        else:
            deff = min(93, max(45, int(def_base)))

        # 6. PHYSICAL (PHY)
        phy_base = 58.0
        phy_base += min(14.0, stats.duels_won * 1.2)
        duel_win_rate = (stats.duels_won / max(1, stats.duels_won + stats.duels_lost)) if (stats.duels_won + stats.duels_lost) > 0 else 0.5
        phy_base += (duel_win_rate * 8.0)
        phy_base += min(10.0, stats.aerial_won * 3.0)
        phy_base += min(6.0, (mins / 360.0) * 6.0)
        phy = min(92, max(52, int(phy_base)))

        # Discipline (0 - 100)
        disc_raw = 85.0 - (stats.fouls_conceded * 2.0) - (stats.yellow_cards * 8.0) - (stats.red_cards * 25.0)
        disc_raw += min(15.0, (stats.starts * 3.0) + (mins / 40.0))
        discipline = min(99, max(35, int(disc_raw)))

        # OVERALL (OVR)
        if "forward" in pos:
            ovr = int(sho * 0.35 + pac * 0.25 + dri * 0.20 + pas * 0.12 + phy * 0.05 + deff * 0.03)
        elif "midfield" in pos:
            ovr = int(pas * 0.35 + dri * 0.22 + deff * 0.18 + phy * 0.12 + sho * 0.08 + pac * 0.05)
        elif "defender" in pos:
            ovr = int(deff * 0.42 + phy * 0.28 + pas * 0.15 + pac * 0.10 + dri * 0.05)
        else:
            ovr = int((pac + sho + pas + dri + deff + phy) / 6)

        ovr = min(95, max(60, ovr))

        return ProfileScores(
            overall_rating=ovr,
            pace=pac,
            shooting=sho,
            passing=pas,
            dribbling=dri,
            defending=deff,
            physical=phy,
            is_goalkeeper=False,
            attacking=sho,
            playmaking=pas,
            discipline_reliability=discipline,
            physical_duels=phy
        )

    @staticmethod
    def determine_archetype(bio: PlayerBio, stats: PlayerStats, scores: ProfileScores) -> Tuple[str, Optional[str]]:
        pos = (bio.position_name or "").lower()

        if "goalkeeper" in pos:
            if stats.high_claims >= 2 or stats.punches >= 1:
                return "Box Commander / Sweeper Keeper", "Commanding Goalkeeper"
            return "Shot-Stopper Goalkeeper", "Reflex Goalkeeper"

        if "forward" in pos:
            if stats.goals >= 3 and (stats.shots_ibox / max(1, stats.shots)) >= 0.65:
                return "Clinical Finisher / Poacher", "Penalty Box Assassin"
            if stats.dribbles_won >= 3 or stats.crosses >= 3:
                return "Inverted Winger / Dynamic Attacker", "1v1 Dribbler"
            if stats.key_passes >= 3 or stats.assists >= 1:
                return "Creative Forward / False 9", "Playmaking Forward"
            if stats.aerial_won >= 3:
                return "Target Man / Aerial Focal Point", "Physical Forward"
            if stats.shots >= 5:
                return "High-Volume Striker", "Inside Forward"
            return "Pressing Forward", "Versatile Attacker"

        if "midfield" in pos:
            if stats.key_passes >= 3 or stats.assists >= 2:
                return "Creative Playmaker / Maestro", "Chance Creator"
            if stats.tackles_won >= 3 or stats.interceptions >= 2:
                return "Ball-Winning Midfielder / Anchor", "Defensive Shield"
            if stats.forward_passes >= 30 and stats.passes_accurate >= 50:
                return "Deep-Lying Playmaker / Regista", "Tempo Controller"
            if stats.goals >= 1 and stats.tackles_won >= 1:
                return "Box-to-Box Engine", "Dynamic All-Rounder"
            if stats.dribbles_won >= 2:
                return "Progressive Ball-Carrier", "Attacking Midfielder"
            return "Central Controller", "Link-Up Midfielder"

        if "defender" in pos:
            if stats.crosses >= 3 or stats.dribbles_won >= 2:
                return "Attacking Wing-Back", "Wide Creator"
            if stats.passes_accurate >= 40 and stats.forward_passes >= 20:
                return "Ball-Playing Centre-Back", "Modern Build-Up Defender"
            if stats.aerial_won >= 4 or stats.clearances >= 8:
                return "Dominant Aerial Stopper", "Defensive Wall"
            if stats.tackles_won >= 3 or stats.interceptions >= 2:
                return "Aggressive Ball-Winner", "Interception Specialist"
            return "Commanding Centre-Back", "Reliable Defender"

        return "Versatile Utility Player", None

    @staticmethod
    def generate_scout_report(bio: PlayerBio, stats: PlayerStats, per90: Dict[str, float],
                              rankings: Dict[str, int], scores: ProfileScores) -> Tuple[List[str], List[str]]:
        strengths = []
        weaknesses = []

        # Strengths
        if stats.goals >= 3:
            strengths.append(f"Exceptional goal efficiency: {stats.goals} goals in {stats.minutes_played} minutes ({per90.get('goals_per90', 0)} per 90)")
        elif stats.goals > 0:
            strengths.append(f"Reliable goal contribution ({stats.goals} goals scored)")

        if stats.shots_on_target > 0:
            acc = round((stats.shots_on_target / max(1, stats.shots)) * 100, 1)
            if acc >= 50:
                strengths.append(f"High shot accuracy: {acc}% of shots hitting target ({stats.shots_on_target}/{stats.shots})")

        if stats.assists >= 1:
            strengths.append(f"Direct playmaking value: {stats.assists} official assists registered")

        if stats.key_passes >= 3:
            strengths.append(f"High-volume chance creator with {stats.key_passes} key passes delivered")

        if stats.tackles_won >= 3:
            strengths.append(f"Tenacious tackler: won {stats.tackles_won} tackles ({per90.get('tackles_per90', 0)} per 90)")

        if stats.interceptions >= 2:
            strengths.append(f"Anticipation & positional awareness: {stats.interceptions} interceptions")

        if stats.aerial_won >= 3:
            strengths.append(f"Dominant in aerial duels: won {stats.aerial_won} aerial contests")

        if stats.dribbles_won >= 2:
            strengths.append(f"Takes on defenders effectively: {stats.dribbles_won} successful dribbles completed")

        if stats.clean_sheets >= 1:
            strengths.append(f"Proven clean sheet security ({stats.clean_sheets} clean sheets)")

        if stats.saves_total >= 3:
            strengths.append(f"Reliable shot-stopper with {stats.saves_total} recorded saves")

        if not strengths:
            strengths.append("Consistent team tactical contributor with dependable positioning")
            strengths.append("Disciplined player executing coaching instructions")

        # Weaknesses / Tactical Risks
        if stats.yellow_cards >= 1 or stats.red_cards > 0:
            weaknesses.append(f"Disciplinary caution risk: {stats.yellow_cards} yellow cards, {stats.red_cards} red cards")

        if stats.fouls_conceded >= 3:
            weaknesses.append(f"Prone to conceding fouls: {stats.fouls_conceded} fouls committed ({per90.get('fouls_conceded_per90', 0)} per 90)")

        if stats.shots >= 6 and stats.goals == 0:
            weaknesses.append(f"Finishing conversion deficit: 0 goals from {stats.shots} total attempts")

        if stats.duels_lost > stats.duels_won and (stats.duels_lost + stats.duels_won) >= 4:
            weaknesses.append(f"Duel vulnerability: lost {stats.duels_lost} duels compared to {stats.duels_won} won")

        if stats.minutes_played < 90 and stats.games_played >= 2:
            weaknesses.append("Rotation / impact substitute role; limited sustained match conditioning")

        if not weaknesses:
            weaknesses.append("Minor sample size in advanced pressure situations")

        return strengths[:4], weaknesses[:3]

    @classmethod
    def build_profile(cls, bio: PlayerBio, stats: PlayerStats, rankings: Dict[str, int]) -> PlayerProfile:
        per90 = cls.calculate_per90(stats)
        scores = cls.calculate_scores(bio, stats, rankings)
        primary_arch, secondary_arch = cls.determine_archetype(bio, stats, scores)
        strengths, weaknesses = cls.generate_scout_report(bio, stats, per90, rankings, scores)

        # Approximate league percentiles from official ranking
        # Total league active players is ~520
        total_players = 520.0
        percentiles = {}
        for metric, rank in rankings.items():
            if rank and rank > 0:
                pct = max(1, min(99, int((1.0 - (rank / total_players)) * 100)))
                clean_key = metric.replace("_ranking", "").replace("total_", "")
                percentiles[clean_key] = pct

        return PlayerProfile(
            bio=bio,
            stats=stats,
            rankings=rankings,
            scores=scores,
            archetype=primary_arch,
            secondary_archetype=secondary_arch,
            strengths=strengths,
            weaknesses=weaknesses,
            per90=per90,
            percentiles=percentiles
        )
