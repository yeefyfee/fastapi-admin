import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_register_creates_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "secret123", "full_name": "Test User"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_login_returns_tokens():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={"email": "login@example.com", "password": "secret123", "full_name": "Login Test"},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "login@example.com", "password": "secret123"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_me_returns_current_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={"email": "me@example.com", "password": "secret123", "full_name": "Me User"},
        )
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "me@example.com", "password": "secret123"},
        )
        token = login_resp.json()["access_token"]
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={"email": "wrong@example.com", "password": "secret123", "full_name": "Wrong"},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "wrong@example.com", "password": "wrongpassword"},
        )
    assert resp.status_code == 401
