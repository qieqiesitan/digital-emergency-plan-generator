-- 风格个性化 — 数据模型变更
-- 迁移日期: 2026-07-27
-- 注意: 这些列允许 NULL，已有行默认 fallback 到标准风格

ALTER TABLE plan_projects ADD COLUMN IF NOT EXISTS style_preference JSONB;
ALTER TABLE plan_projects ADD COLUMN IF NOT EXISTS advanced_prompt_overrides JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_style_preference JSONB;

-- 验证
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name IN ('plan_projects', 'users')
  AND column_name IN ('style_preference', 'advanced_prompt_overrides', 'default_style_preference')
ORDER BY table_name, column_name;
