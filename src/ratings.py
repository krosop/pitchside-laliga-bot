"""
Club Elo rating engine — the "opponent point system".

Computes every club's strength rating from the full mirror archive of real
results (2021/22 -> today), using the World-Football-Elo recipe adapted to a
closed league:

  expected = 1 / (1 + 10 ** ((elo_away - elo_home - HOME_ADV) / 400))
  delta    = K * margin_mult * (score - expected)

  K        = 28, HOME_ADV = 65 elo points
  margin_mult = sqrt(gd) capped at 3.5 (margins carry extra information)

Newly promoted clubs enter at the 1500 baseline and converge within ~10
matches. Ratings persist in `club_ratings` with:
  elo            — current rating (higher = stronger)
  rank           — 1..N among all rated clubs
  difficulty     — 1.0..5.0 tier (5 = elite opponent) derived from percentile
  matches_counted— how many real results back the number

Recompute after every mirror sync; incremental and deterministic.
"""
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .mirror_footballdata import DB_PATH

ELO_BASE = 1500.0
K_FACTOR = 28.0
HOME_ADV = 65.0


class RatingsEngine:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def recompute_all(self) -> Dict[str, float]:
        """Replays every finished fixture chronologically and writes fresh ratings."""
        conn = self._connect()
        try:
            teams = {r["id"] for r in conn.execute("SELECT id FROM clubs")}
            elo = {tid: ELO_BASE for tid in teams}

            rows = conn.execute(
                "SELECT home_team_id, away_team_id, home_score, away_score "
                "FROM fixtures WHERE status='FINISHED' AND home_score IS NOT NULL "
                "ORDER BY kickoff_time ASC, id ASC"
            ).fetchall()

            for r in rows:
                h, a = r["home_team_id"], r["away_team_id"]
                if h not in elo:
                    elo[h] = ELO_BASE
                if a not in elo:
                    elo[a] = ELO_BASE
                hs, as_ = r["home_score"] or 0, r["away_score"] or 0
                exp_h = 1.0 / (1.0 + 10 ** ((elo[a] - elo[h] - HOME_ADV) / 400.0))
                score_h = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0
                margin = abs(hs - as_)
                mult = min(3.5, math.sqrt(margin)) if margin > 1 else 1.0
                delta = K_FACTOR * mult * (score_h - exp_h)
                elo[h] += delta
                elo[a] -= delta

            # Difficulty tiers 1..5: percentile of elo among rated clubs
            rated = sorted(elo.items(), key=lambda kv: kv[1])
            n = len(rated)
            tiers: Dict[int, float] = {}
            for i, (tid, e) in enumerate(rated):
                pct = (i / max(1, n - 1)) if n > 1 else 0.5
                tiers[tid] = round(1.0 + pct * 4.0, 2)

            conn.execute("DELETE FROM club_ratings")
            for tid, e in elo.items():
                conn.execute(
                    "INSERT INTO club_ratings (club_id, elo, difficulty, rank, matches_counted, updated_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (tid, round(e, 1), tiers.get(tid, 2.5),
                     None,  # rank filled below
                     0, datetime.utcnow().isoformat()),
                )
            ranked = sorted(elo.items(), key=lambda kv: kv[1], reverse=True)
            for pos, (tid, _) in enumerate(ranked, start=1):
                conn.execute("UPDATE club_ratings SET rank=? WHERE club_id=?", (pos, tid))
            for tid in elo:
                conn.execute(
                    "UPDATE club_ratings SET matches_counted=(SELECT COUNT(*) FROM fixtures "
                    "WHERE status='FINISHED' AND (home_team_id=? OR away_team_id=?)) WHERE club_id=?",
                    (tid, tid, tid),
                )
            conn.commit()
            return {slug: e for slug, e in ((str(t), elo[t]) for t in elo)}
        finally:
            conn.close()

    def get_all(self) -> Dict[str, Dict]:
        """{club_slug: {elo, difficulty, rank, matches_counted}} for the live season's clubs."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT c.slug, r.elo, r.difficulty, r.rank, r.matches_counted "
                "FROM club_ratings r JOIN clubs c ON c.id = r.club_id"
            ).fetchall()
            return {
                r["slug"]: {"elo": r["elo"], "difficulty": r["difficulty"],
                            "rank": r["rank"], "matches_counted": r["matches_counted"]}
                for r in rows
            }
        finally:
            conn.close()

    def get_rating(self, club_slug: str) -> Optional[Dict]:
        return self.get_all().get(club_slug)

    @classmethod
    def get_or_none(cls, db, club_slug: str) -> Optional[Dict]:
        """Ratings lookup accepting a Database instance (uses its db_path)."""
        try:
            path = getattr(db, "db_path", None)
            if not path:
                return None
            return cls(db_path=path).get_rating(club_slug)
        except Exception:
            return None


if __name__ == "__main__":
    eng = RatingsEngine()
    eng.recompute_all()
    ratings = eng.get_all()
    top = sorted(ratings.items(), key=lambda kv: kv[1]["elo"], reverse=True)[:6]
    for slug, r in top:
        print(f"{slug:18s} elo={r['elo']:7.1f} rank={r['rank']:2d} tier={r['difficulty']}")
