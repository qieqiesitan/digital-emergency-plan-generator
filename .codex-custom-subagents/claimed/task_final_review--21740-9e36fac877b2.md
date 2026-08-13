# Codex Custom Subagents task handoff v1

Task: task_final_review

## 最终整体审查：风险告知卡自动生成（分支 codex/risk-notice-card）

你正在对「风险告知卡自动生成」整个分支做最终整体审查。所有 15 个任务已实现并通过各自的双审，回归门禁全绿，手工冒烟全链路通过。你的职责是**整体把关**：确认规格全部落地、无遗漏、可合并。

### 审查对象

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card，master..HEAD 共 36 提交，最新 HEAD=9cbd30b）。

设计规格：`docs/superpowers/specs/2026-08-11-risk-notice-card-design.md`
实现计划：`docs/superpowers/plans/2026-08-11-risk-notice-card.md`

### 你的工作

1. 对照设计规格逐节审查（§1 概述、§2 决策 10 项、§4 版式、§5 架构、§6 数据模型、§7 标志库、§8 应急处置、§9 API、§10 页面交互、§11 导出二维码、§12 AI 优化、§13 错误处理、§14 测试、§15 范围里程碑），确认每项都有对应实现。
2. 检查：
* 功能完整性（是否有规格要求但未实现的部分）
* 前后端契约一致性（CardData 字段、API 路径）
* 安全项（公开 token 404 语义、越权防护、无敏感泄露）
* 分支卫生（commit 列表、无 TASKS.md 误入源码提交【savepoint cada4dd 例外】、无未提交源码）
* 测试覆盖与门禁（pytest 408 / vitest 61 / tsc 0）
3. 运行关键门禁复验：`cd backend && python -m pytest tests/test_risk_notice_card*.py tests/test_public_risk_notice.py -q` 与 `cd frontend && npx tsc -b`（可只跑风险告知卡相关测试，不必全量）。
4. 报告格式：
* 结论：✅ 可合并 或 ❌ 存在问题
* 规格覆盖矩阵（每节 → 实现位置）
* 发现的问题（如有，带 file:line 与级别）
* 遗留/后续建议（非阻塞）

### 上下文

* 审查只读，不修改文件、不提交。
* 审查通过后主控将走 finishing-a-development-branch 收尾（合并决策）。
