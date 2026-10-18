"""
One-command data refresh — orchestrates every mirror into a single pipeline:

  1. football-data.co.uk CSVs   (results archive + current-season results)
  2. ESPN live feed             (schedule, kickoffs, statuses, scorer timelines)
  3. Elo ratings recompute      (strength + difficulty tiers from all seasons)
  4. TheSportsDB enrichment     (club badges, player cutouts, bio facts)

Incremental and idempotent: safe to run after every matchday. The current
season's CSV is always re-fetched (only historical seasons use the cache).
"""
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Optional

from .mirror_footballdata import sync_all as sync_mirror, _recompute_standings, DB_PATH, SEASON_CODES
from .espn_feed import sync_all as sync_espn
from .ratings import RatingsEngine


def refresh(with_timelines: bool = False, backup: bool = True,
            db_path: Optional[str] = None) -> Dict[str, object]:
    """db_path lets serverless deployments operate on their own DB copy."""
    report: Dict[str, object] = {}
    try:
        # 1. Mirror (historical archive + current results). Always re-fetch the
        # newest season code so freshly played matches are picked up.
        newest_code = SEASON_CODES[-1][0]
        mirror = sync_mirror(backup=backup, fresh_codes=(newest_code,), db_path=db_path)
        report["mirror"] = mirror
        if str(mirror.get("status", "")).startswith("failed"):
            report["status"] = "mirror_failed"
            return report

        # 2. ESPN live layer for the current season
        espn = sync_espn(with_timelines=with_timelines, db_path=db_path)
        report["espn"] = espn

        # 2b. Recompute standings AFTER ESPN: fresh scores may include results
        # the CSV mirror has not published yet — the table must never lag.
        conn = sqlite3.connect(db_path or DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT value FROM app_meta WHERE key='current_season'").fetchone()
            live = int(row[0]) if row else SEASON_CODES[-1][1]
            _recompute_standings(conn, live)
            conn.commit()
            report["standings_recomputed"] = live
        finally:
            conn.close()

        # 3. Ratings from the full archive
        ratings = RatingsEngine(db_path=db_path).recompute_all()
        report["ratings"] = {"clubs_rated": len(ratings)}

        # 3b. Prediction ledger: record forecasts for newly-scheduled fixtures
        # within the horizon, settle any that just finished (hit-or-miss feed).
        try:
            from .predictions import record_pending, settle_due, DBHandle
            ledger_db = DBHandle(db_path or DB_PATH)
            report["ledger"] = {
                "recorded": record_pending(ledger_db),
                "settled": settle_due(ledger_db),
            }
        except Exception as e:  # the feed must never break the data pipeline
            report["ledger"] = {"status": f"skipped: {type(e).__name__}: {e}"}

        # 3c. TheSportsDB imagery/bio enrichment (badges, cutouts, DOB/height)
        #     — network pass, skipped automatically when offline; never fatal.
        try:
            from .tsdb_feed import run_enrichment as _tsdb_enrich
            report["tsdb"] = _tsdb_enrich(db_path=db_path, log=lambda *_: None)
        except Exception as e:  # images must never break the data pipeline
            report["tsdb"] = {"status": f"skipped: {type(e).__name__}: {e}"}

        # 3d. Market odds (historical CSVs + weekly fixtures file) for the
        #     prediction blend — best-effort, never fatal.
        try:
            from .odds_feed import run as _odds_run
            report["odds"] = _odds_run(db_path=db_path or DB_PATH)
        except Exception as e:  # missing odds only cost model accuracy, not the pipeline
            report["odds"] = {"status": f"skipped: {type(e).__name__}: {e}"}

        # 4. Pipeline log entry
        conn = sqlite3.connect(db_path or DB_PATH)
        try:
            conn.execute(
                "INSERT INTO sync_log (source, last_sync, rows_affected, status) VALUES ('pipeline', ?, ?, 'ok') "
                "ON CONFLICT(source) DO UPDATE SET last_sync=excluded.last_sync, "
                "rows_affected=excluded.rows_affected, status=excluded.status",
                (datetime.now(timezone.utc).isoformat(),
                 int(mirror.get("seasons", {}).get(max((k for k in mirror.get("seasons", {})), key=lambda x: int(x)), {}).get("upserted", 0))
                 if mirror.get("seasons") else 0),
            )
            conn.commit()
        finally:
            conn.close()

        report["status"] = "ok"
    except Exception as e:
        report["status"] = f"failed: {type(e).__name__}: {e}"
    return report


def sync_status(db_path: Optional[str] = None) -> Dict[str, object]:
    """Last sync time per source + the live season, for the UI indicator."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        logs = {
            r["source"]: {"last_sync": r["last_sync"], "rows": r["rows_affected"], "status": r["status"]}
            for r in conn.execute("SELECT * FROM sync_log")
        }
        row = conn.execute("SELECT value FROM app_meta WHERE key='current_season'").fetchone()
        finished = conn.execute(
            "SELECT COUNT(*) FROM fixtures WHERE season=? AND status='FINISHED'",
            (int(row[0]) if row else 2026,),
        ).fetchone()[0]
        return {"sources": logs, "current_season": int(row[0]) if row else None,
                "matches_played": finished}
    finally:
        conn.close()


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    print(json.dumps(refresh(with_timelines="--timelines" in sys.argv), indent=2, default=str))
