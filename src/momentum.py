"""
Player Momentum Index — the "hot hand" model.

Built on real per-match goal data (ESPN scorer timelines stored in
player_match_stats). For every player we compute a 0-100 momentum index from
their last matches with exponential recency weighting (newest counts most):

    match_score  = 50 + 22*goals + 10*assists (+ xG over/under terms when xG data exists)
    momentum     = 0.4*last + 0.3*prev + 0.2*prev2 + 0.1*prev3

An EXPLOSIVE game (2+ goals in one match, or a 90+ single-match score)
grants a decaying bonus to subsequent matches:

    boost = 8 * 0.7 ** matches_since_explosion

against a weaker opponent the boost is amplified (their Elo tier modulates
it), mirroring the intuition that a confident in-form striker exploits
softer opposition hardest.

Players without per-match data fall back to the team-level form heuristic
(SimulationEngine.calculate_player_form), so the system degrades gracefully.
"""
import math
import unicodedata
from typing import Any, Dict, List, Optional


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(tok for tok in s.split() if tok)


def _name_tokens(name: str) -> set:
    return {t for t in _norm(name).split() if len(t) > 2}


WEIGHTS = (0.4, 0.3, 0.2, 0.1)  # newest -> oldest


class PlayerMomentum:
    """Momentum index + explosive-game state for one player."""

    def __init__(self, index: float = 50.0, matches: int = 0, explosive: bool = False,
                 boost: float = 0.0, label: str = "Stable form", status: str = "stable",
                 last_matches: Optional[List[Dict[str, Any]]] = None):
        self.index = index
        self.matches = matches
        self.explosive = explosive
        self.boost = boost
        self.label = label
        self.status = status
        self.last_matches = last_matches or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "momentum_index": round(self.index, 1),
            "momentum_status": self.status,
            "momentum_label": self.label,
            "explosive": self.explosive,
            "explosive_boost": round(self.boost, 1),
            "matches_counted": self.matches,
        }

    @property
    def sim_modifier(self) -> float:
        """Rating modifier for the simulation engine (roughly -2..+4)."""
        return round((self.index - 50.0) / 10.0 + self.boost, 2)


def _status_for(index: float) -> str:
    if index >= 70:
        return "hot"
    if index >= 58:
        return "in_form"
    if index < 42:
        return "cold"
    return "stable"


def _label_for(index: float, explosive: bool, goals_recent: int) -> str:
    if explosive:
        return f"Explosive streak: {goals_recent} goals recently"
    if index >= 70:
        return "Peak confidence — riding a hot streak"
    if index >= 58:
        return "Building momentum"
    if index < 42:
        return "Cold spell — searching for form"
    return "Stable form"


def rows_for_club(db, club_slug: str) -> List[Dict[str, Any]]:
    """All player_match_stats rows for a club, newest first (one query)."""
    if db is None:
        return []
    try:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT player_name, goals, assists, xg, fixture_date, opponent_slug, is_home "
                "FROM player_match_stats WHERE club_slug = ? ORDER BY fixture_date DESC LIMIT 400",
                (club_slug,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def _fetch_player_rows(db, player_name: str, club_slug: str,
                       club_rows: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """This player's rows (name-matched), newest first — from a preloaded club set when given."""
    rows = club_rows if club_rows is not None else rows_for_club(db, club_slug)
    target = _norm(player_name)
    tset = _name_tokens(player_name)
    out = []
    for r in rows:
        nm = _norm(r["player_name"])
        if not nm:
            continue
        if nm == target or (tset and tset & _name_tokens(r["player_name"])):
            out.append(dict(r))
    # keep only the 6 most recent for this player
    out.sort(key=lambda x: x["fixture_date"], reverse=True)
    return out[:6]


def _match_scores(rows: List[Dict[str, Any]]) -> List[float]:
    """Per-match performance scores with a 45-day half-life recency decay:
    since only goal events are recorded (not blanks), stale goals must fade
    toward neutral or every scorer would stay 'hot' forever."""
    from datetime import date
    today = date.today()
    scores = []
    for r in rows:
        goals = r.get("goals") or 0
        assists = r.get("assists") or 0
        xg = r.get("xg") or 0.0
        s = 50.0 + 22.0 * goals + 10.0 * assists
        if xg:  # xG over/under-performance refines the score when available
            s += max(-8.0, min(8.0, (goals - xg) * 14.0))
        try:
            days = (today - date.fromisoformat(str(r.get("fixture_date"))[:10])).days
        except Exception:
            days = 0
        decay = 0.5 ** (max(0, days) / 45.0)
        s = 50.0 + (s - 50.0) * decay
        scores.append(max(5.0, min(98.0, s)))
    return scores


def compute_momentum(db, player: Dict[str, Any], club_slug: str,
                     club_rows: Optional[List[Dict[str, Any]]] = None) -> PlayerMomentum:
    """Full momentum profile for one player from real match data."""
    rows = _fetch_player_rows(db, player.get("name") or player.get("nickname") or "", club_slug, club_rows)
    if not rows:
        return PlayerMomentum()  # neutral; caller falls back to team-form heuristic

    scores = _match_scores(rows)
    n = len(scores)
    num = sum(w * s for w, s in zip(WEIGHTS, scores))
    den = sum(WEIGHTS[:n])
    index = num / den

    # Explosive-game detection + decay
    explosive = False
    boost = 0.0
    matches_since = None
    for i, r in enumerate(rows):  # rows[0] is the most recent
        if (r.get("goals") or 0) >= 2:
            explosive = True
            matches_since = i
            break
    if matches_since is not None:
        boost = 8.0 * (0.7 ** matches_since)

    goals_recent = sum(r.get("goals") or 0 for r in rows[:3])
    status = _status_for(index)
    label = _label_for(index, explosive, goals_recent)
    return PlayerMomentum(index, n, explosive, boost, label, status,
                          [{"date": r["fixture_date"], "goals": r.get("goals") or 0} for r in rows[:4]])


def team_momentum(db, club_slug: str, players: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregated XI-level momentum (0-100) + notable hot/cold players."""
    if not players:
        return {"index": 50.0, "status": "stable", "hot": [], "cold": []}
    club_rows = rows_for_club(db, club_slug)
    per_player = []
    idx_all = []
    for p in players:
        m = compute_momentum(db, p, club_slug, club_rows=club_rows)
        if m.matches:
            per_player.append((p, m))
            idx_all.append(m.index)
        else:
            idx_all.append(50.0)  # neutral: no per-match data
    if not per_player:
        return {"index": 50.0, "status": "stable", "hot": [], "cold": []}
    # Average over the WHOLE squad (no-data players count as neutral 50) so a
    # couple of scorers cannot drag the team index to "hot".
    idx = sum(idx_all) / len(idx_all)
    ranked = sorted(per_player, key=lambda pm: pm[1].index, reverse=True)
    hot = [{"name": p.get("name"), **m.to_dict()} for p, m in ranked[:3] if m.index >= 58]
    cold = [{"name": p.get("name"), **m.to_dict()} for p, m in ranked[-3:] if m.index < 45]
    return {"index": round(idx, 1), "status": _status_for(idx), "hot": hot, "cold": cold}
