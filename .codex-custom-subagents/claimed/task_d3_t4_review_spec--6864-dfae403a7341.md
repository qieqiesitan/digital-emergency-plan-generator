# Codex Custom Subagents task handoff v1

Task: task_d3_t4_review_spec

## 任务：规格合规审查（diagrams batch3 任务 4：导出接入）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md` §5、§6.5
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch3.md` 任务 4
3. 实现：git commit `e8649f9`（`git show e8649f9`）

### 审查重点

- get_export_preview 是否渲染非占位 SVG 与占位文字（占位文字含转义）
- docx 是否插入附图 SVG→PNG、占位转文字行
- sections_data 是否传入 diagram_svgs
- 测试是否覆盖占位与 SVG
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
