"""
Bank statement template fingerprint
===================================

For a statement that claims to be from a known UK bank (HSBC, NatWest,
Barclays, Santander, Lloyds), compare its visual layout against a
stored reference fingerprint and raise TEMPLATE_VISUAL_MISMATCH if
they don't match.

The fingerprint is the perceptual hash (pHash) of the page-1 header
band — typically the most stable visual element on a bank statement
(the logo / address / account-summary panel). pHash tolerates minor
shifts and antialiasing, so a genuine statement from a slightly
different month still matches; a hand-built fake of an HSBC statement
won't.

Reference fingerprints live as JSON in
`backend/app/services/bank_templates/`. Each file looks like:

    { "bank": "HSBC", "header_phash": "abc123…", "added": "2026-05-16" }

If no reference exists for the named bank we silently no-op (better
to under-flag than to false-positive).

Wiring: called from document_verification_pipeline as stage 8e.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import List, Optional

from app.services.document_verification_pipeline import VerificationFlag


# pHash distance above which we declare a mismatch. Empirical — pHash
# returns Hamming distance between two 64-bit hashes. Genuine variants
# usually sit under 12; a deliberately-faked layout will sit way above.
PHASH_MISMATCH_THRESHOLD = 18

TEMPLATES_DIR = Path(__file__).resolve().parent / "bank_templates"

# Bank brand keywords for header-band identification. Deliberately
# scoped to the page-1 header region (see infer_bank_from_header): a
# whole-document scan misattributes statements that merely mention
# another bank in a transaction narrative ("TRANSFER FROM HSBC ...").
_BANK_KEYWORDS: dict = {
    "HSBC": ["hsbc", "first direct"],
    "Barclays": ["barclays"],
    "NatWest": ["natwest", "national westminster"],
    "Lloyds": ["lloyds"],
    "Halifax": ["halifax"],
    "Santander": ["santander"],
    "Nationwide": ["nationwide"],
    "TSB": ["tsb"],
    "Monzo": ["monzo"],
    "Starling": ["starling"],
}


def infer_bank_from_header(header_text: str) -> Optional[str]:
    """Identify which known bank a statement CLAIMS to be from, using only
    the page-1 header band text. Earliest keyword occurrence wins — the
    brand name leads the header on a genuine (or convincingly faked)
    statement. Returns None when no known bank is named there, in which
    case the template check should be skipped (under-flag, never guess)."""
    if not header_text:
        return None
    lowered = header_text.lower()
    best_bank: Optional[str] = None
    best_pos: Optional[int] = None
    for bank, keywords in _BANK_KEYWORDS.items():
        for kw in keywords:
            pos = lowered.find(kw)
            if pos != -1 and (best_pos is None or pos < best_pos):
                best_bank, best_pos = bank, pos
    return best_bank


def _load_reference(bank: str) -> Optional[dict]:
    if not bank:
        return None
    safe = bank.lower().replace(" ", "_")
    path = TEMPLATES_DIR / f"{safe}.json"
    if not path.is_file():
        return None
    try:
        with path.open() as fp:
            return json.load(fp)
    except Exception:
        return None


def _compute_header_phash(file_bytes: bytes) -> Optional[str]:
    """Render page 1 and pHash the top 20% of the page (header band)."""
    try:
        import fitz
        from PIL import Image
        import imagehash  # type: ignore
    except ImportError:
        return None

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if doc.page_count == 0:
            doc.close()
            return None
        page = doc[0]
        pix = page.get_pixmap(dpi=100, alpha=False)
        full = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        doc.close()
        w, h = full.size
        header = full.crop((0, 0, w, max(int(h * 0.20), 80)))
        return str(imagehash.phash(header))
    except Exception:
        return None


def _hex_to_imagehash(s: str):
    """Re-hydrate an imagehash from its hex string."""
    try:
        import imagehash  # type: ignore
        return imagehash.hex_to_hash(s)
    except Exception:
        return None


def check_template_match(file_bytes: bytes, bank: Optional[str]) -> List[VerificationFlag]:
    if not bank:
        return []

    ref = _load_reference(bank)
    if not ref or not ref.get("header_phash"):
        # No reference fingerprint registered for this bank yet — silent.
        return []

    new_phash = _compute_header_phash(file_bytes)
    if not new_phash:
        return []

    ref_hash = _hex_to_imagehash(ref["header_phash"])
    cur_hash = _hex_to_imagehash(new_phash)
    if ref_hash is None or cur_hash is None:
        return []

    try:
        distance = ref_hash - cur_hash
    except Exception:
        return []

    if distance > PHASH_MISMATCH_THRESHOLD:
        return [VerificationFlag(
            "template_fingerprint", "TEMPLATE_VISUAL_MISMATCH", "high",
            f"Document claims to be a {bank} statement but its visual "
            f"layout does not match the registered {bank} template "
            f"(pHash distance {distance}, threshold {PHASH_MISMATCH_THRESHOLD}).",
            {
                "bank": bank,
                "reference_phash": ref["header_phash"],
                "document_phash": new_phash,
                "distance": distance,
                "threshold": PHASH_MISMATCH_THRESHOLD,
            },
        )]
    return []
