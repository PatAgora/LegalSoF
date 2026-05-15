"""
Authentication endpoints with account lockout, MFA enforcement, and password rehashing.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import LoginRequest, Token, UserCreate, UserPublic, UserInDB
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
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
async def login(
    login_request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login and get access token with account lockout and MFA enforcement."""
    # Find user
    result = await db.execute(
        select(User).where(User.email == login_request.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Timing-safe: run bcrypt even if user not found to prevent enumeration
        verify_password("dummy-password", _DUMMY_HASH)
        logger.warning("login_failed", email=login_request.email, reason="user_not_found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check account lockout
    if user.locked_until and user.locked_until.replace(tzinfo=None) > datetime.now(timezone.utc).replace(tzinfo=None):
        remaining = int((user.locked_until.replace(tzinfo=None) - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() // 60) + 1
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
            update_values["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            logger.warning("account_locked", email=login_request.email, attempts=new_attempts)

        await db.execute(
            update(User).where(User.id == user.id).values(**update_values)
        )
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
            last_login=datetime.now(timezone.utc),
            failed_login_attempts=0,
            locked_until=None,
        )
    )
    await db.commit()

    # Check if MFA is enabled — require TOTP verification
    if user.mfa_enabled and user.totp_secret:
        # Issue a short-lived MFA-pending token (not a full access token)
        mfa_token = create_access_token(
            data={"sub": str(user.id), "mfa_pending": True},
            expires_delta=timedelta(minutes=5),
        )
        return MFARequiredResponse(mfa_required=True, mfa_token=mfa_token)

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
async def login_mfa(
    mfa_request: MFALoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete MFA login by verifying TOTP code."""
    from app.core.security import decode_token
    from app.services.totp_service import verify_totp

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

    # Verify TOTP code
    if not verify_totp(user.totp_secret, mfa_request.totp_code):
        logger.warning("mfa_verification_failed", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code",
        )

    # Issue full tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    logger.info("user_logged_in_mfa", user_id=user.id, email=user.email)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


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
