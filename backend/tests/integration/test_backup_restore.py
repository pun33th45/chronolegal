"""Real pg_dump/pg_restore round-trip against disposable PostgreSQL
databases. Proves ChronoLegal's backup format actually restores usable,
correct data — not just that pg_dump/pg_restore exit 0 — using the exact
custom-format (-Fc) flags scripts/backup/backup_db.sh and
scripts/backup/restore_db.sh use, so this test is real evidence the
operational scripts' approach works, even though CI can't run the
docker-compose-wrapped scripts themselves (see docs/deployment.md).

Path:
    populate a disposable source DB (real Alembic schema + representative
    rows, including ARRAY-valued fields)
        -> pg_dump -Fc
        -> disposable restore-target DB
        -> pg_restore
        -> verify schema (tables, case_number index, NOT NULL timestamps,
           alembic_version at head) and data (row counts, primary keys,
           ARRAY values, a representative cross-table query) all survived.
"""

import asyncio
import os
import shutil
import uuid
from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401 — registers all models on Base.metadata
from app.core.config import settings
from app.core.database import Base

# DATABASE_URL, not the separate POSTGRES_HOST/PORT/USER settings fields, is
# the actual connection target the app (and this test) uses — in CI those
# fields still default to "postgres" (the docker-compose service name),
# while DATABASE_URL is explicitly overridden to localhost:5432 for the
# GH Actions Postgres service. Parsing the real target from DATABASE_URL
# keeps pg_dump/pg_restore pointed at the same server everything else here
# actually connects to.
_PG_URL = make_url(settings.DATABASE_URL)

pytestmark = pytest.mark.skipif(
    shutil.which("pg_dump") is None or shutil.which("pg_restore") is None,
    reason="pg_dump/pg_restore not on PATH — install the postgresql-client "
    "package to run this test locally (CI installs it automatically)",
)

_SOURCE_DB = "chronolegal_backup_test_source"
_RESTORE_DB = "chronolegal_backup_test_restore"

_TIMESTAMPED_TABLES = (
    "users",
    "conversations",
    "messages",
    "legal_cases",
    "case_chunks",
    "search_logs",
    "search_feedback",
)


def _base_url() -> str:
    return settings.DATABASE_URL.rsplit("/", 1)[0]


def _db_url(name: str) -> str:
    return f"{_base_url()}/{name}"


def _pg_env() -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = _PG_URL.password or ""
    return env


def _conn_args(db_name: str) -> list:
    return [
        "-h",
        _PG_URL.host,
        "-p",
        str(_PG_URL.port),
        "-U",
        _PG_URL.username,
        "-d",
        db_name,
    ]


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


def _run_alembic_upgrade_head(db_name: str) -> None:
    """Runs synchronously (invoked via run_in_executor) since Alembic's
    env.py calls asyncio.run() internally and can't run from a live loop —
    matches tests/integration/test_migration_schema.py's own pattern."""
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _db_url(db_name)
    try:
        cfg = AlembicConfig("alembic.ini")
        alembic_command.upgrade(cfg, "head")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original


def _pg_dump(db_name: str, dest_path: str) -> None:
    import subprocess

    with open(dest_path, "wb") as f:
        result = subprocess.run(
            ["pg_dump", *_conn_args(db_name), "-Fc"],
            stdout=f,
            stderr=subprocess.PIPE,
            env=_pg_env(),
            timeout=60,
        )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()}")


def _pg_restore(dump_path: str, db_name: str) -> None:
    import subprocess

    with open(dump_path, "rb") as f:
        result = subprocess.run(
            ["pg_restore", *_conn_args(db_name), "--no-owner", "--no-privileges"],
            stdin=f,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_pg_env(),
            timeout=60,
        )
    if result.returncode != 0:
        raise RuntimeError(f"pg_restore failed: {result.stderr.decode()}")


async def _reflect_indexes(engine, table_name: str):
    def _get_indexes(sync_conn):
        return inspect(sync_conn).get_indexes(table_name)

    async with engine.connect() as conn:
        return await conn.run_sync(_get_indexes)


async def _reflect_columns(engine, table_name: str):
    def _get_columns(sync_conn):
        return inspect(sync_conn).get_columns(table_name)

    async with engine.connect() as conn:
        return await conn.run_sync(_get_columns)


async def _reflect_table_names(engine):
    def _get_table_names(sync_conn):
        return set(inspect(sync_conn).get_table_names())

    async with engine.connect() as conn:
        return await conn.run_sync(_get_table_names)


@pytest.mark.asyncio
async def test_backup_restore_round_trip_preserves_schema_and_data(tmp_path):
    loop = asyncio.get_event_loop()

    await _create_disposable_db(_SOURCE_DB)
    try:
        await loop.run_in_executor(None, _run_alembic_upgrade_head, _SOURCE_DB)

        source_engine = create_async_engine(_db_url(_SOURCE_DB))
        try:
            user_id = uuid.uuid4()
            case_id = uuid.uuid4()
            case_acts = ["Indian Penal Code", "Companies Act"]
            case_judges = ["Justice A. Sharma", "Justice B. Rao"]
            now = datetime.now(timezone.utc)

            async with source_engine.begin() as conn:
                await conn.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, email, username, hashed_password, is_active, "
                        "is_verified, is_admin, created_at, updated_at) "
                        "VALUES (:id, :email, :username, :hashed_password, "
                        "true, true, false, :now, :now)"
                    ),
                    {
                        "id": user_id,
                        "email": "backup-test@chronolegal.dev",
                        "username": "backup_test_user",
                        "hashed_password": "not-a-real-hash",
                        "now": now,
                    },
                )
                await conn.execute(
                    sa.text(
                        "INSERT INTO legal_cases "
                        "(id, case_id, case_name, case_number, acts, judges, citation_count, "
                        "chunk_count, is_embedded, judgment_date, created_at, updated_at) "
                        "VALUES (:id, :case_id, :case_name, :case_number, :acts, :judges, 3, "
                        "1, false, :judgment_date, :now, :now)"
                    ),
                    {
                        "id": case_id,
                        "case_id": "backup-test-case-001",
                        "case_name": "Backup Test v. Restore Test",
                        "case_number": "BT-2024-001",
                        "acts": case_acts,
                        "judges": case_judges,
                        "judgment_date": date(2024, 1, 15),
                        "now": now,
                    },
                )
                await conn.execute(
                    sa.text(
                        "INSERT INTO case_chunks "
                        "(id, case_id, chunk_index, content, created_at, updated_at) "
                        "VALUES (:id, :case_id, 0, :content, :now, :now)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "case_id": case_id,
                        "content": "Representative chunk content for the backup/restore test.",
                        "now": now,
                    },
                )

            source_table_names = await _reflect_table_names(source_engine)
        finally:
            await source_engine.dispose()

        dump_path = str(tmp_path / "backup_test.dump")
        await loop.run_in_executor(None, _pg_dump, _SOURCE_DB, dump_path)
        assert os.path.getsize(dump_path) > 0, "pg_dump produced an empty file"

        await _create_disposable_db(_RESTORE_DB)
        try:
            await loop.run_in_executor(None, _pg_restore, dump_path, _RESTORE_DB)

            restore_engine = create_async_engine(_db_url(_RESTORE_DB))
            try:
                # --- Schema survived ---
                restored_table_names = await _reflect_table_names(restore_engine)
                assert source_table_names <= restored_table_names
                model_table_names = set(Base.metadata.tables.keys())
                assert model_table_names <= restored_table_names

                indexes = await _reflect_indexes(restore_engine, "legal_cases")
                indexed_columns = {tuple(idx["column_names"]) for idx in indexes}
                assert (
                    "case_number",
                ) in indexed_columns, (
                    "ix_legal_cases_case_number did not survive restore"
                )

                for table in _TIMESTAMPED_TABLES:
                    columns = await _reflect_columns(restore_engine, table)
                    by_name = {c["name"]: c for c in columns}
                    assert by_name["created_at"]["nullable"] is False
                    assert by_name["updated_at"]["nullable"] is False

                async with restore_engine.connect() as conn:
                    version = await conn.scalar(
                        sa.text("SELECT version_num FROM alembic_version")
                    )
                assert (
                    version == "0002"
                ), "restored database is not at the expected head revision"

                # --- Data survived ---
                async with restore_engine.connect() as conn:
                    user_count = await conn.scalar(
                        sa.text("SELECT COUNT(*) FROM users")
                    )
                    case_count = await conn.scalar(
                        sa.text("SELECT COUNT(*) FROM legal_cases")
                    )
                    chunk_count = await conn.scalar(
                        sa.text("SELECT COUNT(*) FROM case_chunks")
                    )
                assert user_count == 1
                assert case_count == 1
                assert chunk_count == 1

                async with restore_engine.connect() as conn:
                    row = (
                        (
                            await conn.execute(
                                sa.text(
                                    "SELECT case_id, case_name, case_number, "
                                    "acts, judges, citation_count "
                                    "FROM legal_cases WHERE id = :id"
                                ),
                                {"id": case_id},
                            )
                        )
                        .mappings()
                        .one()
                    )
                assert row["case_id"] == "backup-test-case-001"
                assert row["case_name"] == "Backup Test v. Restore Test"
                assert row["case_number"] == "BT-2024-001"
                assert (
                    list(row["acts"]) == case_acts
                ), "ARRAY column 'acts' did not survive the round trip intact"
                assert (
                    list(row["judges"]) == case_judges
                ), "ARRAY column 'judges' did not survive the round trip intact"
                assert row["citation_count"] == 3

                # Representative application-shaped query: join case_chunks -> legal_cases,
                # the same relationship CaseService/search rely on.
                async with restore_engine.connect() as conn:
                    joined = (
                        (
                            await conn.execute(
                                sa.text(
                                    "SELECT lc.case_name, cc.content FROM case_chunks cc "
                                    "JOIN legal_cases lc ON lc.id = cc.case_id WHERE lc.id = :id"
                                ),
                                {"id": case_id},
                            )
                        )
                        .mappings()
                        .one()
                    )
                assert joined["case_name"] == "Backup Test v. Restore Test"
                assert "Representative chunk content" in joined["content"]

                async with restore_engine.connect() as conn:
                    user_row = (
                        (
                            await conn.execute(
                                sa.text(
                                    "SELECT email, username, is_active FROM users WHERE id = :id"
                                ),
                                {"id": user_id},
                            )
                        )
                        .mappings()
                        .one()
                    )
                assert user_row["email"] == "backup-test@chronolegal.dev"
                assert user_row["username"] == "backup_test_user"
                assert user_row["is_active"] is True
            finally:
                await restore_engine.dispose()
        finally:
            await _drop_disposable_db(_RESTORE_DB)
    finally:
        await _drop_disposable_db(_SOURCE_DB)
