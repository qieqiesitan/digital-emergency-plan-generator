# Codex Custom Subagents task handoff v1

Task: review_quality_t7_migration_v2

## 任务：代码质量复审 — 迁移 SQL 加固（commit adcdeea）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

复审上一轮质量审查（❌ 需修复）的修正是否到位：commit `adcdeea` 加固了迁移 SQL。这是只读审查：不要修改任何源码。

### 上一轮必须修复项（逐条核对）

1. 告知卡空 JSONB 数组：`jsonb_agg` 需 `COALESCE(..., '[]'::jsonb)` 守卫，不得再出现 content 置 NULL
2. 事务包裹：脚本应为 `BEGIN;` → 函数 → 4 个 UPDATE → DROP FUNCTION → `COMMIT;`
3. 映射前 trim：所有映射调用应为 `_migrate_accident_type(btrim(...))`（risk_events 单值、plan_projects/risk_sources 拆项、告知卡 JSONB 元素）

另核对（上一轮重要/次要项）：
4. risk_sources 拆分是否兼容顿号（`replace(categories, '、', ',')`）
5. 提交是否只含 1 个文件（git show --stat）

### 验证方式

- `git show adcdeea` 阅读实际改动
- 用 `docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend\db_migration_accident_types_2025.sql` 完整执行一遍确认无错（幂等，已执行过、结果应不变）
- 事务内构造空数组卡片验证不再报错（可跳过，实现者已验；如做请 ROLLBACK）
- 确认 `risk_events` 旧值 0 残留

### 汇报格式

- 结论：✅ 通过 | ❌ 需修复（逐条列出，附 file:line）
- 5 项逐条核验结果
- task_id、claim_id、path（claim_task.py 输出）
