-- 2026-09-03 修复：风险评估报告 ch1/ch2 夹带 L×S 计算表
-- 1) system prompt 限定：仅「三、风险等级评估」章节输出 L×S 计算表；
--    其余章节一律不得输出。
-- 2) ch1/ch2 章节指令追加边界约束。
-- 幂等：按文本 replace/concat 定位，重复执行结果不变。

UPDATE prompt_templates
SET system_prompt = replace(
      system_prompt,
      '；风险评估章节必须输出「L×S 风险评估计算表」（含事故类型、L、S、R 值和风险等级，数值以风险源清单为准）。',
      '。只有「三、风险等级评估」章节输出「L×S 风险评估计算表」（含事故类型、L、S、R 值和风险等级，数值以风险源清单为准）；其余章节（辨识、汇总、措施、结论）一律不得输出 L×S 计算表、风险矩阵表或风险等级数值表。'
    )
WHERE template_code = 'risk_assessment_system_default';

UPDATE prompt_templates
SET user_prompt_template = concat(
      user_prompt_template,
      E'\n\n【边界约束】本章仅做危险有害因素辨识分析，禁止输出 L×S 风险评估计算表、风险矩阵表或任何风险等级数值表（该内容由「三、风险等级评估」章节输出）。'
    )
WHERE template_code = 'risk_assessment_section_ch1_hazard_id'
  AND position('【边界约束】本章仅做危险有害因素辨识分析' in user_prompt_template) = 0;

UPDATE prompt_templates
SET user_prompt_template = concat(
      user_prompt_template,
      E'\n\n【边界约束】本章仅做辨识汇总，禁止输出 L×S 风险评估计算表、风险矩阵表或风险等级数值表（该内容由「三、风险等级评估」章节输出）。'
    )
WHERE template_code = 'risk_assessment_section_ch2_summary'
  AND position('【边界约束】本章仅做辨识汇总' in user_prompt_template) = 0;
