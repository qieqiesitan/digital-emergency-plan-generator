# Codex Custom Subagents task handoff v1

Task: task_11_manage_page

## 实现任务 11：卡片管理页

### 任务描述（来自实现计划 2026-08-11-risk-notice-card.md 任务 11 + 设计规格 §10.1）

**文件：**
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\Enterprise\RiskNoticeCardPage.tsx`（填充占位）

### 页面功能（设计规格 §10.1，交互原型已确认）

* 顶部：标题「风险告知卡」+ 说明；右侧「刷新」「批量导出 Word」按钮
* 筛选：风险等级下拉（全部/重大/较大/一般/低/未评估）+ 关键词搜索（风险点名称/责任单位）
* 统计行：总数 + 四色分布（可从列表数据计算）
* 列表（AntD Table）：勾选列、风险点名称（点击进预览 `/enterprises/:id/risk-notice-cards/:objectId`）、所在分区、风险等级 Tag（level_color）、主要事故类型、安全标志缩略（`/signs/{svg_name}.svg` 20px + Tooltip 名称）、责任单位、快照状态（stale →「数据已变更」橙 Tag；有快照 →「V1.{version} AI」蓝 Tag）、操作列（预览 / AI 优化 / 链接）
* 行操作：预览 → 跳预览页；AI 优化 → 跳预览页并带 `?ai=1` 自动触发；链接 → 复制 `{origin}{public_url}` 到剪贴板
* 底部批量栏：勾选后显示「已选 N 项」+「导出选中卡片 Word」+「清除选择」
* 导出：调 `exportCards(enterpriseId, objectIds)` → 返回 `{file_key, warnings}`；`window.open(\`/api/v1/export/download/${file_key}\`)` 下载；warnings 非空时 message.warning 提示「部分卡片未导出：N 张」
* 数据：`useQuery(["risk-notice-cards", id, filters], () => fetchCardSummaries(id, filters))`；`useParams()` 取 `:id`
* 空态：无数据时提示「请先在风险管理中添加风险点」

### 参考代码

计划文档任务 11 有完整组件骨架（AntD Table + Select + Input.Search + rowSelection + Tag），可参考实现；注意适配已确认的改动：路由参数 `:id`、`exportCards` 返回 `{file_key, warnings}`、行操作三件套（预览/AI 优化/链接）。

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npx tsc -b` 0 错误
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npx vitest run` 全部通过（无回归）
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净
* 提交 commit，消息：`feat(risk-notice-card): add card management page`，只含该文件

### 范围与限制

* 只填充 RiskNoticeCardPage.tsx。
* 不修改路由/service/其他文件（如需小调整 service 请说明）。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）。
* 任务 1-10 已完成（最新 HEAD：684e09a）。
* service：fetchCardSummaries(id, {level, keyword})、exportCards(id, ids) → {file_key, warnings}。
* 路由：`/enterprises/:id/risk-notice-cards`（管理页）、`/enterprises/:id/risk-notice-cards/:objectId`（预览页，任务 12）。
* 设计规格：`docs/superpowers/specs/2026-08-11-risk-notice-card-design.md` §10.1（管理页交互）。
