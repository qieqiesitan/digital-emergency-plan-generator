-- 2026-09-02: 用户偏好表（阶段 3 模块 13：跨会话记忆偏好）
-- 幂等：CREATE TABLE IF NOT EXISTS；既有库/空库均可重复执行。
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    style_preference VARCHAR(20),
    detail_level VARCHAR(20),
    report_topics JSONB,
    common_enterprise_ids JSONB,
    extra TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
