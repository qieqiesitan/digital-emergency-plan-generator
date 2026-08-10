# Codex Custom Subagents task handoff v1

Task: task_d2_t3_review_spec

## 任务：规格合规审查（diagrams batch2 任务 3：生成后处理）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md` §6.3
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch2.md` 任务 3
3. 实现：git commit `6b8d66f`（`git show 6b8d66f`）

### 审查重点

- `_attach_diagrams` 是否按章节写入风险矩阵（sec_2 comprehensive）与疏散图（sec_3_3 onsite）
- `_collect_enterprise_data` 是否提供 risk_events/zones/risk_objects/floor_plan_url
- `risk_context_builder` 返回是否扩展且向后兼容（旧调用方 risk_sources 不受影响）
- 生成流程（单章+批量）是否在写库前调用 `_attach_diagrams`
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
