import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


async def get_admin_token(client: AsyncClient) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "roles@test.com", "password": "admin123456", "full_name": "Admin"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "roles@test.com", "password": "admin123456"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_and_get_role():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        create_resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "tester", "description": "测试角色"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        role_id = create_resp.json()["id"]

        get_resp = await client.get(
            f"/api/v1/rbac/roles/{role_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "tester"


@pytest.mark.asyncio
async def test_delete_system_role_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        list_resp = await client.get(
            "/api/v1/rbac/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
        admin_role = next(r for r in list_resp.json() if r["name"] == "admin")
        resp = await client.delete(
            f"/api/v1/rbac/roles/{admin_role['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_assign_role_to_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register a normal user
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "normal@test.com", "password": "normal123456", "full_name": "Normal"},
        )
        user_id = reg_resp.json()["id"]

        # Get admin token
        token = await get_admin_token(client)

        # Get viewer role ID
        list_resp = await client.get(
            "/api/v1/rbac/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
        viewer_role = next(r for r in list_resp.json() if r["name"] == "viewer")

        # Assign role
        resp = await client.post(
            f"/api/v1/rbac/users/{user_id}/roles",
            json={"role_id": viewer_role["id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

        # Verify user's roles
        resp = await client.get(
            f"/api/v1/rbac/users/{user_id}/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        roles = resp.json()
        assert any(r["name"] == "viewer" for r in roles)
