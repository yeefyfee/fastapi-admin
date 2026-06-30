from sqlalchemy import select
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.tenant.deps import get_current_tenant
from src.db.session import get_db
from src.rbac.schemas import (
    RoleCreate, RoleResponse, RoleWithPermissions,
    AssignPermissions, AssignRole, PermissionResponse,
)
from src.rbac.service import (
    create_role, list_roles, get_role, update_role, delete_role,
    assign_permissions, assign_role_to_user, list_user_roles,
)
from src.rbac.deps import require_permission
from src.rbac.models import Permission

router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])


@router.post("/roles", status_code=201, response_model=RoleResponse)
async def create_role_endpoint(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:create")),
):
    return await create_role(db, data, tenant_id)


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles_endpoint(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:read")),
):
    return await list_roles(db, tenant_id)


@router.get("/roles/{role_id}", response_model=RoleWithPermissions)
async def get_role_endpoint(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:read")),
):
    role = await get_role(db, role_id, tenant_id)
    perms = [rp.permission for rp in role.permissions]
    return RoleWithPermissions(
        id=role.id, name=role.name, description=role.description,
        is_system=role.is_system, permissions=perms,
    )


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role_endpoint(
    role_id: str,
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:update")),
):
    return await update_role(db, role_id, data, tenant_id)


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role_endpoint(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:delete")),
):
    await delete_role(db, role_id, tenant_id)


@router.post("/roles/{role_id}/permissions")
async def assign_permissions_endpoint(
    role_id: str,
    data: AssignPermissions,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:update")),
):
    role = await assign_permissions(db, role_id, data.permissions, tenant_id)
    return {"permissions": [rp.permission for rp in role.permissions]}


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions_endpoint(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("role:read")),
):
    result = await db.scalars(select(Permission).order_by(Permission.code))
    return list(result.all())


@router.post("/users/{user_id}/roles", status_code=201)
async def assign_role_to_user_endpoint(
    user_id: str,
    data: AssignRole,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("user:assign_role")),
):
    await assign_role_to_user(db, user_id, data.role_id, tenant_id)
    return {"message": "角色分配成功"}


@router.get("/users/{user_id}/roles", response_model=list[RoleResponse])
async def list_user_roles_endpoint(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("user:read")),
):
    return await list_user_roles(db, user_id, tenant_id)
