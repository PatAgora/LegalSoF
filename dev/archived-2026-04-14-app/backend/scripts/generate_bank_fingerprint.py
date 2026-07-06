#!/usr/bin/env python3
"""
Generate a bank template fingerprint JSON from a known-good statement PDF.

Usage (from backend/):
    python scripts/generate_bank_fingerprint.py <pdf> <bank_name> [--force] [--notes "..."]

Writes app/services/bank_templates/<bank>.json (lowercase, spaces →
underscores — the same convention template_fingerprint._load_reference
uses to look the file up). The pHash is computed by the SAME function
the runtime check uses (_compute_header_phash), so a round-trip of the
source PDF against its own fingerprint always yields distance 0.

Refuses to overwrite an existing fingerprint unless --force is given.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

# Ensure the backend package is importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.template_fingerprint import (  # noqa: E402
    TEMPLATES_DIR,
    _compute_header_phash,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register a known-good statement PDF as a bank template fingerprint."
    )
    parser.add_argument("pdf", help="Path to a known-good statement PDF")
    parser.add_argument("bank_name", help="Bank name, e.g. HSBC, Barclays, Santander")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing fingerprint for this bank")
    parser.add_argument("--notes", default=None,
                        help="Free-text provenance note stored in the JSON")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        print(f"[!] PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    safe = args.bank_name.lower().replace(" ", "_")
    out_path = TEMPLATES_DIR / f"{safe}.json"
    if out_path.exists() and not args.force:
        print(f"[!] {out_path} already exists — pass --force to overwrite.",
              file=sys.stderr)
        return 3

    file_bytes = pdf_path.read_bytes()
    phash = _compute_header_phash(file_bytes)
    if not phash:
        print("[!] Could not compute a header pHash (is this a readable PDF, "
              "and are PyMuPDF/Pillow/imagehash installed?)", file=sys.stderr)
        return 4

    record = {
        "bank": args.bank_name,
        "header_phash": phash,
        "added": datetime.date.today().isoformat(),
        "source_filename": pdf_path.name,
        "notes": args.notes or (
            f"Generated from {pdf_path.name} — page 1 header band, 100 dpi."
        ),
    }
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fp:
        json.dump(record, fp, indent=2)
        fp.write("\n")

    print(f"[+] Wrote {out_path}")
    print(f"    bank         : {record['bank']}")
    print(f"    header_phash : {record['header_phash']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
