-- 20260919 角色/权限基线种子（幂等，仅插入缺失项）
--
-- 背景（2026-09-19 空库演练）：`backend/app/seed_roles.sql` 从未被任何迁移/启动流程执行，
-- 结果**全新安装的库里 roles/permissions 为空**：角色管理页空白、新用户的菜单权限
-- 只能走前端降级路径。本迁移把该种子纳入迁移链，空库/缺权限的库都会补齐；
-- 已存在的 code 一律跳过（ON CONFLICT DO NOTHING），不覆盖线上自定义角色与权限。
--
-- 说明：原 `app/seed_roles.sql` 已删除，本文件即唯一来源；需要调整基线时改这里。

-- 角色预设
INSERT INTO roles (id, code, name, is_system, description) VALUES
  (gen_random_uuid(), 'super_admin', '超级管理员', TRUE, '系统最高权限，可管理所有资源'),
  (gen_random_uuid(), 'admin',       '管理员',     TRUE, '可管理企业和用户'),
  (gen_random_uuid(), 'user',        '普通用户',   TRUE, '基础权限，可创建和编辑自己的预案')
ON CONFLICT (code) DO NOTHING;

-- 操作权限
INSERT INTO permissions (id, code, name, resource, action, category) VALUES
  (gen_random_uuid(), 'user:create',   '创建用户', 'user',   'create', 'action'),
  (gen_random_uuid(), 'user:read',     '查看用户', 'user',   'read',   'action'),
  (gen_random_uuid(), 'user:update',   '编辑用户', 'user',   'update', 'action'),
  (gen_random_uuid(), 'user:delete',   '删除用户', 'user',   'delete', 'action'),
  (gen_random_uuid(), 'role:manage',   '角色管理', 'system', 'manage', 'action'),
  (gen_random_uuid(), 'system:config', '系统配置', 'system', 'manage', 'action')
ON CONFLICT (code) DO NOTHING;

-- 菜单权限（所有系统页面）
INSERT INTO permissions (id, code, name, resource, action, category) VALUES
  (gen_random_uuid(), 'menu:dashboard',       '工作台',      'menu', 'dashboard',       'menu'),
  (gen_random_uuid(), 'menu:enterprises',     '企业管理',    'menu', 'enterprises',     'menu'),
  (gen_random_uuid(), 'menu:plans',           '预案列表',    'menu', 'plans',           'menu'),
  (gen_random_uuid(), 'menu:users',           '用户管理',    'menu', 'users',           'menu'),
  (gen_random_uuid(), 'menu:roles',           '角色管理',    'menu', 'roles',           'menu'),
  (gen_random_uuid(), 'menu:system_config',   '系统配置',    'menu', 'system_config',   'menu'),
  (gen_random_uuid(), 'menu:prompts',         '提示词管理',  'menu', 'prompts',         'menu'),
  (gen_random_uuid(), 'menu:profile',         '个人资料',    'menu', 'profile',         'menu'),
  (gen_random_uuid(), 'menu:ai_config',       'AI 配置',     'menu', 'ai_config',       'menu')
ON CONFLICT (code) DO NOTHING;

-- 角色-权限分配
DO $$
DECLARE
  super_id UUID; admin_id UUID; user_id UUID;
BEGIN
  SELECT id INTO super_id FROM roles WHERE code = 'super_admin';
  SELECT id INTO admin_id FROM roles WHERE code = 'admin';
  SELECT id INTO user_id  FROM roles WHERE code = 'user';

  -- super_admin: 全部权限
  INSERT INTO role_permissions (role_id, permission_id)
    SELECT super_id, id FROM permissions
  ON CONFLICT DO NOTHING;

  -- admin: 操作权限 user:* + 菜单权限(除角色管理)
  INSERT INTO role_permissions (role_id, permission_id)
    SELECT admin_id, id FROM permissions WHERE resource = 'user'
  ON CONFLICT DO NOTHING;
  INSERT INTO role_permissions (role_id, permission_id)
    SELECT admin_id, id FROM permissions WHERE category = 'menu' AND code != 'menu:roles'
  ON CONFLICT DO NOTHING;

  -- user: 基础菜单（工作台+企业管理+预案列表+个人资料）
  -- 注：menu:ai_config 属系统级设置（W2 起 require_admin），基线不给普通用户
  INSERT INTO role_permissions (role_id, permission_id)
    SELECT user_id, id FROM permissions WHERE code IN (
      'menu:dashboard', 'menu:enterprises', 'menu:plans', 'menu:profile'
    )
  ON CONFLICT DO NOTHING;
END $$;
