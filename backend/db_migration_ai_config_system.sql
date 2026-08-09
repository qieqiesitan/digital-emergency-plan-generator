-- AI 配置全局化：user_id 可空（NULL = 系统级配置），加 is_system 标记
ALTER TABLE ai_configs ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE ai_configs ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;

-- 系统级配置唯一（user_id 为 NULL 的行）
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_configs_system ON ai_configs (is_system) WHERE user_id IS NULL;

-- 数据回填：无系统级配置时，把最早的用户配置复制为系统配置（幂等：重复执行不产生重复）
INSERT INTO ai_configs (id, user_id, is_system, provider, api_key_encrypted, model_name, base_url, temperature, max_tokens, top_p, is_active)
SELECT gen_random_uuid(), NULL, TRUE, provider, api_key_encrypted, model_name, base_url, temperature, max_tokens, top_p, is_active
FROM ai_configs
WHERE user_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ai_configs WHERE user_id IS NULL AND is_system = TRUE)
ORDER BY created_at ASC, id ASC
LIMIT 1;
