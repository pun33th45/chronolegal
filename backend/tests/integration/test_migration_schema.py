"""Verifies the REAL Alembic migration (0001_initial.py) against a live
PostgreSQL database — proving what `alembic upgrade head` actually creates
in production, as opposed to `Base.metadata.create_all` (what the rest of
the test suite uses, per tests/conftest.py's db_engine fixture).

Runs against its own disposable database, created and dropped by the test
itself, so it never interferes with the shared chronolegal_test database
the rest of the suite uses.
"""

import asyncio
import os

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401 — registers all models on Base.metadata
from app.core.config import settings
from app.core.database import Base

_MIGRATION_TEST_DB = "chronolegal_migration_test"


def _base_url() -> str:
    return settings.DATABASE_URL.rsplit("/", 1)[0]


def _migration_test_url() -> str:
    return f"{_base_url()}/{_MIGRATION_TEST_DB}"


def _run_alembic_upgrade() -> None:
    """Runs synchronously (called via run_in_executor, exactly like the
    app's own _alembic_upgrade() in database.py) since Alembic's env.py
    calls asyncio.run() internally and can't be invoked from a running
    event loop. env.py resolves the DB URL from the DATABASE_URL
    environment variable directly, not from the Config object, so that
    env var is temporarily overridden here rather than via set_main_option.
    """
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _migration_test_url()
    try:
        cfg = AlembicConfig("alembic.ini")
        alembic_command.upgrade(cfg, "head")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original


@pytest_asyncio.fixture
async def migrated_engine():
    admin_engine = create_async_engine(
        _base_url() + "/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as conn:
        await conn.execute(
            sa.text(f'DROP DATABASE IF EXISTS "{_MIGRATION_TEST_DB}" WITH (FORCE)')
        )
        await conn.execute(sa.text(f'CREATE DATABASE "{_MIGRATION_TEST_DB}"'))
    await admin_engine.dispose()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_alembic_upgrade)

    engine = create_async_engine(_migration_test_url())
    yield engine
    await engine.dispose()

    admin_engine = create_async_engine(
        _base_url() + "/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as conn:
        await conn.execute(
            sa.text(f'DROP DATABASE IF EXISTS "{_MIGRATION_TEST_DB}" WITH (FORCE)')
        )
    await admin_engine.dispose()


@pytest.mark.asyncio
async def test_migration_upgrade_creates_all_model_tables(migrated_engine):
    """Proves `alembic upgrade head` actually executes successfully against
    real PostgreSQL and creates every table the ORM models declare."""

    def _get_table_names(sync_conn):
        return set(inspect(sync_conn).get_table_names())

    async with migrated_engine.connect() as conn:
        table_names = await conn.run_sync(_get_table_names)

    model_table_names = set(Base.metadata.tables.keys())
    assert model_table_names <= table_names


@pytest.mark.xfail(
    reason=(
        "Known issue: LegalCase.case_number is declared index=True on the "
        "model, but 0001_initial.py never creates ix_legal_cases_case_number. "
        "Tracked for a future migration fix — remove this xfail once fixed."
    ),
    strict=True,
)
@pytest.mark.asyncio
async def test_migration_case_number_index(migrated_engine):
    def _get_indexes(sync_conn):
        return inspect(sync_conn).get_indexes("legal_cases")

    async with migrated_engine.connect() as conn:
        indexes = await conn.run_sync(_get_indexes)

    indexed_columns = {tuple(idx["column_names"]) for idx in indexes}
    assert ("case_number",) in indexed_columns


@pytest.mark.xfail(
    reason=(
        "Known issue: TimestampMixin declares created_at/updated_at as "
        "nullable=False, but 0001_initial.py's raw sa.Column(...) calls omit "
        "nullable=False, leaving them nullable in the real migrated schema. "
        "Tracked for a future migration fix — remove this xfail once fixed."
    ),
    strict=True,
)
@pytest.mark.asyncio
async def test_migration_timestamp_columns_not_nullable(migrated_engine):
    def _get_columns(sync_conn):
        return inspect(sync_conn).get_columns("legal_cases")

    async with migrated_engine.connect() as conn:
        columns = await conn.run_sync(_get_columns)

    by_name = {c["name"]: c for c in columns}
    assert by_name["created_at"]["nullable"] is False
    assert by_name["updated_at"]["nullable"] is False
