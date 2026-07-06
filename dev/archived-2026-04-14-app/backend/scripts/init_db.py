#!/usr/bin/env python3
"""
Database initialisation script.
Creates all tables, runs Alembic migrations, and seeds the default admin user.

Usage (from backend/):
    python -m scripts.init_db

Admin seeding requires the ADMIN_PASSWORD env var; if unset, seeding is
skipped (with a warning) and the rest of the initialisation still runs.
"""
import asyncio
import os
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
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@agora.ai")
ADMIN_FULL_NAME = "System Administrator"


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
    ("document_verifications", "file_bytes",                  "BYTEA"),
    # Matter risk assessment, Source of Wealth, compliance submission
    ("matters", "risk_factors",              "TEXT"),
    ("matters", "risk_assessed_at",          "TIMESTAMP WITH TIME ZONE"),
    ("matters", "risk_assessed_by",          "VARCHAR(200)"),
    ("matters", "compliance_status",         "VARCHAR(20)"),
    ("matters", "compliance_submitted_at",   "TIMESTAMP WITH TIME ZONE"),
    ("matters", "compliance_submitted_by",   "VARCHAR(200)"),
    ("matters", "compliance_reason",         "TEXT"),
    ("matters", "compliance_reviewed_at",    "TIMESTAMP WITH TIME ZONE"),
    ("matters", "compliance_reviewed_by",    "VARCHAR(200)"),
    ("matters", "compliance_review_outcome", "VARCHAR(20)"),
    ("matters", "compliance_review_notes",   "TEXT"),
]

# Raw idempotent statements applied after the column patches: indexes
# added to existing tables and enum members added to existing types.
# create_all does not alter existing tables/types, so drift is patched
# here. Each statement must be safe to run on every boot.
_SCHEMA_STATEMENTS: list[str] = [
    # Audit-log query indexes (added 2026-07)
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_matter_id ON audit_logs (matter_id)",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type_entity_id ON audit_logs (entity_type, entity_id)",
    # AssessmentStorage matter_id lookup index (FK added to the model 2026-07)
    "CREATE INDEX IF NOT EXISTS ix_assessment_storage_matter_id ON assessment_storage (matter_id)",
    # New AuditLogAction members (SQLEnum stores the member NAMES)
    "ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'ARCHIVED'",
    "ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'LOGIN'",
    "ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'LOGIN_FAILED'",
    "ALTER TYPE auditlogaction ADD VALUE IF NOT EXISTS 'LOGOUT'",
]


async def patch_schema(engine):
    """Apply idempotent ALTER TABLE ADD COLUMN IF NOT EXISTS for any
    columns that were added to SQLAlchemy models after the table was
    first created, then the raw statements in _SCHEMA_STATEMENTS.
    Postgres-only syntax (IF NOT EXISTS on ADD COLUMN)."""
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

    # Each ALTER TYPE ... ADD VALUE needs its own transaction on older
    # Postgres versions, so run these statements one connection each.
    for stmt in _SCHEMA_STATEMENTS:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception as exc:
            print(f"[!] Schema statement skipped ({stmt}): {exc}")
    print("[+] Schema index/enum statements applied.")


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
    """Seed the admin user IF it does not already exist.

    Requires the ADMIN_PASSWORD env var — without it, seeding is skipped
    with a warning (the rest of startup continues). An existing admin
    user is NEVER modified: no password reset, no role change, no
    lockout clearing. The password is never printed to logs.
    """
    from app.core.security import validate_password_policy

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Never touch an existing user — password, role, and lockout
            # state are left exactly as they are.
            print(f"[+] Admin user already exists ({ADMIN_EMAIL}) — seeding skipped.")
            return

        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            print(
                "[!] WARNING: ADMIN_PASSWORD env var is not set and no admin "
                f"user ({ADMIN_EMAIL}) exists — admin seeding SKIPPED. Set "
                "ADMIN_PASSWORD and re-run to create the admin account."
            )
            return

        valid, msg = validate_password_policy(password)
        if not valid:
            print(f"[!] WARNING: ADMIN_PASSWORD does not meet policy ({msg}) — admin seeding SKIPPED.")
            return

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
        print(f"[+] Admin user created  —  {ADMIN_EMAIL} (password from ADMIN_PASSWORD env var)")


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

    # 3. Seed admin user (skipped with a warning if ADMIN_PASSWORD is
    #    unset or the user already exists — must not abort startup)
    try:
        await seed_admin(engine)
    except Exception as exc:
        print(f"[!] WARNING: admin seeding failed ({exc}) — continuing startup.")

    # 4. Seed / backfill the platform configuration catalogue
    seed_app_config()

    await engine.dispose()
    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
