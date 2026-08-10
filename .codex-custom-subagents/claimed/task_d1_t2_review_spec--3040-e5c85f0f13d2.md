# Codex Custom Subagents task handoff v1

Task: task_d1_t2_review_spec

## 任务：规格合规审查（diagrams batch1 任务 2：图提示词模板）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md` §6.2（org_chart 提示词）、§3
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch1.md` 任务 2
3. 实现：git commit `0e126fb`（`git show 0e126fb`）

### 审查重点

- 4 类图提示词（org_chart/report_sequence/response_timeline/drill_gantt）是否齐全
- org_chart 提示词是否注入 {{org_structure}} 变量
- 是否含「全角括号保留原样、不用半角括号」约束（与 mermaid v11 兼容修复一致）
- `get_additional_diagram_prompt` 查询函数是否正确
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
