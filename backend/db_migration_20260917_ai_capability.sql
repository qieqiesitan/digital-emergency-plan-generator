-- 20260917 AI 能力注册表。
-- code 与 llm_call_logs.capability 对齐，便于把"能力"与其"调用记录"关联起来。
CREATE TABLE IF NOT EXISTS ai_capabilities (
    id UUID PRIMARY KEY,
    code VARCHAR(60) NOT NULL,
    module VARCHAR(60) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    prompt_ref VARCHAR(120),
    model_override VARCHAR(120),
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    allow_manual BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ai_capability_code UNIQUE (code)
);

-- 内置能力种子（与现有 24 个 AI 端点对应；用确定性 UUID5，可重复执行）
-- 显式写出 NOT NULL 列（is_enabled/allow_manual）：即使目标库的 DDL 来自
-- create_all（模型侧只有 ORM default、无库级默认值）也不会违反非空约束。
INSERT INTO ai_capabilities (id, code, module, name, description, sort_order, is_enabled, allow_manual) VALUES
 ('3f1a1c9e-0000-5000-8000-000000000001', 'risk_suggest_objects', '风险分级管控',
  'AI 建议风险分析对象', '按工艺/设备资料生成风险分析对象候选', 10, TRUE, TRUE),
 ('3f1a1c9e-0000-5000-8000-000000000002', 'risk_suggest_events', '风险分级管控',
  'AI 建议风险事件', '生成风险事件与后果描述', 20, TRUE, TRUE),
 ('3f1a1c9e-0000-5000-8000-000000000003', 'risk_suggest_measures', '风险分级管控',
  'AI 建议管控措施', '生成管控措施并匹配法规条文', 30, TRUE, TRUE),
 ('3f1a1c9e-0000-5000-8000-000000000004', 'hazard_record_assist', '隐患排查治理',
  '隐患登记辅助', '隐患摘要与分类', 40, TRUE, TRUE),
 ('3f1a1c9e-0000-5000-8000-000000000005', 'hazard_grade', '隐患排查治理',
  '隐患分级建议', '按认定依据建议隐患等级', 50, TRUE, TRUE),
 ('3f1a1c9e-0000-5000-8000-000000000006', 'major_hazard_extract', '重大危险源',
  '资料抽取（单元/品种）', '从安全评价报告中抽取重大危险源单元与品种存量', 60, TRUE, TRUE),
 ('3f1a1c9e-0000-5000-8000-000000000007', 'work_ticket_jsa', '特殊作业',
  'JSA 作业安全分析生成', '按作业内容生成危害识别与预防措施', 70, TRUE, TRUE),
 ('3f1a1c9e-0000-5000-8000-000000000008', 'work_ticket_precheck', '特殊作业',
  '提交前合规校验建议', '提示缺项与法规依据（不阻断，阻断由确定性校验负责）', 80, TRUE, TRUE)
ON CONFLICT (id) DO NOTHING;
