-- 任务 8：chat_messages 增加 name 列（存储 role=tool 消息的函数名）
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS name VARCHAR(100);
