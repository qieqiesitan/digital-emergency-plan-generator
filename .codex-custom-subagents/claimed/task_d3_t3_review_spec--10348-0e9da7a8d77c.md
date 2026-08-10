# Codex Custom Subagents task handoff v1

Task: task_d3_t3_review_spec

## 任务：规格合规审查（diagrams batch3 任务 3：缺数据提示条 + 补图按钮）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md` §4.2
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch3.md` 任务 3
3. 实现：git commit `7d256c5`（`git show 7d256c5`）

### 审查重点

- 是否统计占位图 key 并展示提示条（含数量与 key 列表）
- 是否提供「去补数据」跳转与「重新生成缺失附图」按钮
- 补图按钮是否调用 regenerateMissingDiagrams 并刷新章节
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
