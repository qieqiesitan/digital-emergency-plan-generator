# Codex Custom Subagents task handoff v1

Task: migration_sql_fix_2025

## 任务：修复迁移 SQL 三个问题（空数组 NULL、无事务、未 trim）

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行；Postgres 在 Docker 端口 5438（`docker exec -i emergency-plan-db psql -U postgres -d emergency_plan`）。

### 背景

质量审查发现 `backend/db_migration_accident_types_2025.sql` 三个必须修复项：
1. 告知卡 `accident_types` 为空数组时 `jsonb_agg` 返回 NULL → `jsonb_set` 把 content 置 NULL → NOT NULL 约束失败、脚本在第 4 步中断
2. 无事务包裹，中途失败会部分应用（前 3 步 UPDATE 已生效）
3. 映射前未 trim，与运行时 `normalize_accident_type` 的 `strip()` 行为不一致，带空白旧值会静默残留

### 第 1 步：修改 `backend\db_migration_accident_types_2025.sql`

按以下精确改动（保留其余内容）：

1. 文件开头（注释块之后、`CREATE OR REPLACE FUNCTION` 之前）插入 `BEGIN;`
2. `UPDATE risk_events` 的 SET 改为：`SET accident_type = _migrate_accident_type(btrim(accident_type))`
3. plan_projects 的 unnest 部分改为：`unnest(string_to_array(replace(accident_type, ',', '、'), '、'))` 不变，但映射调用改为 `_migrate_accident_type(btrim(t))`
4. risk_sources 的 unnest 部分改为：
   `unnest(string_to_array(replace(categories, '、', ','), ','))`，映射调用 `_migrate_accident_type(btrim(t))`（回拼仍用 ','）
5. risk_notice_cards 的 jsonb_set 改为：

```sql
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
```

6. 文件末尾（`DROP FUNCTION IF EXISTS` 之后）插入 `COMMIT;`

最终结构：`BEGIN;` → 函数 → 4 个 UPDATE → `DROP FUNCTION` → `COMMIT;`

### 第 2 步：验证（含空数组场景 + 幂等）

在本地库事务内做只读验证（不持久化）：

```powershell
docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 -c "BEGIN; INSERT INTO risk_notice_cards (id, enterprise_id, object_id, version, content, source, created_by) VALUES ('00000000-0000-0000-0000-00000000ffff', (SELECT id FROM enterprises LIMIT 1), (SELECT id FROM risk_objects LIMIT 1), 1, '{\"accident_types\": []}'::jsonb, 'rule', NULL) ON CONFLICT DO NOTHING; ROLLBACK;" -c "SELECT 'ok';"
```

然后完整执行迁移脚本（含事务）：

```powershell
docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend\db_migration_accident_types_2025.sql
```

预期：脚本完整执行成功（4 个 UPDATE + 函数清理），无 NOT NULL 错误。再原样执行第二次确认幂等（结果不变）。用 `docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) FROM risk_events WHERE accident_type IN ('车辆伤害','机械伤害','起重伤害','冒顶片帮','透水','放炮','火药爆炸','瓦斯爆炸','锅炉爆炸','其他爆炸','中毒和窒息','其他伤害','爆炸','中毒窒息');"` 确认 0 残留。

### 第 3 步：提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/db_migration_accident_types_2025.sql
git commit -m "fix(accident-types): harden migration SQL with transaction, trim and empty-array guard"
```

### 红线

- 只修改 `backend/db_migration_accident_types_2025.sql` 一个文件
- 禁止 DELETE/TRUNCATE；验证用的事务必须 ROLLBACK 或仅执行脚本本身
- 不要更新 TASKS.md；中文保持 UTF-8
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 6 处改动确认、空数组场景验证结果、幂等重跑结果、旧值 0 残留结果
- commit SHA（git log -1 --format=%h）
