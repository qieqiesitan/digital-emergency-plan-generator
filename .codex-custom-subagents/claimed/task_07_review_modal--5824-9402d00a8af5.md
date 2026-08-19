# Codex Custom Subagents task handoff v1

Task: task_07_review_modal

## 实现任务 7：预览页「AI 审查标志」按钮 + 差异对比 Modal

### 任务描述（来自实现计划 2026-08-15-ai-sign-review.md 任务 7 + 设计规格 §9.2）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx`

### 功能要求（设计规格 §9.2，视觉原型已确认）

* 预览页工具栏新增「AI 审查标志」按钮（与「AI 优化」并列，loading 防重入）
* 点击后调 `aiReviewSigns(id, objectId)` → 差异对比 Modal：
  * 三组展示：建议删除（红色删除线 + 理由）、建议增加（绿色 + 理由）、保留（灰）
  * 底部「采用建议并保存快照（版本 +1）」/「放弃，保留原版」
* 采用逻辑 `handleAdoptSigns`：
  * 当前标志（card.signs）应用 AI 建议：remove 的去掉、add 的加入（用 svg_name 匹配）
  * 组装完整 content：当前右栏四块（hazard_description/accident_types/control_measures/emergency_measures）+ 新 signs + signs_source="ai"
  * `saveSnapshot(id, objectId, content)` → message.success → refetch → 关闭 Modal → 版本 +1
* 失败：message.error「AI 审查失败，已保留原版」（与后端 502 文案一致）
* 采用前无需再次确认（Modal 本身即确认环节）

### 实现参考

参考现有「AI 优化」对比 Modal（handleOptimize/adoptOptimized 模式）扩展；差异三组用 AntD List/Tag + 理由文字。

### 验证

* `cd frontend && npx tsc -b` 0 错误
* `cd frontend && npx vitest run` 全通过（无回归）
* `cd frontend && npx eslint src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx` 0 问题
* `git show --check HEAD` 干净
* 提交 `feat(risk-notice-card): add ai sign review compare modal`，只含该文件

### 范围与限制

* 只改预览页组件。
* 不修改 service/后端/其他组件。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review，HEAD=e7f0ac3）。
* aiReviewSigns/saveSnapshot 已就绪（任务 6 + 既有）；CardData.signs_source 已回填。
* 任务 8 做人工微调 + 来源 Tag。
