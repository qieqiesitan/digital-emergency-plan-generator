# Codex Custom Subagents task handoff v1

Task: task_d2_t1_review_spec

## 任务：规格合规审查（diagrams batch2 任务 1：diagram_svgs 列）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md` §6.1
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch2.md` 任务 1
3. 实现：git commit `1bf0234`（`git show 1bf0234`）

### 审查重点

- PlanSection 是否新增 diagram_svgs JSONB 列（默认 dict）
- 迁移 SQL 是否幂等（ADD COLUMN IF NOT EXISTS）且与模型一致
- 是否有多余改动

### 输出

```
结论：PASS / FAIL
问题清单：
- [严重/一般] 描述（如无问题写「无」）
缺失项：...
多余项：...
```

不要修改任何文件、不要提交。
