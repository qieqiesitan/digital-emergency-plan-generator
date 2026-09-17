-- 20260917 LLM 调用留痕：回答"花了多少 / 哪次失败 / 是不是被截断"
-- 背景：此前任何 AI 调用都没有记录，出问题只能靠猜。

CREATE TABLE IF NOT EXISTS llm_call_logs (
    id UUID PRIMARY KEY,
    module VARCHAR(64) NOT NULL,
    capability VARCHAR(64) NOT NULL,
    model VARCHAR(120),
    prompt_version VARCHAR(64),
    duration_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_code INTEGER,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    truncated BOOLEAN NOT NULL DEFAULT FALSE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    enterprise_id UUID REFERENCES enterprises(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 统计按 module + 时间查；按纯时间查的（近 30 天总量）也要走索引
CREATE INDEX IF NOT EXISTS idx_llm_log_module_time ON llm_call_logs (module, created_at);
CREATE INDEX IF NOT EXISTS ix_llm_log_created_at ON llm_call_logs (created_at);
