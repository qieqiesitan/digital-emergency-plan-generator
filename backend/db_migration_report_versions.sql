-- 风险评估/资源调查报告：支持编辑保存与版本快照（复用预案版本模式）
ALTER TABLE risk_assessment_reports ADD COLUMN IF NOT EXISTS current_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE resource_investigation_reports ADD COLUMN IF NOT EXISTS current_version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS risk_assessment_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES risk_assessment_reports(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by VARCHAR(20) NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_risk_assessment_versions_report ON risk_assessment_versions(report_id);

CREATE TABLE IF NOT EXISTS resource_investigation_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES resource_investigation_reports(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by VARCHAR(20) NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_resource_investigation_versions_report ON resource_investigation_versions(report_id);
