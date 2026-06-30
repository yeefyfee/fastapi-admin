-- ============================================
-- Enterprise Platform — 数据库初始化 SQL
-- 此文件由 SQLAlchemy 模型自动导出，仅作参考。
-- 生产环境使用: alembic upgrade head
-- ============================================

-- 1. 创建 uuid-ossp 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. 租户表
CREATE TABLE IF NOT EXISTS auth_tenants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(128) NOT NULL,
    slug        VARCHAR(64)  NOT NULL UNIQUE,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 3. 用户表（全局用户，不绑定租户）
CREATE TABLE IF NOT EXISTS auth_users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(128) NOT NULL DEFAULT '',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    is_super_admin  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 4. 角色表（租户级）
CREATE TABLE IF NOT EXISTS auth_roles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(64)  NOT NULL,
    description VARCHAR(256) NOT NULL DEFAULT '',
    is_system   BOOLEAN      NOT NULL DEFAULT FALSE,
    tenant_id   VARCHAR(64)  REFERENCES auth_tenants(slug),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 5. 权限定义表（全局）
CREATE TABLE IF NOT EXISTS auth_permissions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code        VARCHAR(128) NOT NULL UNIQUE,
    description VARCHAR(256) NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 6. 角色-权限关联表
CREATE TABLE IF NOT EXISTS auth_role_permissions (
    id         SERIAL PRIMARY KEY,
    role_id    UUID         NOT NULL REFERENCES auth_roles(id) ON DELETE CASCADE,
    permission VARCHAR(128) NOT NULL,
    UNIQUE(role_id, permission)
);

-- 7. 用户-角色关联表（租户级）
CREATE TABLE IF NOT EXISTS auth_user_roles (
    id         SERIAL PRIMARY KEY,
    user_id    UUID        NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    role_id    UUID        NOT NULL REFERENCES auth_roles(id) ON DELETE CASCADE,
    tenant_id  VARCHAR(64) REFERENCES auth_tenants(slug),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, role_id)
);

-- 8. 示例业务表：文章
CREATE TABLE IF NOT EXISTS demo_articles (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title      VARCHAR(256) NOT NULL,
    content    TEXT         NOT NULL DEFAULT '',
    author_id  UUID         NOT NULL REFERENCES auth_users(id),
    tenant_id  VARCHAR(64)  REFERENCES auth_tenants(slug),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 9. 索引
CREATE INDEX IF NOT EXISTS idx_auth_users_email        ON auth_users(email);
CREATE INDEX IF NOT EXISTS idx_auth_tenants_slug        ON auth_tenants(slug);
CREATE INDEX IF NOT EXISTS idx_auth_roles_tenant        ON auth_roles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_auth_user_roles_user     ON auth_user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_user_roles_tenant   ON auth_user_roles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_demo_articles_author     ON demo_articles(author_id);
CREATE INDEX IF NOT EXISTS idx_demo_articles_tenant     ON demo_articles(tenant_id);
