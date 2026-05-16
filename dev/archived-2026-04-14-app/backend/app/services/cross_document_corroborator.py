"""
Cross-document corroboration
============================

Runs after a single document's verification finishes, and asks the
question: does this document agree with the OTHER documents on this
matter?

Phase 1 checks (no schema migration required):

  * `ACCOUNT_NAME_MISMATCH`   — the matter's `client_name` does not appear
                                anywhere in this document's text. Almost
                                every genuine bank statement / completion
                                statement / probate grant carries the
                                client's name on it.
  * `PERIOD_GAP_VS_OTHER_STATEMENTS` — this statement's period leaves an
                                unexplained gap (>35 days) relative to the
                                neighbouring statements already uploaded
                                for this matter.

The corroborator is deliberately pipeline-agnostic: callers extract the
relevant inputs (text, period bounds) and call `corroborate(...)`. We
return a list of `VerificationFlag` dataclass instances to keep the
shape identical to the rest of the verification pipeline output.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import Matter
from app.models.document_verification import DocumentVerification
from app.services.document_verification_pipeline import VerificationFlag


# How big a gap between adjacent statements is "unexplained"? UK bank
# statements are typically monthly so anything over ~5 weeks merits a flag.
PERIOD_GAP_DAYS = 35

# Tokens that should be ignored when checking whether the client name
# appears in a document — they're meaningless on their own.
_NAME_STOPWORDS = {
    "mr", "mrs", "miss", "ms", "dr", "prof",
    "and", "the", "of", "ltd", "limited", "llp", "plc", "inc",
}


@dataclass
class CorroborationContext:
    """Per-matter context cached across multiple corroborate() calls."""
    matter_id: int
    client_name: str = ""
    other_period_ranges: List["PeriodRange"] = field(default_factory=list)


@dataclass
class PeriodRange:
    start: datetime
    end: datetime


def _significant_name_tokens(client_name: str) -> List[str]:
    """Split a client name into the parts worth searching for in a document."""
    if not client_name:
        return []
    tokens = re.findall(r"[A-Za-z]{3,}", client_name.lower())
    return [t for t in tokens if t not in _NAME_STOPWORDS]


def _parse_period(s: Optional[str]) -> Optional[datetime]:
    """The pipeline stores periods as free-text strings — try the most
    common UK statement formats."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _load_context(db: Session, matter_id: int, exclude_verification_id: Optional[int]) -> CorroborationContext:
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    ctx = CorroborationContext(matter_id=matter_id)
    if matter:
        ctx.client_name = matter.client_name or ""

    q = db.query(DocumentVerification).filter(DocumentVerification.matter_id == matter_id)
    if exclude_verification_id is not None:
        q = q.filter(DocumentVerification.id != exclude_verification_id)
    for dv in q.all():
        start = _parse_period(dv.period_start)
        end = _parse_period(dv.period_end)
        if start and end and end >= start:
            ctx.other_period_ranges.append(PeriodRange(start=start, end=end))

    return ctx


def _check_client_name(doc_text: str, ctx: CorroborationContext) -> Optional[VerificationFlag]:
    """Flag if NONE of the significant tokens from the matter's client
    name appear in the document text. This is intentionally lenient — we
    only flag when there's zero overlap, so OCR-fuzzy / minor-spelling
    differences don't cause false positives."""
    tokens = _significant_name_tokens(ctx.client_name)
    if not tokens or not doc_text:
        return None

    lowered = doc_text.lower()
    found = [t for t in tokens if t in lowered]
    if found:
        return None

    return VerificationFlag(
        "cross_document", "ACCOUNT_NAME_MISMATCH", "high",
        f"Document does not appear to mention the client ('{ctx.client_name}'). "
        "Worth checking the document was uploaded to the right matter.",
        {
            "matter_client_name": ctx.client_name,
            "tokens_searched": tokens,
            "tokens_found": found,
        },
    )


def _check_period_gap(
    new_start: Optional[datetime],
    new_end: Optional[datetime],
    ctx: CorroborationContext,
) -> Optional[VerificationFlag]:
    """Flag if this statement's period leaves a >35 day gap to the nearest
    neighbouring period in the matter (either before or after).

    Only fires when there's at least one other dated statement to compare
    against — a single statement on a matter is never "leaving a gap"."""
    if not new_start or not new_end or new_end < new_start:
        return None
    if not ctx.other_period_ranges:
        return None

    nearest_before_end: Optional[datetime] = None
    nearest_after_start: Optional[datetime] = None
    for r in ctx.other_period_ranges:
        if r.end < new_start:
            if nearest_before_end is None or r.end > nearest_before_end:
                nearest_before_end = r.end
        elif r.start > new_end:
            if nearest_after_start is None or r.start < nearest_after_start:
                nearest_after_start = r.start

    gaps: List[Dict[str, Any]] = []
    threshold = timedelta(days=PERIOD_GAP_DAYS)
    if nearest_before_end is not None and (new_start - nearest_before_end) > threshold:
        gaps.append({
            "direction": "before",
            "neighbour_period_end": nearest_before_end.strftime("%Y-%m-%d"),
            "this_period_start": new_start.strftime("%Y-%m-%d"),
            "gap_days": (new_start - nearest_before_end).days,
        })
    if nearest_after_start is not None and (nearest_after_start - new_end) > threshold:
        gaps.append({
            "direction": "after",
            "this_period_end": new_end.strftime("%Y-%m-%d"),
            "neighbour_period_start": nearest_after_start.strftime("%Y-%m-%d"),
            "gap_days": (nearest_after_start - new_end).days,
        })

    if not gaps:
        return None

    biggest = max(gaps, key=lambda g: g["gap_days"])
    return VerificationFlag(
        "cross_document", "PERIOD_GAP_VS_OTHER_STATEMENTS", "high",
        f"Statement period leaves a {biggest['gap_days']}-day gap "
        f"({'before' if biggest['direction'] == 'before' else 'after'}) "
        "the neighbouring statements on this matter.",
        {"gaps": gaps, "threshold_days": PERIOD_GAP_DAYS},
    )


def corroborate(
    db: Session,
    matter_id: int,
    new_verification_id: int,
    new_doc_text: str = "",
    new_period_start: Optional[str] = None,
    new_period_end: Optional[str] = None,
) -> List[VerificationFlag]:
    """Run all corroboration checks for a newly-created verification.

    Returns a list of `VerificationFlag` to be persisted as
    `DocumentVerificationFlag` rows against `new_verification_id`. Empty
    list means everything corroborates fine (no flag).
    """
    ctx = _load_context(db, matter_id, exclude_verification_id=new_verification_id)

    flags: List[VerificationFlag] = []

    f = _check_client_name(new_doc_text, ctx)
    if f:
        flags.append(f)

    start_dt = _parse_period(new_period_start)
    end_dt = _parse_period(new_period_end)
    f = _check_period_gap(start_dt, end_dt, ctx)
    if f:
        flags.append(f)

    return flags
