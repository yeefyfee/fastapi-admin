# 通用基础架构平台 — 设计文档

> **日期:** 2026-06-30
> **状态:** 设计阶段
> **版本:** v1.0

## 1. 概述

### 1.1 目标

构建一套基于 FastAPI 的**模块化单体（Modular Monolith）**通用基础架构平台。基座提供鉴权、多租户、事件总线、系统管理等横切能力；业务线以独立 package 形式挂载。

### 1.2 设计决策摘要

| 决策点 | 选择 |
|--------|------|
| **架构模式** | 模块化单体（方案 B） |
| **第一条验证业务线** | RBAC（角色级权限管理） |
| **权限粒度** | 角色级（User → Role → Permissions） |
| **多租户隔离** | 行级隔离（共享表 + tenant_id） |

---

## 2. 架构分层与模块边界

```
┌─────────────────────────────────────────────────────────┐
│                    API Gateway Layer                     │
│   (rate-limit, request-id, cors, global exception)      │
├─────────────────────────────────────────────────────────┤
│                  Business Modules (插件式)               │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │   RBAC   │  │  (CRM)   │  │  (OA)    │  ...        │
│   │ routers  │  │ routers  │  │ routers  │             │
│   │ services │  │ services │  │ services │             │
│   │  models  │  │  models  │  │  models  │             │
│   └──────────┘  └──────────┘  └──────────┘             │
├─────────────────────────────────────────────────────────┤
│                    Base Kernel (基座)                    │
│  ┌──────────┬──────────┬──────────┬──────────────┐     │
│  │  Auth    │ Tenant   │  Event   │   System     │     │
│  │  (JWT)   │(隔离策略) │  Bus     │  (config,    │     │
│  │          │          │          │   logging)   │     │
│  └──────────┴──────────┴──────────┴──────────────┘     │
├─────────────────────────────────────────────────────────┤
│                    Infrastructure                       │
│         DB (AsyncSession)  │  Redis (Cache)             │
└─────────────────────────────────────────────────────────┘
```

**核心原则：**
- 基座不知道业务模块的存在 — 业务模块依赖基座，基座不依赖任何业务模块
- 业务模块间不直接互相调用 — 通过 Event Bus 松耦合
- 每个模块有独立的 `router`，统一由 `main.py` 收集挂载

---

## 3. 基座核心模块设计

### 3.1 Auth 模块（统一鉴权）

**流程：**
```
注册/登录 → JWT (access + refresh token)
    ↓
依赖注入: Depends(get_current_user) → 自动解析当前用户
    ↓
RBAC 模块通过 Depends(require_permission) 消费
```

**关键设计：**
- **JWT 双 token**：access（15 min）+ refresh（7 days），refresh 存在 Redis
- **Token 黑名单**：登出后将 access token 加入 Redis 黑名单（TTL = 剩余过期时间）
- **密码存储**：bcrypt + salt
- **对外接口**：`POST /api/v1/auth/login`, `/logout`, `/refresh`, `GET /me`

**get_current_user 依赖注入：**
```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    # 1. 检查黑名单
    if await redis.exists(f"blacklist:{token}"):
        raise HTTPException(401, "Token已失效")
    # 2. 解码 JWT
    payload = decode_jwt(token)
    # 3. 查用户
    user = await db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已禁用")
    return user
```

### 3.2 Tenant 模块（多租户行级隔离）

**流程：**
```
请求 → Header: X-Tenant-ID
    ↓
中间件: set_current_tenant(tenant_id)
    ↓
所有 DB 查询自动带上 tenant_id 过滤
```

**关键设计：**
- **租户上下文**：通过 `ContextVar` 在请求生命周期中传播
- **行级隔离**：所有业务表含 `tenant_id` 列，基座提供 `TenantFilter` mixin
- **Super Admin**：无 tenant 限制（`tenant_id = NULL`），可跨租户管理
- **默认租户**：系统内置 `default` 租户，用于 Super Admin 登录

### 3.3 Event Bus（事件总线，内存版）

```python
# 发布
await event_bus.emit("user.created", {"user_id": 1, "tenant_id": "t-001"})

# 订阅
@event_bus.on("user.created")
async def on_user_created(payload: dict):
    # 初始化默认角色
    await assign_default_role(payload["user_id"], payload["tenant_id"])
```

**关键设计：**
- 第一版使用内存版（asyncio.Queue），零外部依赖
- 接口统一：`emit(event_name, payload)` / `on(event_name, handler)`
- 未来可无痛切换到 Redis Pub/Sub

### 3.4 System 模块（配置 / 日志 / 健康检查）

- **配置**：Pydantic Settings，`.env` → `BaseSettings`，按模块分区
- **日志**：structlog + 自动注入 `request_id`, `tenant_id`, `user_id`
- **健康检查**：`GET /health`（DB + Redis 联通性检查）

---

## 4. RBAC 业务模块设计（第一条验证线）

### 4.1 数据模型

```
┌──────────┐     ┌──────────────┐     ┌──────────┐
│   User   │────→│  UserRole    │←────│   Role   │
│          │     │ user_id      │     │          │
│          │     │ role_id      │     │  name    │
│          │     │ tenant_id    │     │  desc    │
│ tenant_id│     └──────────────┘     │ is_system│
└──────────┘                          └────┬─────┘
                                           │
                                           ↓
                                    ┌──────────────┐
                                    │RolePermission│
                                    │  role_id     │
                                    │  permission  │ (字符串 "user:read")
                                    └──────────────┘
```

- **Users** — 全局用户表（含 `tenant_id`）
- **Roles** — 角色定义（含 `tenant_id`, `is_system`）
- **Permissions** — 权限定义表（预置数据，如 `user:read`, `role:create`）
- **UserRoles** — 用户-角色多对多关联
- **RolePermissions** — 角色-权限多对多关联

**系统预置角色：** `admin` / `editor` / `viewer`（`is_system=True`，不可删除）

### 4.2 API 端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/rbac/roles` | 创建角色 | `role:create` |
| GET | `/api/v1/rbac/roles` | 角色列表 | `role:read` |
| GET | `/api/v1/rbac/roles/{id}` | 角色详情 | `role:read` |
| PUT | `/api/v1/rbac/roles/{id}` | 更新角色 | `role:update` |
| DELETE | `/api/v1/rbac/roles/{id}` | 删除角色 | `role:delete` |
| POST | `/api/v1/rbac/roles/{id}/permissions` | 分配权限 | `role:update` |
| GET | `/api/v1/rbac/permissions` | 可用权限列表 | `role:read` |
| POST | `/api/v1/rbac/users/{id}/roles` | 为用户分配角色 | `user:assign_role` |
| GET | `/api/v1/rbac/users/{id}/roles` | 查看用户角色 | `user:read` |

### 4.3 `require_permission` 权限检查

```python
@router.get("/users", dependencies=[Depends(require_permission("user:read"))])
async def list_users(...):
    ...

# require_permission 内部逻辑：
# 1. 获取当前用户 (get_current_user)
# 2. 查询用户的所有角色
# 3. 查询角色关联的所有权限
# 4. 匹配 → 放行 or 403
```

### 4.4 多租户行为

- 每个租户独立管理自己的角色和权限
- 租户创建时自动初始化 `admin` / `editor` / `viewer` 默认角色
- Super Admin（`tenant_id = NULL`）可跨租户查看/管理

---

## 5. 工程目录结构

```
fastapi-platform/
├── src/
│   ├── base/                      # 基座（独立 package）
│   │   ├── __init__.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── models.py          # User, RefreshToken
│   │   │   ├── schemas.py         # LoginRequest, TokenResponse
│   │   │   ├── service.py         # 登录/注册/刷新逻辑
│   │   │   ├── router.py          # /api/v1/auth/*
│   │   │   └── deps.py            # get_current_user
│   │   ├── tenant/
│   │   │   ├── __init__.py
│   │   │   ├── models.py          # Tenant
│   │   │   ├── service.py
│   │   │   ├── middleware.py       # set_current_tenant
│   │   │   └── deps.py            # get_current_tenant, TenantFilter
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   └── bus.py             # emit / on (内存版)
│   │   └── system/
│   │       ├── __init__.py
│   │       ├── config.py          # Pydantic Settings
│   │       ├── logging.py         # structlog 配置
│   │       └── health.py          # /health
│   ├── rbac/                      # 业务模块: RBAC
│   │   ├── __init__.py
│   │   ├── models.py              # Role, Permission, UserRole, RolePermission
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── router.py              # /api/v1/rbac/*
│   │   └── deps.py                # require_permission
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py             # AsyncSession factory
│   │   └── base.py                # BaseModel (declarative base)
│   └── main.py                    # FastAPI app 组装
├── alembic/
│   └── versions/
├── tests/
│   ├── base/
│   │   ├── test_auth.py
│   │   └── test_tenant.py
│   └── rbac/
│       ├── test_roles.py
│       └── test_permissions.py
├── alembic.ini
├── pyproject.toml
├── .env.example
└── docker-compose.yml             # PostgreSQL + Redis
```

---

## 6. 技术治理与运维

### 6.1 技术选型

| 关注点 | 选型 | 理由 |
|--------|------|------|
| **Web 框架** | FastAPI 0.111+ | 异步原生、Pydantic v2、依赖注入 |
| **ORM** | SQLAlchemy 2.0 asyncio | 成熟、与 FastAPI 深度集成 |
| **迁移** | Alembic | SQLAlchemy 官方配套 |
| **数据库** | PostgreSQL 16 | 行级安全、JSONB、ACID |
| **缓存/消息** | Redis 7 | JWT 黑名单、速率限制 |
| **序列化** | Pydantic v2 | 与 FastAPI 一体 |
| **日志** | structlog | 结构化日志，自动绑定上下文 |
| **限流** | slowapi | 基于 Redis，简单够用 |

### 6.2 安全

- **限流**：`/auth/login` 5次/分钟/IP，普通 API 100次/分钟
- **审计**：关键操作（角色变更、权限分配）写入 `audit_log` 表
- **CORS**：白名单配置
- **密码**：bcrypt 哈希，最小长度 8

### 6.3 部署

- **开发环境**：`docker-compose up`（PostgreSQL + Redis + App）
- **生产环境**：Docker 镜像 + K8s（后续，当前暂不引入）

### 6.4 测试策略

- **单元测试**：pytest + httpx (async)
- **覆盖范围**：鉴权流（登录/登出/刷新）、RBAC CRUD 全链路
- **测试数据库**：独立 PostgreSQL 容器

---

## 7. 扩展：新业务线接入标准流程

未来接入新业务线（如 CRM）的标准步骤：

1. 创建 `src/crm/` package，包含 `models.py`, `schemas.py`, `service.py`, `router.py`
2. Models 继承基座 `TenantFilter` mixin，自动获得租户隔离
3. Routers 使用 `require_permission` 保护端点
4. 在 `main.py` 中 `app.include_router(crm_router)`
5. 运行 `alembic revision --autogenerate` 生成迁移
6. 通过 Event Bus 与其他模块通信（如有需要）

---

*本文档由 brainstorming skill 生成，后续实现将通过 writing-plans skill 编排。*
