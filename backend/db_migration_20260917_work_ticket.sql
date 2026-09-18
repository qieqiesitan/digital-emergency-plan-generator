-- 20260917 作业票模板层（票面字段 / 措施库 / 审批流程 / 流程节点）
-- 要点：is_statutory 标记法定审批环节，服务层据此拒绝删除（"可加不可删"）。

CREATE TABLE IF NOT EXISTS work_ticket_templates (
    id UUID PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(200) NOT NULL,
    level VARCHAR(20),
    is_graded BOOLEAN NOT NULL DEFAULT FALSE,
    standard_ref VARCHAR(80) NOT NULL DEFAULT 'GB 30871-2022',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_wtt_code_level
    ON work_ticket_templates (code, COALESCE(level, ''));

CREATE TABLE IF NOT EXISTS work_ticket_template_fields (
    id UUID PRIMARY KEY,
    template_id UUID NOT NULL REFERENCES work_ticket_templates(id) ON DELETE CASCADE,
    field_key VARCHAR(60) NOT NULL,
    label VARCHAR(200) NOT NULL,
    field_type VARCHAR(20) NOT NULL DEFAULT 'text',
    group_name VARCHAR(40) NOT NULL DEFAULT '基本信息',
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    options JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation JSONB NOT NULL DEFAULT '{}'::jsonb,
    allow_ai_prefill BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_wttf_template_key UNIQUE (template_id, field_key)
);

CREATE TABLE IF NOT EXISTS work_ticket_template_measures (
    id UUID PRIMARY KEY,
    template_id UUID NOT NULL REFERENCES work_ticket_templates(id) ON DELETE CASCADE,
    measure_text TEXT NOT NULL,
    article_anchor VARCHAR(120) NOT NULL,
    is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_wttm_template_order
    ON work_ticket_template_measures (template_id, sort_order);

CREATE TABLE IF NOT EXISTS work_ticket_flow_templates (
    id UUID PRIMARY KEY,
    template_id UUID NOT NULL REFERENCES work_ticket_templates(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS work_ticket_flow_nodes (
    id UUID PRIMARY KEY,
    flow_template_id UUID NOT NULL REFERENCES work_ticket_flow_templates(id) ON DELETE CASCADE,
    node_key VARCHAR(60) NOT NULL,
    name VARCHAR(200) NOT NULL,
    sort_order INTEGER NOT NULL,
    role_code VARCHAR(30),
    countersign_units JSONB,
    sign_policy VARCHAR(10) NOT NULL DEFAULT 'any',
    condition_expr VARCHAR(200),
    reject_to VARCHAR(20) NOT NULL DEFAULT 'previous',
    is_statutory BOOLEAN NOT NULL DEFAULT FALSE,
    timeout_hours INTEGER,
    CONSTRAINT uq_wtfn_flow_order UNIQUE (flow_template_id, sort_order),
    CONSTRAINT uq_wtfn_flow_key UNIQUE (flow_template_id, node_key)
);

CREATE TABLE IF NOT EXISTS work_ticket_instances (
    id UUID PRIMARY KEY,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES work_ticket_templates(id) ON DELETE RESTRICT,
    flow_template_id UUID REFERENCES work_ticket_flow_templates(id) ON DELETE SET NULL,
    code VARCHAR(64) NOT NULL,
    ticket_type VARCHAR(20) NOT NULL,
    level VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    current_node_key VARCHAR(60),
    current_order INTEGER NOT NULL DEFAULT 0,
    values JSONB NOT NULL DEFAULT '{}'::jsonb,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    extend_count INTEGER NOT NULL DEFAULT 0,
    cancel_reason TEXT,
    submitted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_wti_ent_code UNIQUE (enterprise_id, code)
);
CREATE INDEX IF NOT EXISTS idx_wti_enterprise_status ON work_ticket_instances (enterprise_id, status);
CREATE INDEX IF NOT EXISTS ix_wti_valid_to ON work_ticket_instances (valid_to);

CREATE TABLE IF NOT EXISTS work_ticket_node_records (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES work_ticket_instances(id) ON DELETE CASCADE,
    node_key VARCHAR(60) NOT NULL,
    action VARCHAR(20) NOT NULL,
    opinion TEXT,
    acted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtnr_instance ON work_ticket_node_records (instance_id, created_at);

CREATE TABLE IF NOT EXISTS work_ticket_gas_tests (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES work_ticket_instances(id) ON DELETE CASCADE,
    sampled_at TIMESTAMPTZ NOT NULL,
    location VARCHAR(200),
    gas_type VARCHAR(100),
    result VARCHAR(100),
    tester VARCHAR(100),
    conclusion VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtgt_instance ON work_ticket_gas_tests (instance_id, sampled_at);

CREATE TABLE IF NOT EXISTS work_ticket_audit_logs (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES work_ticket_instances(id) ON DELETE CASCADE,
    action VARCHAR(30) NOT NULL,
    from_status VARCHAR(20),
    to_status VARCHAR(20),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    acted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtal_instance ON work_ticket_audit_logs (instance_id, created_at);

CREATE TABLE IF NOT EXISTS work_ticket_print_snapshots (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES work_ticket_instances(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    content_hash VARCHAR(64) NOT NULL,
    snapshot JSONB NOT NULL,
    printed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_wtps_instance_version UNIQUE (instance_id, version)
);
