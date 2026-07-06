"""
Audit Trail & Status History API Endpoints

Provides:
- GET /matters/{matter_id}/audit-trail      - chronological audit log entries for a matter
- GET /matters/{matter_id}/status-history    - all status transitions for a matter
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_sync_db
from app.api.dependencies.auth import require_analyst, require_matter_access
from app.models.user import User
from app.models.audit import AuditLog
from app.models.status_history import MatterStatusHistory

router = APIRouter()


@router.get("/matters/{matter_id}/audit-trail", tags=["audit"])
def get_audit_trail(
    matter_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Return the full audit trail for a matter, oldest first."""
    require_matter_access(matter_id, current_user, db)

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.matter_id == matter_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )

    result = []
    for log in logs:
        user = db.query(User).filter(User.id == log.user_id).first() if log.user_id else None
        result.append({
            "id": log.id,
            "action": log.action.value if log.action else None,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "description": log.description,
            "details": log.details,
            "user_name": user.full_name if user else None,
            "user_email": user.email if user else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return result


@router.get("/matters/{matter_id}/status-history", tags=["audit"])
def get_status_history(
    matter_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Return all status transitions for a matter, oldest first."""
    require_matter_access(matter_id, current_user, db)

    entries = (
        db.query(MatterStatusHistory)
        .filter(MatterStatusHistory.matter_id == matter_id)
        .order_by(MatterStatusHistory.changed_at.asc())
        .all()
    )

    result = []
    for entry in entries:
        user = db.query(User).filter(User.id == entry.changed_by).first() if entry.changed_by else None
        result.append({
            "id": entry.id,
            "old_status": entry.old_status,
            "new_status": entry.new_status,
            "reason": entry.reason,
            "changed_by_name": user.full_name if user else None,
            "changed_by_email": user.email if user else None,
            "changed_at": entry.changed_at.isoformat() if entry.changed_at else None,
        })

    return result
