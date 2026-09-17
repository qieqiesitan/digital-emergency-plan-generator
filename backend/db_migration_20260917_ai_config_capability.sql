-- 20260917 AI 配置支持按能力覆盖模型（如抽取用便宜的小模型、报告用强模型）
-- 覆盖结构：{"extract": {"model": "small"}, "report": {"model": "big"}}
-- 只认白名单键（见 ai_config_service.ALLOWED_OVERRIDE_KEYS），其余键被忽略。

ALTER TABLE ai_configs
    ADD COLUMN IF NOT EXISTS capability_overrides JSONB NOT NULL DEFAULT '{}'::jsonb;
