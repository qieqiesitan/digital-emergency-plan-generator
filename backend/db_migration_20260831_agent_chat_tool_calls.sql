-- 任务 8：chat_messages 增加 name 列（存储 role=tool 消息的函数名）
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS name VARCHAR(100);

-- 验证修复：chat_messages 增加 seq 自增列（同一事务内多条消息 created_at 相同，
-- 需按插入顺序排序，避免历史重建时 user/assistant/tool 顺序错乱）
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS seq BIGSERIAL;

-- 任务 3：chat_tool_calls 表（工具执行轨迹记录，进度回放数据源）
CREATE TABLE IF NOT EXISTS chat_tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    round_no INTEGER NOT NULL,
    fn_name VARCHAR(100) NOT NULL,
    fn_args JSONB,
    result TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_chat_tool_calls_conv ON chat_tool_calls(conversation_id, created_at);
