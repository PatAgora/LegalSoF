"""
JWT authentication, bcrypt password hashing, and password policy utilities.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import hashlib
import re
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.core.config import settings

# Bcrypt password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Password policy constants
MIN_PASSWORD_LENGTH = 12
PASSWORD_POLICY_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{}|;:\'",.<>?/`~])'
)


def validate_password_policy(password: str) -> tuple[bool, str]:
    """Validate password meets security policy requirements."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:\'",.<>?/`~]', password):
        return False, "Password must contain at least one special character"
    return True, "Password meets requirements"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    Supports dual-hash migration: tries bcrypt first, falls back to SHA256.
    """
    # Try bcrypt first
    if hashed_password.startswith("$2"):
        return pwd_context.verify(plain_password, hashed_password)
    # Fall back to legacy SHA256
    sha256_hash = hashlib.sha256(plain_password.encode()).hexdigest()
    return sha256_hash == hashed_password


def needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash needs to be upgraded to bcrypt."""
    return not hashed_password.startswith("$2")


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def create_portal_token(matter_id: int) -> str:
    """Create a time-limited portal access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.PORTAL_TOKEN_EXPIRE_HOURS
    )
    to_encode = {
        "matter_id": matter_id,
        "exp": expire,
        "type": "portal",
    }
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
