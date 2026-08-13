# Codex Custom Subagents task handoff v1

Task: task_q_t4_review_quality

## 任务：代码质量审查（quality 任务 4：E1-E3 可执行性）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

### 审查对象

git commits `d5594e2` + `8ba76ea`（`git show`），文件：
- `backend/app/services/plan_quality_service.py`
- `backend/app/routers/export.py`
- `backend/tests/test_plan_quality.py`

### 审查重点

- E1 电话提取正则是否避免拆分座机、避免误抓身份证/编号等长数字
- E2/E3 逻辑是否简洁、has_risk 参数传递是否合理
- resources 参数向后兼容
- 测试是否有效覆盖
- 是否有死代码、冗余

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
