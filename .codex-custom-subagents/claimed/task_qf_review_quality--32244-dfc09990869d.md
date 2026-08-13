# Codex Custom Subagents task handoff v1

Task: task_qf_review_quality

## 任务：代码质量审查（quality 规则修复）

你是一个代码质量审查子智能体。审查修复实现质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-fixes`

### 审查对象

git commit `8355151`（`git show 8355151`），文件：
- `backend/app/services/plan_quality_service.py`
- `backend/tests/test_plan_quality.py`
- `docs/superpowers/specs/2026-08-10-plan-quality-check-enhancement-design.md`

### 审查重点

- C1 正则（分隔符要求、负向后顾、括号形式）是否稳健、无新误报/漏报
- `_role_matches` 语义映射是否简洁、边界（role/position 为空、包含关系）正确
- C3 负向前瞻是否覆盖「设置/分为/划分」，是否遗漏其他数量表述
- E3 类别聚合逻辑是否正确处理 None/正数/全 0
- 测试是否覆盖修复点、是否删除/适配了旧断言
- 是否有死代码、冗余

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
