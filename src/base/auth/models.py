from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """
    Platform-level user — global across all tenants.
    Tenant association is through UserRole (src/rbac/models.py).
    """
    __tablename__ = "auth_users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False)
