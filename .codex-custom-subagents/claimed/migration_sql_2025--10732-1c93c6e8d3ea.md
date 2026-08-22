# Codex Custom Subagents task handoff v1

Task: migration_sql_2025

## 任务：编写事故类型存量数据迁移 SQL（幂等）

### 项目工作目录（所有文件操作在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行。PostgreSQL 16 容器可用（`emergency-plan-db`，库 `emergency_plan`，用户/密码 postgres/postgres，端口 5438）。

### 背景

存量数据含旧国标值（车辆伤害/机械伤害/中毒和窒息/其他伤害 等）与旧预设值（爆炸/中毒窒息），需映射到 GB 6441-2025 27 类。自由事件名（设备损坏/数据丢失 等）保留原样。迁移必须幂等。

### 第 1 步：创建 `backend\db_migration_accident_types_2025.sql`

内容（完整粘贴，UTF-8）：

```sql
-- 事故类型存量迁移：GB/T 6441-1986 + 旧系统预设 → GB 6441-2025（幂等）
-- 自由事件名/复合表述（不在映射表内）保持原样。

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
SET accident_type = _migrate_accident_type(accident_type)
WHERE accident_type IS NOT NULL AND accident_type <> '';

-- 2) 预案事故类型（顿号/逗号分隔多值；回拼保留顿号）
UPDATE plan_projects p
SET accident_type = sub.new_val
FROM (
  SELECT id, string_agg(_migrate_accident_type(t), '、' ORDER BY ord) AS new_val
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
  SELECT id, string_agg(_migrate_accident_type(t), ',' ORDER BY ord) AS new_val
  FROM risk_sources,
       unnest(string_to_array(categories, ',')) WITH ORDINALITY AS x(t, ord)
  WHERE categories <> ''
  GROUP BY id
) sub
WHERE s.id = sub.id;

-- 4) 风险告知卡快照 content.accident_types（JSONB 数组逐元素；不动 signs）
UPDATE risk_notice_cards
SET content = jsonb_set(
  content,
  '{accident_types}',
  (SELECT jsonb_agg(_migrate_accident_type(elem))
   FROM jsonb_array_elements_text(content->'accident_types') AS elem)
)
WHERE content ? 'accident_types'
  AND jsonb_typeof(content->'accident_types') = 'array';

-- 清理（幂等：重复执行时函数重建无害）
DROP FUNCTION IF EXISTS _migrate_accident_type(text);
```

### 第 2 步：在本地库执行验证

先备份当前值（供恢复）：

```powershell
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "CREATE TABLE IF NOT EXISTS _bak_accident_types AS SELECT 'risk_events' AS tbl, id::text AS rid, accident_type AS val FROM risk_events UNION ALL SELECT 'plan_projects', id::text, accident_type FROM plan_projects UNION ALL SELECT 'risk_sources', id::text, categories FROM risk_sources;"
```

执行迁移：

```powershell
docker exec -i emergency-plan-db psql -U postgres -d emergency_plan < backend\db_migration_accident_types_2025.sql
```

校验 1（旧值零残留）：

```powershell
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT 'risk_events' AS tbl, accident_type, count(*) FROM risk_events WHERE accident_type IN ('车辆伤害','机械伤害','起重伤害','冒顶片帮','透水','放炮','火药爆炸','瓦斯爆炸','锅炉爆炸','其他爆炸','中毒和窒息','其他伤害','爆炸','中毒窒息') GROUP BY 1,2 UNION ALL SELECT 'plan_projects', accident_type, count(*) FROM plan_projects WHERE accident_type LIKE '%车辆伤害%' OR accident_type LIKE '%机械伤害%' OR accident_type LIKE '%冒顶片帮%' OR accident_type LIKE '%透水%' OR accident_type LIKE '%放炮%' OR accident_type LIKE '%火药爆炸%' OR accident_type LIKE '%瓦斯爆炸%' OR accident_type LIKE '%锅炉爆炸%' OR accident_type LIKE '%其他爆炸%' OR accident_type LIKE '%中毒和窒息%' OR accident_type LIKE '%其他伤害%' OR accident_type LIKE '%爆炸%' OR accident_type LIKE '%中毒窒息%' GROUP BY 1,2 UNION ALL SELECT 'risk_sources', categories, count(*) FROM risk_sources WHERE categories LIKE '%车辆伤害%' OR categories LIKE '%机械伤害%' OR categories LIKE '%冒顶片帮%' OR categories LIKE '%透水%' OR categories LIKE '%放炮%' OR categories LIKE '%火药爆炸%' OR categories LIKE '%瓦斯爆炸%' OR categories LIKE '%锅炉爆炸%' OR categories LIKE '%其他爆炸%' OR categories LIKE '%中毒和窒息%' OR categories LIKE '%其他伤害%' OR categories LIKE '%爆炸%' OR categories LIKE '%中毒窒息%' GROUP BY 1,2;"
```

预期：0 行。

校验 2（自由值未动 + 幂等）：再原样执行一次迁移脚本，然后确认风险事件里自由值（设备损坏/数据丢失、火灾爆炸 等）与迁移前一致（对照 _bak_accident_types）。

**注意**：若本地库数据与仓库内数据不一致（例如有测试残留），以实际库为准验证；迁移脚本本身照常提交。

### 第 3 步：提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/db_migration_accident_types_2025.sql
git commit -m "feat(accident-types): add idempotent legacy-to-2025 data migration SQL"
```

### 红线

- 只创建 `backend/db_migration_accident_types_2025.sql` 一个文件
- 迁移只允许 UPDATE 上述 4 张表；禁止其他写操作（备份表 _bak_accident_types 是 CREATE TABLE 只读拷贝，允许）
- 不要更新 TASKS.md
- 中文内容保持 UTF-8
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 迁移前后各类值数量摘要（旧值清零、自由值保留、各表总行数）
- 幂等重跑结果
- commit SHA（git log -1 --format=%h）
