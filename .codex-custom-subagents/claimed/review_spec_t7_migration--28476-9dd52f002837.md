# Codex Custom Subagents task handoff v1

Task: review_spec_t7_migration

## 任务：规格合规审查 — 迁移 SQL（commit 4c4334b）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现者构建的是否为**所要求的内容（不多不少）**。这是只读审查：不要修改任何源码。

### 要求的内容（规格）

完整读取任务规格文件：`.codex-custom-subagents\claimed\migration_sql_2025--10732-1c93c6e8d3ea.md`

### 实现者声称构建了什么

- `backend/db_migration_accident_types_2025.sql`（74 行）：映射函数 + 4 张表 UPDATE + 幂等清理
- 已在本地库执行验证：旧值词级精确 0 残留、自由值保留、幂等重跑无漂移；备份表 _bak_accident_types 已建

### 关键：不要信任报告

必须独立验证：

- `git show 4c4334b` 阅读 SQL，逐段与规格文件中的 SQL 比对（映射函数 22 个 WHEN 分支、4 个 UPDATE、JSONB 数组处理、DROP FUNCTION）
- 确认脚本只含 SELECT/UPDATE/CREATE FUNCTION/DROP FUNCTION，无破坏性语句
- 运行只读校验（不改数据）：
  - `docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) FROM risk_events WHERE accident_type IN ('车辆伤害','机械伤害','起重伤害','冒顶片帮','透水','放炮','火药爆炸','瓦斯爆炸','锅炉爆炸','其他爆炸','中毒和窒息','其他伤害','爆炸','中毒窒息');"` 预期 0
  - 同上对 plan_projects（LIKE 匹配）与 risk_sources（LIKE 匹配）校验
- 确认脚本幂等设计（函数重建 + 值不再命中映射）
- git show --stat 应恰 1 文件

### 汇报格式

- 结论：✅ 符合规格 | ❌ 发现问题（逐条列出，附 file:line）
- 四表旧值校验结果、幂等设计评估
- task_id、claim_id、path（claim_task.py 输出）
