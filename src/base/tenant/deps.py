from contextvars import ContextVar
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)


def get_current_tenant() -> str | None:
    return current_tenant_id.get()


class TenantFilter:
    """Mixin: adds tenant_id (UUID FK → auth_tenants.id) for row-level multi-tenant isolation."""
    tenant_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("auth_tenants.id"), nullable=True, index=True
    )
