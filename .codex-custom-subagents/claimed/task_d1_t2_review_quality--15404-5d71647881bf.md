# Codex Custom Subagents task handoff v1

Task: task_d1_t2_review_quality

## 任务：代码质量审查（diagrams batch1 任务 2：图提示词模板）

你是一个代码质量审查子智能体。审查实现代码质量，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

git commit `0e126fb`（`git show 0e126fb`），文件：
- `backend/app/services/prompt_cache.py`
- `backend/tests/test_plan_diagram_prompts.py`

### 审查重点

- 提示词文案质量（是否清晰、可执行、与现有 COMPLIANCE_BLOCK 风格一致）
- `ADDITIONAL_DIAGRAM_PROMPTS` 字典与 `get_additional_diagram_prompt` 命名/位置是否合适
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
