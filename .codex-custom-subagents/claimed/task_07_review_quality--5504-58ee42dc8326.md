# Codex Custom Subagents task handoff v1

Task: task_07_review_quality

## 代码质量审查：任务 7（预览页 AI 审查按钮 + 差异对比 Modal）

你正在审查一个已通过规格合规审查的实现的质量。独立阅读实际代码，不信任报告。

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review）的 commit `b0a5e1e`：

* `frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx`

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show b0a5e1e` 通读。
2. 对照项目既有模式（AI 优化对比 Modal、其他页面组件）检查：组件拆分（SignReviewModal 是否内联过大）、hooks 使用（loading 防重入、useCallback）、applySignSuggestion 逻辑（svg_name 匹配/categoryOf 推断健壮性）、样式组织（.rnc-sr-* 前缀）、测试覆盖（页面级交互无测试的惯例）、`git show --check` 干净度。
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 8 做人工微调 + 来源 Tag + catalog 中文名映射（解决 add 行中文名兜底）。
