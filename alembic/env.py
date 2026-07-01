from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from src.db.base import Base
from src.base.auth.models import User  # noqa: F401
from src.base.tenant.models import Tenant  # noqa: F401
from src.rbac.models import Role, Permission, RolePermission, UserRole  # noqa: F401
from src.demo.models import Article  # noqa: F401
from src.system.config import settings
import re

target_metadata = Base.metadata

# 自动补全 async 驱动前缀，兼容 FastAPI Cloud / Neon 注入的标准 URL
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# 处理 Neon / 云端 PostgreSQL 的 psycopg2 专属参数，转换为 asyncpg 兼容格式
_db_url = re.sub(r'[?&]sslmode=\w+', '', _db_url)
_db_url = re.sub(r'[?&]channel_binding=\w+', '', _db_url)
_db_url = re.sub(r'\?&', '?', _db_url)

config.set_main_option("sqlalchemy.url", _db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
