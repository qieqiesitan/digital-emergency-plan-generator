# Codex Custom Subagents task handoff v1

Task: task_q_t3_review_spec

## 任务：规格合规审查（quality 任务 3：L1-L3 合规性）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-10-plan-quality-check-enhancement-design.md` §3.2
2. 计划：`docs\superpowers\plans\2026-08-10-plan-quality-check-enhancement.md` 任务 3
3. 实现：git commit `3c7ad30`（`git show 3c7ad30`）

### 审查重点

- L1：必含章节缺失 → issue，check_plan 支持 required_sections 参数且默认兼容旧调用
- L2：法规引用提取（书名号/标准号/令号）、与 graph.json 比对、库不可用静默
- L3：术语混用检测
- export.py 是否传 required_sections（从 PlanTemplate 读顶层 required）
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
