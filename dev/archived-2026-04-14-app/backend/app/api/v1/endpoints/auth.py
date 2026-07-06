"""
Authentication endpoints with account lockout, MFA enforcement, and password rehashing.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from typing import Optional

from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.models.audit import AuditLog, AuditLogAction
from app.schemas.user import LoginRequest, Token, UserCreate, UserPublic, UserInDB
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    needs_rehash,
    validate_password_policy,
)
from app.api.dependencies.auth import get_current_active_user, require_admin
import structlog

router = APIRouter()
logger = structlog.get_logger(__name__)

# Account lockout settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Dummy bcrypt hash for timing-safe user-not-found path
_DUMMY_HASH = "$2b$12$LJ3m4ys3Lg3aKyhDNHb5YeJzHfxjKOFVVGHg3GKzTqEyJhdMCrdmu"


class MFARequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str


class MFALoginRequest(BaseModel):
    mfa_token: str
    totp_code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _client_ip(request: Request) -> Optional[str]:
    """Client IP for audit rows — first X-Forwarded-For hop (the app sits
    behind nginx), falling back to the direct peer address."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


def _auth_audit(
    request: Request,
    action: AuditLogAction,
    description: str,
    user_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> AuditLog:
    """Build an authentication audit row with request context attached."""
    return AuditLog(
        user_id=user_id,
        action=action,
        entity_type="user",
        entity_id=user_id,
        description=description,
        details=details,
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("User-Agent") or "")[:500] or None,
    )


def _lockout_remaining_minutes(user: User, now: datetime) -> int:
    """Minutes of lockout remaining, or 0 if not locked.

    locked_until is a timezone-aware column (DateTime(timezone=True)) —
    compare aware-to-aware, guarding against any legacy naive rows by
    assuming UTC for them.
    """
    locked_until = user.locked_until
    if not locked_until:
        return 0
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until <= now:
        return 0
    return int((locked_until - now).total_seconds() // 60) + 1


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Register a new user (admin only)."""
    # Enforce password policy
    valid, message = validate_password_policy(user_create.password)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    # Check if user exists
    result = await db.execute(
        select(User).where(User.email == user_create.email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    hashed_password = get_password_hash(user_create.password)
    new_user = User(
        email=user_create.email,
        hashed_password=hashed_password,
        full_name=user_create.full_name,
        role=user_create.role,
    )

    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    logger.info(
        "user_registered",
        user_id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        by_user_id=current_user.id,
    )

    return new_user


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    login_request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login and get access token with account lockout and MFA enforcement."""
    now = datetime.now(timezone.utc)

    # Find user
    result = await db.execute(
        select(User).where(User.email == login_request.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Timing-safe: run bcrypt even if user not found to prevent enumeration
        verify_password("dummy-password", _DUMMY_HASH)
        logger.warning("login_failed", email=login_request.email, reason="user_not_found")
        db.add(_auth_audit(
            request,
            AuditLogAction.LOGIN_FAILED,
            f"Failed login attempt for unknown email {login_request.email}",
            details={"email": login_request.email, "reason": "user_not_found"},
        ))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check account lockout
    remaining = _lockout_remaining_minutes(user, now)
    if remaining:
        logger.warning("login_blocked_lockout", email=login_request.email)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked due to too many failed attempts. Try again in {remaining} minutes.",
        )

    # Verify password
    if not verify_password(login_request.password, user.hashed_password):
        # Increment failed attempts
        new_attempts = (user.failed_login_attempts or 0) + 1
        update_values: dict = {"failed_login_attempts": new_attempts}

        if new_attempts >= MAX_FAILED_ATTEMPTS:
            update_values["locked_until"] = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            logger.warning("account_locked", email=login_request.email, attempts=new_attempts)

        await db.execute(
            update(User).where(User.id == user.id).values(**update_values)
        )
        db.add(_auth_audit(
            request,
            AuditLogAction.LOGIN_FAILED,
            f"Failed login attempt for {user.email} (attempt {new_attempts})",
            user_id=user.id,
            details={"reason": "bad_password", "attempts": new_attempts},
        ))
        await db.commit()

        logger.warning("login_failed", email=login_request.email, attempts=new_attempts)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Rehash password if using legacy SHA256
    if needs_rehash(user.hashed_password):
        new_hash = get_password_hash(login_request.password)
        await db.execute(
            update(User).where(User.id == user.id).values(hashed_password=new_hash)
        )
        logger.info("password_rehashed", user_id=user.id)

    # Reset failed attempts and update last login
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            last_login=now,
            failed_login_attempts=0,
            locked_until=None,
        )
    )

    # Check if MFA is enabled — require TOTP verification
    if user.mfa_enabled and user.totp_secret:
        await db.commit()
        # Issue a short-lived MFA-pending token (not a full access token)
        mfa_token = create_access_token(
            data={"sub": str(user.id), "mfa_pending": True},
            expires_delta=timedelta(minutes=5),
        )
        return MFARequiredResponse(mfa_required=True, mfa_token=mfa_token)

    db.add(_auth_audit(
        request,
        AuditLogAction.LOGIN,
        f"User {user.email} logged in",
        user_id=user.id,
    ))
    await db.commit()

    # No MFA — issue full tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    logger.info("user_logged_in", user_id=user.id, email=user.email)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/login/mfa", response_model=Token)
@limiter.limit("10/minute")
async def login_mfa(
    request: Request,
    mfa_request: MFALoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete MFA login by verifying TOTP code."""
    from app.services.totp_service import verify_totp

    now = datetime.now(timezone.utc)

    # Decode the MFA-pending token
    payload = decode_token(mfa_request.mfa_token)

    if not payload.get("mfa_pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA token",
        )

    # Get user
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()

    if not user or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA configuration",
        )

    # Re-check account state — it may have changed since the MFA-pending
    # token was issued.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    remaining = _lockout_remaining_minutes(user, now)
    if remaining:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked due to too many failed attempts. Try again in {remaining} minutes.",
        )

    # Verify TOTP code
    if not verify_totp(user.totp_secret, mfa_request.totp_code):
        logger.warning("mfa_verification_failed", user_id=user.id)
        db.add(_auth_audit(
            request,
            AuditLogAction.LOGIN_FAILED,
            f"Failed MFA verification for {user.email}",
            user_id=user.id,
            details={"reason": "bad_totp"},
        ))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code",
        )

    db.add(_auth_audit(
        request,
        AuditLogAction.LOGIN,
        f"User {user.email} logged in (MFA)",
        user_id=user.id,
        details={"mfa": True},
    ))
    await db.commit()

    # Issue full tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    logger.info("user_logged_in_mfa", user_id=user.id, email=user.email)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=Token)
async def refresh_tokens(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a new access + refresh token pair.

    The refresh token is rotated on every call.
    """
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    if _lockout_remaining_minutes(user, datetime.now(timezone.utc)):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is locked",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Record a logout for the audit trail.

    NOTE: JWTs are stateless — true server-side revocation would require
    a token denylist, which is out of scope here. Clients must discard
    their tokens on logout.
    """
    db.add(_auth_audit(
        request,
        AuditLogAction.LOGOUT,
        f"User {current_user.email} logged out",
        user_id=current_user.id,
    ))
    await db.commit()

    logger.info("user_logged_out", user_id=current_user.id, email=current_user.email)

    return {"message": "logged out"}


@router.post("/change-password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Change the current user's password.

    Requires the current password. Returns 400 (not 401) on a wrong
    current password so the frontend's authFetch does not treat it as
    an expired session and eject the user.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        db.add(_auth_audit(
            request,
            AuditLogAction.UPDATED,
            f"Rejected password change for {current_user.email}: current password incorrect",
            user_id=current_user.id,
            details={"event": "password_change_rejected", "reason": "bad_current_password"},
        ))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    valid, message = validate_password_policy(body.new_password)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    new_hash = get_password_hash(body.new_password)
    await db.execute(
        update(User).where(User.id == current_user.id).values(hashed_password=new_hash)
    )
    # AuditLogAction has no PASSWORD_CHANGED member — record as UPDATED
    # with an explicit description and structured details.
    db.add(_auth_audit(
        request,
        AuditLogAction.UPDATED,
        f"User {current_user.email} changed their password",
        user_id=current_user.id,
        details={"event": "password_changed"},
    ))
    await db.commit()

    logger.info("password_changed", user_id=current_user.id, email=current_user.email)

    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserInDB)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """Get current user information."""
    return current_user


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100,
):
    """List all users (admin only)."""
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return users
