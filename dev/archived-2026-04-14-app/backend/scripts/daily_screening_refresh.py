#!/usr/bin/env python3
"""Daily sanctions refresh + re-screen (cron entry point).

Runs the two steps that keep the strict-liability sanctions layer current:

  1. Download and import the latest FCDO UK Sanctions List
     (delegates to scripts.update_sanctions_list.run_update).
  2. Re-screen every non-archived matter's latest subjects against the
     freshly imported dataset, creating a new screening check only where
     a subject's hit set has changed (a newly listed person now matches,
     or a de-listing clears a prior hit).

Designed to run unattended: the re-screen actor is the automated system
(AuditLog.user_id = NULL), and any newly surfaced potential match lands
in the normal per-matter screening queue for a human to adjudicate.

Usage
-----
    python -m scripts.daily_screening_refresh            # update + rescreen
    python -m scripts.daily_screening_refresh --no-update # rescreen only
    python -m scripts.daily_screening_refresh --force     # force re-import

Scheduling
----------
Railway: add a Cron service running this module (e.g. `0 6 * * *`).
System cron / Docker sidecar:
    0 6 * * * cd /app && python -m scripts.daily_screening_refresh >> /var/log/sanctions.log 2>&1

Exit code is non-zero if the update step fails, so a scheduler can alert.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s daily_screening_refresh: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily sanctions refresh + re-screen")
    parser.add_argument("--no-update", action="store_true",
                        help="Skip the list download; re-screen against the current dataset only.")
    parser.add_argument("--force", action="store_true",
                        help="Force re-import even if the dataset version is unchanged.")
    parser.add_argument("--url", default=None, help="Override the sanctions list URL.")
    args = parser.parse_args()

    from app.db.session import get_sync_session
    from scripts.update_sanctions_list import run_update
    from app.api.v1.endpoints.screening import rescreen_all_matters

    exit_code = 0
    db = get_sync_session()()  # get_sync_session() returns the sessionmaker
    try:
        if not args.no_update:
            result = run_update(db=db, url=args.url, force=args.force)
            status = result.get("status")
            logger.info("update step: %s (version=%s, entries=%s)",
                        status, result.get("version"), result.get("entry_count"))
            if status == "error":
                # Keep going to re-screen against whatever data we already
                # hold, but report failure so the scheduler can alert.
                logger.error("update failed: %s", result.get("error"))
                exit_code = 1
        else:
            logger.info("update step skipped (--no-update)")

        try:
            summary = rescreen_all_matters(db, actor_user_id=None)
            logger.info(
                "rescreen step: dataset=%s matters=%s subjects=%s new_checks=%s",
                summary["dataset_version"], summary["matters_scanned"],
                summary["subjects_screened"], summary["new_checks_created"],
            )
            if summary["new_checks_created"]:
                logger.warning(
                    "%s subject(s) have a CHANGED screening result and need review "
                    "in the per-matter screening queue.",
                    summary["new_checks_created"],
                )
        except RuntimeError as exc:
            logger.error("rescreen step skipped: %s", exc)
            exit_code = 1
    finally:
        db.close()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
