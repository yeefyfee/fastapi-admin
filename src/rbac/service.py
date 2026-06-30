from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from src.rbac.models import Role, Permission, RolePermission, UserRole
from src.rbac.schemas import RoleCreate


async def create_role(db: AsyncSession, data: RoleCreate, tenant_id: str) -> Role:
    existing = await db.scalar(
        select(Role).where(Role.name == data.name, Role.tenant_id == tenant_id)
    )
    if existing:
        raise HTTPException(409, "角色名已存在")
    role = Role(name=data.name, description=data.description, tenant_id=tenant_id)
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


async def list_roles(db: AsyncSession, tenant_id: str) -> list[Role]:
    result = await db.scalars(
        select(Role).where(Role.tenant_id == tenant_id).order_by(Role.created_at)
    )
    return list(result.all())


async def get_role(db: AsyncSession, role_id: str, tenant_id: str) -> Role:
    role = await db.get(Role, role_id)
    if not role or role.tenant_id != tenant_id:
        raise HTTPException(404, "角色不存在")
    return role


async def update_role(db: AsyncSession, role_id: str, data: RoleCreate, tenant_id: str) -> Role:
    role = await get_role(db, role_id, tenant_id)
    if role.is_system:
        raise HTTPException(403, "系统角色不可修改名称")
    role.name = data.name
    role.description = data.description
    await db.flush()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role_id: str, tenant_id: str):
    role = await get_role(db, role_id, tenant_id)
    if role.is_system:
        raise HTTPException(403, "系统角色不可删除")
    await db.delete(role)
    await db.flush()


async def assign_permissions(db: AsyncSession, role_id: str, permissions: list[str], tenant_id: str) -> Role:
    role = await get_role(db, role_id, tenant_id)
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    for perm in permissions:
        db.add(RolePermission(role_id=role_id, permission=perm))
    await db.flush()
    await db.refresh(role)
    return role


async def assign_role_to_user(db: AsyncSession, user_id: str, role_id: str, tenant_id: str):
    existing = await db.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.tenant_id == tenant_id,
        )
    )
    if existing:
        raise HTTPException(409, "用户已有此角色")
    user_role = UserRole(user_id=user_id, role_id=role_id, tenant_id=tenant_id)
    db.add(user_role)
    await db.flush()


async def list_user_roles(db: AsyncSession, user_id: str, tenant_id: str) -> list[Role]:
    result = await db.scalars(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
    )
    return list(result.all())


async def get_user_permissions(db: AsyncSession, user_id: str, tenant_id: str) -> set[str]:
    """Get all permission codes for a user within a specific tenant."""
    result = await db.scalars(
        select(RolePermission.permission)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
    )
    return set(result.all())
