CREATE TABLE IF NOT EXISTS data_dicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dict_type VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    label VARCHAR(100) NOT NULL,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    scope VARCHAR(10) NOT NULL DEFAULT 'system',
    enterprise_id UUID NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dict_type, enterprise_id, code)
);
CREATE INDEX IF NOT EXISTS idx_data_dicts_type_scope ON data_dicts(dict_type, scope);

INSERT INTO data_dicts (dict_type, code, label, value, scope, is_system, sort_order, description) VALUES
  ('measure_factors', 'engineering', '工程技术', '{"factor":0.5}', 'system', TRUE, 1, '自动折算参考系数'),
  ('measure_factors', 'management', '管理措施', '{"factor":0.7}', 'system', TRUE, 2, '自动折算参考系数'),
  ('measure_factors', 'ppe', '个体防护', '{"factor":0.85}', 'system', TRUE, 3, '自动折算参考系数'),
  ('measure_factors', 'emergency', '应急措施', '{"factor":0.9}', 'system', TRUE, 4, '自动折算参考系数'),
  ('measure_factors', 'mode', '折算口径', '{"mode":"min"}', 'system', TRUE, 0, 'min=最小值主导，product=连乘'),
  ('control_level_map', 'major', '重大→企业', '{"level":"重大","control_level":"企业"}', 'system', TRUE, 1, '管控层级默认映射'),
  ('control_level_map', 'large', '较大→部门', '{"level":"较大","control_level":"部门"}', 'system', TRUE, 2, '管控层级默认映射'),
  ('control_level_map', 'general', '一般→班组', '{"level":"一般","control_level":"班组"}', 'system', TRUE, 3, '管控层级默认映射'),
  ('control_level_map', 'low', '低→岗位', '{"level":"低","control_level":"岗位"}', 'system', TRUE, 4, '管控层级默认映射'),
  ('hazard_type', 'equipment', '设备设施', '{}', 'system', TRUE, 1, '隐患类型（B 规格使用）'),
  ('hazard_type', 'fire', '消防', '{}', 'system', TRUE, 2, '隐患类型（B 规格使用）'),
  ('hazard_type', 'behavior', '作业行为', '{}', 'system', TRUE, 3, '隐患类型（B 规格使用）'),
  ('hazard_type', 'management', '管理缺陷', '{}', 'system', TRUE, 4, '隐患类型（B 规格使用）'),
  ('hazard_type', 'environment', '环境', '{}', 'system', TRUE, 5, '隐患类型（B 规格使用）'),
  ('hazard_type', 'other', '其他', '{}', 'system', TRUE, 6, '隐患类型（B 规格使用）');
