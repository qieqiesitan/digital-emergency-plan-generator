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
    sign_policy VARCHAR(10) NOT NULL DEFAULT 'any',
    condition_expr VARCHAR(200),
    reject_to VARCHAR(20) NOT NULL DEFAULT 'previous',
    is_statutory BOOLEAN NOT NULL DEFAULT FALSE,
    timeout_hours INTEGER,
    CONSTRAINT uq_wtfn_flow_order UNIQUE (flow_template_id, sort_order),
    CONSTRAINT uq_wtfn_flow_key UNIQUE (flow_template_id, node_key)
);
