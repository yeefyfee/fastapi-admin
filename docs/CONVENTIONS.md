# 新业务模块对接规范

> 本文档说明如何在通用基础架构平台上开发新的业务模块。

## 快速开始（3 步接入）

```
1. 创建 src/<模块名>/ 目录
2. 编写 models.py / schemas.py / service.py / router.py
3. 在 __init__.py 中导出 router
```

**无需修改 main.py** — 平台自动扫描并挂载。

---

## 1. 目录结构

```
src/my_biz/
├── __init__.py      # 导出 router（行数：1-3 行）
├── models.py        # 数据模型
├── schemas.py       # Pydantic 请求/响应模型
├── service.py       # 业务逻辑
└── router.py        # API 端点
```

### __init__.py 模板

```python
# my_biz business module
from .router import router

__all__ = ["router"]
```

---

## 2. 数据模型规范

### 2.1 必须继承的基类

```python
from src.db.base import Base, TimestampMixin
from src.base.tenant.deps import TenantFilter

class MyModel(Base, TimestampMixin, TenantFilter):
    __tablename__ = "my_biz_items"    # 表名：模块名_实体名

    # 自定义字段
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # tenant_id 由 TenantFilter 自动提供 — 无需手动定义
```

**继承说明：**

| 基类 | 提供 |
|------|------|
| `Base` | SQLAlchemy DeclarativeBase |
| `TimestampMixin` | `id` (UUID), `created_at`, `updated_at` |
| `TenantFilter` | `tenant_id` (UUID FK → auth_tenants.id) |

### 2.2 表命名规范

- **系统表**：`auth_` 前缀（如 `auth_users`, `auth_roles`）
- **业务表**：`{模块名}_{实体名}`（如 `demo_articles`, `crm_contacts`）

### 2.3 引用系统表

```python
# 引用系统用户
author_id: Mapped[str] = mapped_column(
    ForeignKey("auth_users.id"), nullable=False, index=True
)

# 引用系统角色
role_id: Mapped[str] = mapped_column(
    ForeignKey("auth_roles.id"), nullable=False
)
```

---

## 3. Schema 规范

```python
from pydantic import BaseModel, Field

class MyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # ...

class MyResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}  # 必须 — 支持 ORM 模式
```

---

## 4. Service 层规范

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

async def create_item(
    db: AsyncSession,
    data: MyCreate,
    tenant_id: str,       # ← 接收租户 ID
) -> MyModel:
    item = MyModel(name=data.name, tenant_id=tenant_id)
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item

async def list_items(
    db: AsyncSession,
    tenant_id: str,        # ← 租户隔离过滤
) -> list[MyModel]:
    result = await db.scalars(
        select(MyModel)
        .where(MyModel.tenant_id == tenant_id)
        .order_by(MyModel.created_at.desc())
    )
    return list(result.all())
```

**关键约定：**
- 所有查询必须带上 `WHERE tenant_id = ?` 过滤
- 创建时必须显式设置 `tenant_id`

---

## 5. Router 层规范

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.auth.deps import get_current_user
from src.base.auth.models import User
from src.base.tenant.deps import get_current_tenant
from src.db.session import get_db
from src.rbac.deps import require_permission

router = APIRouter(tags=["my_biz"])


@router.post("/items", status_code=201)
async def create(
    data: MyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),       # ← 当前用户
    tenant_id: str = Depends(get_current_tenant),  # ← 当前租户
    _: None = Depends(require_permission("my:create")),  # ← 权限检查
):
    return await create_item(db, data, tenant_id)


@router.get("/items")
async def list_all(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("my:read")),
):
    return await list_items(db, tenant_id)
```

**可用依赖注入：**

| 依赖 | 来源 | 说明 |
|------|------|------|
| `get_current_user` | `src.base.auth.deps` | 当前登录用户（401 若未登录） |
| `get_current_tenant` | `src.base.tenant.deps` | 当前请求租户 ID（来自 X-Tenant-ID 头） |
| `require_permission("xxx")` | `src.rbac.deps` | 权限检查（403 若无权限） |
| `get_db` | `src.db.session` | 异步数据库会话 |

---

## 6. 请求体加解密（双向 AES-256-GCM）

平台支持可选的请求/响应双向 AES-256-GCM 加解密。在 `.env` 中配置 `ENCRYPTION_KEY` 即可启用。

### 6.1 加解密流程

```
请求方向（客户端 → 服务端）:
  Client: JSON body → AES-256-GCM encrypt → Base64 → HTTP body + X-Encrypted: true
  Server: CryptoMiddleware → decrypt → 注入原始 JSON → 路由正常处理

响应方向（服务端 → 客户端）:
  Server: JSON response → AES-256-GCM encrypt → Base64 → HTTP body + X-Encrypted: true
  Client: Base64 decode → AES-256-GCM decrypt → 原始 JSON
```

**触发条件**：请求头 `X-Encrypted: true` 同时触发请求解密和响应加密。不带此头的请求正常透传。

### 6.2 配置

```bash
# 生成 32 字节密钥
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"

# .env 中设置
ENCRYPTION_KEY=dGhpcyBpcyBhIDMyLWJ5dGUgQVMyNTYgR0NNIGtleSE=
```

留空则不启用加密，所有请求照常处理。

### 6.3 客户端加解密示例

```python
import json, base64, os, requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY = base64.b64decode("dGhpcyBpcyBhIDMyLWJ5dGUgQVMyNTYgR0NNIGtleSE=")
aesgcm = AESGCM(KEY)

# ── 加密请求 ──
def encrypt_body(payload: dict) -> str:
    plain = json.dumps(payload).encode()
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plain, None)
    return base64.b64encode(nonce + ciphertext).decode()

# ── 解密响应 ──
def decrypt_response(encrypted: str) -> dict:
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    plain = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plain)

# ── 完整调用 ──
encrypted = encrypt_body({"email": "alice@example.com", "password": "secret123"})
resp = requests.post("http://localhost:8000/api/v1/auth/register",
    data=encrypted,
    headers={"X-Encrypted": "true", "Content-Type": "text/plain"})

# 解密服务端响应
result = decrypt_response(resp.text)
print(result)  # → {"id":"...","email":"alice@example.com",...}
```

### 6.4 注意事项

- 响应体只在请求带 `X-Encrypted: true` 头且 HTTP 状态码 < 400 时才加密；错误响应（4xx/5xx）明文返回便于调试
- 加密响应 Content-Type 变为 `text/plain`（Base64 字符串），调用方需自行解密
- 每个请求使用独立的随机 nonce（12 字节），防重放
- 流式响应（`StreamingResponse`）和文件下载不支持加密，直接透传

---

## 7. 权限注册

### 7.1 定义新权限

在 `src/main.py` 的 `lifespan()` 中找到 `seed_permissions` 列表，添加新权限：

```python
seed_permissions = [
    # ... 已有权限 ...
    ("my:create", "创建XXX"),
    ("my:read", "查看XXX"),
    ("my:update", "更新XXX"),
    ("my:delete", "删除XXX"),
]
```

### 7.2 分配权限给角色

在同一处 `default_roles` 中：

```python
("admin", "系统管理员", [
    # ... 已有权限 ...
    "my:create", "my:read", "my:update", "my:delete",
]),
("editor", "编辑者", [
    # ...
    "my:create", "my:read", "my:update",
]),
```

---

## 8. 数据库迁移

```bash
# 1. 确保 models 已导入 alembic/env.py
#    在 env.py 中添加: from src.my_biz.models import MyModel  # noqa: F401

# 2. 生成迁移
alembic revision --autogenerate -m "add my_biz tables"

# 3. 执行迁移
alembic upgrade head
```

---

## 9. 事件通信（模块间解耦）

```python
from src.base.events.bus import EventBus

# 发布事件
await event_bus.emit("order.created", {"order_id": "123", "amount": 99})

# 订阅事件
@event_bus.on("order.created")
async def on_order_created(payload: dict):
    order_id = payload["order_id"]
    # 处理逻辑...
```

---

## 10. 完整示例

参考 `src/demo/` — 一个完整的文章管理模块，演示了所有上述规范的实际使用。

---

## 11. 注意事项

| 禁止 | 正确做法 |
|------|----------|
| ❌ 手动创建 `app.include_router()` | ✅ 在 `__init__.py` 中导出 `router` |
| ❌ 查询忘记 `tenant_id` 过滤 | ✅ 所有查询加 `.where(Model.tenant_id == tenant_id)` |
| ❌ 硬编码用户 ID / 角色名 | ✅ 使用 `get_current_user` / `require_permission` |
| ❌ 模块间直接 import service | ✅ 通过 Event Bus 通信 |
| ❌ 表名不加模块前缀 | ✅ `{模块名}_{实体名}` 格式 |
| ❌ 系统表引用用旧表名 | ✅ 使用 `auth_users`, `auth_roles` 等 |
