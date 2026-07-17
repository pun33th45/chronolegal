import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@chronolegal.ai",
            "username": "testuser",
            "password": "TestPass123!",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@chronolegal.ai"
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "email": "dup@chronolegal.ai",
        "username": "dupuser",
        "password": "TestPass123!",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@chronolegal.ai",
            "username": "loginuser",
            "password": "TestPass123!",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@chronolegal.ai", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong@chronolegal.ai",
            "username": "wronguser",
            "password": "TestPass123!",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@chronolegal.ai", "password": "WrongPass!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_token(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@chronolegal.ai",
            "username": "meuser",
            "password": "TestPass123!",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "me@chronolegal.ai", "password": "TestPass123!"},
    )
    token = login.json()["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@chronolegal.ai"


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
