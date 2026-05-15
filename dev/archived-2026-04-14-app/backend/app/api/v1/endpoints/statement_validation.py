"""
Statement Authenticity Validation API Endpoints

Provides:
- GET  /matters/{id}/statement-validations          – list all validations for a matter
- GET  /matters/{id}/statement-validations/{vid}     – get a single validation with flags
- POST /matters/{id}/statement-validations/{vid}/admin-override – admin override
- GET  /matters/{id}/statement-validations/summary   – summary for the SOF assessment UI
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import get_sync_db
from app.api.dependencies.auth import require_analyst, require_admin
from app.models.user import User
from app.models import Matter
from app.models.statement_validation import (
    StatementValidation, StatementValidationFlag, StatementValidationTransaction,
    ValidationStatus, FlagSeverity,
)
from app.models.audit import AuditLog, AuditLogAction
from app.schemas.statement_validation import (
    StatementValidationResponse, AdminOverrideRequest, AdminOverrideResponse,
    ValidationSummaryResponse, ValidationFlagResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# LIST validations for a matter
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/statement-validations",
    response_model=List[StatementValidationResponse],
    tags=["statement-validation"],
)
def list_validations(matter_id: int, current_user: User = Depends(require_analyst), db: Session = Depends(get_sync_db)):
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(404, "Matter not found")

    validations = (
        db.query(StatementValidation)
        .filter(StatementValidation.matter_id == matter_id)
        .order_by(StatementValidation.created_at.desc())
        .all()
    )
    return [v.to_dict() for v in validations]


# ---------------------------------------------------------------------------
# GET single validation
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/statement-validations/{validation_id}",
    response_model=StatementValidationResponse,
    tags=["statement-validation"],
)
def get_validation(matter_id: int, validation_id: int, current_user: User = Depends(require_analyst), db: Session = Depends(get_sync_db)):
    v = (
        db.query(StatementValidation)
        .filter(StatementValidation.id == validation_id, StatementValidation.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Validation not found")
    return v.to_dict()


# ---------------------------------------------------------------------------
# ADMIN OVERRIDE
# ---------------------------------------------------------------------------

@router.post(
    "/matters/{matter_id}/statement-validations/{validation_id}/admin-override",
    response_model=AdminOverrideResponse,
    tags=["statement-validation"],
)
def admin_override(
    matter_id: int,
    validation_id: int,
    body: AdminOverrideRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    v = (
        db.query(StatementValidation)
        .filter(StatementValidation.id == validation_id, StatementValidation.matter_id == matter_id)
        .first()
    )
    if not v:
        raise HTTPException(404, "Validation not found")

    previous_status = v.status.value if v.status else "unknown"

    v.admin_override = True
    v.admin_override_by = body.admin_user
    v.admin_override_rationale = body.rationale
    v.admin_override_at = datetime.now(timezone.utc)
    v.blocked = False  # unblock

    # Audit log
    audit = AuditLog(
        matter_id=matter_id,
        action=AuditLogAction.APPROVED,
        entity_type="statement_validation",
        entity_id=validation_id,
        description=f"Admin override on statement validation #{validation_id} (was {previous_status}). Rationale: {body.rationale}",
        details={
            "validation_id": validation_id,
            "previous_status": previous_status,
            "admin_user": body.admin_user,
            "rationale": body.rationale,
        },
    )
    db.add(audit)
    db.commit()

    return AdminOverrideResponse(
        validation_id=validation_id,
        previous_status=previous_status,
        admin_override=True,
        admin_override_by=body.admin_user,
        admin_override_rationale=body.rationale,
        blocked=False,
        message=f"Validation #{validation_id} has been overridden by {body.admin_user}. Downstream processing unblocked.",
    )


# ---------------------------------------------------------------------------
# SUMMARY for SOF Assessment UI
# ---------------------------------------------------------------------------

@router.get(
    "/matters/{matter_id}/statement-validations/summary",
    response_model=ValidationSummaryResponse,
    tags=["statement-validation"],
)
def get_validation_summary(matter_id: int, current_user: User = Depends(require_analyst), db: Session = Depends(get_sync_db)):
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(404, "Matter not found")

    validations = (
        db.query(StatementValidation)
        .filter(StatementValidation.matter_id == matter_id)
        .order_by(StatementValidation.created_at.desc())
        .all()
    )

    if not validations:
        return ValidationSummaryResponse()

    trusted = sum(1 for v in validations if v.status == ValidationStatus.TRUSTED)
    review = sum(1 for v in validations if v.status == ValidationStatus.REVIEW)
    high_risk = sum(1 for v in validations if v.status == ValidationStatus.HIGH_RISK)
    blocked = sum(1 for v in validations if v.blocked)
    overridden = sum(1 for v in validations if v.admin_override)
    avg_score = sum(v.authenticity_score for v in validations) / len(validations)

    all_flags = []
    for v in validations:
        for f in v.flags:
            all_flags.append(ValidationFlagResponse(
                id=f.id,
                pipeline_stage=f.pipeline_stage,
                code=f.code,
                severity=f.severity.value if f.severity else "medium",
                message=f.message,
                details=f.details,
                created_at=f.created_at.isoformat() if f.created_at else None,
            ))

    has_blocking = any(v.blocked and not v.admin_override for v in validations)

    return ValidationSummaryResponse(
        total_statements=len(validations),
        trusted_count=trusted,
        review_count=review,
        high_risk_count=high_risk,
        blocked_count=blocked,
        overridden_count=overridden,
        average_score=round(avg_score, 1),
        validations=[v.to_dict() for v in validations],
        all_flags=all_flags,
        has_blocking_issues=has_blocking,
    )
