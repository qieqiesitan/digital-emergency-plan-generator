# Codex Custom Subagents task handoff v1

Task: task_12_review_quality

## 代码质量审查：任务 12（卡片组件 + 预览页 + AI 优化对比）

你正在审查一个已通过规格合规审查的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `b941b14`：

* `frontend/src/components/enterprise/RiskNoticeCard.tsx`（新建）
* `frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx`（填充）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show b941b14` 通读。
2. 对照项目前端模式（其他组件/页面）检查：
* 卡片组件质量（样式组织、可读性、语义化、重复）
* 预览页 hooks 使用（useEffect 依赖、防重入、setState 时序）、错误处理、加载态
* AI 对比 Modal 实现（差异高亮逻辑、空数据处理）
* 样式一致性（与 v5 原型、项目风格）
* `git show --check` 干净度
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 13 填充公开页（复用 RiskNoticeCard 组件）。
