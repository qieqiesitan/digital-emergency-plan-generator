# Codex Custom Subagents task handoff v1

Task: task_13_public_page

## 实现任务 13：公开只读页

### 任务描述（来自实现计划 2026-08-11-risk-notice-card.md 任务 13 + 设计规格 §10.3）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\PublicRiskNoticePage.tsx`（填充占位）

### 页面功能（设计规格 §10.3，交互原型已确认）

* 路由 `/r/:token`（已在登录守卫外注册）；`useParams` 取 `token`
* `useQuery(["public-risk-notice", token], () => fetchPublicCard(token), { retry: false })`
* 加载中：居中 Spin
* 错误（404/网络）：居中「卡片不存在或链接已失效」（与后端 404 文案一致），不做重试（retry: false）
* 成功：`<RiskNoticeCard card={card} />`（复用任务 12 组件），外层容器 max-width 480px 居中、上下留白
* 底部提示条：「公开只读页面 · 数据来自系统快照 · 无需登录」（与原型一致）

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npx tsc -b` 0 错误
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npx vitest run` 全部通过（无回归）
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npx eslint src/pages/PublicRiskNoticePage.tsx` 0 问题
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净
* 提交 commit，消息：`feat(risk-notice-card): add public read-only page`，只含该文件

### 范围与限制

* 只填充 PublicRiskNoticePage.tsx。
* 不修改路由/组件/其他文件。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）。
* 任务 1-12 已完成（最新 HEAD：1aba3d9）。
* service：fetchPublicCard(token) → CardData（无鉴权）；后端 404「卡片不存在或链接已失效」。
* 组件：RiskNoticeCard 已就绪（v5 版式，可复用）。
* 设计规格：`docs/superpowers/specs/2026-08-11-risk-notice-card-design.md` §10.3（公开页交互）。
