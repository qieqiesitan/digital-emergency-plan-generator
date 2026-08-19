# Codex Custom Subagents task handoff v1

Task: task_07_review_spec

## 规格合规审查：任务 7（预览页 AI 审查按钮 + 差异对比 Modal）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 7 规格 + 设计规格 §9.2）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx`

**要求：**

* 工具栏新增「AI 审查标志」按钮（loading 防重入）
* 点击调 aiReviewSigns → 差异对比 Modal：建议删除（红删除线+理由）、建议增加（绿+理由）、保留（灰）
* 底部「采用建议并保存快照（版本 +1）」/「放弃，保留原版」
* handleAdoptSigns：当前标志应用建议（remove/add 按 svg_name）→ 完整 content（右栏四块+signs+signs_source="ai"）→ saveSnapshot → refetch → 版本+1
* 失败：message.error「AI 审查失败，已保留原版」

**实现者说明：** 「建议增加」行中文名暂以 svg_name 兜底（前端无 svg_name→中文名映射；任务 8 计划加 catalog 解决）。请核实当前展示是否可接受。

**范围限制：** 只改预览页组件；commit 消息 `feat(risk-notice-card): add ai sign review compare modal`。

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show b0a5e1e` 逐行核对。
2. 核对：按钮/loading、Modal 三组展示与理由、采用逻辑（svg_name 匹配、content 组装、saveSnapshot 参数、refetch）、错误处理、展示取舍、提交范围与消息。
3. 门禁实测：`cd frontend && npx tsc -b`（0 错误）+ `cd frontend && npx vitest run`（全通过）+ `cd frontend && npx eslint src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx`（0 问题）。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line）。

### 上下文

* worktree 独立分支 codex/ai-sign-review，审查只读，不修改文件、不提交。
* 任务 8 做人工微调 + 来源 Tag + catalog 中文名映射。
