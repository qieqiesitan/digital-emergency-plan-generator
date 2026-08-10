# Codex Custom Subagents task handoff v1

Task: task_q_t1_review_quality

## 任务：代码质量审查（quality 任务 1：C0 基础修正）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

### 审查对象

git commit `a727bfa`（`git show a727bfa`），文件：
- `backend/app/services/plan_quality_service.py`
- `backend/tests/test_plan_quality.py`

### 审查重点

- 片段提取正则是否稳健（空地址、无匹配、异常字符）
- 必含章节逻辑是否简洁、无重复
- 测试是否有效覆盖（非必含章节不报、片段匹配不报）
- 是否有死代码、冗余

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
