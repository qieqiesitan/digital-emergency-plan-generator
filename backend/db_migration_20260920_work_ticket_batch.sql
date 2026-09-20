-- 20260920 作业包（情景化批量开票）：一次检修的同地点同时段多张票共享信息
--
-- 三处结构变更：
--   1. 新表 work_ticket_batches（作业包容器）
--   2. work_ticket_instances.batch_id（票归属作业包）
--   3. work_ticket_gas_tests 支持"归属票"或"归属包"二选一（包级检测共享）
--
-- 幂等：表/列用 IF NOT EXISTS；CHECK 约束用 DO 块（PG 不支持 ADD CONSTRAINT IF NOT EXISTS）。

BEGIN;

CREATE TABLE IF NOT EXISTS work_ticket_batches (
    id                UUID PRIMARY KEY,
    enterprise_id     UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    title             VARCHAR(200) NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'draft',
    floor_id          UUID NULL REFERENCES enterprise_floors(id) ON DELETE SET NULL,
    zone_id           UUID NULL REFERENCES risk_zones(id) ON DELETE SET NULL,
    risk_object_id    UUID NULL REFERENCES risk_objects(id) ON DELETE SET NULL,
    location_text     VARCHAR(500) NULL,
    work_period_start TIMESTAMPTZ NULL,
    work_period_end   TIMESTAMPTZ NULL,
    shared_values     JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_base      TEXT NULL,
    risk_basis        TEXT NULL,
    created_by        UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtb_enterprise_status ON work_ticket_batches(enterprise_id, status);

ALTER TABLE work_ticket_instances
    ADD COLUMN IF NOT EXISTS batch_id UUID NULL REFERENCES work_ticket_batches(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_wti_batch ON work_ticket_instances(batch_id);

ALTER TABLE work_ticket_gas_tests ALTER COLUMN instance_id DROP NOT NULL;
ALTER TABLE work_ticket_gas_tests
    ADD COLUMN IF NOT EXISTS batch_id UUID NULL REFERENCES work_ticket_batches(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_wtgt_batch ON work_ticket_gas_tests(batch_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_wtgt_owner') THEN
        ALTER TABLE work_ticket_gas_tests ADD CONSTRAINT ck_wtgt_owner
            CHECK ((instance_id IS NULL) <> (batch_id IS NULL));
    END IF;
END $$;

COMMIT;

-- 核验（执行后手查）：
-- SELECT conname FROM pg_constraint WHERE conname='ck_wtgt_owner';                 -- 期望 1 行
-- SELECT count(*) FROM work_ticket_gas_tests WHERE (instance_id IS NULL) = (batch_id IS NULL);  -- 期望 0
-- SELECT is_nullable FROM information_schema.columns
--  WHERE table_name='work_ticket_gas_tests' AND column_name='instance_id';         -- 期望 YES
