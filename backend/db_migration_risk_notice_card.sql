BEGIN;

-- 风险告知卡：risk_objects 新增字段
ALTER TABLE risk_objects
    ADD COLUMN IF NOT EXISTS responsible_unit VARCHAR(255),
    ADD COLUMN IF NOT EXISTS responsible_person VARCHAR(100),
    ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50),
    ADD COLUMN IF NOT EXISTS public_token VARCHAR(64);

-- 存量行补随机 token（迁移幂等：仅空值行，64 位 hex 与模型默认一致）
UPDATE risk_objects
   SET public_token = encode(gen_random_bytes(32), 'hex')
 WHERE public_token IS NULL OR public_token = '';

ALTER TABLE risk_objects ALTER COLUMN public_token SET NOT NULL;
ALTER TABLE risk_objects ALTER COLUMN public_token SET DEFAULT encode(gen_random_bytes(32), 'hex');
CREATE UNIQUE INDEX IF NOT EXISTS uq_risk_objects_public_token ON risk_objects(public_token);

-- 风险告知卡快照表
CREATE TABLE IF NOT EXISTS risk_notice_cards (
    id UUID PRIMARY KEY,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    object_id UUID NOT NULL REFERENCES risk_objects(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    content JSONB NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'ai',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_risk_notice_cards_object UNIQUE (object_id)
);
CREATE INDEX IF NOT EXISTS idx_rnc_enterprise ON risk_notice_cards(enterprise_id);

COMMIT;
