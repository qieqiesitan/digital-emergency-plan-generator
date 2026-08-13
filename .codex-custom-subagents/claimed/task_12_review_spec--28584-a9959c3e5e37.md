# Codex Custom Subagents task handoff v1

Task: task_12_review_spec

## 规格合规审查：任务 12（卡片组件 + 预览页 + AI 优化对比）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 12 规格 + 设计规格 §4/§10.2/§12）

**文件：**

* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\components\enterprise\RiskNoticeCard.tsx`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx`

**卡片组件（v5 版式）**：头部企业名+标题+level_color 色线+右上角二维码占位；左栏 40% 等级色带+键值表 6 行+安全标志区（/signs/{svg_name}.svg 56px）；右栏四信息块（事故类型带 GB 6441）；页脚签发/日期/版本；空正文兜底。

**预览页**：useParams :id/:objectId；版本 Tag；stale Alert；复制链接（origin+public_url）；导出单张 Word；AI 优化按钮（loading 防重入）；AI 优化对比（左右三块，事故类型不参与，差异高亮）；采用（saveSnapshot→refetch）/放弃；?ai=1 自动触发；失败提示。

**范围限制**：只创建 2 文件；commit 消息 `feat(risk-notice-card): add card preview and ai optimize compare`。

### 实现者声称构建了什么

* commit `b941b14`（2 文件 633+/2-），tsc/eslint 0、vitest 61 通过
* 卡片组件 v5 版式 + 预览页完整交互（AI 对比 Modal、?ai=1 自动触发、导出单张）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show b941b14` 逐行核对。
2. 核对：
* 卡片版式全部要素（头部/左栏/右栏/页脚/二维码占位/空兜底）
* 预览页交互（版本 Tag、stale Alert、复制链接、导出、AI 优化流程、?ai=1、失败提示）
* AI 优化对比仅三块（事故类型不参与）
* 提交范围与消息
3. 门禁实测：`cd frontend && npx tsc -b`（0 错误）+ `cd frontend && npx vitest run`（全通过）+ `cd frontend && npx eslint src/components/enterprise/RiskNoticeCard.tsx src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx`（0 问题）
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-11 已过审；任务 13 填充公开页。
