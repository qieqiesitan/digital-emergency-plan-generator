# Codex Custom Subagents task handoff v1

Task: task_08_review_spec

## 规格合规审查：任务 8（人工微调 + 来源 Tag + catalog）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 8 规格 + 设计规格 §9.3/§9.4）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\schemas\risk_notice_card.py`、`backend\app\routers\risk_notice_card.py`、`backend\tests\test_risk_notice_card_api.py`
* 修改：`frontend\src\types\riskNoticeCard.ts`、`frontend\src\components\enterprise\RiskNoticeCard.tsx`、`frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx`
* 创建：`frontend\src\utils\riskNoticeCardSigns.ts` + 测试

**要求：**

* 后端 AiSignReviewResponse 加 catalog（候选库）；路由返回
* 前端类型加 catalog；SignReviewModal add 行中文名用 catalog 解析
* 来源 Tag：signs_source=ai 显示「AI 审查」、manual 显示「人工调整」
* 人工微调编辑模式：标志区编辑入口 → 已选可移除 + 候选库网格勾选（每类≤2 总数≤8 即时提示）→ 保存 signs_source=manual
* 抽 utils 补单测（增删/去重/类别推断）

**实现者取舍：** 人工微调候选库仅来自 ai-review-signs 响应 catalog——未先运行 AI 审查时候选库为空（Modal 提示先运行审查，但仍可移除已选）。请核实这是否符合规格 §9.3「36 候选标志网格勾选添加」。

**范围限制：** commit 消息 `feat(risk-notice-card): add manual sign editing and source tag`。

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show e22d432` 逐行核对。
2. 核对：catalog 全链路、来源 Tag、编辑模式（含候选库空态取舍）、utils 抽取与单测、提交范围与消息。
3. 门禁实测：后端相关测试 + `cd frontend && npx tsc -b` + `npx vitest run` + eslint。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line，含候选库空态取舍结论）。

### 上下文

* worktree 独立分支 codex/ai-sign-review，审查只读，不修改文件、不提交。
* 任务 9 回归。
