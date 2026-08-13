# Codex Custom Subagents task handoff v1

Task: task_10_frontend_base

## 实现任务 10：前端类型 + API service + 入口与路由

### 任务描述（来自实现计划 2026-08-11-risk-notice-card.md 任务 10）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\types\riskNoticeCard.ts`
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\services\riskNoticeCardService.ts`
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\services\riskNoticeCardService.test.ts`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\App.tsx`（加路由：管理页 + 预览页 + 公开页）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\Enterprise\RiskManagementTab.tsx`（顶部「风险告知卡」按钮）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\types\riskManagement.ts`（RiskObject 加 4 字段）
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\Enterprise\RiskNoticeCardPage.tsx`（占位，任务 11 填充）
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx`（占位，任务 12 填充）
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\PublicRiskNoticePage.tsx`（占位，任务 13 填充）

### 类型（`frontend/src/types/riskNoticeCard.ts`）

SignCategory（warning/prohibition/instruction/notice）、SignItem、RightColumn、CardData（extends RightColumn，含 object_id/enterprise_name/name/code/level/level_color/responsible_unit/responsible_person/contact_phone/fallback_used/signs/snapshot/stale/public_url/generated_at）、CardSummary。完整代码见计划文档任务 10 或后端 schemas 对应结构。

### service（`frontend/src/services/riskNoticeCardService.ts`）

参考项目既有请求封装（`frontend/src/services/riskManagementService.ts` 或 `riskMappingWorkbenchService.ts` 的请求模式）实现：

* `fetchCardSummaries(enterpriseId, params?: {level?, zone_id?, keyword?})` → CardSummary[]
* `fetchCardDetail(enterpriseId, objectId)` → CardData
* `exportCards(enterpriseId, objectIds)` → file_key
* `aiOptimize(enterpriseId, objectId)` → {original: RightColumn, optimized: RightColumn}
* `saveSnapshot(enterpriseId, objectId, content: RightColumn)` → {version}
* `resetToken(enterpriseId, objectId)` → public_url
* `fetchPublicCard(token)` → CardData（无鉴权）

### service 测试（`riskNoticeCardService.test.ts`）

用 vi.spyOn(globalThis, "fetch") mock：fetchCardSummaries 调用 GET 列表 URL（含筛选参数）；exportCards POST object_ids 返回 file_key；fetchPublicCard 调用 /public/risk-notice-cards/{token}。参考计划任务 10 的测试代码。

### 路由与入口

* `App.tsx`：查看现有 router 结构（createBrowserRouter），新增：
  * `/enterprises/:enterpriseId/risk-notice-cards` → RiskNoticeCardPage（企业布局内）
  * `/enterprises/:enterpriseId/risk-notice-cards/:objectId` → RiskNoticeCardPreviewPage（企业布局内）
  * `/r/:token` → PublicRiskNoticePage（**登录守卫外**，顶层路由）
* `RiskManagementTab.tsx` 顶部操作区添加按钮：`<Button icon={<ApartmentOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards`)}>风险告知卡</Button>`（参照现有按钮样式；ApartmentOutlined 已在 import 中）
* `riskManagement.ts`：RiskObject 类型加 `responsible_unit?/responsible_person?/contact_phone?: string|null; public_token?: string`

### 验证

* worktree 的 frontend 需要 node_modules：运行 `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npm ci`（或 npm install）安装依赖
* `cd frontend && npx tsc -b` 预期 0 错误
* `cd frontend && npx vitest run src/services/riskNoticeCardService.test.ts` 预期 PASS
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净
* 提交 commit，消息：`feat(risk-notice-card): add frontend types, service, routes and entry`，只含上述文件

### 范围与限制

* 只创建类型/service/测试/占位页 + 改路由/入口/类型。
* 管理页/预览页/公开页在任务 11-13 填充实现（本任务先建占位组件保证路由可编译）。
* 不修改后端。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）。
* 后端 9 个任务已全部完成（最新 HEAD：33e5edd），API 已就绪：GET 列表/详情、POST export、POST ai-optimize、PUT snapshot、POST token/reset、GET /public/risk-notice-cards/{token}。
* 设计规格：`docs/superpowers/specs/2026-08-11-risk-notice-card-design.md` §9（API）与 §10（页面交互）。
* 标志 SVG 通过 `/signs/{svg_name}.svg` 引用（后端已挂载）。
