"""
E-IDV (Electronic Identity Verification) endpoints.

Routes:
- POST /matters/{matter_id}/eidv
    Start a verification for a subject (client / beneficial_owner /
    giftor). provider='manual' returns the structured checklist the
    solicitor completes; provider='complycube' returns 409 with
    guidance while COMPLYCUBE_API_KEY is unset.
- PUT  /matters/{matter_id}/eidv/{check_id}/manual-result
    Complete a manual verification with the checklist answers.
- GET  /matters/{matter_id}/eidv
    List verifications for the matter.

Compliance posture: manual verification is the TRADITIONAL route and
does NOT constitute DIATF-certified E-IDV (HMT Feb 2026 guidance on
MLR 2017 reg 28(19)) — the caveat is embedded in every manual payload
and diatf_certified is False on those rows.
"""
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_analyst, require_matter_access
from app.db.session import get_sync_db
from app.models.audit import AuditLog, AuditLogAction
from app.models.eidv import EidvCheck, EidvStatus, EidvSubjectType
from app.models.user import User
from app.services.companies_house import ConfigurationError
from app.services.eidv_providers import (
    MANUAL_METHOD_CAVEAT,
    ManualEidvProvider,
    get_provider,
)

router = APIRouter()

_SUBJECT_TYPES = {t.value for t in EidvSubjectType}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EidvCreateRequest(BaseModel):
    subject_type: str = Field(..., description="client | beneficial_owner | giftor")
    subject_name: str = Field(..., min_length=2, max_length=255)
    subject_dob: Optional[str] = Field(None, description="ISO date YYYY-MM-DD")
    subject_email: Optional[str] = Field(None, max_length=255)
    provider: str = Field("manual", description="manual | complycube")

    @field_validator("subject_type")
    @classmethod
    def _valid_subject_type(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in _SUBJECT_TYPES:
            raise ValueError(
                f"subject_type must be one of: {', '.join(sorted(_SUBJECT_TYPES))}"
            )
        return v

    @field_validator("subject_dob")
    @classmethod
    def _valid_dob(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        try:
            parsed = date.fromisoformat(v)
        except ValueError:
            raise ValueError("subject_dob must be an ISO date (YYYY-MM-DD)")
        if parsed >= date.today():
            raise ValueError("subject_dob must be in the past")
        return v


class ManualResultRequest(BaseModel):
    document_type: str = Field(..., min_length=2, max_length=100)
    document_number: str = Field(..., min_length=2, max_length=100)
    expiry_date: str = Field(..., description="ISO date YYYY-MM-DD")
    likeness_confirmed: bool
    certified_copy_details: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=4000)

    @field_validator("expiry_date")
    @classmethod
    def _valid_expiry(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("expiry_date must be an ISO date (YYYY-MM-DD)")
        return v


# ---------------------------------------------------------------------------
# POST /matters/{matter_id}/eidv — start a verification
# ---------------------------------------------------------------------------

@router.post("/matters/{matter_id}/eidv", status_code=201, tags=["eidv"])
def create_eidv_check(
    matter_id: int,
    body: EidvCreateRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)

    try:
        provider = get_provider(body.provider)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    subject = {
        "name": body.subject_name.strip(),
        "dob": body.subject_dob,
        "email": body.subject_email,
    }
    try:
        created = provider.create_verification(subject)
    except ConfigurationError as exc:
        # ComplyCube (or any live provider) without an API key — clear
        # guidance rather than a broken flow.
        raise HTTPException(409, str(exc))

    check = EidvCheck(
        matter_id=matter_id,
        subject_type=body.subject_type,
        subject_name=subject["name"],
        subject_dob=body.subject_dob,
        subject_email=body.subject_email,
        provider=provider.name,
        provider_ref=created.get("provider_ref"),
        method="manual" if provider.name == "manual" else "electronic",
        status=EidvStatus.PENDING.value,
        diatf_certified=False,  # set true only when a certified provider PASSES
        created_by_id=current_user.id,
    )
    db.add(check)
    db.flush()

    db.add(
        AuditLog(
            matter_id=matter_id,
            user_id=current_user.id,
            action=AuditLogAction.CREATED,
            entity_type="eidv_check",
            entity_id=check.id,
            description=(
                f"E-IDV started for {check.subject_name} "
                f"({check.subject_type}) via {provider.name}"
            ),
            details={"provider": provider.name, "subject_type": check.subject_type},
        )
    )
    db.commit()
    db.refresh(check)

    response = {**check.to_dict(), "client_url": created.get("client_url")}
    if provider.name == "manual":
        response["instructions"] = created.get("instructions")
        response["caveat"] = MANUAL_METHOD_CAVEAT
    return response


# ---------------------------------------------------------------------------
# PUT /matters/{matter_id}/eidv/{check_id}/manual-result — complete manual
# ---------------------------------------------------------------------------

@router.put("/matters/{matter_id}/eidv/{check_id}/manual-result", tags=["eidv"])
def complete_manual_result(
    matter_id: int,
    check_id: int,
    body: ManualResultRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)
    check = (
        db.query(EidvCheck)
        .filter(EidvCheck.id == check_id, EidvCheck.matter_id == matter_id)
        .first()
    )
    if not check:
        raise HTTPException(404, "E-IDV check not found")
    if check.provider != "manual":
        raise HTTPException(
            409,
            f"This check uses the '{check.provider}' provider — manual "
            "results can only be recorded on manual checks.",
        )
    if check.completed_at is not None:
        raise HTTPException(409, "This manual verification has already been completed.")

    expired = date.fromisoformat(body.expiry_date) < date.today()
    result = ManualEidvProvider.build_result(
        document_type=body.document_type.strip(),
        document_number=body.document_number.strip(),
        expiry_date=body.expiry_date,
        likeness_confirmed=body.likeness_confirmed,
        certified_copy_details=(body.certified_copy_details or "").strip() or None,
        notes=(body.notes or "").strip() or None,
        document_expired=expired,
    )

    check.status = result["status"]
    check.checks = result["checks"]
    check.evidence_notes = _format_evidence_notes(body, expired)
    check.method = "manual"
    check.diatf_certified = False  # manual is never DIATF-certified
    check.completed_by_id = current_user.id
    check.completed_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            matter_id=matter_id,
            user_id=current_user.id,
            action=AuditLogAction.UPDATED,
            entity_type="eidv_check",
            entity_id=check.id,
            description=(
                f"Manual identity verification completed for "
                f"{check.subject_name} ({check.subject_type}) — {check.status}"
            ),
            details={
                "status": check.status,
                "document_type": body.document_type,
                "likeness_confirmed": body.likeness_confirmed,
                "document_expired": expired,
            },
        )
    )
    db.commit()
    db.refresh(check)

    return {**check.to_dict(), "report": result["report"], "caveat": MANUAL_METHOD_CAVEAT}


def _format_evidence_notes(body: ManualResultRequest, expired: bool) -> str:
    lines = [
        f"Document type: {body.document_type.strip()}",
        f"Document number: {body.document_number.strip()}",
        f"Expiry date: {body.expiry_date}" + (" (EXPIRED at time of check)" if expired else ""),
        f"Likeness confirmed: {'yes' if body.likeness_confirmed else 'NO'}",
    ]
    if body.certified_copy_details and body.certified_copy_details.strip():
        lines.append(f"Certified copy: {body.certified_copy_details.strip()}")
    if body.notes and body.notes.strip():
        lines.append(f"Notes: {body.notes.strip()}")
    lines.append(MANUAL_METHOD_CAVEAT)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GET /matters/{matter_id}/eidv — list verifications
# ---------------------------------------------------------------------------

@router.get("/matters/{matter_id}/eidv", tags=["eidv"])
def list_eidv_checks(
    matter_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)
    checks = (
        db.query(EidvCheck)
        .filter(EidvCheck.matter_id == matter_id)
        .order_by(EidvCheck.created_at.desc())
        .all()
    )
    return {
        "items": [c.to_dict() for c in checks],
        "manual_caveat": MANUAL_METHOD_CAVEAT,
    }
