import asyncio
import os
from logging.config import fileConfig
from urllib.parse import quote

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all models so Alembic can detect them
import app.models  # noqa: F401 — registers all models on Base.metadata
from app.core.database import Base

# Docker/CI already inject real OS env vars, so this is a no-op there.
# Locally (e.g. running `alembic upgrade head` directly against backend/.env,
# outside Docker Compose), nothing sources backend/.env into the process
# environment on its own — only pydantic-settings' own Settings() does
# that, and this file deliberately does NOT go through the cached Settings
# singleton (see below). load_dotenv()'s default override=False means any
# already-set real env var (including one a test sets via
# monkeypatch.setenv(), e.g. test_migration_concurrency.py) still wins.
load_dotenv()

config = context.config

# Deliberately reads live os.getenv() values rather than the cached
# `app.core.config.settings` singleton: settings is constructed once at
# import time, so a test overriding DATABASE_URL afterwards (e.g. to point
# migrations at a disposable per-test database) would otherwise be
# silently ignored.
db_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}".format(
        # Percent-encode user/password: a plain f-string/format() URL like
        # this breaks as soon as either contains a URL-reserved character
        # (e.g. a password containing "@" gets misread as the
        # user:password@host separator) — see the identical fix in
        # app/core/config.py's build_database_url/build_redis_url.
        user=quote(os.getenv("POSTGRES_USER", "chronolegal_user"), safe=""),
        pw=quote(os.getenv("POSTGRES_PASSWORD", "chronolegal_password"), safe=""),
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        db=os.getenv("POSTGRES_DB", "chronolegal"),
    ),
)
# Alembic stores this via Python's configparser, which treats "%" as its
# own interpolation syntax (for %(name)s-style substitution) — a
# percent-encoded URL (e.g. "%40" for a literal "@") must have every "%"
# doubled to "%%" so configparser reads it as a literal, escaped percent
# sign instead of raising "invalid interpolation syntax".
config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
