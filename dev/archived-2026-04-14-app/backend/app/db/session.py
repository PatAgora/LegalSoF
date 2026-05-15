"""
Database session management with PostgreSQL connection pooling.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Create async engine with connection pooling
# NullPool for testing (no pool), QueuePool with sizing for all other envs
_engine_kwargs = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if settings.ENVIRONMENT == "testing":
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_recycle"] = 3600

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Shared synchronous engine and session factory
# (Replaces per-request create_engine() calls in endpoint files)
# ---------------------------------------------------------------------------
_sync_engine = None
_SyncSessionLocal = None


def get_sync_engine():
    """Return the shared synchronous SQLAlchemy engine, creating it on first call."""
    global _sync_engine
    if _sync_engine is None:
        sync_url = str(settings.DATABASE_URL).replace(
            "postgresql+asyncpg", "postgresql"
        )
        _sync_engine = create_engine(
            sync_url,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_sync_session():
    """Return the shared synchronous sessionmaker, creating it on first call."""
    global _SyncSessionLocal
    if _SyncSessionLocal is None:
        _SyncSessionLocal = sessionmaker(bind=get_sync_engine())
    return _SyncSessionLocal


def get_sync_db():
    """Dependency that yields a synchronous DB session."""
    SessionLocal = get_sync_session()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
