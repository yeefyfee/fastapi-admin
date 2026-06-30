# 通用基础架构平台 — 实现计划

> **用于 Agentic Workers:** 必需子技能: 使用 `subagent-driven-development`（推荐）或 `executing-plans` 逐任务实现此计划。步骤使用 `- [ ]` 勾选语法追踪。

**目标:** 构建基于 FastAPI 的模块化单体企业平台基座 + RBAC 业务模块

**架构:** 模块化单体 — `src/base/`（Auth/Tenant/EventBus/System）+ `src/rbac/`，单进程部署，PostgreSQL + Redis

**技术栈:** FastAPI 0.111+, SQLAlchemy 2.0 asyncio, Alembic, PostgreSQL 16, Redis 7, Pydantic v2, structlog, python-jose, bcrypt

## 全局约束

- 所有业务表必须包含 `tenant_id` 列（UUID, nullable, FK → tenants）
- 系统预置角色 `admin`/`editor`/`viewer` 设置 `is_system=True`，API 层禁止删除/修改名称
- access token 过期时间 15 分钟，refresh token 7 天
- `/auth/login` 限流 5次/分钟/IP
- 密码最小长度 8，bcrypt 哈希
- 所有 API 响应使用 `application/json`
- 项目根目录 `fastapi-platform/`，但源文件在 `src/` 下

---

### Task 1: 项目脚手架

**文件:**
- 创建: `pyproject.toml`
- 创建: `.env.example`
- 创建: `docker-compose.yml`
- 创建: `src/__init__.py`
- 创建: `src/main.py`

**接口:**
- 产出: `app` (FastAPI 实例), 后续任务向其挂载 router 和 lifespan handler

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "fastapi-platform"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi[standard]>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "redis>=5.0.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "pydantic-settings>=2.3.0",
    "structlog>=24.2.0",
    "slowapi>=0.1.9",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "factory-boy>=3.3.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: 创建 .env.example**

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/platform

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# App
APP_ENV=development
LOG_LEVEL=INFO
```

- [ ] **Step 3: 创建 docker-compose.yml**

```yaml
version: "3.9"
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: platform
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

- [ ] **Step 4: 创建 src/main.py 骨架**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 初始化 Redis, Event Bus
    yield
    # Shutdown: 关闭连接


app = FastAPI(
    title="Enterprise Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 5: 安装依赖并验证服务启动**

```bash
pip install -e ".[dev]"
uvicorn src.main:app --reload
```

预期: `GET http://localhost:8000/` 返回 `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example docker-compose.yml src/
git commit -m "chore: project scaffolding with FastAPI skeleton"
```

---

### Task 2: 数据库基础设施

**文件:**
- 创建: `src/db/__init__.py`
- 创建: `src/db/base.py`
- 创建: `src/db/session.py`
- 修改: `src/main.py`（集成 DB session）
- 创建: `alembic.ini`
- 创建: `alembic/env.py`
- 创建: `alembic/script.py.mako`

**接口:**
- 产出: `get_db()` → `AsyncGenerator[AsyncSession]`, `Base` (declarative base)

- [ ] **Step 1: 创建 src/db/base.py**

```python
from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: 创建 src/db/session.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.system.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.APP_ENV == "development")
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 3: 写入测试: tests/test_db.py**

```python
import pytest
from src.db.session import get_db


@pytest.mark.asyncio
async def test_get_db_yields_session():
    gen = get_db()
    session = await gen.__anext__()
    assert session is not None
```

预期: FAIL — `settings` 模块尚未创建（下一任务补全）

- [ ] **Step 4: Commit**

```bash
git add src/db/ tests/test_db.py
git commit -m "feat: add database base models and session factory"
```

---

### Task 3: System 模块（配置、日志、健康检查）

**文件:**
- 创建: `src/system/__init__.py`
- 创建: `src/system/config.py`
- 创建: `src/system/logging.py`
- 创建: `src/system/health.py`
- 修改: `src/main.py`（挂载 health router, 配置日志）
- 创建: `tests/test_health.py`

**接口:**
- 消耗: (无 — 基座不依赖任何模块)
- 产出: `settings` (全局配置对象), `setup_logging()`, `health_router`

- [ ] **Step 1: 创建 src/system/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/platform"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 2: 创建 src/system/logging.py**

```python
import structlog
from src.system.config import settings


def setup_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if settings.APP_ENV == "development"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), settings.LOG_LEVEL, 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()
```

- [ ] **Step 3: 创建 src/system/health.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "database": db_status,
    }
```

- [ ] **Step 4: 更新 src/main.py 集成 system 模块**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.system.config import settings
from src.system.logging import setup_logging
from src.system.health import router as health_router

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up", env=settings.APP_ENV)
    yield
    logger.info("shutting down")


app = FastAPI(
    title="Enterprise Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.get("/")
async def root():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 5: 创建测试 tests/test_health.py**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_200():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data
```

- [ ] **Step 6: 运行测试并验证**

```bash
pytest tests/test_health.py -v
```

预期: 1 passed（当 PostgreSQL 可用时 `database: ok`，否则 `database: error` 但 API 仍返回 200）

- [ ] **Step 7: Commit**

```bash
git add src/system/ tests/test_health.py src/main.py
git commit -m "feat: add system module (config, logging, health check)"
```

---

### Task 4: Auth 模块（用户、JWT 鉴权）

**文件:**
- 创建: `src/base/__init__.py`
- 创建: `src/base/auth/__init__.py`
- 创建: `src/base/auth/models.py`
- 创建: `src/base/auth/schemas.py`
- 创建: `src/base/auth/service.py`
- 创建: `src/base/auth/deps.py`
- 创建: `src/base/auth/router.py`
- 修改: `src/main.py`（挂载 auth router, lifespan 初始化 Redis）
- 创建: `tests/base/test_auth.py`

**接口:**
- 消耗: `settings`, `get_db`, Redis client
- 产出: `get_current_user()`, `auth_router` (`/api/v1/auth/*`)

- [ ] **Step 1: 写入测试 — 测试注册和登录**

````python
# tests/base/test_auth.py
import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_register_creates_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "secret123", "full_name": "Test User"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_login_returns_tokens():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 先注册
        await client.post(
            "/api/v1/auth/register",
            json={"email": "login@example.com", "password": "secret123", "full_name": "Login Test"},
        )
        # 再登录
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "login@example.com", "password": "secret123"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_me_returns_current_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 注册
        await client.post(
            "/api/v1/auth/register",
            json={"email": "me@example.com", "password": "secret123", "full_name": "Me User"},
        )
        # 登录
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "me@example.com", "password": "secret123"},
        )
        token = login_resp.json()["access_token"]
        # 访问 /me
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={"email": "wrong@example.com", "password": "secret123", "full_name": "Wrong"},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "wrong@example.com", "password": "wrongpassword"},
        )
    assert resp.status_code == 401
````

运行: `pytest tests/base/test_auth.py -v`
预期: 全部 FAIL（模块尚未实现）

- [ ] **Step 2: 创建 src/base/auth/models.py**

```python
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 3: 创建 src/base/auth/schemas.py**

```python
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(default="", max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_super_admin: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

- [ ] **Step 4: 创建 src/base/auth/service.py**

```python
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from src.base.auth.models import User
from src.base.auth.schemas import UserRegister, UserResponse
from src.system.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "refresh"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


async def register_user(db: AsyncSession, data: UserRegister) -> User:
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing:
        raise HTTPException(409, "邮箱已注册")
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(401, "邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(401, "用户已禁用")
    return user
```

- [ ] **Step 5: 创建 src/base/auth/deps.py**

```python
from redis.asyncio import Redis
from jose import JWTError, jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.auth.models import User
from src.db.session import get_db
from src.system.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    # 检查黑名单
    if await redis.exists(f"blacklist:{token}"):
        raise HTTPException(401, "Token已失效")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "无效的 token 类型")
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Token 无效")
    except JWTError:
        raise HTTPException(401, "Token 无效")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已禁用")
    return user
```

- [ ] **Step 6: 创建 src/base/auth/router.py**

```python
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from src.base.auth.schemas import UserRegister, UserResponse, TokenResponse
from src.base.auth.service import (
    register_user, authenticate_user, create_access_token, create_refresh_token, hash_password
)
from src.base.auth.deps import get_current_user, get_redis
from src.base.auth.models import User
from src.db.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user = await authenticate_user(db, form.username, form.password)
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    await redis.setex(
        f"refresh:{user.id}",
        60 * 60 * 24 * 7,
        refresh_token,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "无效的 refresh token")
        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(401, "Refresh token 无效")
    stored = await redis.get(f"refresh:{user_id}")
    if stored != refresh_token:
        raise HTTPException(401, "Refresh token 不匹配")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已禁用")
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    await redis.setex(f"refresh:{user_id}", 60 * 60 * 24 * 7, new_refresh)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    redis: Redis = Depends(get_redis),
):
    from jose import jwt
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    exp = payload.get("exp", 0)
    from time import time
    ttl = max(int(exp - time()), 1)
    await redis.setex(f"blacklist:{token}", ttl, "1")
    return {"message": "已登出"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
```

添加缺失的 import 在 router 顶部:
```python
from fastapi import HTTPException
from src.system.config import settings
```

- [ ] **Step 7: 更新 src/main.py 挂载 auth router 并初始化 Redis**

在 `src/main.py` 中:
```python
# 在 lifespan 中初始化 Redis 连接
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up", env=settings.APP_ENV)
    app.state.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await app.state.redis.close()
    logger.info("shutting down")

# 挂载 auth router
from src.base.auth.router import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 8: 运行迁移**

```bash
alembic revision --autogenerate -m "add users table"
alembic upgrade head
```

- [ ] **Step 9: 运行测试**

```bash
pytest tests/base/test_auth.py -v
```

预期: 全部 4 个测试通过

- [ ] **Step 10: Commit**

```bash
git add src/base/auth/ tests/base/test_auth.py src/main.py alembic/versions/
git commit -m "feat: add auth module (register, login, refresh, logout, me)"
```

---

### Task 5: Tenant 模块（多租户行级隔离）

**文件:**
- 创建: `src/base/tenant/__init__.py`
- 创建: `src/base/tenant/models.py`
- 创建: `src/base/tenant/service.py`
- 创建: `src/base/tenant/middleware.py`
- 创建: `src/base/tenant/deps.py`
- 修改: `src/base/auth/models.py`（加 tenant_id）
- 修改: `src/main.py`（加 tenant middleware）
- 创建: `tests/base/test_tenant.py`

**接口:**
- 消耗: `get_db`, `settings`
- 产出: `TenantFilter` mixin, `get_current_tenant()`, `tenant_middleware`

- [ ] **Step 1: 写入测试**

```python
# tests/base/test_tenant.py
import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_tenant_isolation_context_var():
    """验证 tenant_id 通过 ContextVar 在请求间隔离"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_a = await client.get("/health", headers={"X-Tenant-ID": "t-aaa"})
        resp_b = await client.get("/health", headers={"X-Tenant-ID": "t-bbb"})
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
```

预期: FAIL（middleware 尚未实现）

- [ ] **Step 2: 创建 src/base/tenant/models.py**

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
```

- [ ] **Step 3: 创建 src/base/tenant/middleware.py 和 deps.py**

````python
# src/base/tenant/deps.py
from contextvars import ContextVar

current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)


def get_current_tenant() -> str | None:
    return current_tenant_id.get()
```

```python
# src/base/tenant/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from src.base.tenant.deps import current_tenant_id


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID")
        token = current_tenant_id.set(tenant_id)
        try:
            response = await call_next(request)
        finally:
            current_tenant_id.reset(token)
        return response
````

- [ ] **Step 4: 创建 TenantFilter mixin 在 src/base/tenant/deps.py 追加**

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class TenantFilter:
    """Mixin: 为业务表添加 tenant_id 列。使用时继承即可。"""
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    # NULL = super admin 可见 / 跨租户
```

- [ ] **Step 5: 创建 src/base/tenant/service.py**

```python
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
```

- [ ] **Step 6: 更新 src/base/auth/models.py 加 tenant_id**

修改 User 模型，将 `src/base/tenant/deps.py` 的 `TenantFilter` 混入:

```python
from src.base.tenant.deps import TenantFilter

class User(Base, TimestampMixin, TenantFilter):
    # ... 其余字段不变
```

- [ ] **Step 7: 更新 src/main.py 加 TenantMiddleware**

```python
from src.base.tenant.middleware import TenantMiddleware
# 在 CORS middleware 之后:
app.add_middleware(TenantMiddleware)
```

- [ ] **Step 8: 运行迁移和测试**

```bash
alembic revision --autogenerate -m "add tenants table and tenant_id to users"
alembic upgrade head
pytest tests/base/test_tenant.py -v
```

预期: 1 passed

- [ ] **Step 9: Commit**

```bash
git add src/base/tenant/ tests/base/test_tenant.py src/base/auth/models.py src/main.py alembic/versions/
git commit -m "feat: add tenant module with row-level isolation middleware"
```

---

### Task 6: Event Bus（内存事件总线）

**文件:**
- 创建: `src/base/events/__init__.py`
- 创建: `src/base/events/bus.py`
- 修改: `src/main.py`（在 lifespan 中初始化 event bus）
- 创建: `tests/base/test_events.py`

**接口:**
- 产出: `EventBus` 实例 (`emit`, `on`)

- [ ] **Step 1: 写入测试**

```python
# tests/base/test_events.py
import pytest
from src.base.events.bus import EventBus


@pytest.mark.asyncio
async def test_emit_and_on():
    bus = EventBus()
    received = []

    @bus.on("test.event")
    async def handler(payload):
        received.append(payload)

    await bus.emit("test.event", {"key": "value"})
    # 给 asyncio 一个事件循环周期来分发
    import asyncio
    await asyncio.sleep(0.01)
    assert len(received) == 1
    assert received[0] == {"key": "value"}


@pytest.mark.asyncio
async def test_multiple_handlers():
    bus = EventBus()
    results = []

    @bus.on("multi")
    async def h1(p): results.append(("h1", p))

    @bus.on("multi")
    async def h2(p): results.append(("h2", p))

    await bus.emit("multi", {"x": 1})
    import asyncio
    await asyncio.sleep(0.01)
    assert len(results) == 2
```

预期: FAIL（EventBus 未实现）

- [ ] **Step 2: 创建 src/base/events/bus.py**

```python
import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

Handler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event_name: str):
        """装饰器：注册事件处理器"""
        def decorator(handler: Handler):
            self._handlers[event_name].append(handler)
            return handler
        return decorator

    async def emit(self, event_name: str, payload: dict[str, Any]):
        """异步发布事件，并发执行所有处理器"""
        handlers = self._handlers.get(event_name, [])
        if not handlers:
            return
        tasks = [handler(payload) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/base/test_events.py -v
```

预期: 全部通过

- [ ] **Step 4: Commit**

```bash
git add src/base/events/ tests/base/test_events.py
git commit -m "feat: add in-memory event bus (emit/on)"
```

---

### Task 7: RBAC 业务模块（角色、权限、权限检查）

**文件:**
- 创建: `src/rbac/__init__.py`
- 创建: `src/rbac/models.py`
- 创建: `src/rbac/schemas.py`
- 创建: `src/rbac/service.py`
- 创建: `src/rbac/deps.py`
- 创建: `src/rbac/router.py`
- 修改: `src/main.py`（挂载 rbac router）
- 创建: `tests/rbac/test_roles.py`
- 创建: `tests/rbac/test_permissions.py`

**接口:**
- 消耗: `get_db`, `get_current_user`, `get_current_tenant`, `TenantFilter`
- 产出: `require_permission(perm)`, `rbac_router` (`/api/v1/rbac/*`)

- [ ] **Step 1: 写入角色测试**

```python
# tests/rbac/test_roles.py
import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


async def get_admin_token(client: AsyncClient) -> str:
    """Helper: 注册 + 登录获取 token"""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "admin@test.com", "password": "admin123456", "full_name": "Admin"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "admin123456"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_role():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "operator", "description": "操作员"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "operator"


@pytest.mark.asyncio
async def test_list_roles():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        resp = await client.get(
            "/api/v1/rbac/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_delete_system_role_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        # 获取系统角色
        list_resp = await client.get(
            "/api/v1/rbac/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
        admin_role = next(r for r in list_resp.json() if r["name"] == "admin")
        resp = await client.delete(
            f"/api/v1/rbac/roles/{admin_role['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 403
```

- [ ] **Step 2: 写入权限测试**

```python
# tests/rbac/test_permissions.py
import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


async def get_admin_token(client: AsyncClient) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "permtest@test.com", "password": "perm123456", "full_name": "Perm Test"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "permtest@test.com", "password": "perm123456"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_assign_permissions_to_role():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_admin_token(client)
        # 创建角色
        create_resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "reader", "description": "只读"},
            headers={"Authorization": f"Bearer {token}"},
        )
        role_id = create_resp.json()["id"]
        # 分配权限
        resp = await client.post(
            f"/api/v1/rbac/roles/{role_id}/permissions",
            json={"permissions": ["user:read", "role:read"]},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["permissions"]) == 2
```

运行: `pytest tests/rbac/ -v`
预期: 全部 FAIL

- [ ] **Step 3: 创建 src/rbac/models.py**

```python
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, TimestampMixin
from src.base.tenant.deps import TenantFilter


class Role(Base, TimestampMixin, TenantFilter):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(256), default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(256), default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(128), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="permissions")


class UserRole(Base, TimestampMixin, TenantFilter):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="user_roles")
```

注意 `UserRole` 不使用 `id` 字段（覆盖 `TimestampMixin.id`），改为手动定义:

```python
class UserRole(Base, TenantFilter):
    __tablename__ = "user_roles"
    # ...
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: 创建 src/rbac/schemas.py**

```python
from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=256)


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    is_system: bool

    model_config = {"from_attributes": True}


class PermissionResponse(BaseModel):
    id: str
    code: str
    description: str

    model_config = {"from_attributes": True}


class AssignPermissions(BaseModel):
    permissions: list[str]


class RoleWithPermissions(RoleResponse):
    permissions: list[str] = []


class AssignRole(BaseModel):
    role_id: str
```

- [ ] **Step 5: 创建 src/rbac/service.py**

```python
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from src.rbac.models import Role, Permission, RolePermission, UserRole
from src.rbac.schemas import RoleCreate


async def create_role(db: AsyncSession, data: RoleCreate, tenant_id: str) -> Role:
    existing = await db.scalar(
        select(Role).where(Role.name == data.name, Role.tenant_id == tenant_id)
    )
    if existing:
        raise HTTPException(409, "角色名已存在")
    role = Role(name=data.name, description=data.description, tenant_id=tenant_id)
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


async def list_roles(db: AsyncSession, tenant_id: str) -> list[Role]:
    result = await db.scalars(
        select(Role).where(Role.tenant_id == tenant_id).order_by(Role.created_at)
    )
    return list(result.all())


async def get_role(db: AsyncSession, role_id: str, tenant_id: str) -> Role:
    role = await db.get(Role, role_id)
    if not role or role.tenant_id != tenant_id:
        raise HTTPException(404, "角色不存在")
    return role


async def update_role(db: AsyncSession, role_id: str, data: RoleCreate, tenant_id: str) -> Role:
    role = await get_role(db, role_id, tenant_id)
    if role.is_system:
        raise HTTPException(403, "系统角色不可修改名称")
    role.name = data.name
    role.description = data.description
    await db.flush()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role_id: str, tenant_id: str):
    role = await get_role(db, role_id, tenant_id)
    if role.is_system:
        raise HTTPException(403, "系统角色不可删除")
    await db.delete(role)
    await db.flush()


async def assign_permissions(db: AsyncSession, role_id: str, permissions: list[str], tenant_id: str) -> Role:
    role = await get_role(db, role_id, tenant_id)
    # 清除旧权限
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    # 批量插入新权限
    for perm in permissions:
        db.add(RolePermission(role_id=role_id, permission=perm))
    await db.flush()
    await db.refresh(role)
    return role


async def assign_role_to_user(db: AsyncSession, user_id: str, role_id: str, tenant_id: str):
    existing = await db.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.tenant_id == tenant_id,
        )
    )
    if existing:
        raise HTTPException(409, "用户已有此角色")
    user_role = UserRole(user_id=user_id, role_id=role_id, tenant_id=tenant_id)
    db.add(user_role)
    await db.flush()


async def list_user_roles(db: AsyncSession, user_id: str, tenant_id: str) -> list[Role]:
    result = await db.scalars(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
    )
    return list(result.all())


async def get_user_permissions(db: AsyncSession, user_id: str) -> set[str]:
    """获取用户的所有权限码集合"""
    result = await db.scalars(
        select(RolePermission.permission)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    return set(result.all())
```

- [ ] **Step 6: 创建 src/rbac/deps.py**

```python
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.auth.deps import get_current_user
from src.base.auth.models import User
from src.db.session import get_db
from src.rbac.service import get_user_permissions


class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(
        self,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        # Super admin 跳过检查
        if user.is_super_admin:
            return
        permissions = await get_user_permissions(db, user.id)
        if self.required_permission not in permissions:
            raise HTTPException(403, f"缺少权限: {self.required_permission}")


def require_permission(permission: str):
    return Depends(PermissionChecker(permission))
```

- [ ] **Step 7: 创建 src/rbac/router.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.auth.models import User
from src.base.auth.deps import get_current_user
from src.base.tenant.deps import get_current_tenant
from src.db.session import get_db
from src.rbac.schemas import (
    RoleCreate, RoleResponse, RoleWithPermissions,
    AssignPermissions, AssignRole, PermissionResponse,
)
from src.rbac.service import (
    create_role, list_roles, get_role, update_role, delete_role,
    assign_permissions, assign_role_to_user, list_user_roles,
)
from src.rbac.deps import require_permission
from src.rbac.models import Permission

router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])


@router.post("/roles", status_code=201, response_model=RoleResponse)
async def create_role_endpoint(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:create")),
):
    return await create_role(db, data, tenant_id)


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles_endpoint(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:read")),
):
    return await list_roles(db, tenant_id)


@router.get("/roles/{role_id}", response_model=RoleWithPermissions)
async def get_role_endpoint(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:read")),
):
    role = await get_role(db, role_id, tenant_id)
    perms = [rp.permission for rp in role.permissions]
    return RoleWithPermissions(
        id=role.id, name=role.name, description=role.description,
        is_system=role.is_system, permissions=perms,
    )


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role_endpoint(
    role_id: str,
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:update")),
):
    return await update_role(db, role_id, data, tenant_id)


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role_endpoint(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:delete")),
):
    await delete_role(db, role_id, tenant_id)


@router.post("/roles/{role_id}/permissions")
async def assign_permissions_endpoint(
    role_id: str,
    data: AssignPermissions,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("role:update")),
):
    role = await assign_permissions(db, role_id, data.permissions, tenant_id)
    return {"permissions": [rp.permission for rp in role.permissions]}


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions_endpoint(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("role:read")),
):
    from sqlalchemy import select
    result = await db.scalars(select(Permission).order_by(Permission.code))
    return list(result.all())


@router.post("/users/{user_id}/roles", status_code=201)
async def assign_role_to_user_endpoint(
    user_id: str,
    data: AssignRole,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("user:assign_role")),
):
    await assign_role_to_user(db, user_id, data.role_id, tenant_id)
    return {"message": "角色分配成功"}


@router.get("/users/{user_id}/roles", response_model=list[RoleResponse])
async def list_user_roles_endpoint(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("user:read")),
):
    return await list_user_roles(db, user_id, tenant_id)
```

- [ ] **Step 8: 创建种子数据迁移（预置权限 + 默认角色）**

创建 `alembic/versions/seed_permissions_and_roles.py`（手动创建）:

```python
"""seed permissions and default roles

Revision ID: seed001
"""
from alembic import op
import sqlalchemy as sa

# 预置权限列表
PERMISSIONS = [
    ("user:read", "查看用户"),
    ("user:assign_role", "分配用户角色"),
    ("role:create", "创建角色"),
    ("role:read", "查看角色"),
    ("role:update", "更新角色"),
    ("role:delete", "删除角色"),
]

def upgrade():
    # 插入权限
    for code, desc in PERMISSIONS:
        op.execute(
            f"INSERT INTO permissions (id, code, description) "
            f"VALUES (gen_random_uuid(), '{code}', '{desc}') "
            f"ON CONFLICT (code) DO NOTHING"
        )

def downgrade():
    for code, _ in PERMISSIONS:
        op.execute(f"DELETE FROM permissions WHERE code = '{code}'")
```

- [ ] **Step 9: 更新 src/main.py 挂载 rbac router + 初始化种子数据**

```python
from src.rbac.router import router as rbac_router
app.include_router(rbac_router)

# 在 lifespan 启动时初始化默认角色（含 admin 权限）
# 在 startup 中添加:
from src.base.tenant.service import get_or_create_default_tenant
from src.base.tenant.models import Tenant
from src.rbac.models import Role, RolePermission, Permission
```

在 lifespan startup 中追加:

```python
async with async_session_factory() as db:
    tenant = await get_or_create_default_tenant(db)
    # 创建系统默认角色
    default_roles = [
        ("admin", "系统管理员", ["user:read", "user:assign_role", "role:create", "role:read", "role:update", "role:delete"]),
        ("editor", "编辑者", ["user:read", "role:read"]),
        ("viewer", "只读用户", ["user:read", "role:read"]),
    ]
    for name, desc, perms in default_roles:
        existing = await db.scalar(select(Role).where(Role.name == name, Role.tenant_id == tenant.id))
        if not existing:
            role = Role(name=name, description=desc, is_system=True, tenant_id=tenant.id)
            db.add(role)
            await db.flush()
            for perm in perms:
                db.add(RolePermission(role_id=role.id, permission=perm))
    await db.commit()
```

- [ ] **Step 10: 运行迁移和测试**

```bash
alembic revision --autogenerate -m "add rbac tables"
alembic upgrade head
pytest tests/rbac/ -v
```

预期: 全部 5 个测试通过

- [ ] **Step 11: Commit**

```bash
git add src/rbac/ tests/rbac/ src/main.py alembic/versions/
git commit -m "feat: add RBAC module (roles, permissions, require_permission)"
```

---

### Task 8: 集成测试与验收

**文件:**
- 创建: `tests/test_integration.py`

- [ ] **Step 1: 写入端到端集成测试**

```python
# tests/test_integration.py
import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_full_auth_to_rbac_flow():
    """端到端: 注册 → 登录 → 创建角色 → 分配权限 → 为用户分配角色"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 注册
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "flow@test.com", "password": "flow123456", "full_name": "Flow Test"},
        )
        assert resp.status_code == 201
        user_id = resp.json()["id"]

        # 2. 登录
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "flow@test.com", "password": "flow123456"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. 创建角色
        resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "manager", "description": "管理者"},
            headers=headers,
        )
        assert resp.status_code == 201
        role_id = resp.json()["id"]

        # 4. 分配权限
        resp = await client.post(
            f"/api/v1/rbac/roles/{role_id}/permissions",
            json={"permissions": ["user:read", "role:read"]},
            headers=headers,
        )
        assert resp.status_code == 200

        # 5. 为用户分配角色
        resp = await client.post(
            f"/api/v1/rbac/users/{user_id}/roles",
            json={"role_id": role_id},
            headers=headers,
        )
        assert resp.status_code == 201

        # 6. 查看用户角色
        resp = await client.get(
            f"/api/v1/rbac/users/{user_id}/roles",
            headers=headers,
        )
        assert resp.status_code == 200
        roles = resp.json()
        assert any(r["name"] == "manager" for r in roles)


@pytest.mark.asyncio
async def test_permission_denied_for_viewer():
    """viewer 无权创建角色"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 注册一个用户并手动设为 viewer（通过直接给 admin 角色的用户分 viewer）
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "viewer@test.com", "password": "viewer123456", "full_name": "Viewer"},
        )
        assert resp.status_code == 201
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "viewer@test.com", "password": "viewer123456"},
        )
        token = resp.json()["access_token"]
        # viewer（未分配 admin 角色）应该无权创建角色
        resp = await client.post(
            "/api/v1/rbac/roles",
            json={"name": "should-fail"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/test_integration.py -v
```

预期: 全部通过

- [ ] **Step 3: 运行全部测试确认无回归**

```bash
pytest -v
```

预期: 全部测试通过

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration tests"
```

---

### 验收标准

- [ ] `pytest` 全部通过
- [ ] `POST /api/v1/auth/register` 创建用户
- [ ] `POST /api/v1/auth/login` 返回 JWT token 对
- [ ] `GET /api/v1/auth/me` 返回当前用户
- [ ] `POST /api/v1/auth/refresh` 刷新 token
- [ ] `POST /api/v1/auth/logout` 加入黑名单
- [ ] `X-Tenant-ID` 头通过 ContextVar 传播
- [ ] 系统角色 `admin`/`editor`/`viewer` 自动初始化
- [ ] 系统角色无法删除/修改名称
- [ ] `require_permission` 正确拦截无权限请求
- [ ] RBAC CRUD 全部链路通过
