from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# Auth-endpoint rate limiting (5-20/minute per IP) is real production
# behavior we want covered by tests, not bypassed by mocking it away — but
# many independent test functions each call /auth/login via auth_headers
# below, all sharing one client "IP" through the ASGI test transport, so
# the limit would otherwise trip within the first handful of tests in a
# session and cascade into unrelated 401s. Disabling the shared Limiter
# singleton for the test process (not touching the app's route
# decorators/wiring at all) is slowapi's documented way to exempt tests
# from limits that are still fully exercised by real traffic.
app.state.limiter.enabled = False

# Real PostgreSQL, same dialect as production — read from the same
# configuration/environment the app itself uses (CI already provides
# DATABASE_URL pointing at its postgres service; local runs fall back to
# whatever POSTGRES_* settings/.env resolve to, matching docker-compose).
# LegalCase relies on genuine PostgreSQL ARRAY behavior (unnest, ANY), which
# has no SQLite equivalent, so the test database must be PostgreSQL too.
#
# The engine is created fresh per test (see db_engine below), not once at
# module scope: pytest-asyncio 0.24 gives each test function its own event
# loop by default, and an asyncpg connection pool cannot be reused across
# different event loops ("attached to a different loop" / "another
# operation is in progress"). A single module-level engine bound to
# whichever loop first used it would break as soon as a later test ran on
# a different loop.


@pytest_asyncio.fixture
async def db_engine():
    """Fresh engine + schema per test, bound to that test's own event loop.
    create_all/drop_all use checkfirst, so the DDL cost is small."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_maker = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    session_maker = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register a test user and return Authorization headers."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@chronolegal.dev",
            "username": "testuser",
            "full_name": "Test User",
            "password": "TestPass123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@chronolegal.dev", "password": "TestPass123"},
    )
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}
