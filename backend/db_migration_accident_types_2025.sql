-- 事故类型存量迁移：GB/T 6441-1986 + 旧系统预设 → GB 6441-2025（幂等）
-- 自由事件名/复合表述（不在映射表内）保持原样。

BEGIN;

-- 单值映射函数（旧值 → 新值；未知值原样返回）
CREATE OR REPLACE FUNCTION _migrate_accident_type(v text) RETURNS text AS $$
  SELECT CASE v
    WHEN '物体打击' THEN '物体打击'
    WHEN '车辆伤害' THEN '厂（场）内车辆致害'
    WHEN '机械伤害' THEN '机械致害'
    WHEN '起重伤害' THEN '起重致害'
    WHEN '触电' THEN '触电'
    WHEN '淹溺' THEN '淹溺'
    WHEN '灼烫' THEN '灼烫'
    WHEN '火灾' THEN '火灾'
    WHEN '高处坠落' THEN '高处坠落'
    WHEN '坍塌' THEN '坍塌'
    WHEN '冒顶片帮' THEN '坍塌'
    WHEN '透水' THEN '水害'
    WHEN '放炮' THEN '民用爆炸物品爆炸'
    WHEN '火药爆炸' THEN '民用爆炸物品爆炸'
    WHEN '瓦斯爆炸' THEN '可燃气体爆炸'
    WHEN '锅炉爆炸' THEN '容器爆炸'
    WHEN '容器爆炸' THEN '容器爆炸'
    WHEN '其他爆炸' THEN '其他'
    WHEN '中毒和窒息' THEN '中毒'
    WHEN '其他伤害' THEN '其他'
    WHEN '爆炸' THEN '其他'
    WHEN '中毒窒息' THEN '中毒'
    ELSE v
  END;
$$ LANGUAGE sql IMMUTABLE;

-- 1) 风险事件事故类型（单值）
UPDATE risk_events
SET accident_type = _migrate_accident_type(btrim(accident_type))
WHERE accident_type IS NOT NULL AND accident_type <> '';

-- 2) 预案事故类型（顿号/逗号分隔多值；回拼保留顿号）
UPDATE plan_projects p
SET accident_type = sub.new_val
FROM (
  SELECT id, string_agg(_migrate_accident_type(btrim(t)), '、' ORDER BY ord) AS new_val
  FROM plan_projects,
       unnest(string_to_array(replace(accident_type, ',', '、'), '、')) WITH ORDINALITY AS x(t, ord)
  WHERE accident_type IS NOT NULL AND accident_type <> ''
  GROUP BY id
) sub
WHERE p.id = sub.id;

-- 3) 风险源类别（逗号分隔多值）
UPDATE risk_sources s
SET categories = sub.new_val
FROM (
  SELECT id, string_agg(_migrate_accident_type(btrim(t)), ',' ORDER BY ord) AS new_val
  FROM risk_sources,
       unnest(string_to_array(replace(categories, '、', ','), ',')) WITH ORDINALITY AS x(t, ord)
  WHERE categories <> ''
  GROUP BY id
) sub
WHERE s.id = sub.id;

-- 4) 风险告知卡快照 content.accident_types（JSONB 数组逐元素；不动 signs）
UPDATE risk_notice_cards
SET content = jsonb_set(
  content,
  '{accident_types}',
  COALESCE(
    (SELECT jsonb_agg(_migrate_accident_type(btrim(elem)))
     FROM jsonb_array_elements_text(content->'accident_types') AS elem),
    '[]'::jsonb
  )
)
WHERE content ? 'accident_types'
  AND jsonb_typeof(content->'accident_types') = 'array';

-- 清理（幂等：重复执行时函数重建无害）
DROP FUNCTION IF EXISTS _migrate_accident_type(text);

COMMIT;
