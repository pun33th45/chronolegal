import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=engine_test, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
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
