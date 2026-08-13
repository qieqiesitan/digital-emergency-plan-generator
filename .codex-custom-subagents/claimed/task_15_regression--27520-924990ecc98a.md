# Codex Custom Subagents task handoff v1

Task: task_15_regression

## 实现任务 15：回归门禁 + 收尾验证

### 任务描述（来自实现计划 2026-08-11-risk-notice-card.md 任务 15）

**文件：** 无新增（视验证情况）

### 验证步骤

**步骤 1：后端全量测试**

运行：`cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/ -q`
预期：全部 PASS（基线 405 + 新增约 4 = 408+）

**步骤 2：前端全量门禁**

运行：`cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npx tsc -b && npx vitest run`
预期：tsc 0 错误、vitest 全通过（61 用例）

**步骤 3：SVG 合规复检**

运行：`cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/test_static_signs.py -v`
预期：PASS（形状/颜色/引用全覆盖）

**步骤 4：分支历史检查**

`git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card log --oneline master..HEAD`：确认所有功能提交与 fix 提交在分支上、无 TASKS.md 误入、无未提交源码改动。

**步骤 5：手工冒烟（可选，如环境允许）**

如本地 Docker 可用（docker compose），可尝试：起后端 → 登录 → 风险管理 Tab →「风险告知卡」→ 列表可见 → 预览单卡（含安全标志）→ 导出 Word（每卡一页 + 二维码）→ AI 优化对比 → 保存快照版本 +1 → 复制公开链接打开无需登录。若环境不允许（无 DB/无 Docker），如实记录即可，不强制。

### 验证

* 全部门禁通过后，如无代码修复则无需新 commit；如有修复，提交 `chore(risk-notice-card): regression fixes`。

### 汇报

* 状态：DONE | DONE_WITH_CONCERNS | BLOCKED
* 各门禁实际结果（命令 + 输出摘要）
* 分支 commit 列表（master..HEAD）
* 手工冒烟结果（如执行）
* 任何遗留问题

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）。
* 任务 1-14 已完成（最新 HEAD：9cbd30b）。
* 设计规格：`docs/superpowers/specs/2026-08-11-risk-notice-card-design.md` §14（测试计划）与 §15（范围里程碑）。
