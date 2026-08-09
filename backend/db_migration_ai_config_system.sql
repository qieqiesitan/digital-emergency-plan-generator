-- AI 配置全局化：user_id 可空（NULL = 系统级配置），加 is_system 标记
ALTER TABLE ai_configs ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE ai_configs ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;
