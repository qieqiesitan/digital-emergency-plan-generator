-- 2026-09-03 报告工作台：报告级创作风格偏好列
ALTER TABLE risk_assessment_reports
  ADD COLUMN IF NOT EXISTS style_preference JSONB NOT NULL DEFAULT '{}';

ALTER TABLE resource_investigation_reports
  ADD COLUMN IF NOT EXISTS style_preference JSONB NOT NULL DEFAULT '{}';
