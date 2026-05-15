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
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.db.session import get_sync_db
from app.api.dependencies.auth import require_analyst, require_admin
from app.models.user import User
from app.models import Matter
from app.models.document_verification import (
    DocumentVerification, DocumentVerificationFlag, VerificationVerdict,
)
from app.models.audit import AuditLog, AuditLogAction
from app.schemas.document_verification import (
    DocumentVerificationResponse, AdminOverrideRequest, AdminOverrideResponse,
    VerificationSummaryResponse, VerificationFlagResponse,
)

router = APIRouter()


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
    v = (
        db.query(DocumentVerification)
        .filter(DocumentVerification.id == verification_id, DocumentVerification.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Verification not found")

    previous_verdict = v.verdict.value if v.verdict else "unknown"

    v.admin_override = True
    v.admin_override_by = body.admin_user
    v.admin_override_rationale = body.rationale
    v.admin_override_at = datetime.now(timezone.utc)
    v.blocked = False  # unblock

    # Audit log
    audit = AuditLog(
        matter_id=matter_id,
        action=AuditLogAction.APPROVED,
        entity_type="document_verification",
        entity_id=verification_id,
        description=f"Admin override on document verification #{verification_id} (was {previous_verdict}). Rationale: {body.rationale}",
        details={
            "verification_id": verification_id,
            "previous_verdict": previous_verdict,
            "admin_user": body.admin_user,
            "rationale": body.rationale,
        },
    )
    db.add(audit)
    db.commit()

    return AdminOverrideResponse(
        verification_id=verification_id,
        previous_verdict=previous_verdict,
        admin_override=True,
        admin_override_by=body.admin_user,
        admin_override_rationale=body.rationale,
        blocked=False,
        message=f"Verification #{verification_id} has been overridden by {body.admin_user}. Downstream processing unblocked.",
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

    file_path = os.path.join(UPLOAD_ROOT, str(matter_id), safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(404, "File not found")

    ext = os.path.splitext(safe_filename)[1].lower()
    media_type = _MIME_MAP.get(ext, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type, filename=safe_filename)
