from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.tenant.models import Tenant


async def get_or_create_default_tenant(db: AsyncSession) -> Tenant:
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == "default"))
    if not tenant:
        tenant = Tenant(name="Default", slug="default")
        db.add(tenant)
        await db.flush()
        await db.refresh(tenant)
    return tenant
