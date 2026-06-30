from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.auth.deps import get_current_user
from src.base.auth.models import User
from src.base.tenant.deps import get_current_tenant
from src.db.session import get_db
from src.rbac.service import get_user_permissions


class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(
        self,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        tenant_id: str = Depends(get_current_tenant),
    ):
        if user.is_super_admin:
            return
        permissions = await get_user_permissions(db, user.id, tenant_id)
        if self.required_permission not in permissions:
            raise HTTPException(403, f"缺少权限: {self.required_permission}")


def require_permission(permission: str):
    return PermissionChecker(permission)
