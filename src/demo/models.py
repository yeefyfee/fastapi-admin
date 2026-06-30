"""
Demo module: 文章管理（示例业务模块）

演示如何基于基座开发新业务：
1. 继承 TenantFilter 获得多租户隔离
2. 引用系统表 (auth_users) 建立外键关联
3. 使用 require_permission 保护端点
4. 通过 router 导出自动注册到平台
"""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base, TimestampMixin
from src.base.tenant.deps import TenantFilter


class Article(Base, TimestampMixin, TenantFilter):
    """示例：文章表 — 演示如何引用系统 users 表"""
    __tablename__ = "demo_articles"

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[str] = mapped_column(
        ForeignKey("auth_users.id"), nullable=False, index=True
    )
    # tenant_id 由 TenantFilter mixin 自动提供
