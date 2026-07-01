from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.system.config import settings
import re

# 自动补全 async 驱动前缀，兼容 FastAPI Cloud / Neon 注入的标准 URL
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# 处理 Neon / 云端 PostgreSQL 的 psycopg2 专属参数，转换为 asyncpg 兼容格式
_db_url = re.sub(r'[?&]sslmode=\w+', '', _db_url)        # asyncpg 默认 SSL，不需要 sslmode
_db_url = re.sub(r'[?&]channel_binding=\w+', '', _db_url)  # asyncpg 不支持
_db_url = re.sub(r'\?&', '?', _db_url)                     # 清理残留的 ?&

engine = create_async_engine(_db_url, echo=settings.APP_ENV == "development")
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
