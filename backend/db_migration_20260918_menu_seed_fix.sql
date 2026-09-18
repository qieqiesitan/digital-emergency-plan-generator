-- 权限种子补齐（W2）：
-- 1) menu:regulations 历史上靠手工插库，全新安装会缺 → 法规管理页对 admin 直接 403
-- 2) 普通用户拥有企业数据但没有 menu:enterprises → /enterprises 403（信息架构矛盾）
-- 3) AI 配置页菜单对 user 开放、后端接口却 require_admin → 移除 user 的 menu:ai_config
--    （AI 配置是系统级设置；用户级 AI Key 如需开放属于新产品能力，另行实现）

INSERT INTO permissions (id, code, name, resource, action, category)
VALUES (gen_random_uuid(), 'menu:regulations', '法规管理', 'menu', 'regulations', 'menu')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('admin', 'super_admin')
  AND p.code = 'menu:regulations'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'user'
  AND p.code = 'menu:enterprises'
ON CONFLICT DO NOTHING;

DELETE FROM role_permissions rp
USING roles r, permissions p
WHERE rp.role_id = r.id
  AND rp.permission_id = p.id
  AND r.code = 'user'
  AND p.code = 'menu:ai_config';
