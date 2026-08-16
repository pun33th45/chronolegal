"""Regression test for the concurrent-migration-bootstrap race.

Production runs uvicorn with --workers 4 (see backend/Dockerfile's
production CMD), and every worker is a fully independent process that runs
its own app.main:app lifespan startup — including run_migrations().
uvicorn.supervisors.multiprocess.Multiprocess.init_processes() starts all
worker processes back-to-back with no readiness barrier between them, so
without protection every worker races `alembic upgrade head` against the
same (possibly fresh) database at once. The migrations' CREATE TABLE /
CREATE INDEX DDL (db_migrations/versions/0001_initial.py,
0002_align_schema_with_models.py) has no IF NOT EXISTS guard, so a losing
worker hits a real Postgres DuplicateTable/DuplicateObject error and its
startup crashes.

This exercises the REAL app.core.database.run_migrations() concurrently
against a disposable database, proving the pg_advisory_lock added there
serializes the racing callers instead of letting them collide.
"""

import asyncio

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

import app.core.database as db_module
from app.core.config import settings
from app.core.database import run_migrations

_DB_NAME = "chronolegal_migration_race_test"


def _base_url() -> str:
    return settings.DATABASE_URL.rsplit("/", 1)[0]


def _db_url(name: str) -> str:
    return f"{_base_url()}/{name}"


async def _create_disposable_db(db_name: str) -> None:
    admin_engine = create_async_engine(
        _db_url("postgres"), isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as conn:
        await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        await conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    await admin_engine.dispose()


async def _drop_disposable_db(db_name: str) -> None:
    admin_engine = create_async_engine(
        _db_url("postgres"), isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as conn:
        await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    await admin_engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_run_migrations_does_not_race(monkeypatch):
    """N callers invoking run_migrations() concurrently against the same
    fresh database — simulating N uvicorn workers cold-starting together —
    must not raise, and must converge to the fully migrated schema."""
    await _create_disposable_db(_DB_NAME)
    disposable_url = _db_url(_DB_NAME)
    test_engine = create_async_engine(disposable_url)

    # run_migrations() takes its advisory lock on the module-level `engine`,
    # and alembic's env.py resolves the migration target from the
    # DATABASE_URL environment variable directly (not from the Config
    # object) — both must point at the disposable database.
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setenv("DATABASE_URL", disposable_url)

    try:
        results = await asyncio.gather(
            *(run_migrations() for _ in range(5)), return_exceptions=True
        )
        failures = [r for r in results if isinstance(r, BaseException)]
        assert not failures, f"run_migrations() raised under concurrency: {failures}"

        async with test_engine.connect() as conn:
            version = await conn.scalar(
                sa.text("SELECT version_num FROM alembic_version")
            )
        assert version == "0002"

        async def _table_names(conn):
            return set(sa.inspect(conn).get_table_names())

        async with test_engine.connect() as conn:
            table_names = await conn.run_sync(_table_names)
        assert {"users", "conversations", "legal_cases"} <= table_names
    finally:
        await test_engine.dispose()
        await _drop_disposable_db(_DB_NAME)
