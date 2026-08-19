# Codex Custom Subagents task handoff v1

Task: task_06_review_quality

## 代码质量审查：任务 6（前端类型 + service）

你正在审查一个已通过规格合规审查的实现的质量。独立阅读实际代码，不信任报告。

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review）的 commit `e7f0ac3`：

* `frontend/src/types/riskNoticeCard.ts`
* `frontend/src/services/riskNoticeCardService.ts`
* `frontend/src/services/riskNoticeCardService.test.ts`

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show e7f0ac3` 通读。
2. 对照项目前端模式（riskManagementService/其他 service/类型定义）检查：类型定义质量（复用/命名/联合类型）、service 一致性（api 封装、错误处理、解包）、测试质量（断言真实性）、命名/风格、`git show --check` 干净度。
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 7-8 使用 aiReviewSigns 做页面交互；CardData.signs_source 用于来源 Tag。
