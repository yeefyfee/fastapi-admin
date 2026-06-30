from contextlib import asynccontextmanager
from redis.asyncio import Redis
from sqlalchemy import select
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.system.config import settings
from src.system.logging import setup_logging
from src.system.health import router as health_router
from src.base.auth.router import router as auth_router
from src.base.tenant.middleware import TenantMiddleware
from src.base.crypto.middleware import CryptoMiddleware
from src.base.tenant.service import get_or_create_default_tenant
from src.db.session import async_session_factory
from src.rbac.models import Role, RolePermission
from src.rbac.router import router as rbac_router
from src.discovery import discover_routers

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up", env=settings.APP_ENV)
    if settings.JWT_SECRET_KEY == "change-me-in-production" and settings.APP_ENV != "development":
        logger.error("JWT_SECRET_KEY is set to default — refusing to start in non-dev environment")
        raise RuntimeError("JWT_SECRET_KEY must be changed from default value")
    if settings.JWT_SECRET_KEY == "change-me-in-production":
        logger.warning("JWT_SECRET_KEY is using default value — change before production deployment")
    app.state.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    # 初始化默认租户 + 系统角色
    async with async_session_factory() as db:
        tenant = await get_or_create_default_tenant(db)

        # 种子权限定义
        from src.rbac.models import Permission as PermModel
        seed_permissions = [
            ("user:read", "查看用户"),
            ("user:assign_role", "分配用户角色"),
            ("role:create", "创建角色"),
            ("role:read", "查看角色"),
            ("role:update", "更新角色"),
            ("role:delete", "删除角色"),
            ("article:create", "创建文章"),
            ("article:read", "查看文章"),
        ]
        for code, desc in seed_permissions:
            existing = await db.scalar(select(PermModel).where(PermModel.code == code))
            if not existing:
                db.add(PermModel(code=code, description=desc))
        await db.flush()

        default_roles = [
            ("admin", "系统管理员", ["user:read", "user:assign_role", "role:create", "role:read", "role:update", "role:delete", "article:create", "article:read"]),
            ("editor", "编辑者", ["user:read", "role:read", "article:create", "article:read"]),
            ("viewer", "只读用户", ["user:read", "role:read", "article:read"]),
        ]
        for name, desc, perms in default_roles:
            existing = await db.scalar(
                select(Role).where(Role.name == name, Role.tenant_id == tenant.id)
            )
            if not existing:
                role = Role(name=name, description=desc, is_system=True, tenant_id=tenant.id)
                db.add(role)
                await db.flush()
                for perm in perms:
                    db.add(RolePermission(role_id=role.id, permission=perm))
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            # Race condition: another worker seeded first — that's fine
            pass

    yield
    await app.state.redis.close()
    logger.info("shutting down")


app = FastAPI(
    title="Enterprise Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# ---- Middleware ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)

# 请求体加解密（可选，ENCRYPTION_KEY 为空时自动跳过）
encryption_key = settings.ENCRYPTION_KEY
if encryption_key:
    import base64
    key_bytes = base64.b64decode(encryption_key) if len(encryption_key) == 44 else encryption_key.encode().ljust(32, b'\0')[:32]
    app.add_middleware(CryptoMiddleware, key=key_bytes[:32])

# ---- Core Routers (always loaded) ----
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(rbac_router)

# ---- Business Module Auto-Discovery ----
for name, router in discover_routers():
    app.include_router(router, prefix=f"/api/v1/{name}")
    logger.info("mounted business module", module=name)


@app.get("/")
async def root():
    return {"status": "ok", "version": "0.1.0"}
