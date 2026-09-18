-- 修复：chat_messages.seq 的默认值引用 chat_messages_seq，但历史库里该序列可能缺失
-- （2026-09-19 空库演练发现：全新安装时 create_all 因缺序列直接失败）。
-- 本迁移幂等补齐序列，并把序列当前值对齐到现有最大 seq，避免新消息序号回退。

CREATE SEQUENCE IF NOT EXISTS chat_messages_seq;

DO $$
DECLARE
    max_seq bigint;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 'chat_messages') THEN
        SELECT COALESCE(MAX(seq), 0) INTO max_seq FROM chat_messages;
        IF max_seq > 0 THEN
            PERFORM setval('chat_messages_seq', max_seq, true);
        END IF;
    END IF;
END $$;
