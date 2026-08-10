# Codex Custom Subagents task handoff v1

Task: task_d2_t3_review_quality

## 任务：代码质量审查（diagrams batch2 任务 3：生成后处理）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

git commits `6b8d66f` + `e6064cb`（`git show`），文件：
- `backend/app/routers/generation.py`
- `backend/app/services/risk_context_builder.py`
- `backend/tests/test_plan_diagram_service.py`

### 审查重点

- `_attach_diagrams` 是否简洁、章节/类型判定清晰
- risk_context_builder 扩展是否向后兼容（旧调用方只取 risk_sources 不受影响）、无 N+1 查询
- enterprise_data 扩展字段是否命名一致
- 生成流程调用点是否正确（单章+批量）
- 是否有死代码、冗余

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
