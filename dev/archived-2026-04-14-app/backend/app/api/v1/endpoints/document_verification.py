"""
Document Verification API Endpoints

Provides:
- GET  /matters/{id}/document-verifications          - list all verifications for a matter
- GET  /matters/{id}/document-verifications/{vid}     - get a single verification with flags
- POST /matters/{id}/document-verifications/{vid}/admin-override - admin override
- GET  /matters/{id}/document-verifications/summary   - summary for the SOF assessment UI
- GET  /matters/{id}/documents/{filename}             - serve uploaded document file
"""
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.db.session import get_sync_db
from app.api.dependencies.auth import require_analyst, require_admin
from app.models.user import User
from app.models import Matter
from app.models.document_verification import (
    DocumentVerification, DocumentVerificationFlag, DocumentVerificationTransaction,
    VerificationVerdict,
)
from app.models.audit import AuditLog, AuditLogAction
from app.models.transaction import TransactionConfig
from app.schemas.document_verification import (
    DocumentVerificationResponse, AdminOverrideRequest, AdminOverrideResponse,
    VerificationSummaryResponse, VerificationFlagResponse,
)
from app.services.evidence_pack_builder import build_evidence_pack

router = APIRouter()


def _dv_enabled(db: Session) -> bool:
    """Whether the Document Verification module is switched on in the
    Configuration page. When off, the verification UI is hidden — the
    summary reports zero documents and the list returns nothing."""
    row = db.query(TransactionConfig).filter(TransactionConfig.key == 'dv_enabled').first()
    return (row is None) or (str(row.value).lower() in ('true', '1', 'yes'))


# ---------------------------------------------------------------------------
# LIST verifications for a matter
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/document-verifications",
    response_model=List[DocumentVerificationResponse],
    tags=["document-verification"],
)
def list_verifications(matter_id: int, current_user: User = Depends(require_analyst), db: Session = Depends(get_sync_db)):
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(404, "Matter not found")

    # Document Verification module switched off on the Configuration page.
    if not _dv_enabled(db):
        return []

    verifications = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.matter_id == matter_id)
        .order_by(DocumentVerification.created_at.desc())
        .all()
    )
    return [v.to_dict() for v in verifications]


# ---------------------------------------------------------------------------
# SUMMARY for SOF Assessment UI (must be before /{verification_id} to avoid
# "summary" being captured as a path parameter)
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/document-verifications/summary",
    response_model=VerificationSummaryResponse,
    tags=["document-verification"],
)
def get_verification_summary(matter_id: int, current_user: User = Depends(require_analyst), db: Session = Depends(get_sync_db)):
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(404, "Matter not found")

    # Document Verification module switched off on the Configuration page —
    # report an empty summary so the SoF results tile hides itself.
    if not _dv_enabled(db):
        return VerificationSummaryResponse()

    verifications = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.matter_id == matter_id)
        .order_by(DocumentVerification.created_at.desc())
        .all()
    )

    if not verifications:
        return VerificationSummaryResponse()

    verified = sum(1 for v in verifications if v.verdict == VerificationVerdict.VERIFIED)
    suspicious = sum(1 for v in verifications if v.verdict == VerificationVerdict.SUSPICIOUS)
    likely_tampered = sum(1 for v in verifications if v.verdict == VerificationVerdict.LIKELY_TAMPERED)
    blocked = sum(1 for v in verifications if v.blocked)
    overridden = sum(1 for v in verifications if v.admin_override)
    avg_score = sum(v.authenticity_score for v in verifications) / len(verifications)

    all_flags = []
    for v in verifications:
        for f in v.flags:
            all_flags.append(VerificationFlagResponse(
                id=f.id,
                pipeline_stage=f.pipeline_stage,
                code=f.code,
                severity=f.severity,
                message=f.message,
                details=f.details,
                created_at=f.created_at.isoformat() if f.created_at else None,
            ))

    has_blocking = any(v.blocked and not v.admin_override for v in verifications)

    return VerificationSummaryResponse(
        total_documents=len(verifications),
        verified_count=verified,
        suspicious_count=suspicious,
        likely_tampered_count=likely_tampered,
        blocked_count=blocked,
        overridden_count=overridden,
        average_score=round(avg_score, 1),
        verifications=[v.to_dict() for v in verifications],
        all_flags=all_flags,
        has_blocking_issues=has_blocking,
    )


# ---------------------------------------------------------------------------
# GET single verification
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/document-verifications/{verification_id}",
    response_model=DocumentVerificationResponse,
    tags=["document-verification"],
)
def get_verification(matter_id: int, verification_id: int, current_user: User = Depends(require_analyst), db: Session = Depends(get_sync_db)):
    v = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.id == verification_id, DocumentVerification.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Verification not found")
    return v.to_dict()


# ---------------------------------------------------------------------------
# ADMIN OVERRIDE
# ---------------------------------------------------------------------------

@router.post(
    "/matters/{matter_id}/document-verifications/{verification_id}/propose-override",
    tags=["document-verification"],
)
def propose_override(
    matter_id: int,
    verification_id: int,
    body: AdminOverrideRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Step 1 of the 4-eyes flow: any analyst proposes lifting the block,
    with a rationale. A DIFFERENT admin must then call admin-override to
    approve it."""
    v = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.id == verification_id, DocumentVerification.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Verification not found")
    if not v.blocked:
        raise HTTPException(409, "Verification is not blocked — nothing to propose")

    v.override_proposed_by = body.admin_user or current_user.email
    v.override_proposed_at = datetime.now(timezone.utc)
    v.override_proposed_rationale = body.rationale

    db.add(AuditLog(
        matter_id=matter_id,
        action=AuditLogAction.UPDATED,
        entity_type="document_verification",
        entity_id=verification_id,
        description=(
            f"Override proposed for verification #{verification_id} by "
            f"{v.override_proposed_by}. Rationale: {body.rationale}"
        ),
        details={
            "verification_id": verification_id,
            "proposer": v.override_proposed_by,
            "rationale": body.rationale,
            "stage": "proposed",
        },
    ))
    db.commit()

    return {
        "verification_id": verification_id,
        "override_proposed_by": v.override_proposed_by,
        "override_proposed_at": v.override_proposed_at.isoformat(),
        "override_proposed_rationale": v.override_proposed_rationale,
        "message": (
            "Override proposed. A second reviewer (different admin) must "
            "now approve via /admin-override."
        ),
    }


@router.post(
    "/matters/{matter_id}/document-verifications/{verification_id}/admin-override",
    response_model=AdminOverrideResponse,
    tags=["document-verification"],
)
def admin_override(
    matter_id: int,
    verification_id: int,
    body: AdminOverrideRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Step 2 of the 4-eyes flow (or step 1 for single-step legacy use):
    an admin approves the override and unblocks downstream processing.

    Four-eyes rule: if `override_proposed_by` is set, the admin
    approving here must be DIFFERENT from the proposer.
    """
    v = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.id == verification_id, DocumentVerification.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Verification not found")

    approver = body.admin_user or current_user.email
    proposer = v.override_proposed_by
    if proposer and proposer.strip().lower() == (approver or "").strip().lower():
        raise HTTPException(
            403,
            "Four-eyes rule: the override must be approved by a different "
            "user than the one who proposed it.",
        )

    previous_verdict = v.verdict.value if v.verdict else "unknown"

    v.admin_override = True
    v.admin_override_by = approver
    v.admin_override_rationale = body.rationale
    v.admin_override_at = datetime.now(timezone.utc)
    v.blocked = False  # unblock

    # Audit log
    audit = AuditLog(
        matter_id=matter_id,
        action=AuditLogAction.APPROVED,
        entity_type="document_verification",
        entity_id=verification_id,
        description=(
            f"Admin override on document verification #{verification_id} "
            f"(was {previous_verdict}). Rationale: {body.rationale}"
            + (f" [proposed by {proposer}]" if proposer else "")
        ),
        details={
            "verification_id": verification_id,
            "previous_verdict": previous_verdict,
            "admin_user": approver,
            "rationale": body.rationale,
            "proposed_by": proposer,
            "stage": "approved",
        },
    )
    db.add(audit)
    db.commit()

    return AdminOverrideResponse(
        verification_id=verification_id,
        previous_verdict=previous_verdict,
        admin_override=True,
        admin_override_by=approver,
        admin_override_rationale=body.rationale,
        blocked=False,
        message=(
            f"Verification #{verification_id} has been overridden by "
            f"{approver}. Downstream processing unblocked."
        ),
    )


# ---------------------------------------------------------------------------
# ACCEPT verification (single-step reviewer disposition)
# ---------------------------------------------------------------------------

@router.post(
    "/matters/{matter_id}/document-verifications/{verification_id}/accept",
    tags=["document-verification"],
)
def accept_verification(
    matter_id: int,
    verification_id: int,
    body: AdminOverrideRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Single-step reviewer acceptance. Any analyst may accept the
    verdict on a document with a rationale; the action is captured in
    the verification row (admin_override_*) and the audit log. Used by
    the verification tab in the matter detail UI so reviewers can sign
    off Suspicious / Likely-Tampered documents inline rather than going
    through the four-eyes propose+approve flow."""
    v = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.id == verification_id, DocumentVerification.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Verification not found")
    if v.admin_override:
        raise HTTPException(409, "Verification has already been accepted")

    reviewer = body.admin_user or current_user.full_name or current_user.email
    previous_verdict = v.verdict.value if v.verdict else "unknown"

    v.admin_override = True
    v.admin_override_by = reviewer
    v.admin_override_rationale = body.rationale
    v.admin_override_at = datetime.now(timezone.utc)
    v.blocked = False

    db.add(AuditLog(
        matter_id=matter_id,
        user_id=current_user.id,
        action=AuditLogAction.APPROVED,
        entity_type="document_verification",
        entity_id=verification_id,
        description=(
            f"Document verification #{verification_id} ({v.filename}) accepted "
            f"by {reviewer}. Previous verdict: {previous_verdict}. "
            f"Rationale: {body.rationale}"
        ),
        details={
            "verification_id": verification_id,
            "filename": v.filename,
            "previous_verdict": previous_verdict,
            "reviewer": reviewer,
            "rationale": body.rationale,
            "stage": "accepted",
        },
    ))
    db.commit()
    db.refresh(v)
    return v.to_dict()


# ---------------------------------------------------------------------------
# TRANSACTIONS extracted for a verification
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/document-verifications/{verification_id}/transactions",
    tags=["document-verification"],
)
def get_verification_transactions(
    matter_id: int,
    verification_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Return all extracted transactions for a verification — used by the
    reviewer UI to preview CSV / statement-only uploads."""
    v = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.id == verification_id, DocumentVerification.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Verification not found")

    rows = (
        db.query(DocumentVerificationTransaction)
        .filter(DocumentVerificationTransaction.verification_id == verification_id)
        .order_by(DocumentVerificationTransaction.id.asc())
        .all()
    )
    return [
        {
            "id": t.id,
            "date": t.date,
            "description": t.description,
            "amount": t.amount,
            "direction": t.direction,
            "balance": t.balance,
            "transaction_type": t.transaction_type,
        }
        for t in rows
    ]


# ---------------------------------------------------------------------------
# AUDIT TRAIL for a verification
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/document-verifications/{verification_id}/audit-trail",
    tags=["document-verification"],
)
def get_verification_audit_trail(
    matter_id: int,
    verification_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Return the audit log entries for a single verification."""
    v = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.id == verification_id, DocumentVerification.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Verification not found")

    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "document_verification",
            AuditLog.entity_id == verification_id,
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "action": r.action.value if r.action else None,
            "description": r.description,
            "details": r.details,
            "timestamp": r.created_at.isoformat() if r.created_at else None,
            "user": (r.details or {}).get("admin_user") if isinstance(r.details, dict) else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# EVIDENCE PACK export
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/document-verifications/{verification_id}/evidence-pack.pdf",
    tags=["document-verification"],
)
def download_evidence_pack(
    matter_id: int,
    verification_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Generate a PDF report covering the verification: header, all flags
    with severity and details, and the audit trail. Streams the bytes
    directly so we don't write a temp file to disk."""
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(404, "Matter not found")
    v = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.id == verification_id, DocumentVerification.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Verification not found")

    flag_rows = (
        db.query(DocumentVerificationFlag)
        .filter(DocumentVerificationFlag.verification_id == verification_id)
        .all()
    )
    audit_rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "document_verification",
            AuditLog.entity_id == verification_id,
        )
        .order_by(AuditLog.created_at.asc())
        .all()
    )

    pdf_bytes = build_evidence_pack(
        matter={
            "id": matter.id,
            "reference_number": getattr(matter, "reference_number", None),
            "client_name": getattr(matter, "client_name", None),
        },
        verification={
            "id": v.id,
            "filename": v.filename,
            "file_category": v.file_category,
            "file_hash": v.file_hash,
            "identified_bank_template": v.identified_bank_template,
            "verdict": v.verdict.value if v.verdict else None,
            "authenticity_score": v.authenticity_score,
            "structural_pipeline_score": v.structural_pipeline_score,
            "statement_pipeline_score": v.statement_pipeline_score,
            "verification_phase": v.verification_phase,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "admin_override": bool(v.admin_override),
            "admin_override_by": v.admin_override_by,
            "admin_override_rationale": v.admin_override_rationale,
            "admin_override_at": v.admin_override_at.isoformat() if v.admin_override_at else None,
        },
        flags=[
            {
                "code": f.code,
                "severity": f.severity,
                "message": f.message,
                "pipeline_stage": f.pipeline_stage,
                "details": f.details,
            }
            for f in flag_rows
        ],
        audit_entries=[
            {
                "timestamp": a.created_at.isoformat() if a.created_at else "",
                "action": a.action.value if a.action else "",
                "description": a.description or "",
                "user": (a.details or {}).get("admin_user") if isinstance(a.details, dict) else "",
            }
            for a in audit_rows
        ],
    )

    safe_filename = f"verification-{verification_id}-evidence-pack.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


# ---------------------------------------------------------------------------
# SERVE uploaded document file
# ---------------------------------------------------------------------------

UPLOAD_ROOT = "/app/uploads"

# Map extensions to MIME types
_MIME_MAP = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


@router.get(
    "/matters/{matter_id}/documents/{filename}",
    tags=["document-verification"],
)
def serve_document(
    matter_id: int,
    filename: str,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Serve an uploaded document file from disk."""
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(404, "Matter not found")

    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    ext = os.path.splitext(safe_filename)[1].lower()
    media_type = _MIME_MAP.get(ext, "application/octet-stream")

    file_path = os.path.join(UPLOAD_ROOT, str(matter_id), safe_filename)
    if os.path.isfile(file_path):
        return FileResponse(file_path, media_type=media_type, filename=safe_filename)

    # Fall back to the copy held in the database. The upload directory
    # on the host is ephemeral — files uploaded before a redeploy are
    # no longer on disk, so the DB copy is the durable source. Match on
    # the stored disk name OR the original upload name, so a download
    # link built from the original filename still resolves.
    from sqlalchemy import or_
    dv = (
        db.query(DocumentVerification)
        .filter(
            DocumentVerification.matter_id == matter_id,
            or_(
                DocumentVerification.disk_filename == safe_filename,
                DocumentVerification.filename == filename,
            ),
        )
        .order_by(DocumentVerification.created_at.desc())
        .first()
    )
    if dv is not None and dv.file_bytes:
        return Response(
            content=bytes(dv.file_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{safe_filename}"'},
        )

    raise HTTPException(404, "File not found")
