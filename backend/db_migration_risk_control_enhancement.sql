-- 风险分级管控增强：风险事件双等级字段 + 企业公开风险 token
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS inherent_risk_level VARCHAR(20);
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS inherent_risk_score VARCHAR(50);
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS control_level VARCHAR(20);
UPDATE risk_events SET inherent_risk_level = risk_level WHERE inherent_risk_level IS NULL;
UPDATE risk_events SET inherent_risk_score = risk_score WHERE inherent_risk_score IS NULL;

ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS public_risk_token VARCHAR(64);
CREATE UNIQUE INDEX IF NOT EXISTS uq_enterprises_public_risk_token
    ON enterprises(public_risk_token) WHERE public_risk_token IS NOT NULL;
