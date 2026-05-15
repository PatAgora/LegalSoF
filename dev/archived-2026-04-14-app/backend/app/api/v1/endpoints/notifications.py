"""
Notifications API Endpoints

Provides:
- GET   /notifications              - list notifications for current user (unread first)
- PATCH /notifications/{id}/read    - mark a single notification as read
- PATCH /notifications/read-all     - mark all notifications as read
- GET   /notifications/unread-count - count of unread notifications
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_sync_db
from app.api.dependencies.auth import require_analyst
from app.models.user import User
from app.models.notification import Notification

router = APIRouter()


@router.get("/notifications", tags=["notifications"])
def list_notifications(
    limit: int = 50,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Return notifications for the current user, unread first, then by recency."""
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.read.asc(), desc(Notification.created_at))
        .limit(limit)
        .all()
    )

    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "matter_id": n.matter_id,
            "read": n.read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@router.get("/notifications/unread-count", tags=["notifications"])
def unread_count(
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Return the count of unread notifications for the current user."""
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read == False)
        .count()
    )
    return {"unread_count": count}


@router.patch("/notifications/{notification_id}/read", tags=["notifications"])
def mark_as_read(
    notification_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Mark a single notification as read."""
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read = True
    db.commit()
    return {"success": True, "message": "Notification marked as read"}


@router.patch("/notifications/read-all", tags=["notifications"])
def mark_all_as_read(
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Mark all notifications for the current user as read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False,
    ).update({"read": True})
    db.commit()
    return {"success": True, "message": "All notifications marked as read"}
