# Codex Custom Subagents task handoff v1

Task: task_10_review_spec

## 规格合规审查：任务 10（前端类型 + API service + 入口与路由）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 10 规格）

**文件：**

* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\types\riskNoticeCard.ts`
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\services\riskNoticeCardService.ts` + test
* 修改：前端路由（计划写 App.tsx，实现者按实际项目结构改在 `routes/index.tsx`——请核实）
* 修改：`RiskManagementTab.tsx`（顶部「风险告知卡」按钮）
* 修改：`frontend/src/types/riskManagement.ts`（RiskObject 加 4 字段）
* 创建：3 个占位页（RiskNoticeCardPage / RiskNoticeCardPreviewPage / PublicRiskNoticePage）

**service 要求**：7 个函数与后端 API 对应（列表含 level/zone_id/keyword 筛选、详情、export→file_key、aiOptimize、saveSnapshot、resetToken→public_url、fetchPublicCard）

**类型要求**：CardData/CardSummary 与后端 schemas 逐字段对应

**路由要求**：管理页/预览页在企业布局内；公开页 /r/:token 在登录守卫外顶层

**范围限制**：commit 消息 `feat(risk-notice-card): add frontend types, service, routes and entry`。

### 实现者声称构建了什么

* commit `33a353d`（9 文件 200+），tsc 0 错误、vitest 57 通过
* 路由改在 routes/index.tsx（App.tsx 只调用 createRouter，计划笔误）
* 测试用 vi.mock("@/services/api")（项目走 axios，非全局 fetch）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 33a353d` 逐行核对。
2. 核对：
* 类型与后端 schemas 字段一致
* service 7 函数 URL/方法/参数与后端 API 一致（含筛选参数）
* 路由位置与守卫（公开页在登录守卫外）
* RiskManagementTab 按钮 navigate 路径
* riskManagement.ts 字段
* 两处偏差（路由文件、axios mock）是否合理
* 提交范围与消息
3. 门禁实测：`cd frontend && npx tsc -b`（0 错误）+ `cd frontend && npx vitest run`（全通过）
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 后端 API 已就绪（HEAD 33e5edd）；任务 11-13 填充占位页。
