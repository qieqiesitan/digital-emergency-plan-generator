-- 20260920 作业票智能预填：来源留痕、措施三态、成员证照
-- 三列均为非空 + 默认值，老行自动填充，幂等可重复执行。

ALTER TABLE work_ticket_instances
    ADD COLUMN IF NOT EXISTS values_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE work_ticket_instances
    ADD COLUMN IF NOT EXISTS measures_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE enterprise_members
    ADD COLUMN IF NOT EXISTS certificates JSONB NOT NULL DEFAULT '[]'::jsonb;

-- 核验（执行后手查）：
-- SELECT column_name, is_nullable, column_default FROM information_schema.columns
--  WHERE (table_name='work_ticket_instances' AND column_name IN ('values_meta','measures_meta'))
--     OR (table_name='enterprise_members' AND column_name='certificates');
-- 期望三行、is_nullable=NO、default 分别为 '{}'::jsonb / '{}'::jsonb / '[]'::jsonb
-- SELECT count(*) FROM work_ticket_instances WHERE values_meta IS NULL;  -- 期望 0
