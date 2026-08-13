# Codex Custom Subagents task handoff v1

Task: task_10_review_quality

## 代码质量审查：任务 10（前端类型 + API service + 入口与路由）

你正在审查一个已通过规格合规审查的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `33a353d`：

* `frontend/src/types/riskNoticeCard.ts`（新建）
* `frontend/src/services/riskNoticeCardService.ts` + test（新建）
* `frontend/src/routes/index.tsx`（修改）
* `frontend/src/pages/Enterprise/RiskManagementTab.tsx`（修改）
* `frontend/src/types/riskManagement.ts`（修改）
* 3 个占位页（新建）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 33a353d` 通读。
2. 对照项目前端模式（riskManagementService.ts / riskMappingWorkbenchService.ts / routes 结构）检查：
* service 代码质量（axios 封装一致性、错误处理、类型安全）
* 类型定义质量（复用 vs 重复、命名）
* 路由配置风格（与既有路由一致、参数命名）
* RiskManagementTab 按钮位置与样式
* 占位页是否最小化且可编译
* 测试质量
* `git show --check` 干净度
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 11-13 填充占位页；任务 14 表单字段。
