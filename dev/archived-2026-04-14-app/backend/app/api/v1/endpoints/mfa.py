"""
MFA (Multi-Factor Authentication) endpoints for TOTP setup and verification.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from pydantic import BaseModel

from app.db.session import get_db
from app.models.user import User
from app.api.dependencies.auth import get_current_active_user
from app.services.totp_service import (
    generate_totp_secret,
    get_totp_uri,
    generate_qr_code_base64,
    verify_totp,
)
import structlog

router = APIRouter()
logger = structlog.get_logger(__name__)


class MFASetupResponse(BaseModel):
    qr_code: str      # base64-encoded PNG (no data: prefix)
    secret: str       # base32 secret for manual authenticator entry
    otpauth_uri: str  # otpauth:// provisioning URI


class MFAVerifyRequest(BaseModel):
    token: str


class MFAStatusResponse(BaseModel):
    mfa_enabled: bool


@router.post("/setup", response_model=MFASetupResponse)
async def setup_mfa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate TOTP secret and QR code for MFA setup."""
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled for this account",
        )

    secret = generate_totp_secret()

    # Store the secret (not yet enabled)
    await db.execute(
        update(User).where(User.id == current_user.id).values(totp_secret=secret)
    )

    uri = get_totp_uri(secret, current_user.email)
    qr_code = generate_qr_code_base64(uri)

    logger.info("mfa_setup_initiated", user_id=current_user.id)

    return MFASetupResponse(qr_code=qr_code, secret=secret, otpauth_uri=uri)


@router.post("/verify", response_model=MFAStatusResponse)
async def verify_and_enable_mfa(
    request: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Verify TOTP token and enable MFA."""
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup not initiated. Call /setup first.",
        )

    if not verify_totp(current_user.totp_secret, request.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP token",
        )

    await db.execute(
        update(User).where(User.id == current_user.id).values(mfa_enabled=True)
    )

    logger.info("mfa_enabled", user_id=current_user.id)

    return MFAStatusResponse(mfa_enabled=True)


@router.post("/disable", response_model=MFAStatusResponse)
async def disable_mfa(
    request: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Disable MFA (requires valid TOTP token)."""
    if not current_user.mfa_enabled or not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not currently enabled",
        )

    if not verify_totp(current_user.totp_secret, request.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP token",
        )

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(mfa_enabled=False, totp_secret=None)
    )

    logger.info("mfa_disabled", user_id=current_user.id)

    return MFAStatusResponse(mfa_enabled=False)


@router.get("/status", response_model=MFAStatusResponse)
async def mfa_status(
    current_user: User = Depends(get_current_active_user),
):
    """Get current MFA status."""
    return MFAStatusResponse(mfa_enabled=current_user.mfa_enabled)
