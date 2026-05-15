#!/usr/bin/env python3
"""
Script to create initial admin user.
Password is read from ADMIN_PASSWORD environment variable or generated randomly.
"""
import asyncio
import os
import secrets
import string
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add parent directory to path
sys.path.insert(0, ".")

from app.models.user import User, UserRole
from app.core.security import get_password_hash, validate_password_policy
from app.core.config import settings


def generate_secure_password(length: int = 16) -> str:
    """Generate a password that meets the security policy."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        valid, _ = validate_password_policy(password)
        if valid:
            return password


async def create_admin():
    """Create initial admin user."""
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Get password from env var or generate a secure one
    password = os.environ.get("ADMIN_PASSWORD")
    generated = False
    if not password:
        password = generate_secure_password()
        generated = True
    else:
        valid, msg = validate_password_policy(password)
        if not valid:
            print(f"ERROR: ADMIN_PASSWORD does not meet policy: {msg}")
            sys.exit(1)

    async with async_session() as session:
        # Check if admin exists
        result = await session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print("Admin user already exists")
            return

        # Create admin user
        admin_user = User(
            email="admin@example.com",
            hashed_password=get_password_hash(password),
            full_name="System Administrator",
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
        )

        session.add(admin_user)
        await session.commit()

        print("Admin user created successfully")
        print(f"  Email: admin@example.com")
        if generated:
            print(f"  Password: {password}")
            print("  (auto-generated — save this and change it after first login)")
        else:
            print("  Password: (set via ADMIN_PASSWORD env var)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin())
