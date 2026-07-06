#!/usr/bin/env python3
"""
Download and import the UK Sanctions List (FCDO).

The UK Sanctions List is the free authoritative source for UK financial
sanctions designations (the old OFSI consolidated list closed in January
2026). The FCDO publishes the list at a stable URL:

    https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml

(validated live on 06/07/2026 — linked from
https://www.gov.uk/government/publications/the-uk-sanctions-list).
Override with the SANCTIONS_LIST_URL environment variable if the FCDO
moves the publication.

Usage (standalone / cron):
    python scripts/update_sanctions_list.py [--url URL] [--force]

Also callable in-process:
    from scripts.update_sanctions_list import run_update
    summary = run_update()

Behaviour on download/parse failure: the previously imported dataset is
KEPT untouched, a warning is logged, and the script exits non-zero (so
cron alerts fire) — screening keeps working on the old data.

Cron story: run this script, then POST /api/v1/screening/rescreen-all as
an admin to re-screen every open matter against the new dataset.
"""
import argparse
import logging
import os
import sys

# Allow running as `python scripts/update_sanctions_list.py` from backend/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402

logger = logging.getLogger("update_sanctions_list")

DEFAULT_SANCTIONS_LIST_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml"


def get_sanctions_list_url() -> str:
    return os.environ.get("SANCTIONS_LIST_URL", DEFAULT_SANCTIONS_LIST_URL)


def download_sanctions_list(url: str | None = None, timeout: float = 120.0) -> bytes:
    """Download the raw XML. Raises on any HTTP/network failure."""
    url = url or get_sanctions_list_url()
    logger.info("Downloading UK Sanctions List from %s", url)
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.content


def run_update(db=None, url: str | None = None, force: bool = False) -> dict:
    """Download, parse and import the UK Sanctions List.

    Returns a summary dict:
      {"status": "imported"|"unchanged"|"error", "version": ..., "entry_count": ...}

    On failure the existing dataset is left untouched (status="error").
    """
    # Imports deferred so the module can be imported without app deps loaded.
    from app.db.session import get_sync_engine, get_sync_session
    from app.db.base import Base
    import app.models  # noqa: F401 — register all core models with Base
    from app.models.screening import SanctionsDataset, SanctionsEntry
    from app.services.sanctions_screening import (
        parse_uk_sanctions_xml, invalidate_index_cache,
    )

    url = url or get_sanctions_list_url()

    try:
        content = download_sanctions_list(url)
        date_generated, entries = parse_uk_sanctions_xml(content)
    except Exception as exc:  # noqa: BLE001 — keep old data on ANY failure
        logger.warning(
            "UK Sanctions List update failed (%s) — keeping the previously "
            "imported dataset. Error: %s", url, exc,
        )
        return {"status": "error", "error": str(exc), "url": url}

    if not entries:
        logger.warning("Downloaded list parsed to zero entries — keeping old dataset")
        return {"status": "error", "error": "parsed zero entries", "url": url}

    version = date_generated.strftime("%d/%m/%Y") if date_generated else "unknown"

    own_session = db is None
    if own_session:
        # Standalone (cron) path — make sure tables exist even if the API
        # has never booted with the screening models registered.
        Base.metadata.create_all(
            get_sync_engine(),
            tables=[SanctionsDataset.__table__, SanctionsEntry.__table__],
        )
        db = get_sync_session()()

    try:
        latest = (
            db.query(SanctionsDataset)
            .order_by(SanctionsDataset.imported_at.desc(), SanctionsDataset.id.desc())
            .first()
        )
        if (
            not force
            and latest is not None
            and latest.version == version
            and latest.entry_count == len(entries)
        ):
            logger.info("UK Sanctions List unchanged (version %s) — skipping import", version)
            return {
                "status": "unchanged",
                "version": version,
                "entry_count": latest.entry_count,
            }

        dataset = SanctionsDataset(
            source="uk_fcdo",
            version=version,
            date_generated=date_generated,
            entry_count=len(entries),
            source_url=url,
        )
        db.add(dataset)
        db.flush()  # assign dataset.id

        db.bulk_insert_mappings(
            SanctionsEntry,
            [{**entry, "dataset_id": dataset.id} for entry in entries],
        )
        # Retire entries of previous datasets (dataset rows are kept as an
        # import history; only the entry payloads are replaced).
        db.query(SanctionsEntry).filter(
            SanctionsEntry.dataset_id != dataset.id
        ).delete(synchronize_session=False)

        db.commit()
        invalidate_index_cache()
        logger.info(
            "Imported UK Sanctions List version %s: %d entries", version, len(entries),
        )
        return {"status": "imported", "version": version, "entry_count": len(entries)}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("UK Sanctions List import failed — keeping old dataset: %s", exc)
        return {"status": "error", "error": str(exc), "url": url}
    finally:
        if own_session:
            db.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Update the UK Sanctions List dataset")
    parser.add_argument("--url", help="Override the download URL (or set SANCTIONS_LIST_URL)")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-import even when the published version is unchanged",
    )
    args = parser.parse_args()

    summary = run_update(url=args.url, force=args.force)
    print(summary)
    return 0 if summary["status"] in ("imported", "unchanged") else 1


if __name__ == "__main__":
    sys.exit(main())
