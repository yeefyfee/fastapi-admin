from contextvars import ContextVar
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)


def get_current_tenant() -> str | None:
    return current_tenant_id.get()


class TenantFilter:
    """Mixin: adds tenant_id column for row-level multi-tenant isolation."""
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
