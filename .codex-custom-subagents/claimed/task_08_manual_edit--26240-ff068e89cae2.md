# Codex Custom Subagents task handoff v1

Task: task_08_manual_edit

## 实现任务 8：人工微调 + 来源 Tag + catalog 中文名映射

### 任务描述（来自实现计划 2026-08-15-ai-sign-review.md 任务 8 + 设计规格 §9.3/§9.4）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\schemas\risk_notice_card.py`（AiSignReviewResponse 加 catalog）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\routers\risk_notice_card.py`（响应返回 catalog）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\types\riskNoticeCard.ts`（AiSignReviewResponse 加 catalog: SignItem[]）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\components\enterprise\RiskNoticeCard.tsx`（来源 Tag）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx`（人工微调编辑模式 + add 行中文名用 catalog 解析）
* 测试：后端 API 测试（catalog 返回）、前端 tsc/eslint/vitest

### 功能要求（设计规格 §9.3/§9.4）

**1. catalog 中文名映射（解决任务 7 add 行中文名兜底）**
* 后端：AiSignReviewResponse 增加 `catalog: list[SignItem]`（即端点已组装的候选库）；路由返回时带上
* 前端：AiSignReviewResponse 类型加 catalog；SignReviewModal 的 add 行中文名用 catalog 查 svg_name 对应的 name（不再 svg_name 兜底）；同时 catalog 供人工微调候选库用

**2. 来源 Tag（RiskNoticeCard）**
* 标志区根据 `card.signs_source`：`"ai"` 显示「AI 审查」Tag、`"manual"` 显示「人工调整」，规则/缺省不显示
* 版本 Tag 逻辑不变（V1.x）

**3. 人工微调编辑模式（预览页）**
* 标志区「编辑」入口 → 编辑 Modal：
  * 当前已选标志（可移除）
  * 候选库网格（catalog，从 /signs/{svg_name}.svg 渲染，勾选添加）
  * 校验：每类 ≤2、总数 ≤8，超限即时提示
  * 保存：组装完整 content（右栏四块 + 调整后 signs + signs_source="manual"）→ saveSnapshot → refetch → 版本+1；取消不保存

**4. 顺带（任务 7 质量审查建议）**
* 把 applySignSuggestion/categoryOf/signSrc 等页面内纯函数抽到 `frontend/src/utils/riskNoticeCardSigns.ts` 并补 vitest 单测（增删/去重/类别推断）
* 预览侧 kept+added 按类别排序（与后端 normalize 结果一致）

### 验证

* `cd backend && python -m pytest tests/test_risk_notice_card_api.py -v` 全部 PASS
* `cd frontend && npx tsc -b` 0 错误 + `npx vitest run` 全通过 + `npx eslint` 改动文件 0 问题
* `git show --check HEAD` 干净
* 提交 `feat(risk-notice-card): add manual sign editing and source tag`，只含上述文件

### 范围与限制

* 改后端 schemas/路由（catalog）、前端类型/组件/页面、新增 utils 与测试。
* 不修改 service/AI 服务。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review，HEAD=b0a5e1e）。
* aiReviewSigns/saveSnapshot/normalize_signs 已就绪；CardData.signs_source 已回填。
* 任务 9 回归。
