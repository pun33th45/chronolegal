import asyncio
from collections.abc import AsyncGenerator

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import logger

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _alembic_upgrade() -> None:
    """Run alembic upgrade head synchronously (called from executor)."""
    cfg = AlembicConfig("alembic.ini")
    alembic_command.upgrade(cfg, "head")


# Arbitrary constant identifying this app's migration bootstrap for
# pg_advisory_lock. Every uvicorn worker process runs its own independent
# lifespan startup (production runs --workers 4, and Uvicorn's Multiprocess
# supervisor forks all of them back-to-back with no readiness barrier
# between them — see uvicorn.supervisors.multiprocess.init_processes()), so
# without this lock, all workers race `alembic upgrade head` against the
# same possibly-fresh database at once. The migrations' CREATE TABLE/CREATE
# INDEX DDL has no IF NOT EXISTS guard, so the losing workers hit a real
# Postgres DuplicateTable/DuplicateObject error and crash on startup. A
# session-level advisory lock serializes them: one worker performs the
# upgrade while the rest wait, then find the database already at head and
# no-op.
_MIGRATION_LOCK_KEY = 847_291_003


async def run_migrations() -> None:
    """Apply all pending Alembic migrations (replaces create_all_tables)."""
    lock_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    async with lock_engine.connect() as conn:
        await conn.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": _MIGRATION_LOCK_KEY}
        )
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _alembic_upgrade)
        finally:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _MIGRATION_LOCK_KEY}
            )
    logger.info("Alembic migrations applied")


async def create_all_tables() -> None:
    """Legacy helper retained for tests and scripts that bypass Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created (create_all fallback)")


async def drop_all_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped")
