#!/usr/bin/env python3
"""
Database initialisation script.
Creates all tables, runs Alembic migrations, and seeds the default admin user.

Usage (from backend/):
    python -m scripts.init_db

Set ADMIN_PASSWORD env var to specify admin password, otherwise one is generated.
"""
import asyncio
import os
import secrets
import string
import subprocess
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base

# Import every model so Base.metadata knows about all tables
from app.models import (  # noqa: F401
    User, UserRole,
    Matter, MatterStatus, RiskRating, TransactionType,
    QuestionnaireResponse, SourceType,
    Document, DocumentType, DocumentStatus, QualityIssue,
    Entity, EntityType,
    FundsEvent, EventType, document_event_links,
    Check, CheckType, CheckSeverity, CheckStatus,
    Note, Approval, ApprovalType, ApprovalStatus, AuditLog, AuditLogAction,
    Transaction, TransactionAlert, CountryRisk, KYCProfile, TransactionConfig,
    StatementValidation, StatementValidationFlag, StatementValidationTransaction,
    ValidationStatus, FlagSeverity,
    AssessmentStorage,
)
from app.core.config import settings
from app.core.security import get_password_hash

# ── Admin seed data ──────────────────────────────────────────
ADMIN_EMAIL = "admin@agora.ai"
ADMIN_FULL_NAME = "System Administrator"


def _get_admin_password() -> tuple[str, bool]:
    """Get admin password from env var or generate a secure one.
    Returns (password, was_generated)."""
    from app.core.security import validate_password_policy
    env_pw = os.environ.get("ADMIN_PASSWORD")
    if env_pw:
        valid, msg = validate_password_policy(env_pw)
        if not valid:
            raise ValueError(f"ADMIN_PASSWORD does not meet policy: {msg}")
        return env_pw, False
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pw = ''.join(secrets.choice(alphabet) for _ in range(16))
        ok, _ = validate_password_policy(pw)
        if ok:
            return pw, True


async def create_tables(engine):
    """Create all tables defined in Base.metadata."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[+] All database tables created (or already exist).")


def run_migrations():
    """Run Alembic migrations to HEAD.

    If create_all already built the schema, stamp the current revision
    so Alembic knows the database is up-to-date.
    """
    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    if not alembic_ini.exists():
        print("[!] alembic.ini not found — skipping migrations.")
        return
    cwd = str(alembic_ini.parent)
    try:
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=cwd,
            check=True,
        )
        print("[+] Alembic migrations applied.")
    except FileNotFoundError:
        print("[!] alembic command not found — skipping migrations.")
    except subprocess.CalledProcessError:
        # Tables/enums likely already exist from create_all — stamp head
        try:
            subprocess.run(
                ["alembic", "stamp", "head"],
                cwd=cwd,
                check=True,
            )
            print("[+] Alembic stamped to HEAD (schema already current).")
        except Exception:
            print("[!] Alembic stamp failed — continuing.")


async def seed_admin(engine):
    """Create the default admin user if it does not already exist."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        if result.scalar_one_or_none():
            print(f"[=] Admin user ({ADMIN_EMAIL}) already exists — skipping.")
            return

        password, was_generated = _get_admin_password()
        admin = User(
            email=ADMIN_EMAIL,
            hashed_password=get_password_hash(password),
            full_name=ADMIN_FULL_NAME,
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()
        print(f"[+] Admin user created  —  {ADMIN_EMAIL}")
        if was_generated:
            print(f"[+] Generated password: {password}")
            print("[!] Save this password — it will not be shown again.")


async def main():
    print("=== Agora Consulting AI — Database Init ===\n")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    # 1. Create tables
    await create_tables(engine)

    # 2. Run Alembic migrations
    run_migrations()

    # 3. Seed admin user
    await seed_admin(engine)

    await engine.dispose()
    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
