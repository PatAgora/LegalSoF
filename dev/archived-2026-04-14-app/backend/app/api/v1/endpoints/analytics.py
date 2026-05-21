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

from app.api.dependencies.auth import require_analyst, require_admin
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
    from app.api.v1.endpoints.matters import derive_matter_status, MATTER_STATUSES
    from app.models.assessment_storage import AssessmentStorage

    all_matters = db.query(Matter).all()
    total_matters = len(all_matters)

    # Bucket by the single derived matter status so the dashboard
    # agrees with every other view.
    storage_map = {
        row.matter_id: row.data
        for row in db.query(AssessmentStorage).all() if row.data
    }
    matters_by_status: Dict[str, int] = {s: 0 for s in MATTER_STATUSES}
    derived_for: Dict[int, str] = {}
    for m in all_matters:
        ds = derive_matter_status(m, storage_map.get(m.id))
        derived_for[m.id] = ds
        matters_by_status[ds] = matters_by_status.get(ds, 0) + 1

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
            "status": derived_for.get(m.id) or derive_matter_status(m, storage_map.get(m.id)),
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


# Plain-English labels for the source-of-funds gap types recorded in
# each matter's evidence-match differences.
_GAP_LABELS: Dict[str, str] = {
    "untraced_funds":   "Funds not traced to a declared source",
    "funds_discrepancy": "Declared amount not fully evidenced",
    "statement_gap":    "Missing statement period",
    "missing":          "Required document field missing",
}


@router.get("/analytics/rca-dashboard", tags=["analytics"])
def rca_dashboard(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
) -> Dict[str, Any]:
    """Root-cause analysis rollup across every matter — the recurring
    issues, risk concentration, compliance loop and derived training
    recommendations that support the firm's continuous learning."""
    from app.models.assessment_storage import AssessmentStorage

    all_matters = db.query(Matter).all()
    total_matters = len(all_matters)

    storage_rows = [row.data for row in db.query(AssessmentStorage).all() if row.data]
    matters_assessed = sum(
        1 for s in storage_rows
        if (s.get("assessment_result") or {}).get("claims") is not None
    )

    # --- Recurring document-verification flags --------------------------
    flag_rows = (
        db.query(DocumentVerificationFlag.code, DocumentVerificationFlag.severity)
        .filter(DocumentVerificationFlag.code.notin_(_NOISE_FLAG_CODES))
        .filter(DocumentVerificationFlag.severity.notin_(["info", "low"]))
        .all()
    )
    flag_counter: Counter = Counter()
    flag_severity: Dict[str, str] = {}
    for code, severity in flag_rows:
        flag_counter[code] += 1
        prev = flag_severity.get(code)
        if prev is None or _severity_rank(severity) < _severity_rank(prev):
            flag_severity[code] = severity
    top_document_flags = [
        {"code": c, "label": _label_for(c), "severity": flag_severity.get(c, "medium"), "count": n}
        for c, n in flag_counter.most_common(8)
    ]

    # --- SoF gap types, source-type breakdown, referrals (from storage) -
    gap_counter: Counter = Counter()
    source_stats: Dict[str, Dict[str, int]] = {}
    referral_reasons: Counter = Counter()
    claims_referred = 0
    # Per-user activity — who refers to compliance and who signs claims off.
    user_stats: Dict[str, Dict[str, int]] = {}

    def _user(name) -> Dict[str, int]:
        key = (str(name).strip() or "Unknown")
        return user_stats.setdefault(key, {"referrals": 0, "verified": 0})

    for s in storage_rows:
        ar = s.get("assessment_result") or {}
        claims = ar.get("claims") or []
        evidence = ar.get("evidence_matches") or []
        actions = s.get("claim_actions") or {}
        for idx, claim in enumerate(claims):
            st = (str(claim.get("source_type") or "other").lower().strip()) or "other"
            rec = source_stats.setdefault(st, {"total": 0, "verified": 0})
            rec["total"] += 1
            act = actions.get(str(idx)) or {}
            suff = act.get("sufficient")
            if suff:
                rec["verified"] += 1
                if isinstance(suff, dict) and suff.get("by"):
                    _user(suff["by"])["verified"] += 1
            comp = act.get("compliance") or {}
            if comp.get("state"):
                claims_referred += 1
                reason = (comp.get("reason") or "").strip()
                if reason:
                    referral_reasons[reason[:90]] += 1
                if comp.get("sent_by"):
                    _user(comp["sent_by"])["referrals"] += 1
        # Non-claim review items (e.g. Transaction Review) referrals.
        for entry in (s.get("item_actions") or {}).values():
            comp = (entry or {}).get("compliance") or {}
            if comp.get("state"):
                claims_referred += 1
                reason = (comp.get("reason") or "").strip()
                if reason:
                    referral_reasons[reason[:90]] += 1
                if comp.get("sent_by"):
                    _user(comp["sent_by"])["referrals"] += 1
        for ev in evidence:
            dv = (ev or {}).get("document_verification") or {}
            for d in (dv.get("differences") or []):
                field = str(d.get("field") or "").lower()
                if d.get("severity") == "missing":
                    gap_counter["missing"] += 1
                elif field in _GAP_LABELS:
                    gap_counter[field] += 1

    sof_gap_types = [
        {"key": k, "label": _GAP_LABELS.get(k, k), "count": n}
        for k, n in gap_counter.most_common()
    ]
    source_types = sorted(
        (
            {
                "source_type": st,
                "label": st.replace("_", " ").title(),
                "total": v["total"],
                "verified": v["verified"],
                "outstanding": v["total"] - v["verified"],
            }
            for st, v in source_stats.items()
        ),
        key=lambda x: x["total"],
        reverse=True,
    )

    # --- Risk and matter-type concentration -----------------------------
    matters_by_risk: Dict[str, int] = {r.value: 0 for r in RiskRating}
    matters_by_type: Dict[str, int] = {}
    for m in all_matters:
        if m.risk_rating is not None:
            rkey = m.risk_rating.value if hasattr(m.risk_rating, "value") else str(m.risk_rating)
            matters_by_risk[rkey] = matters_by_risk.get(rkey, 0) + 1
        tt = getattr(m, "transaction_type", None)
        if tt is not None:
            tkey = tt.value if hasattr(tt, "value") else str(tt)
            matters_by_type[tkey] = matters_by_type.get(tkey, 0) + 1

    # --- Compliance loop ------------------------------------------------
    matters_referred = sum(
        1 for m in all_matters
        if (getattr(m, "compliance_status", None) or "none") != "none"
    )
    matters_returned = sum(
        1 for m in all_matters
        if (getattr(m, "compliance_status", None) or "none") == "returned"
    )
    top_reasons = [{"reason": r, "count": n} for r, n in referral_reasons.most_common(5)]

    # --- Derived training recommendations -------------------------------
    recs: List[Dict[str, str]] = []
    if gap_counter.get("untraced_funds", 0) >= 3:
        recs.append({
            "title": "Tracing funds to source",
            "detail": "Untraced credits recur across matters. Reinforce obtaining the full "
                      "statement history and following each credit back to its origin.",
            "basis": f"{gap_counter['untraced_funds']} untraced-funds findings",
        })
    if gap_counter.get("statement_gap", 0) >= 3:
        recs.append({
            "title": "Requesting complete statement coverage",
            "detail": "Statement gaps recur. Train staff to request a continuous statement "
                      "history at the outset of a matter.",
            "basis": f"{gap_counter['statement_gap']} statement-gap findings",
        })
    for st in source_types:
        if st["total"] >= 3 and st["verified"] / max(1, st["total"]) < 0.5:
            recs.append({
                "title": f"Evidencing {st['label'].lower()} claims",
                "detail": f"{st['label']} claims are frequently left without sufficient "
                          f"evidence. Review what is requested for this source type.",
                "basis": f"{st['outstanding']} of {st['total']} {st['label'].lower()} claims outstanding",
            })
    crit_flags = sum(f["count"] for f in top_document_flags if f["severity"] == "critical")
    if crit_flags:
        recs.append({
            "title": "Spotting document red flags",
            "detail": "Critical document-verification flags are recurring. Train fee earners "
                      "on the tampering indicators the pipeline detects.",
            "basis": f"{crit_flags} critical document-verification flags",
        })
    if claims_referred >= 5:
        recs.append({
            "title": "Earlier source-of-funds escalation",
            "detail": "A high volume of claims reach compliance. Consider whether issues can "
                      "be resolved earlier in the fee earner's own review.",
            "basis": f"{claims_referred} claims referred to compliance",
        })

    # --- Per-user metrics -----------------------------------------------
    user_metrics = sorted(
        (
            {
                "user": u,
                "referrals": v["referrals"],
                "verified": v["verified"],
            }
            for u, v in user_stats.items()
        ),
        key=lambda x: (x["referrals"], x["verified"]),
        reverse=True,
    )
    # If one user is referring disproportionately, surface it for review.
    if len(user_metrics) >= 2 and user_metrics[0]["referrals"] >= 3:
        top = user_metrics[0]
        rest = sum(u["referrals"] for u in user_metrics[1:])
        if top["referrals"] > rest:
            recs.append({
                "title": f"Review {top['user']}'s source-of-funds approach",
                "detail": f"{top['user']} accounts for most of the compliance referrals. "
                          f"A coaching conversation may resolve issues before escalation.",
                "basis": f"{top['referrals']} of {top['referrals'] + rest} referrals",
            })

    return {
        "total_matters": total_matters,
        "matters_assessed": matters_assessed,
        "top_document_flags": top_document_flags,
        "sof_gap_types": sof_gap_types,
        "source_types": source_types,
        "matters_by_risk": matters_by_risk,
        "matters_by_type": matters_by_type,
        "compliance": {
            "matters_referred": matters_referred,
            "matters_returned": matters_returned,
            "claims_referred": claims_referred,
            "top_reasons": top_reasons,
        },
        "user_metrics": user_metrics,
        "training_recommendations": recs,
    }
