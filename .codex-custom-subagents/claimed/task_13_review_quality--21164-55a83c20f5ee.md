# Codex Custom Subagents task handoff v1

Task: task_13_review_quality

## 代码质量审查：任务 13（公开只读页）

你正在审查一个已通过规格合规审查的实现的质量。独立阅读实际代码，不信任报告。

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `10803c4`：

* `frontend/src/pages/PublicRiskNoticePage.tsx`（填充）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 10803c4` 通读。
2. 检查：
* 页面代码质量（hooks 使用、样式、可读性）
* 错误处理（网络错误 vs 404 语义——规格要求统一文案，评估是否可接受）
* 移动端适配（max-width 480px 容器、卡片组件在窄屏表现）
* 与公开页安全语义一致性（无敏感信息泄露）
* `git show --check` 干净度
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 14 表单字段；任务 15 回归。
