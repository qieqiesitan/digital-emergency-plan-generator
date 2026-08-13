# Codex Custom Subagents task handoff v1

Task: task_11_review_quality

## 代码质量审查：任务 11（卡片管理页 + 后端快照供给修复）

你正在审查一个已通过规格合规审查（含修复复审）的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）：

* commit `7dab40e`：`frontend/src/pages/Enterprise/RiskNoticeCardPage.tsx`（管理页）
* commit `9f647a7`：`backend/app/routers/risk_notice_card.py`（list_cards 补 snapshot/stale）+ `backend/tests/test_risk_notice_card_api.py`

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 7dab40e` + `git show 9f647a7` 通读。
2. 对照项目前端模式（其他 Enterprise 页面）与后端路由模式检查：
* 管理页代码质量（组件拆分、hooks 使用、性能——统计计算 useMemo、导出 loading 态、错误处理）
* 快照映射代码（后端批量查询、is_stale 复用、时间最大值计算）
* 测试质量（前后端）
* 命名/风格/可读性
* `git show --check` 干净度
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 12 填充预览页（复用管理页的跳转与 ?ai=1 参数）。
