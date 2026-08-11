-- 风险告知卡：risk_objects 新增字段
ALTER TABLE risk_objects
    ADD COLUMN IF NOT EXISTS responsible_unit VARCHAR(255),
    ADD COLUMN IF NOT EXISTS responsible_person VARCHAR(100),
    ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50),
    ADD COLUMN IF NOT EXISTS public_token VARCHAR(64);

-- 存量行补随机 token（迁移幂等：仅空值行）
UPDATE risk_objects
   SET public_token = substr(md5(random()::text || clock_timestamp()::text), 1, 64)
 WHERE public_token IS NULL OR public_token = '';

ALTER TABLE risk_objects ALTER COLUMN public_token SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_risk_objects_public_token ON risk_objects(public_token);
