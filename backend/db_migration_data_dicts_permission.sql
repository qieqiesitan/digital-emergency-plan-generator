-- 数据字典管理菜单权限补种（幂等，可重复执行）
-- 背景：MainLayout 菜单项受 hasMenu("/settings/data-dicts")（权限码 menu:data_dicts）
-- 门控，但既有种子/迁移均未含该权限，导致任何角色侧栏都看不到入口。
-- 按 seed_roles.sql 中 menu:prompts / 存量库 menu:regulations 的分配模式：
-- super_admin 全量权限、admin 菜单权限（除 menu:roles）。

INSERT INTO permissions (id, code, name, resource, action, category) VALUES
  (gen_random_uuid(), 'menu:data_dicts', '数据字典管理', 'menu', 'data_dicts', 'menu')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code = 'menu:data_dicts'
WHERE r.code IN ('super_admin', 'admin')
ON CONFLICT DO NOTHING;
