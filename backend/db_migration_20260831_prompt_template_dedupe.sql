-- prompt_templates.template_code 重复数据清理 + 唯一索引
-- 幂等：DELETE 仅删除重复行（每个 template_code 保留最大 id），
-- 重跑时无重复行可删（0 行受影响）；CREATE UNIQUE INDEX IF NOT EXISTS 可重复执行。
-- 背景：历史数据同 template_code 存在多行（模型已声明 unique=True，此处把约束落库），
-- 唯一索引 ix_prompt_templates_template_code 命名与模型 create_all 生成的一致可追溯。
-- 保留策略：运行时取首条为 status active 优先 + id 降序（prompt_cache.py），
-- 真实 0.2.0 数据为「旧 disabled 小 id + 新 active 大 id」，故保留每组最大 id。

-- 1) 删除重复行：保留每组最大 id
DELETE FROM prompt_templates a
USING prompt_templates b
WHERE a.template_code = b.template_code
  AND a.id < b.id;

-- 2) 唯一索引（幂等）
CREATE UNIQUE INDEX IF NOT EXISTS ix_prompt_templates_template_code
  ON prompt_templates (template_code);
