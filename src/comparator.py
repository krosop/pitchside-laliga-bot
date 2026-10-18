"""
Head-to-Head Player Comparison Engine.
Compares any two players across tactical dimensions, per-90 metrics, and radar scores.
"""
from typing import Dict, Any, Optional
from .database import Database


class PlayerComparator:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def compare_players(self, slug1: str, slug2: str) -> Optional[Dict[str, Any]]:
        p1 = self.db.get_player_by_slug(slug1)
        p2 = self.db.get_player_by_slug(slug2)

        if not p1 or not p2:
            return None

        bio1 = p1.get("bio", {})
        bio2 = p2.get("bio", {})
        scores1 = p1.get("scores", {})
        scores2 = p2.get("scores", {})
        stats1 = p1.get("stats", {})
        stats2 = p2.get("stats", {})
        per90_1 = p1.get("per90", {})
        per90_2 = p2.get("per90", {})

        # Calculate metric diffs and advantages
        metric_comparisons = []
        metrics_to_compare = [
            ("Minutes Played", "minutes_played", "raw"),
            ("Goals Scored", "goals", "raw"),
            ("Assists", "assists", "raw"),
            ("Shots on Target", "shots_on_target", "raw"),
            ("Key Passes (Chances Created)", "key_passes", "raw"),
            ("Passes Total", "passes_total", "raw"),
            ("Successful Dribbles", "dribbles_won", "raw"),
            ("Tackles Won", "tackles_won", "raw"),
            ("Interceptions", "interceptions", "raw"),
            ("Duels Won", "duels_won", "raw"),
            ("Aerial Duels Won", "aerial_won", "raw"),
            ("Fouls Conceded", "fouls_conceded", "inverse"),  # less is better
            ("Yellow Cards", "yellow_cards", "inverse"),     # less is better
        ]

        for label, key, comp_type in metrics_to_compare:
            v1 = stats1.get(key, 0)
            v2 = stats2.get(key, 0)
            if comp_type == "inverse":
                advantage = "p1" if v1 < v2 else ("p2" if v2 < v1 else "tie")
            else:
                advantage = "p1" if v1 > v2 else ("p2" if v2 > v1 else "tie")

            p90_1 = per90_1.get(f"{key}_per90")
            p90_2 = per90_2.get(f"{key}_per90")

            metric_comparisons.append({
                "label": label,
                "key": key,
                "player1_value": v1,
                "player2_value": v2,
                "player1_per90": p90_1,
                "player2_per90": p90_2,
                "advantage": advantage
            })

        # Card rating attributes comparison (PAC, SHO, PAS, DRI, DEF, PHY or GK attributes)
        if scores1.get("is_goalkeeper") and scores2.get("is_goalkeeper"):
            card_attrs = [
                ("DIV", "Diving", "gk_diving"),
                ("HAN", "Handling", "gk_handling"),
                ("KIC", "Kicking", "gk_kicking"),
                ("REF", "Reflexes", "gk_reflexes"),
                ("SPD", "Speed", "gk_speed"),
                ("POS", "Positioning", "gk_positioning"),
            ]
        else:
            card_attrs = [
                ("PAC", "Pace", "pace"),
                ("SHO", "Shooting", "shooting"),
                ("PAS", "Passing", "passing"),
                ("DRI", "Dribbling", "dribbling"),
                ("DEF", "Defending", "defending"),
                ("PHY", "Physical", "physical"),
            ]
        card_comparisons = []
        for abbr, name, key in card_attrs:
            v1 = scores1.get(key, 50) or 50
            v2 = scores2.get(key, 50) or 50
            card_comparisons.append({
                "abbr": abbr,
                "name": name,
                "player1_score": v1,
                "player2_score": v2,
                "advantage": "p1" if v1 > v2 else ("p2" if v2 > v1 else "tie"),
                "diff": abs(v1 - v2)
            })

        # Pillar comparison
        pillars = ["overall_rating", "attacking", "playmaking", "defending", "physical_duels", "discipline_reliability"]
        pillar_comparisons = []
        for p in pillars:
            v1 = scores1.get(p, 50)
            v2 = scores2.get(p, 50)
            pillar_comparisons.append({
                "pillar": p.replace("_", " ").title(),
                "player1_score": v1,
                "player2_score": v2,
                "advantage": "p1" if v1 > v2 else ("p2" if v2 > v1 else "tie"),
                "diff": abs(v1 - v2)
            })

        # Generate comparative scout verdict
        verdict = self._generate_verdict(bio1, bio2, scores1, scores2, stats1, stats2)

        return {
            "player1": {
                "bio": bio1,
                "scores": scores1,
                "archetype": p1.get("archetype"),
                "strengths": p1.get("strengths", []),
            },
            "player2": {
                "bio": bio2,
                "scores": scores2,
                "archetype": p2.get("archetype"),
                "strengths": p2.get("strengths", []),
            },
            "cards": card_comparisons,
            "pillars": pillar_comparisons,
            "metrics": metric_comparisons,
            "verdict": verdict
        }

    def _generate_verdict(self, bio1: dict, bio2: dict, s1: dict, s2: dict, st1: dict, st2: dict) -> str:
        name1 = bio1.get("nickname") or bio1.get("name", "Player 1")
        name2 = bio2.get("nickname") or bio2.get("name", "Player 2")

        parts = []
        # Attacking comparison
        att_diff = s1.get("attacking", 50) - s2.get("attacking", 50)
        if att_diff >= 8:
            parts.append(f"{name1} possesses a clear offensive advantage with higher finishing and box threat (+{att_diff} Attack rating).")
        elif att_diff <= -8:
            parts.append(f"{name2} holds the edge in offensive firepower and goal expectancy (+{abs(att_diff)} Attack rating).")

        # Playmaking comparison
        play_diff = s1.get("playmaking", 50) - s2.get("playmaking", 50)
        if play_diff >= 8:
            parts.append(f"{name1} provides superior distribution and key pass creation.")
        elif play_diff <= -8:
            parts.append(f"{name2} dictates tempo with higher volume passing and chance creation.")

        # Defending comparison
        def_diff = s1.get("defending", 50) - s2.get("defending", 50)
        if def_diff >= 8:
            parts.append(f"Defensively, {name1} commits more heavily to challenges and ball recoveries.")
        elif def_diff <= -8:
            parts.append(f"Defensively, {name2} demonstrates higher tackle effectiveness and disruption.")

        if not parts:
            parts.append(f"Both {name1} and {name2} exhibit closely matched tactical output across primary metrics.")

        return " ".join(parts)

    def compare_clubs(self, club1_id: str, club2_id: str) -> Optional[Dict[str, Any]]:
        """Compares two clubs side-by-side across ratings, tactical pillars, and squad metrics."""
        c1 = self.db.get_club_profile(club1_id)
        c2 = self.db.get_club_profile(club2_id)

        if not c1 or not c2:
            return None

        club_meta1 = c1.get("club", {})
        club_meta2 = c2.get("club", {})
        scores1 = c1.get("scores", {})
        scores2 = c2.get("scores", {})
        stats1 = c1.get("stats", {})
        stats2 = c2.get("stats", {})

        name1 = club_meta1.get("nickname") or club_meta1.get("name", "Club 1")
        name2 = club_meta2.get("nickname") or club_meta2.get("name", "Club 2")

        # 1. Card ratings comparison
        ratings_list = [
            ("OVR", "Overall Rating", "overall_rating"),
            ("ATT", "Attack", "att_rating"),
            ("MID", "Midfield", "mid_rating"),
            ("DEF", "Defense", "def_rating"),
        ]
        rating_comparisons = []
        for abbr, label, key in ratings_list:
            v1 = scores1.get(key, 50)
            v2 = scores2.get(key, 50)
            rating_comparisons.append({
                "abbr": abbr,
                "label": label,
                "club1_score": v1,
                "club2_score": v2,
                "advantage": "c1" if v1 > v2 else ("c2" if v2 > v1 else "tie"),
                "diff": abs(v1 - v2)
            })

        # 2. Tactical Pillars comparison
        pillars = [
            ("possession_control", "Possession & Control"),
            ("attacking_potency", "Attacking Potency"),
            ("defensive_solidity", "Defensive Solidity"),
            ("pressing_workrate", "Pressing & Workrate"),
            ("physical_dominance", "Physical Dominance"),
        ]
        pillar_comparisons = []
        for key, label in pillars:
            v1 = scores1.get(key, 50)
            v2 = scores2.get(key, 50)
            pillar_comparisons.append({
                "key": key,
                "label": label,
                "club1_score": v1,
                "club2_score": v2,
                "advantage": "c1" if v1 > v2 else ("c2" if v2 > v1 else "tie"),
                "diff": abs(v1 - v2)
            })

        # 3. Squad & League Metrics
        metrics_to_compare = [
            ("League Position", "position", "meta", "inverse"),
            ("League Points", "points", "meta", "raw"),
            ("Goal Difference", "goal_difference", "meta", "raw"),
            ("Goals Scored", "goals", "stat", "raw"),
            ("Goals Conceded", "goals_conceded", "stat", "inverse"),
            ("Shot Accuracy %", "shot_accuracy_pct", "stat", "raw"),
            ("Pass Accuracy %", "pass_accuracy_pct", "stat", "raw"),
            ("Passes Per Game", "passes_per_game", "stat", "raw"),
            ("Tackle Win %", "tackle_pct", "stat", "raw"),
            ("Clean Sheets", "clean_sheets", "stat", "raw"),
            ("Aerial Win %", "aerial_win_pct", "stat", "raw"),
        ]
        metric_comparisons = []
        for label, key, src, comp_type in metrics_to_compare:
            if src == "meta":
                v1 = club_meta1.get(key, 0)
                v2 = club_meta2.get(key, 0)
            else:
                v1 = stats1.get(key, 0)
                v2 = stats2.get(key, 0)

            if comp_type == "inverse":
                adv = "c1" if v1 < v2 else ("c2" if v2 < v1 else "tie")
            else:
                adv = "c1" if v1 > v2 else ("c2" if v2 > v1 else "tie")

            metric_comparisons.append({
                "label": label,
                "key": key,
                "club1_value": v1,
                "club2_value": v2,
                "advantage": adv
            })

        # 4. Tactical Matchup Verdict
        verdict_parts = []
        att_diff = scores1.get("att_rating", 50) - scores2.get("att_rating", 50)
        mid_diff = scores1.get("mid_rating", 50) - scores2.get("mid_rating", 50)
        def_diff = scores1.get("def_rating", 50) - scores2.get("def_rating", 50)

        if att_diff >= 4:
            verdict_parts.append(f"{name1} boasts superior offensive potency (+{att_diff} ATT).")
        elif att_diff <= -4:
            verdict_parts.append(f"{name2} poses a sharper attacking threat in the final third (+{abs(att_diff)} ATT).")

        if mid_diff >= 4:
            verdict_parts.append(f"{name1} is expected to dominate midfield circulation and transition tempo (+{mid_diff} MID).")
        elif mid_diff <= -4:
            verdict_parts.append(f"{name2} commands midfield territory and tempo control (+{abs(mid_diff)} MID).")

        if def_diff >= 4:
            verdict_parts.append(f"{name1} holds the defensive edge with stronger structure and lower concession rate.")
        elif def_diff <= -4:
            verdict_parts.append(f"{name2} presents greater defensive solidity and box protection.")

        if not verdict_parts:
            verdict_parts.append(f"A finely balanced tactical duel with both {name1} and {name2} operating at comparable tactical thresholds.")

        return {
            "club1": {
                "meta": club_meta1,
                "scores": scores1,
                "archetype": c1.get("archetype"),
                "strengths": c1.get("strengths", []),
                "top_scorer": c1.get("top_scorer"),
                "star_player": c1.get("star_player"),
            },
            "club2": {
                "meta": club_meta2,
                "scores": scores2,
                "archetype": c2.get("archetype"),
                "strengths": c2.get("strengths", []),
                "top_scorer": c2.get("top_scorer"),
                "star_player": c2.get("star_player"),
            },
            "ratings": rating_comparisons,
            "pillars": pillar_comparisons,
            "metrics": metric_comparisons,
            "verdict": " ".join(verdict_parts),
        }


# Alias for backward compatibility
Comparator = PlayerComparator

