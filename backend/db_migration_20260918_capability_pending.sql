-- 标注：以下两个 AI 能力目前只有注册表记录、尚无调用点实现。
-- 管理页把未实现能力显示成"可启停的已上线能力"会误导管理员，故在描述里写明"规划中"。
-- 幂等：已标注过则不再追加。

UPDATE ai_capabilities
SET description = COALESCE(NULLIF(description, ''), name) || '（规划中：功能尚未接入调用点）'
WHERE code IN ('work_ticket_jsa', 'work_ticket_precheck')
  AND COALESCE(description, '') NOT LIKE '%规划中%';
