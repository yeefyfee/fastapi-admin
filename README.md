<p align="center">
  <h1 align="center">Enterprise Platform</h1>
  <p align="center">基于 FastAPI 的通用基础架构平台</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.111+-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16-blue" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Redis-7-red" alt="Redis">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

---

## 概述

**Enterprise Platform** 是一个模块化单体的 API 基座。它提供开箱即用的鉴权、RBAC 权限管理、多租户隔离和事件总线，使后续业务线只需关注业务逻辑，无需重复开发基础设施。

### 核心能力

| 模块 | 功能 |
|------|------|
| 🔐 **Auth** | 注册/登录、JWT 双 Token（access+refresh）、Token 黑名单、登出 |
| 🔑 **RBAC** | 角色-权限管理、`require_permission()` 一行鉴权、系统角色保护 |
| 🏢 **Tenant** | 多租户行级隔离、`X-Tenant-ID` 头自动透传、`TenantFilter` Mixin |
| 📡 **Event Bus** | 内存异步事件总线，`emit()`/`on()` 模块间解耦通信 |
| 🔌 **Discovery** | 业务模块自动发现 — 创建目录即注册，零 `main.py` 改动 |
| 🔒 **Crypto** | 请求体 AES-256-GCM 加密（可选，`X-Encrypted: true` 头触发） |
| 📊 **System** | 配置管理 (Pydantic Settings)、结构化日志 (structlog)、健康检查 |

---

## 快速开始

### 前置要求

- Python 3.11+
- Docker & Docker Compose
- (可选) PostgreSQL 16 + Redis 7 本地安装

### 1. 克隆并启动

```bash
git clone <your-repo-url>
cd fastapi-platform

# 复制环境变量
cp .env.example .env

# 启动全部服务 (PostgreSQL + Redis + App)
docker-compose up -d

# App 自动执行数据库迁移和种子数据初始化
```

### 2. 验证

```bash
# 健康检查
curl http://localhost:8000/health
# → {"status":"healthy","database":"ok"}

# API 文档
open http://localhost:8000/docs
```

### 3. 本地开发（不使用 Docker）

```bash
pip install -e ".[dev]"
cp .env.example .env
# 确保 PostgreSQL 和 Redis 在本地运行
alembic upgrade head
uvicorn src.main:app --reload
```

---

## 使用用例

### 用例 1: 用户注册与登录

```bash
# 注册新用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"secret123","full_name":"Alice"}'

# 响应
# {"id":"550e8400-...","email":"alice@example.com","full_name":"Alice","is_active":true,"is_super_admin":false}

# 登录获取 Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=secret123"

# 响应
# {"access_token":"eyJ...","refresh_token":"eyJ...","token_type":"bearer"}

# 查看当前用户信息
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

### 用例 2: 刷新 Token 与登出

```bash
# 刷新 Token
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<your_refresh_token>"}'

# 登出（Token 加入黑名单）
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

### 用例 3: RBAC 权限管理

```bash
# 使用 admin 角色的用户 Token
TOKEN="<admin_access_token>"

# 创建角色
curl -X POST http://localhost:8000/api/v1/rbac/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"operator","description":"操作员"}'

# 为角色分配权限
curl -X POST http://localhost:8000/api/v1/rbac/roles/<role_id>/permissions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"permissions":["user:read","role:read"]}'

# 为用户分配角色
curl -X POST http://localhost:8000/api/v1/rbac/users/<user_id>/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role_id":"<role_id>"}'

# 查看用户的所有角色
curl http://localhost:8000/api/v1/rbac/users/<user_id>/roles \
  -H "Authorization: Bearer $TOKEN"

# 查看可用权限列表
curl http://localhost:8000/api/v1/rbac/permissions \
  -H "Authorization: Bearer $TOKEN"
```

### 用例 4: 多租户 API 调用

```bash
# 在请求头中指定租户（UUID 格式）
curl http://localhost:8000/api/v1/rbac/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: 550e8400-e29b-41d4-a716-446655440000"

# 不同租户的数据自动隔离
curl http://localhost:8000/api/v1/rbac/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: 660e8400-e29b-41d4-a716-446655440001"
# → 返回租户 660e8400 的角色列表，看不到 550e8400 的数据
```

### 用例 5: 示例业务模块（文章管理）

```bash
# 创建文章（自动绑定当前用户为作者，租户隔离）
# 默认租户 UUID 在 seed 时自动生成，可通过 GET /api/v1/rbac/roles 响应中推断
curl -X POST http://localhost:8000/api/v1/demo/articles \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: <tenant-uuid>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Hello World","content":"第一篇文章"}'

# 查看文章列表（自动过滤当前租户）
curl http://localhost:8000/api/v1/demo/articles \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: <tenant-uuid>"

# 查看单篇文章
curl http://localhost:8000/api/v1/demo/articles/<article_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: <tenant-uuid>"
```

### 用例 6: 请求体加密（AES-256-GCM）

**服务端配置：**

```bash
# 生成 32 字节密钥
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
# → dGhpcyBpcyBhIDMyLWJ5dGUgQVMyNTYgR0NNIGtleSE=  (示例)

# 写入 .env
echo 'ENCRYPTION_KEY=dGhpcyBpcyBhIDMyLWJ5dGUgQVMyNTYgR0NNIGtleSE=' >> .env

# 重启服务
docker-compose restart app
```

**客户端加密 (Python)：**

```python
import json, base64, os, requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 1. 加载与服务端相同的密钥
SERVER_KEY = base64.b64decode("dGhpcyBpcyBhIDMyLWJ5dGUgQVMyNTYgR0NNIGtleSE=")

# 2. 准备明文请求体
plain_body = json.dumps({
    "email": "alice@example.com",
    "password": "secret123",
    "full_name": "Alice"
}).encode()

# 3. 加密: nonce(12字节) + ciphertext
aesgcm = AESGCM(SERVER_KEY)
nonce = os.urandom(12)
ciphertext = aesgcm.encrypt(nonce, plain_body, None)

# 4. Base64 编码发送
encrypted_body = base64.b64encode(nonce + ciphertext).decode()

# 5. 发送加密请求
resp = requests.post(
    "http://localhost:8000/api/v1/auth/register",
    data=encrypted_body,
    headers={
        "X-Encrypted": "true",
        "Content-Type": "text/plain"
    }
)
print(resp.status_code, resp.json())
# → 201 {"id":"...","email":"alice@example.com",...}
```

**客户端加密 (JavaScript/Node)：**

```javascript
const crypto = require('crypto');

// 1. 加载与服务端相同的密钥
const SERVER_KEY = Buffer.from('dGhpcyBpcyBhIDMyLWJ5dGUgQVMyNTYgR0NNIGtleSE=', 'base64');

// 2. 准备明文请求体
const plainBody = JSON.stringify({
    email: 'alice@example.com',
    password: 'secret123',
    full_name: 'Alice'
});

// 3. 加密: nonce(12字节) + ciphertext (AES-256-GCM)
const nonce = crypto.randomBytes(12);
const cipher = crypto.createCipheriv('aes-256-gcm', SERVER_KEY, nonce);
const encrypted = Buffer.concat([cipher.update(plainBody, 'utf8'), cipher.final()]);
const tag = cipher.getAuthTag();

// 4. Base64 编码发送 (nonce + ciphertext + tag)
const encryptedBody = Buffer.concat([nonce, encrypted, tag]).toString('base64');

// 5. 发送加密请求
fetch('http://localhost:8000/api/v1/auth/register', {
    method: 'POST',
    body: encryptedBody,
    headers: {
        'X-Encrypted': 'true',
        'Content-Type': 'text/plain'
    }
}).then(r => r.json()).then(console.log);
```

**不加密的正常请求**（`ENCRYPTION_KEY` 为空或请求不带 `X-Encrypted` 头）：照常发送 JSON，中间件透传不做任何处理。业务模块无需感知加密层。

---

## 新增业务模块

参考 `docs/CONVENTIONS.md` 获取完整规范。最快方式 — 复制 `src/demo/`：

```
src/my_biz/
├── __init__.py      # from .router import router
├── models.py        # 继承 Base, TimestampMixin, TenantFilter
├── schemas.py       # Pydantic 模型
├── service.py       # 业务逻辑（必须 tenant_id 过滤）
└── router.py        # API 端点 + Depends(require_permission("xxx"))
```

**无需修改 `main.py`** — 模块自动发现并注册。

可用的依赖注入：

| 依赖 | 来源 | 说明 |
|------|------|------|
| `get_current_user` | `src.base.auth.deps` | 当前登录用户 (401) |
| `get_current_tenant` | `src.base.tenant.deps` | 当前租户 ID (来自 `X-Tenant-ID` 头) |
| `require_permission("xxx")` | `src.rbac.deps` | 权限检查 (403) |
| `get_db` | `src.db.session` | 异步 DB 会话 |

---

## 系统表

所有平台级表使用 `auth_` 前缀，业务表使用 `{模块名}_` 前缀：

| 表名 | 说明 |
|------|------|
| `auth_users` | 平台用户（全局） |
| `auth_tenants` | 租户（UUID 主键，slug 为可读别名） |
| `auth_roles` | 角色定义 |
| `auth_permissions` | 权限定义 |
| `auth_role_permissions` | 角色-权限关联 |
| `auth_user_roles` | 用户-角色关联 |
| `demo_articles` | 示例业务表 |

---

## 技术栈

| 组件 | 选型 |
|------|------|
| **Web 框架** | FastAPI 0.111+ |
| **ORM** | SQLAlchemy 2.0 Asyncio |
| **数据库** | PostgreSQL 16 |
| **缓存** | Redis 7 |
| **迁移** | Alembic |
| **JWT** | python-jose |
| **密码** | passlib + bcrypt |
| **日志** | structlog |
| **序列化** | Pydantic v2 |

---

## 项目结构

```
fastapi-platform/
├── src/
│   ├── base/                    # 基座模块
│   │   ├── auth/                # 鉴权 (JWT, 注册, 登录)
│   │   ├── tenant/              # 多租户 (隔离策略)
│   │   └── events/              # 事件总线
│   ├── rbac/                    # RBAC 权限管理
│   ├── demo/                    # 示例业务模块
│   ├── db/                      # 数据库基础设施
│   ├── system/                  # 配置, 日志, 健康检查
│   ├── discovery.py             # 模块自动发现
│   └── main.py                  # FastAPI 入口
├── tests/                       # 测试 (12 个)
├── alembic/                     # 数据库迁移
├── docs/
│   ├── CONVENTIONS.md           # 新业务对接规范
│   └── superpowers/             # 设计文档与计划
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## License

MIT
