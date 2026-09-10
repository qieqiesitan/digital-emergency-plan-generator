-- 20260910：把风险数据权威规则追加到系统提示词（幂等；已包含则跳过）
DO $$
DECLARE
  rule text := E'【风险数据权威规则（系统固定，任何模板不得覆盖）】\n'
    || E'1. 【风险源清单】是风险事实的唯一来源：风险源条目、事故类型、L/S/R、风险等级、管控措施一律以清单为准。\n'
    || E'2. 禁止增删、改名、合并丢失或改判清单中的任何风险源；禁止以企业档案、报告摘要、常识推断为由排除清单条目。\n'
    || E'3. 清单与【企业档案】或【风险评估报告摘要】不一致时，以清单为准；不一致项写入结构化冲突清单，正文保持干净。\n'
    || E'4. 风险源数量、等级分布、类别分布等统计必须由清单逐条计算得出，不得自行估算。\n'
    || E'5. 引用风险源时按系统给出的固定顺序与编号（“第N项”），不得重排。';
BEGIN
  UPDATE prompt_templates
     SET system_prompt = COALESCE(system_prompt, '') || E'\n\n' || rule
   WHERE template_code IN (
     'risk_assessment_system', 'risk_assessment_system_default',
     'resource_investigation_system', 'resource_investigation_system_default',
     'emergency_system_default', 'emergency_system_comprehensive_general',
     'emergency_system_onsite_general', 'emergency_system_special_general'
   )
     AND COALESCE(system_prompt, '') NOT LIKE '%【风险数据权威规则（系统固定，任何模板不得覆盖）】%';
END $$;
