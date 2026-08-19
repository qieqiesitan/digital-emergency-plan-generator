-- 成员支持不绑定账号：user_id 可空 + name/phone/email 字段
-- 应用场景：组织与人员管理中添加成员时可不绑定账号，仅登记人员信息（非用户方式为主）。
ALTER TABLE enterprise_members ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE enterprise_members ADD COLUMN IF NOT EXISTS name VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE enterprise_members ADD COLUMN IF NOT EXISTS phone VARCHAR(30) NULL;
ALTER TABLE enterprise_members ADD COLUMN IF NOT EXISTS email VARCHAR(255) NULL;

-- 存量成员回填姓名
UPDATE enterprise_members m
SET name = u.name
FROM users u
WHERE m.user_id = u.id AND m.name = '';

-- 唯一约束改为部分唯一索引（仅绑定账号时生效），同名未绑定成员允许存在
ALTER TABLE enterprise_members DROP CONSTRAINT IF EXISTS enterprise_members_enterprise_id_user_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_enterprise_members_bound_user
    ON enterprise_members(enterprise_id, user_id)
    WHERE user_id IS NOT NULL;
