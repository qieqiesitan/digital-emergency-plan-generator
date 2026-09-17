-- 20260917 DataHub 数据接入适配层（来源/映射/任务/条目/对账）
-- 硬规则：raw_payload 永久保留；idempotency_key 数据库级唯一；密钥只存 secret_ref。

CREATE TABLE IF NOT EXISTS ingest_sources (
    id UUID PRIMARY KEY,
    source_type VARCHAR(20) NOT NULL,
    name VARCHAR(200) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    secret_ref VARCHAR(120),
    target_entity VARCHAR(60),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS field_mappings (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES ingest_sources(id) ON DELETE CASCADE,
    target_entity VARCHAR(60) NOT NULL,
    mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    transforms JSONB NOT NULL DEFAULT '{}'::jsonb,
    required_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_fm_source_entity UNIQUE (source_id, target_entity)
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id UUID PRIMARY KEY,
    source_id UUID REFERENCES ingest_sources(id) ON DELETE SET NULL,
    trigger VARCHAR(20) NOT NULL DEFAULT 'manual',
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    total INTEGER NOT NULL DEFAULT 0,
    imported INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    pending_review INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_source ON ingest_jobs (source_id, created_at);

CREATE TABLE IF NOT EXISTS ingest_items (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES ingest_jobs(id) ON DELETE CASCADE,
    idempotency_key VARCHAR(300) NOT NULL,
    raw_payload JSONB NOT NULL,
    target_entity VARCHAR(60) NOT NULL,
    target_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    source_locator VARCHAR(200),
    confidence VARCHAR(10) NOT NULL DEFAULT 'medium',
    review_note TEXT,
    error TEXT,
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ingest_items_idem UNIQUE (idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_ingest_items_job_status ON ingest_items (job_id, status);

CREATE TABLE IF NOT EXISTS ingest_reconciliations (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES ingest_sources(id) ON DELETE CASCADE,
    expected_count INTEGER NOT NULL DEFAULT 0,
    actual_count INTEGER NOT NULL DEFAULT 0,
    diff_note TEXT,
    checksum VARCHAR(80),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 菜单权限补种：数据接入（super_admin / admin 默认可见）
INSERT INTO permissions (id, code, name, resource, action, category) VALUES
  (gen_random_uuid(), 'menu:data_hub', '数据接入', 'menu', 'data_hub', 'menu')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code = 'menu:data_hub'
WHERE r.code IN ('super_admin', 'admin')
ON CONFLICT DO NOTHING;

-- 补数据库级默认值：启动迁移器会先执行 Base.metadata.create_all，
-- 已存在的表不会走上面的 CREATE TABLE，ORM 的 Python 默认值只在本进程生效。
-- 这里显式 SET DEFAULT，保证裸 SQL 插入（运维/外部排障）也不会写出 NULL。
ALTER TABLE ingest_sources ALTER COLUMN is_active SET DEFAULT TRUE;
ALTER TABLE ingest_jobs ALTER COLUMN trigger SET DEFAULT 'manual';
ALTER TABLE ingest_jobs ALTER COLUMN status SET DEFAULT 'running';
ALTER TABLE ingest_jobs ALTER COLUMN total SET DEFAULT 0;
ALTER TABLE ingest_jobs ALTER COLUMN imported SET DEFAULT 0;
ALTER TABLE ingest_jobs ALTER COLUMN skipped SET DEFAULT 0;
ALTER TABLE ingest_jobs ALTER COLUMN failed SET DEFAULT 0;
ALTER TABLE ingest_jobs ALTER COLUMN pending_review SET DEFAULT 0;
ALTER TABLE ingest_items ALTER COLUMN status SET DEFAULT 'pending';
ALTER TABLE ingest_items ALTER COLUMN confidence SET DEFAULT 'medium';
ALTER TABLE field_mappings ALTER COLUMN status SET DEFAULT 'active';
ALTER TABLE ingest_reconciliations ALTER COLUMN expected_count SET DEFAULT 0;
ALTER TABLE ingest_reconciliations ALTER COLUMN actual_count SET DEFAULT 0;
