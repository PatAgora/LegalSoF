"""
Users API Endpoints — minimal directory used by assignment pickers.

Deliberately returns only the fields the UI needs (id, full_name,
email, role). No password hashes, MFA secrets, or lockout state ever
leave this endpoint.
"""
from fastapi import APIRouter, Depends

from app.db.session import get_sync_session
from app.api.dependencies.auth import require_analyst
from app.models.user import User

router = APIRouter()


@router.get("/users")
async def list_users(
    current_user: User = Depends(require_analyst),
):
    """List active users for the matter-assignment picker."""
    SessionLocal = get_sync_session()
    sync_db = SessionLocal()
    try:
        users = (
            sync_db.query(User)
            .filter(User.is_active == True)  # noqa: E712 — SQLAlchemy comparison
            .order_by(User.full_name.asc())
            .all()
        )
        return [
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role.value if u.role else None,
            }
            for u in users
        ]
    finally:
        sync_db.close()
