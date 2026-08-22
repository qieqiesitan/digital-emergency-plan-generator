# Codex Custom Subagents task handoff v1

Task: review_quality_t7_migration

## 任务：代码质量审查 — 迁移 SQL（commit 4c4334b）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现是否**构建良好**。规格合规审查已通过。这是只读审查：不要修改任何源码。

### 审查对象

- 提交：`4c4334b`（BASE 4c41a86）
- 文件：`backend/db_migration_accident_types_2025.sql`
- 规格：`.codex-custom-subagents\claimed\migration_sql_2025--10732-1c93c6e8d3ea.md`

### 审查关注点

- SQL 可读性/可维护性（映射函数命名、注释、结构）
- 幂等设计是否稳健（函数重建 + CASE 无匹配原样返回）
- 多值处理是否正确（plan_projects 顿号/逗号、risk_sources 逗号、告知卡 JSONB）
- 是否有潜在风险（如 NULL、空串、异常分隔符）
- 与仓库既有迁移 SQL 风格是否一致（参考 backend/db_migration_*.sql）

### 汇报格式

- 优点（列出）
- 问题（按 关键/重要/次要 分级，附 file:line）
- 评估结论：✅ 通过 | ❌ 需修复（列出必须修复项）
- task_id、claim_id、path（claim_task.py 输出）
