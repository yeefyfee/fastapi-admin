from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "auth_tenants"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
