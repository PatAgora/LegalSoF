"""
Analytics endpoints — cross-matter rollups used by the dashboard.

Designed so the dashboard front-end does ONE request and gets
everything it needs:
  - matter counts grouped by status + risk
  - document verification counts grouped by verdict
  - matters currently blocked downstream
  - top N most-common flag codes ("root cause analysis")
  - recent matters list

Auth: every analyst can read. No write endpoints here.
"""
from collections import Counter
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_analyst
from app.db.session import get_sync_db
from app.models import Matter, MatterStatus, RiskRating
from app.models.document_verification import (
    DocumentVerification,
    DocumentVerificationFlag,
    VerificationVerdict,
)
from app.models.user import User


router = APIRouter()


# Flag codes that are info-level / housekeeping and should not surface
# as "top issues". Mirrors the frontend filter in
# DocumentVerificationModal.tsx so the dashboard agrees with the modal.
_NOISE_FLAG_CODES = {
    "FINAL_SCORE",
    "NON_PDF_FILE",
    "SINGLE_EOF",
    "IMAGE_PHASH_RECORDED",
    "IMAGE_FORENSICS_UNAVAILABLE",
    "IMAGE_FORENSICS_OPEN_FAILED",
    "OCR_UNAVAILABLE",
    "OCR_CONSISTENCY_OK",
    "SIGNATURE_ABSENT",
    "SIGNATURE_VALID",
    "SIGNATURE_PRESENT_UNVERIFIED",
}


# Server-side label lookup for the dashboard "top issues" rows. Kept
# deliberately separate from `flagTranslations.ts` so the API caller
# (or a future report renderer) can read a human label without owning
# a frontend bundle. Same wording as the modal headline though.
_FLAG_LABELS: Dict[str, str] = {
    "TEXT_LAYER_OCR_MISMATCH": "Visible text does not match the document text layer",
    "IMAGE_ELA_ANOMALY":       "Embedded image shows signs of editing",
    "IMAGE_QUANT_TABLE_MIXED": "Embedded images use different compression profiles",
    "TEMPLATE_VISUAL_MISMATCH": "Document does not match the registered bank template",
    "SIGNATURE_INVALID":       "Digital signature failed validation",
    "SUSPICIOUS_CREATOR":      "Document created with image-editing software",
    "FAKE_REDACTION":          "Content hidden behind black boxes",
    "WHITED_OUT_CONTENT":      "Content covered with white boxes",
    "TEXT_INPUT_FIELDS":       "Editable form fields detected",
    "FREETEXT_ANNOTATIONS":    "Text added on top of the document",
    "REDACT_ANNOTATIONS":      "Redaction marks found",
    "HIDDEN_LAYERS":           "Hidden content layers found",
    "BALANCE_ERRORS":          "Running balances do not add up",
    "SUM_CROSS_CHECK_FAIL":    "Transaction totals do not match",
    "DATE_INCONSISTENCY":      "Document dates are contradictory",
    "PRODUCER_DATE_MISMATCH":  "Software version doesn't match document date",
    "CONTENT_AFTER_CREATION":  "Content dates are after the file was created",
    "FUTURE_DATES":            "Document contains future dates",
    "HIGH_DUPLICATE_RATE":     "Many duplicate transactions found",
    "ROUND_NUMBER_BIAS":       "Unusual number of round-figure transactions",
    "PERIOD_GAP_VS_OTHER_STATEMENTS": "Statement period leaves a gap vs. other documents",
    "ACCOUNT_NAME_MISMATCH":   "Account holder name disagrees with other documents",
    "ACCOUNT_NUMBER_MISMATCH": "Account number disagrees with other documents",
    "NO_TEMPLATE_MATCH":       "Bank format not recognised",
    "HINT_MISMATCH":           "Statement does not match the specified bank",
    "PAGE_INCONSISTENCY":      "Pages have different sizes",
    "HEADER_INCONSISTENCY":    "Page headers do not match throughout",
    "DPI_INCONSISTENCY":       "Images have inconsistent quality",
    "EXCESSIVE_FONTS":         "Unusually many fonts used",
    "TEXT_OVER_IMAGE":         "Text layered over scanned images",
    "EXPECTED_SIGNATURE_MISSING": "Expected bank digital signature is missing",
}


def _label_for(code: str) -> str:
    """Return a human-readable label for a flag code. Falls back to a
    de-snake-cased version of the code so unknown flags still read."""
    if code in _FLAG_LABELS:
        return _FLAG_LABELS[code]
    return code.replace("_", " ").title()


@router.get(
    "/analytics/dashboard-summary",
    tags=["analytics"],
)
def dashboard_summary(
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
) -> Dict[str, Any]:
    """Single rollup payload powering the front-end dashboard."""

    # ---- Matter counts -------------------------------------------------
    total_matters = db.query(Matter).count()

    matters_by_status: Dict[str, int] = {s.value: 0 for s in MatterStatus}
    for status, count in (
        db.query(Matter.status, func.count(Matter.id))
        .group_by(Matter.status)
        .all()
    ):
        key = status.value if hasattr(status, "value") else str(status)
        matters_by_status[key] = count

    matters_by_risk: Dict[str, int] = {r.value: 0 for r in RiskRating}
    for risk, count in (
        db.query(Matter.risk_rating, func.count(Matter.id))
        .group_by(Matter.risk_rating)
        .all()
    ):
        if risk is None:
            continue
        key = risk.value if hasattr(risk, "value") else str(risk)
        matters_by_risk[key] = count

    # ---- Document verification counts ----------------------------------
    documents_by_verdict: Dict[str, int] = {v.value: 0 for v in VerificationVerdict}
    for verdict, count in (
        db.query(DocumentVerification.verdict, func.count(DocumentVerification.id))
        .group_by(DocumentVerification.verdict)
        .all()
    ):
        if verdict is None:
            continue
        key = verdict.value if hasattr(verdict, "value") else str(verdict)
        documents_by_verdict[key] = count

    total_documents_verified = sum(documents_by_verdict.values())

    matters_with_blocking_issues = (
        db.query(DocumentVerification.matter_id)
        .filter(DocumentVerification.blocked.is_(True))
        .distinct()
        .count()
    )

    # ---- Top N flag codes (root-cause analysis) ------------------------
    # We pull (code, severity) pairs and bucket in Python — the dataset
    # is bounded by current case volume, and bucketing in Python keeps
    # the labelling logic in one place. If this becomes a hotspot
    # later, swap for a GROUP BY in SQL.
    rows = (
        db.query(
            DocumentVerificationFlag.code,
            DocumentVerificationFlag.severity,
        )
        .filter(DocumentVerificationFlag.code.notin_(_NOISE_FLAG_CODES))
        .filter(DocumentVerificationFlag.severity.notin_(["info", "low"]))
        .all()
    )
    counter: Counter = Counter()
    severity_for_code: Dict[str, str] = {}
    for code, severity in rows:
        counter[code] += 1
        # Keep the highest-severity classification we see per code.
        prev = severity_for_code.get(code)
        if prev is None or _severity_rank(severity) < _severity_rank(prev):
            severity_for_code[code] = severity

    top_flag_codes: List[Dict[str, Any]] = [
        {
            "code": code,
            "severity": severity_for_code.get(code, "medium"),
            "count": count,
            "label": _label_for(code),
        }
        for code, count in counter.most_common(8)
    ]

    # ---- Recent matters ------------------------------------------------
    recent_matter_rows = (
        db.query(Matter)
        .order_by(Matter.created_at.desc())
        .limit(8)
        .all()
    )
    recent_matters = [
        {
            "id": m.id,
            "reference_number": getattr(m, "reference_number", None),
            "client_name": getattr(m, "client_name", None),
            "status": (m.status.value if m.status else None),
            "risk_rating": (m.risk_rating.value if m.risk_rating else None),
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in recent_matter_rows
    ]

    return {
        "total_matters": total_matters,
        "matters_by_status": matters_by_status,
        "matters_by_risk": matters_by_risk,
        "total_documents_verified": total_documents_verified,
        "documents_by_verdict": documents_by_verdict,
        "matters_with_blocking_issues": matters_with_blocking_issues,
        "top_flag_codes": top_flag_codes,
        "recent_matters": recent_matters,
    }


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _severity_rank(s: str) -> int:
    return _SEVERITY_RANK.get((s or "").lower(), 5)
