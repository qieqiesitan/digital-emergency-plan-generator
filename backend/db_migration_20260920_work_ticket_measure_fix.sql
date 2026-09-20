-- 20260920 作业票措施库存量修复
--
-- 问题：v1 种子（db_migration_20260917_work_ticket_seed.sql）把 GB 30871-2022
-- 附录A 表 A.1~A.8 的全部措施（16+15+11+15+20+14+11+4 = 106 条）都写给了
-- 前 4 个模板（DHZY 特级/一级/二级、YXKJ）。v2 种子用确定性 UUID5 +
-- ON CONFLICT (id) DO NOTHING 修正了 sort_order 1~N 的文本，但多出的
-- 第 N+1~106 行无人删除，残留在库中。
--
-- 影响：动火与受限空间票的开票界面要在一个 106 项的措施列表里操作，
-- 其中 90 条属于其他票种（盲板/高处/吊装/临电/动土/断路）。
--
-- 正确条数依据：backend/app/regulations/data/texts/reg_gb_30871_2022.md
--   表 A.1（动火，16 条，第 819~834 行）、表 A.2（受限空间，15 条，第 868~888 行）。
--
-- 幂等：DELETE 基于 sort_order 阈值，重复执行结果一致。

BEGIN;

DELETE FROM work_ticket_template_measures m
USING work_ticket_templates t
WHERE m.template_id = t.id
  AND t.code = 'DHZY'
  AND m.sort_order > 16;

DELETE FROM work_ticket_template_measures m
USING work_ticket_templates t
WHERE m.template_id = t.id
  AND t.code = 'YXKJ'
  AND m.sort_order > 15;

COMMIT;

-- 核验 1：条数（期望 DHZY×3 = 16、YXKJ = 15、其余模板不变）
-- SELECT t.code, t.level, count(m.id) FROM work_ticket_templates t
--   LEFT JOIN work_ticket_template_measures m ON m.template_id = t.id
--  GROUP BY t.code, t.level ORDER BY t.code, t.level;
-- 核验 2：总数（期望 584 - 90*3 - 91 = 223）
-- SELECT count(*) FROM work_ticket_template_measures;
