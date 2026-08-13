# Codex Custom Subagents task handoff v1

Task: t05_review_quality

## 任务：代码质量审查 —— 任务 5（硬编码跳转核对，无代码改动）

你是一个代码质量审查子智能体。本任务预期无代码改动，审查重点是「确认没有产生任何意外改动/半成品改动，且扫描结论本身无遗漏风险」。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。HEAD 应为 `b470cf1`。

### 审查要点

1. `git status --porcelain` 仅应有 `M TASKS.md`（或干净），无任何源码意外改动；
2. `git diff HEAD` 无内容；
3. 复核扫描覆盖面：除指定两命令外，确认 `frontend/src` 下无遗漏的 `window.open(` 或 `<a href="/` 绝对跳转（可抽查）；
4. 结论记录：若后续新增原生跳转，约定用 `APP_BASE + "/xxx"`（来自任务 1 工具函数），此为团队约定备注，不是本任务代码改动。

### 汇报格式

返回：✅ 通过 / ❌ 需修复（附 file:line）。不要修改任何代码。
