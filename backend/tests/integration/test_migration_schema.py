"""Verifies the REAL Alembic migration chain (0001_initial.py +
0002_align_schema_with_models.py) against a live PostgreSQL database —
proving what `alembic upgrade head` actually creates in production, as
opposed to `Base.metadata.create_all` (what the rest of the test suite
uses, per tests/conftest.py's db_engine fixture).

Two paths are verified, matching how this migration chain is actually used:

- PATH A (fresh installation): `alembic upgrade head` on an empty database
  — what a brand-new deployment runs.
- PATH B (existing installation): `alembic upgrade 0001` followed by a
  separate `alembic upgrade 0002` — what an already-deployed database (one
  that ran 0001 before 0002 existed) goes through. This is the
  production-critical path: 0002 must contain real ALTER operations that
  correct an already-created schema, not just work against an empty DB.

All tests run against their own disposable databases, created and dropped
by the tests themselves, so none interferes with the shared
chronolegal_test database the rest of the suite uses.
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

# Every table in 0001_initial.py has created_at/updated_at via TimestampMixin.
_TIMESTAMPED_TABLES = (
    "users",
    "conversations",
    "messages",
    "legal_cases",
    "case_chunks",
    "search_logs",
    "search_feedback",
)

_FRESH_DB = "chronolegal_migration_test_fresh"
_EXISTING_DB = "chronolegal_migration_test_existing"
_DOWNGRADE_DB = "chronolegal_migration_test_downgrade"


def _base_url() -> str:
    return settings.DATABASE_URL.rsplit("/", 1)[0]


def _db_url(name: str) -> str:
    return f"{_base_url()}/{name}"


def _run_alembic(command_fn, target: str, db_name: str) -> None:
    """Runs synchronously (called via run_in_executor, exactly like the
    app's own _alembic_upgrade() in database.py) since Alembic's env.py
    calls asyncio.run() internally and can't be invoked from a running
    event loop. env.py resolves the DB URL from the DATABASE_URL
    environment variable directly, not from the Config object, so that
    env var is temporarily overridden here rather than via set_main_option.
    """
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _db_url(db_name)
    try:
        cfg = AlembicConfig("alembic.ini")
        command_fn(cfg, target)
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original


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


async def _reflect_columns(engine, table_name: str):
    def _get_columns(sync_conn):
        return inspect(sync_conn).get_columns(table_name)

    async with engine.connect() as conn:
        return await conn.run_sync(_get_columns)


async def _reflect_indexes(engine, table_name: str):
    def _get_indexes(sync_conn):
        return inspect(sync_conn).get_indexes(table_name)

    async with engine.connect() as conn:
        return await conn.run_sync(_get_indexes)


async def _reflect_table_names(engine):
    def _get_table_names(sync_conn):
        return set(inspect(sync_conn).get_table_names())

    async with engine.connect() as conn:
        return await conn.run_sync(_get_table_names)


async def _assert_pre_0002_state(engine) -> None:
    """The known, previously xfail-documented discrepancies: no
    case_number index, nullable timestamps."""
    columns = await _reflect_columns(engine, "legal_cases")
    by_name = {c["name"]: c for c in columns}
    assert by_name["created_at"]["nullable"] is True
    assert by_name["updated_at"]["nullable"] is True

    indexes = await _reflect_indexes(engine, "legal_cases")
    indexed_columns = {tuple(idx["column_names"]) for idx in indexes}
    assert ("case_number",) not in indexed_columns


async def _assert_schema_is_corrected(engine) -> None:
    """The fully-migrated (0002) schema: case_number indexed, and
    created_at/updated_at NOT NULL on all 7 tables."""
    for table in _TIMESTAMPED_TABLES:
        columns = await _reflect_columns(engine, table)
        by_name = {c["name"]: c for c in columns}
        assert (
            by_name["created_at"]["nullable"] is False
        ), f"{table}.created_at is nullable; expected NOT NULL after 0002"
        assert (
            by_name["updated_at"]["nullable"] is False
        ), f"{table}.updated_at is nullable; expected NOT NULL after 0002"

    indexes = await _reflect_indexes(engine, "legal_cases")
    indexed_columns = {tuple(idx["column_names"]) for idx in indexes}
    assert ("case_number",) in indexed_columns, "ix_legal_cases_case_number missing"


# ---------------------------------------------------------------------------
# PATH A — fresh installation: `alembic upgrade head`
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def migrated_engine():
    await _create_disposable_db(_FRESH_DB)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, _run_alembic, alembic_command.upgrade, "head", _FRESH_DB
    )

    engine = create_async_engine(_db_url(_FRESH_DB))
    yield engine
    await engine.dispose()
    await _drop_disposable_db(_FRESH_DB)


@pytest.mark.asyncio
async def test_migration_upgrade_creates_all_model_tables(migrated_engine):
    """PATH A: proves `alembic upgrade head` executes successfully against
    real PostgreSQL and creates every table the ORM models declare."""
    table_names = await _reflect_table_names(migrated_engine)
    model_table_names = set(Base.metadata.tables.keys())
    assert model_table_names <= table_names


@pytest.mark.asyncio
async def test_migration_case_number_index(migrated_engine):
    indexes = await _reflect_indexes(migrated_engine, "legal_cases")
    indexed_columns = {tuple(idx["column_names"]) for idx in indexes}
    assert ("case_number",) in indexed_columns


@pytest.mark.asyncio
async def test_migration_timestamp_columns_not_nullable(migrated_engine):
    for table in _TIMESTAMPED_TABLES:
        columns = await _reflect_columns(migrated_engine, table)
        by_name = {c["name"]: c for c in columns}
        assert by_name["created_at"]["nullable"] is False
        assert by_name["updated_at"]["nullable"] is False


# ---------------------------------------------------------------------------
# PATH B — existing installation: `alembic upgrade 0001` then `upgrade 0002`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_install_0001_then_0002_upgrade_path():
    """The production-critical path: an already-deployed database that ran
    0001 before 0002 existed. Verifies 0001 succeeds alone, confirms the
    original known-bad schema at that point, then verifies 0002 alone
    corrects it via real ALTER operations against the already-populated
    schema — not just against an empty database."""
    await _create_disposable_db(_EXISTING_DB)
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None, _run_alembic, alembic_command.upgrade, "0001", _EXISTING_DB
        )

        engine = create_async_engine(_db_url(_EXISTING_DB))
        try:
            await _assert_pre_0002_state(engine)

            await loop.run_in_executor(
                None, _run_alembic, alembic_command.upgrade, "0002", _EXISTING_DB
            )

            await _assert_schema_is_corrected(engine)

            table_names = await _reflect_table_names(engine)
            model_table_names = set(Base.metadata.tables.keys())
            assert (
                model_table_names <= table_names
            ), "0002 must not remove any table 0001 created"
        finally:
            await engine.dispose()
    finally:
        await _drop_disposable_db(_EXISTING_DB)


@pytest.mark.asyncio
async def test_downgrade_0002_reverts_cleanly_and_reupgrade_is_idempotent():
    """Verifies `alembic downgrade 0001` correctly reverses 0002 (index
    dropped, timestamps nullable again), and that re-running
    `alembic upgrade 0002` afterwards is clean — Alembic's own revision
    tracking makes upgrading to a just-reverted revision safe and
    repeatable."""
    await _create_disposable_db(_DOWNGRADE_DB)
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None, _run_alembic, alembic_command.upgrade, "head", _DOWNGRADE_DB
        )

        engine = create_async_engine(_db_url(_DOWNGRADE_DB))
        try:
            await loop.run_in_executor(
                None, _run_alembic, alembic_command.downgrade, "0001", _DOWNGRADE_DB
            )

            await _assert_pre_0002_state(engine)

            # Re-upgrading must be clean/idempotent.
            await loop.run_in_executor(
                None, _run_alembic, alembic_command.upgrade, "0002", _DOWNGRADE_DB
            )

            await _assert_schema_is_corrected(engine)
        finally:
            await engine.dispose()
    finally:
        await _drop_disposable_db(_DOWNGRADE_DB)
