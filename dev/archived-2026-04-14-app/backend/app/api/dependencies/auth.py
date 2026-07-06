"""
Authentication dependencies for protected routes.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.matter import Matter
from app.core.security import decode_token
from app.schemas.user import TokenData

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    token = credentials.credentials
    
    # Decode token
    payload = decode_token(token)
    
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Reject MFA-pending tokens — user must complete TOTP verification first
    if payload.get("mfa_pending"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA verification required",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return current_user


def require_role(*roles: UserRole):
    """Dependency factory for role-based access control."""
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in roles and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(r.value for r in roles)}",
            )
        return current_user
    return role_checker


# Specific role dependencies
require_analyst = require_role(UserRole.ANALYST, UserRole.PARTNER, UserRole.ADMIN)
require_partner = require_role(UserRole.PARTNER, UserRole.ADMIN)
require_admin = require_role(UserRole.ADMIN)


def require_matter_access(matter_id: int, current_user: User, db: Session) -> Matter:
    """Matter-level authorisation check for matter-scoped endpoints.

    Policy:
      - ADMIN and PARTNER (and superusers) may access any matter.
      - ANALYST may access a matter if it is unassigned
        (assigned_analyst_id is None), assigned to them, or created by
        them. Unassigned matters remain open to all analysts so existing
        data keeps working; enforcement tightens once assignment is used.

    Raises 404 if the matter does not exist, 403 if access is not
    permitted. Returns the Matter on success.
    """
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")

    if current_user.is_superuser or current_user.role in (UserRole.ADMIN, UserRole.PARTNER):
        return matter

    if (
        matter.assigned_analyst_id is None
        or matter.assigned_analyst_id == current_user.id
        or matter.created_by_id == current_user.id
    ):
        return matter

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this matter",
    )
