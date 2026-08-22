# Codex Custom Subagents task handoff v1

Task: review_quality_t6_risk_source

## 任务：代码质量审查 — NameError 修复 + normalize（commit a7171cd）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现是否**构建良好**。规格合规审查已通过。这是只读审查：不要修改任何源码。

### 审查对象

- 提交：`a7171cd`（BASE aaf57af）
- 文件：`backend/app/routers/risk_sources_ext.py`、`backend/app/services/risk_source_migration_service.py`、`backend/tests/test_risk_sources_ext.py`
- 规格：`.codex-custom-subagents\claimed\risk_source_fix_2025--27780-d7ab01de3780.md`

### 审查关注点

- 修复是否最小侵入（4 处替换 + normalize 包覆）
- normalize 包覆是否可能引入行为变化（suggested_event 为空时的处理）
- 回归测试是否有效验证 NameError 修复与 27 类下拉
- 测试是否遵循仓库测试模式
- 是否有过度构建

### 汇报格式

- 优点（列出）
- 问题（按 关键/重要/次要 分级，附 file:line）
- 评估结论：✅ 通过 | ❌ 需修复（列出必须修复项）
- task_id、claim_id、path（claim_task.py 输出）
