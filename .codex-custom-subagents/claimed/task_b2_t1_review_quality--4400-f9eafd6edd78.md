# Codex Custom Subagents task handoff v1

Task: task_b2_t1_review_quality

## 任务：代码质量审查（批2 任务 1：PlanProject 编号字段）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

### 审查对象

git commit `43db521`（`git show 43db521`），文件：
- `backend/app/models/enterprise.py`
- `backend/db_migration_plan_number.sql`
- `backend/tests/test_plan_number.py`
- `backend/app/routers/plans.py`

### 审查重点

- 字段命名/类型/位置与项目风格一致
- 迁移 SQL 幂等、与模型一致
- `_generate_plan_number` 边界情况（空名、超长名、未知类型码）
- 测试覆盖是否充分（格式、前缀截取、类型码、空名兜底）

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
