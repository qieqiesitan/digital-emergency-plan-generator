# Codex Custom Subagents task handoff v1

Task: task_d1_t1_review_quality

## 任务：代码质量审查（diagrams batch1 任务 1：章节图映射）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

git commit `21948ff`（`git show 21948ff`），文件：
- `backend/app/routers/generation.py`
- `backend/tests/test_plan_diagram_prompts.py`

### 审查重点

- 映射表命名、位置、注释是否与项目风格一致
- 测试是否有效
- 是否有死代码、冗余

### 输出

```
结论：PASS / FAIL
优点：...
问题（重要）：...
问题（轻微）：...
```

不要修改任何文件、不要提交。
