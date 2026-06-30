import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


async def get_admin_token(client: AsyncClient) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "admin@test.com", "password": "admin123456", "full_name": "Admin"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "admin123456"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_role():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "operator", "description": "操作员"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "operator"


@pytest.mark.asyncio
async def test_list_roles():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        resp = await client.get(
            "/api/v1/rbac/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_assign_permissions_to_role():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        create_resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "reader", "description": "只读"},
            headers={"Authorization": f"Bearer {token}"},
        )
        role_id = create_resp.json()["id"]
        resp = await client.post(
            f"/api/v1/rbac/roles/{role_id}/permissions",
            json={"permissions": ["user:read", "role:read"]},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["permissions"]) == 2
