"""
Client evidence-upload portal endpoints.

Staff (analyst+) generate a time-limited, revocable upload link for a
matter; the client opens /portal/<token> with NO account and uploads
bank statements / supporting documents, which run through exactly the
same processing pipeline as staff uploads (via
sof_assessment.process_uploaded_file).

Security posture:
  - The token is the only credential: 256-bit random
    (secrets.token_urlsafe(32)), stored server-side with expiry, an
    upload budget, and a revoked flag.
  - Public endpoints return a NEUTRAL 404 for any invalid token —
    never confirming whether a matter or link ever existed.
  - Public responses are data-minimised: matter reference plus
    "first name + surname initial" only.
  - client_info uploads are NOT accepted from the portal — clients may
    only submit evidence (bank_statement / supporting_doc), never the
    structured client-details input that drives the assessment.
  - Strict per-IP rate limits on the public routes.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import limiter, client_ip
from app.db.session import get_sync_db
from app.api.dependencies.auth import require_analyst, require_matter_access
from app.api.v1.endpoints.sof_assessment import _resolve_file_type, process_uploaded_file
from app.models import Matter
from app.models.audit import AuditLog, AuditLogAction
from app.models.portal import ClientUploadToken
from app.models.user import User

router = APIRouter()

logger = structlog.get_logger(__name__)

FIRM_NAME = "Agora Consulting AI"

# Neutral message for ANY invalid-token condition — must not leak
# whether the matter or the link ever existed.
_INVALID_LINK_DETAIL = "This upload link is invalid or has expired."

PORTAL_ALLOWED_CATEGORIES = ("bank_statement", "supporting_doc")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_utc(dt_val: Optional[datetime]) -> Optional[datetime]:
    """Normalise a DB datetime to timezone-aware UTC for comparison."""
    if dt_val is None:
        return None
    if dt_val.tzinfo is None:
        return dt_val.replace(tzinfo=timezone.utc)
    return dt_val


def _token_is_active(row: ClientUploadToken) -> bool:
    if row.revoked:
        return False
    expires = _as_utc(row.expires_at)
    if expires is None or expires <= datetime.now(timezone.utc):
        return False
    if (row.upload_count or 0) >= (row.max_uploads or 0):
        return False
    return True


def _get_active_token_or_404(db: Session, token: str) -> ClientUploadToken:
    """Look up a token and 404 (neutrally) unless it is fully usable."""
    row = (
        db.query(ClientUploadToken)
        .filter(ClientUploadToken.token == token)
        .first()
    )
    if row is None or not _token_is_active(row):
        raise HTTPException(status_code=404, detail=_INVALID_LINK_DETAIL)
    return row


def _minimised_client_name(full_name: Optional[str]) -> str:
    """Data minimisation: first name plus surname initial only."""
    parts = [p for p in (full_name or "").strip().split() if p]
    if not parts:
        return "the client"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}."


def _link_to_dict(row: ClientUploadToken) -> dict:
    return {
        "id": row.id,
        "token": row.token,
        "url_path": f"/portal/{row.token}",
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "max_uploads": row.max_uploads,
        "upload_count": row.upload_count,
        "revoked": row.revoked,
        "active": _token_is_active(row),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ---------------------------------------------------------------------------
# Staff endpoints (authenticated)
# ---------------------------------------------------------------------------

class CreateLinkRequest(BaseModel):
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=30)


@router.post("/matters/{matter_id}/client-upload-link")
@limiter.limit("20/minute")
async def create_client_upload_link(
    request: Request,
    matter_id: int,
    body: Optional[CreateLinkRequest] = None,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Create a client evidence-upload link for a matter."""
    matter = require_matter_access(matter_id, current_user, db)

    expires_in_days = 14
    if body and body.expires_in_days:
        expires_in_days = body.expires_in_days

    row = ClientUploadToken(
        token=secrets.token_urlsafe(32),
        matter_id=matter.id,
        created_by_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
    )
    db.add(row)
    db.flush()
    db.add(AuditLog(
        matter_id=matter.id,
        user_id=current_user.id,
        action=AuditLogAction.CREATED,
        entity_type="client_upload_token",
        entity_id=row.id,
        description=(
            f"Client upload link created for matter {matter.reference_number} "
            f"(expires in {expires_in_days} days, up to {row.max_uploads or 20} uploads)."
        ),
        details={"via": "client_portal", "expires_in_days": expires_in_days},
        ip_address=client_ip(request),
    ))
    db.commit()
    db.refresh(row)

    logger.info("client_upload_link_created", matter_id=matter.id, token_id=row.id)

    return {
        "url_path": f"/portal/{row.token}",
        "token": row.token,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


@router.get("/matters/{matter_id}/client-upload-links")
async def list_client_upload_links(
    matter_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """List upload links for a matter (newest first)."""
    require_matter_access(matter_id, current_user, db)
    rows = (
        db.query(ClientUploadToken)
        .filter(ClientUploadToken.matter_id == matter_id)
        .order_by(ClientUploadToken.created_at.desc())
        .all()
    )
    return {"links": [_link_to_dict(r) for r in rows]}


@router.delete("/matters/{matter_id}/client-upload-link/{token_id}")
async def revoke_client_upload_link(
    matter_id: int,
    token_id: int,
    request: Request,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Revoke a client upload link."""
    matter = require_matter_access(matter_id, current_user, db)
    row = (
        db.query(ClientUploadToken)
        .filter(
            ClientUploadToken.id == token_id,
            ClientUploadToken.matter_id == matter_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Upload link not found")

    row.revoked = True
    db.add(AuditLog(
        matter_id=matter.id,
        user_id=current_user.id,
        action=AuditLogAction.UPDATED,
        entity_type="client_upload_token",
        entity_id=row.id,
        description=f"Client upload link revoked for matter {matter.reference_number}.",
        details={"via": "client_portal", "token_id": row.id},
        ip_address=client_ip(request),
    ))
    db.commit()

    logger.info("client_upload_link_revoked", matter_id=matter.id, token_id=row.id)
    return {"message": "Upload link revoked."}


# ---------------------------------------------------------------------------
# Public portal endpoints (NO auth — token is the credential)
# ---------------------------------------------------------------------------

@router.get("/portal/{token}")
@limiter.limit("30/minute")
async def get_portal_info(
    request: Request,
    token: str,
    db: Session = Depends(get_sync_db),
):
    """Validate an upload link and return the minimal context the
    client-facing page needs. Invalid/expired/revoked/exhausted links
    all return the same neutral 404."""
    row = _get_active_token_or_404(db, token)
    matter = db.query(Matter).filter(Matter.id == row.matter_id).first()
    if matter is None:
        raise HTTPException(status_code=404, detail=_INVALID_LINK_DETAIL)

    return {
        "firm_name": FIRM_NAME,
        "matter_reference": matter.reference_number,
        "client_name": _minimised_client_name(matter.client_name),
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "uploads_remaining": max((row.max_uploads or 0) - (row.upload_count or 0), 0),
    }


@router.post("/portal/{token}/upload")
@limiter.limit("10/minute")
async def portal_upload(
    request: Request,
    token: str,
    file: UploadFile = File(...),
    file_category: str = Form(...),
    db: Session = Depends(get_sync_db),
):
    """Accept one evidence file from the client and run it through the
    standard upload pipeline."""
    # Clients may only submit evidence — never client_info.
    if file_category not in PORTAL_ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="file_category must be 'bank_statement' or 'supporting_doc'",
        )

    row = _get_active_token_or_404(db, token)
    matter = db.query(Matter).filter(Matter.id == row.matter_id).first()
    if matter is None:
        raise HTTPException(status_code=404, detail=_INVALID_LINK_DETAIL)

    # Extension / category validation (same 400s as the staff endpoint).
    _resolve_file_type(file.filename, file_category)

    # Size-capped streaming read — reject before buffering an oversized
    # body. Magic-byte checks run inside process_uploaded_file.
    max_upload_bytes = getattr(settings, 'MAX_UPLOAD_SIZE_MB', 50) * 1024 * 1024
    declared_size = getattr(file, 'size', None)
    if declared_size and declared_size > max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {getattr(settings, 'MAX_UPLOAD_SIZE_MB', 50)}MB upload limit"
        )
    chunks = []
    total_read = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {getattr(settings, 'MAX_UPLOAD_SIZE_MB', 50)}MB upload limit"
            )
        chunks.append(chunk)
    raw_bytes = b"".join(chunks)
    del chunks

    result = await process_uploaded_file(
        db=db,
        matter=matter,
        raw_bytes=raw_bytes,
        filename=file.filename,
        file_category=file_category,
        actor_label="Client (portal)",
        content_type=file.content_type,
    )

    # Consume one upload from the budget and record the audit entry.
    row.upload_count = (row.upload_count or 0) + 1
    db.add(AuditLog(
        matter_id=matter.id,
        user_id=None,
        action=AuditLogAction.UPLOADED,
        entity_type="client_upload_token",
        entity_id=row.id,
        description=(
            f"Client uploaded '{file.filename}' ({file_category}) via the "
            "client portal."
        ),
        details={
            "via": "client_portal",
            "filename": file.filename,
            "file_category": file_category,
        },
        ip_address=client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    ))
    db.commit()

    logger.info(
        "client_portal_upload",
        matter_id=matter.id,
        token_id=row.id,
        file_category=file_category,
        verdict=result.get("verification_verdict"),
    )

    return {
        "message": "File received and processed successfully.",
        "filename": file.filename,
        "uploads_remaining": max((row.max_uploads or 0) - (row.upload_count or 0), 0),
    }
