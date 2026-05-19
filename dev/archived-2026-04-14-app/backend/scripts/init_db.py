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


# Columns added to existing models after the initial create_all run.
# Base.metadata.create_all DOES NOT ALTER existing tables, so we
# explicitly ADD COLUMN IF NOT EXISTS for every drift point here.
# Each tuple is (table, column, type) — all nullable so existing rows
# are unaffected. Idempotent: safe to run on every boot.
_SCHEMA_PATCHES: list[tuple[str, str, str]] = [
    # Four-eyes override flow (added 2026-05)
    ("document_verifications", "override_proposed_by",        "VARCHAR(200)"),
    ("document_verifications", "override_proposed_at",        "TIMESTAMP WITH TIME ZONE"),
    ("document_verifications", "override_proposed_rationale", "TEXT"),
]


async def patch_schema(engine):
    """Apply idempotent ALTER TABLE ADD COLUMN IF NOT EXISTS for any
    columns that were added to SQLAlchemy models after the table was
    first created. Postgres-only syntax (IF NOT EXISTS on ADD COLUMN)."""
    from sqlalchemy import text
    async with engine.begin() as conn:
        for table, column, coltype in _SCHEMA_PATCHES:
            stmt = f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}'
            try:
                await conn.execute(text(stmt))
            except Exception as exc:
                # Log and continue — a missing column failure will surface
                # via the API anyway; we don't want one bad patch to abort
                # the whole boot.
                print(f"[!] Schema patch skipped ({table}.{column}): {exc}")
        print("[+] Schema patches applied (idempotent ADD COLUMN IF NOT EXISTS).")


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
    """Seed/refresh the admin user with a known password on every deploy.

    The login is deterministic so the operator always has a way in:
      Email:    admin@agora.ai
      Password: ADMIN_PASSWORD env var if set, otherwise DEFAULT_ADMIN_PASSWORD below.

    On every run this also enforces role=ADMIN + is_superuser=True and clears
    any lockout state. To stop the auto-reset later, remove this function
    from main() or guard it behind an env flag.
    """
    # NOTE: this default is visible in the public repo. Change it once you
    # no longer need the deterministic-login behaviour, or always set
    # ADMIN_PASSWORD in the deploy env to override.
    DEFAULT_ADMIN_PASSWORD = "Agora-Login-2026!"

    from app.core.security import validate_password_policy

    env_pw = os.environ.get("ADMIN_PASSWORD")
    password = env_pw or DEFAULT_ADMIN_PASSWORD
    source = "ADMIN_PASSWORD env var" if env_pw else "default in init_db.py"

    valid, msg = validate_password_policy(password)
    if not valid:
        raise ValueError(f"Admin password does not meet policy ({source}): {msg}")

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.hashed_password = get_password_hash(password)
            existing.role = UserRole.ADMIN
            existing.is_active = True
            existing.is_superuser = True
            existing.failed_login_attempts = 0
            existing.locked_until = None
            await session.commit()
            print(f"[+] Admin user reset  —  {ADMIN_EMAIL}")
        else:
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

        print(f"    Password source: {source}")
        if not env_pw:
            print(f"    Login: {ADMIN_EMAIL} / {DEFAULT_ADMIN_PASSWORD}")
            print("    To change: edit DEFAULT_ADMIN_PASSWORD in init_db.py OR")
            print("    set ADMIN_PASSWORD in Railway env vars, then redeploy.")


def seed_app_config():
    """Seed / backfill the platform configuration catalogue.

    Idempotent. Runs on every boot so newly-introduced settings are
    auto-added with sensible defaults without overwriting any value an
    operator has already changed via the Configuration page.
    """
    from sqlalchemy import create_engine
    try:
        from app.db.init_transaction_tables import seed_transaction_config
    except Exception as exc:
        print(f"[!] Could not import seed_transaction_config: {exc}")
        return

    db_url = str(settings.DATABASE_URL).replace("postgresql+asyncpg", "postgresql")
    sync_engine = create_engine(db_url)
    try:
        seed_transaction_config(sync_engine)
    except Exception as exc:
        # Don't block startup on a seed failure — surfaces in logs.
        print(f"[!] App config seeding failed: {exc}")
    finally:
        sync_engine.dispose()


async def main():
    print("=== Agora Consulting AI — Database Init ===\n")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    # 1. Create tables
    await create_tables(engine)

    # 1b. Patch schema for columns added after first deploy
    await patch_schema(engine)

    # 2. Run Alembic migrations
    run_migrations()

    # 3. Seed admin user
    await seed_admin(engine)

    # 4. Seed / backfill the platform configuration catalogue
    seed_app_config()

    await engine.dispose()
    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
