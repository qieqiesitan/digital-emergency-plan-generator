# Codex Custom Subagents task handoff v1

Task: task_d1_t3_review_spec

## 任务：规格合规审查（diagrams batch1 任务 3：org_chart 构建 + 提示词注入）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md` §6.2（org_chart）、§6.3
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch1.md` 任务 3
3. 实现：git commit `e0227ed`（`git show e0227ed`）

### 审查重点

- `_build_org_chart_mermaid` 是否从 org_structure 生成 graph TD、空数据返回 None
- `_append_additional_diagram_prompt` 是否按章节映射追加提示词、org_chart 注入真实 org_structure JSON
- `_build_section_prompt` 两个返回路径是否都调用注入
- `get_additional_diagram_prompt` 是否已正确导入
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
