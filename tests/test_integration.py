import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_full_auth_to_rbac_flow():
    """端到端: 注册 → 登录 → 创建角色 → 分配权限 → 为用户分配角色"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 注册
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "flow@test.com", "password": "flow123456", "full_name": "Flow Test"},
        )
        assert resp.status_code == 201
        user_id = resp.json()["id"]

        # 2. 登录
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "flow@test.com", "password": "flow123456"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. 创建角色
        resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "manager", "description": "管理者"},
            headers=headers,
        )
        assert resp.status_code == 201
        role_id = resp.json()["id"]

        # 4. 分配权限
        resp = await client.post(
            f"/api/v1/rbac/roles/{role_id}/permissions",
            json={"permissions": ["user:read", "role:read"]},
            headers=headers,
        )
        assert resp.status_code == 200

        # 5. 为用户分配角色
        resp = await client.post(
            f"/api/v1/rbac/users/{user_id}/roles",
            json={"role_id": role_id},
            headers=headers,
        )
        assert resp.status_code == 201

        # 6. 查看用户角色
        resp = await client.get(
            f"/api/v1/rbac/users/{user_id}/roles",
            headers=headers,
        )
        assert resp.status_code == 200
        roles = resp.json()
        assert any(r["name"] == "manager" for r in roles)


@pytest.mark.asyncio
async def test_permission_denied_for_viewer():
    """未授权用户无权创建角色"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "viewer@test.com", "password": "viewer123456", "full_name": "Viewer"},
        )
        assert resp.status_code == 201
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "viewer@test.com", "password": "viewer123456"},
        )
        token = resp.json()["access_token"]
        resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "should-fail"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
