# Codex Custom Subagents task handoff v1

Task: task_q_t2_review_quality

## 任务：代码质量审查（quality 任务 2：C1-C3 一致性）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

### 审查对象

git commits `6d21c65` + `10151e1`（`git show`），文件：
- `backend/app/services/plan_quality_service.py`
- `backend/tests/test_plan_quality.py`

### 审查重点

- 正则是否稳健（负向后顾、中英文标点、全角冒号）
- 角色提取与档案比对逻辑是否简洁、无重复
- C2 冲突检测是否会误报（正文同时含正确与错误地址）
- 测试是否有效覆盖边界
- 是否有死代码、冗余

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
