-- D-3 修正：上一个脚本用 `DEFAULT now()` 给既有资源行补 updated_at，
-- 会让"资源"域时间戳变成迁移时刻 → 所有早于迁移生成的章节被一次性误报「待更新」。
-- 这里把没有被真正改过的行回退为 created_at（演进语义 = 最后变更时间）。
-- 说明：本脚本在启动迁移中紧随上一个脚本执行，期间不存在真实用户编辑，
-- 因此 `updated_at > created_at` 的行都只可能来自上一个脚本的默认值。
UPDATE emergency_resources
   SET updated_at = created_at
 WHERE updated_at > created_at;
