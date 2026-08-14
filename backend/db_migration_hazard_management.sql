-- 隐患排查治理（B 规格 §5.1-5.10）：10 张 hazard_* 表 + 企业配置列 + B 字典种子 + 系统检查表模板种子
-- 幂等：全部 CREATE/ALTER/INSERT 均可重复执行；系统模板用部分唯一索引 + ON CONFLICT 去重。

-- 0) 检查表模板先建（hazard_inspection_plans.template_id 引用它）
CREATE TABLE IF NOT EXISTS hazard_checklist_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(20) NOT NULL,
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_hazard_checklist_templates_system_name
    ON hazard_checklist_templates(name) WHERE enterprise_id IS NULL;

-- 1) 排查计划
CREATE TABLE IF NOT EXISTS hazard_inspection_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(20) NOT NULL,
    frequency VARCHAR(20) NOT NULL,
    weekdays JSONB NULL,
    zone_ids JSONB NOT NULL,
    template_id UUID NULL REFERENCES hazard_checklist_templates(id) ON DELETE SET NULL,
    responsible_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    ai_suggestion JSONB NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hazard_inspection_plans_enterprise ON hazard_inspection_plans(enterprise_id);

-- 2) 排查任务
CREATE TABLE IF NOT EXISTS hazard_inspection_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES hazard_inspection_plans(id) ON DELETE CASCADE,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    title VARCHAR(255) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    responsible_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    due_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    overdue_notified_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hazard_inspection_tasks_plan ON hazard_inspection_tasks(plan_id);
CREATE INDEX IF NOT EXISTS idx_hazard_inspection_tasks_enterprise ON hazard_inspection_tasks(enterprise_id);

-- 3) 排查项
CREATE TABLE IF NOT EXISTS hazard_inspection_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES hazard_inspection_tasks(id) ON DELETE CASCADE,
    object_id UUID NULL REFERENCES risk_objects(id) ON DELETE SET NULL,
    measure_id UUID NULL REFERENCES risk_measures(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    expected_note TEXT NULL,
    result VARCHAR(10) NOT NULL DEFAULT 'pending',
    remark TEXT NULL,
    photo_urls JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hazard_inspection_items_task ON hazard_inspection_items(task_id);

-- 4) 隐患记录（code 企业内唯一）
CREATE TABLE IF NOT EXISTS hazard_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    code VARCHAR(32) NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    source_task_id UUID NULL,
    source_item_id UUID NULL,
    object_id UUID NULL REFERENCES risk_objects(id) ON DELETE SET NULL,
    measure_id UUID NULL REFERENCES risk_measures(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    photo_urls JSONB NULL,
    location VARCHAR(500) NULL,
    hazard_type VARCHAR(20) NULL,
    cause_analysis TEXT NULL,
    level VARCHAR(10) NULL,
    level_source VARCHAR(10) NULL,
    grading_basis TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'registered',
    rectification_plan JSONB NULL,
    deadline DATE NULL,
    rectification_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    reviewer_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    closed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_hazard_records_ent_code UNIQUE (enterprise_id, code)
);
CREATE INDEX IF NOT EXISTS idx_hazard_records_enterprise ON hazard_records(enterprise_id);

-- 5) 整改
CREATE TABLE IF NOT EXISTS hazard_rectifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES hazard_records(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    evidence JSONB NULL,
    submitted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hazard_rectifications_record ON hazard_rectifications(record_id);

-- 6) 复查
CREATE TABLE IF NOT EXISTS hazard_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES hazard_records(id) ON DELETE CASCADE,
    review_type VARCHAR(20) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    result VARCHAR(10) NOT NULL,
    comment TEXT NULL,
    evidence JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hazard_reviews_record ON hazard_reviews(record_id);

-- 7) 审批
CREATE TABLE IF NOT EXISTS hazard_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES hazard_records(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(10) NOT NULL,
    comment TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hazard_approvals_record ON hazard_approvals(record_id);

-- 8) 审计日志
CREATE TABLE IF NOT EXISTS hazard_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    record_id UUID NULL,
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    detail JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hazard_audit_logs_enterprise ON hazard_audit_logs(enterprise_id);

-- 9) 通知
CREATE TABLE IF NOT EXISTS hazard_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    record_id UUID NULL,
    type VARCHAR(20) NOT NULL,
    message VARCHAR(500) NULL,
    read_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hazard_notifications_enterprise ON hazard_notifications(enterprise_id);
CREATE INDEX IF NOT EXISTS idx_hazard_notifications_user ON hazard_notifications(user_id);

-- 10) 企业隐患配置列 + 部分唯一索引
ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS hazard_closure_mode VARCHAR(20) NOT NULL DEFAULT 'standard';
ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS hazard_public_token VARCHAR(64);
ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS hazard_report_token VARCHAR(64);
ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS hazard_config JSONB DEFAULT '{}'::jsonb;
CREATE UNIQUE INDEX IF NOT EXISTS uq_enterprises_hazard_public_token
    ON enterprises(hazard_public_token) WHERE hazard_public_token IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_enterprises_hazard_report_token
    ON enterprises(hazard_report_token) WHERE hazard_report_token IS NOT NULL;

-- 11) B 字典种子（data_dicts，幂等）
INSERT INTO data_dicts (dict_type, code, label, value, scope, is_system, sort_order, description) VALUES
  ('deadline_rules', 'major', '重大隐患整改期限', '{"days":15}', 'system', TRUE, 1, '重大隐患整改期限（天）'),
  ('deadline_rules', 'general', '一般隐患整改期限', '{"days":7}', 'system', TRUE, 2, '一般隐患整改期限（天）'),
  ('deadline_rules', 'review', '整改复查期限', '{"days":3}', 'system', TRUE, 3, '整改复查期限（天）'),
  ('publicity_scope', 'ongoing', '整改中公开', '{}', 'system', TRUE, 1, '隐患公示范围'),
  ('publicity_scope', 'closed', '已销号公开', '{}', 'system', TRUE, 2, '隐患公示范围'),
  ('publicity_scope', 'all', '全部公开', '{}', 'system', TRUE, 3, '隐患公示范围'),
  ('source_type', 'inspection', '排查', '{}', 'system', TRUE, 1, '隐患来源类型'),
  ('source_type', 'report', '上报', '{}', 'system', TRUE, 2, '隐患来源类型'),
  ('source_type', 'regulatory', '监管检查', '{}', 'system', TRUE, 3, '隐患来源类型'),
  ('source_type', 'accident', '事故', '{}', 'system', TRUE, 4, '隐患来源类型'),
  ('source_type', 'manual', '手工', '{}', 'system', TRUE, 5, '隐患来源类型'),
  ('record_status_label', 'registered', '已登记', '{}', 'system', TRUE, 1, '隐患记录状态标签'),
  ('record_status_label', 'grading', '待分级', '{}', 'system', TRUE, 2, '隐患记录状态标签'),
  ('record_status_label', 'pending_approval', '待审批', '{}', 'system', TRUE, 3, '隐患记录状态标签'),
  ('record_status_label', 'rectifying', '整改中', '{}', 'system', TRUE, 4, '隐患记录状态标签'),
  ('record_status_label', 'reviewing', '复查中', '{}', 'system', TRUE, 5, '隐患记录状态标签'),
  ('record_status_label', 'second_review', '二次复核', '{}', 'system', TRUE, 6, '隐患记录状态标签'),
  ('record_status_label', 'closed', '已销号', '{}', 'system', TRUE, 7, '隐患记录状态标签')
ON CONFLICT DO NOTHING;

-- 12) 系统检查表模板种子（enterprise_id NULL、is_system TRUE，幂等）
INSERT INTO hazard_checklist_templates (enterprise_id, name, category, items, is_system) VALUES
  (NULL, '日常检查表', 'daily', '[
    {"content": "作业现场是否存在跑冒滴漏、物料堆放堵塞通道", "expected_note": "现场整洁、通道畅通"},
    {"content": "员工是否按规程穿戴劳动防护用品", "expected_note": "防护用品佩戴齐全"},
    {"content": "消防通道、安全出口是否畅通", "expected_note": "无占用、无堵塞"},
    {"content": "设备设施运行是否正常、有无异常声响或异味", "expected_note": "运行平稳、无异常"}
  ]'::jsonb, TRUE),
  (NULL, '综合检查表', 'comprehensive', '[
    {"content": "安全生产责任制是否落实到位", "expected_note": "责任到岗到人"},
    {"content": "风险分级管控措施是否有效执行", "expected_note": "管控措施落实"},
    {"content": "隐患排查治理台账是否规范完整", "expected_note": "台账闭环"},
    {"content": "特种设备、电气设施是否定期检测检验", "expected_note": "检测在有效期内"},
    {"content": "应急预案是否修订并组织演练", "expected_note": "预案有效、演练记录完整"}
  ]'::jsonb, TRUE),
  (NULL, '专项-消防', 'special', '[
    {"content": "灭火器、消火栓等消防器材是否完好有效", "expected_note": "压力正常、无遮挡"},
    {"content": "疏散指示标志、应急照明是否正常", "expected_note": "完好可用"},
    {"content": "易燃易爆物品存放是否符合要求", "expected_note": "专库专柜、远离火源"},
    {"content": "动火作业是否办理审批并落实监护", "expected_note": "票证齐全、监护到位"}
  ]'::jsonb, TRUE),
  (NULL, '专项-危化品', 'special', '[
    {"content": "危化品储存区是否符合分区分类存放要求", "expected_note": "禁忌混存、标识清晰"},
    {"content": "危化品仓库通风、防泄漏措施是否有效", "expected_note": "通风良好、应急物资齐全"},
    {"content": "危化品出入库台账是否准确完整", "expected_note": "账物相符"},
    {"content": "从业人员是否经培训持证上岗", "expected_note": "证件有效"},
    {"content": "泄漏应急演练是否按计划开展", "expected_note": "演练记录完整"}
  ]'::jsonb, TRUE),
  (NULL, '节假日检查表', 'holiday', '[
    {"content": "节假日值班安排是否落实", "expected_note": "值班表明确、在岗在位"},
    {"content": "节日期间停用设备是否断电、关阀", "expected_note": "断电关阀、张贴标识"},
    {"content": "重点部位（库房、配电室等）是否封闭管理", "expected_note": "封闭上锁、巡查到位"},
    {"content": "应急物资和联系方式是否完好可用", "expected_note": "物资齐备、电话畅通"}
  ]'::jsonb, TRUE)
ON CONFLICT (name) WHERE enterprise_id IS NULL DO NOTHING;
