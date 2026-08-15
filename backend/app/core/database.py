import asyncio
from collections.abc import AsyncGenerator

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
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


async def run_migrations() -> None:
    """Apply all pending Alembic migrations (replaces create_all_tables)."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _alembic_upgrade)
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
