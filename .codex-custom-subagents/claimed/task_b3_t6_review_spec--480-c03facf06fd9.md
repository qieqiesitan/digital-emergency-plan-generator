# Codex Custom Subagents task handoff v1

Task: task_b3_t6_review_spec

## 任务：规格合规审查（批3 任务 6：移动端批量生成）

你是一个规格合规审查子智能体。审查实现是否符合规格，只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-generation-enhancement-design.md` 第 3.7 节「前端改动」
2. 计划：`docs\superpowers\plans\2026-08-08-plan-generation-batch3.md` 任务 6
3. 实现：git commit `faa9e28`（`git show faa9e28`）

### 审查重点

- 移动端批量按钮是否调用 generateBatchBackground 且仅传 aiGeneratable 章节
- 成功后是否提示并刷新章节（invalidateQueries）
- 失败是否 toast 提示
- 单章流式生成是否保持
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
