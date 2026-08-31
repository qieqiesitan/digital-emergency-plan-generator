-- 第三方配置统一管理：third_party_config 表 + 菜单权限点 menu:third_party_config
-- 幂等：CREATE TABLE IF NOT EXISTS / ON CONFLICT DO NOTHING 保护式，可重复执行。
-- 背景：企查查/高德/PROTEGO 密钥统一收口到 DB（secret 加密存储，env 兜底），
-- 管理员页面（任务 4 API 已实现）按菜单权限 menu:third_party_config 门控展示。
-- 权限分配沿用 seed_roles.sql / db_migration_data_dicts_permission.sql 模式：
-- super_admin 全量权限、admin 菜单权限（除 menu:roles）。

-- 1) 配置表（与 app/models/third_party_config.py 对齐）
CREATE TABLE IF NOT EXISTS third_party_config (
    config_key   VARCHAR(128) PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type  VARCHAR(16) NOT NULL DEFAULT 'secret',
    description  VARCHAR(512),
    updated_by   VARCHAR(64),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2) 菜单权限点
INSERT INTO permissions (id, code, name, resource, action, category) VALUES
  (gen_random_uuid(), 'menu:third_party_config', '第三方配置', 'menu', 'third_party_config', 'menu')
ON CONFLICT (code) DO NOTHING;

-- 3) 授予 super_admin / admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code = 'menu:third_party_config'
WHERE r.code IN ('super_admin', 'admin')
ON CONFLICT DO NOTHING;
