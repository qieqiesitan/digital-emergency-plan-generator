# Codex Custom Subagents task handoff v1

Task: task_12_preview

## 实现任务 12：卡片组件 + 单卡预览页 + AI 优化对比

### 任务描述（来自实现计划 2026-08-11-risk-notice-card.md 任务 12 + 设计规格 §10.2）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\components\enterprise\RiskNoticeCard.tsx`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx`（填充占位）

### 卡片组件（`RiskNoticeCard.tsx`，v5 版式，原型已确认）

props：`{ card: CardData }`。版式：
* 头部：企业名（小字居中）+ 标题「{name}安全风险告知卡」（18px 加粗字距）+ 底部 3px `card.level_color` 色线；右上角二维码占位（虚线方块 + 「扫码查看」小字；真实二维码在导出的 Word 中由后端生成）
* 左栏（40%，浅灰底）：等级色带（全宽白字，背景 level_color）+ 键值表格 6 行（名称/编号/等级/责任单位/责任人/电话）+「安全标志」深色标题条 + 标志区（`/signs/{svg_name}.svg` 56px 横排带名称）
* 右栏（60%）：四信息块（主要危险因素描述 / 主要事故类型【GB 6441 标注】/ 主要风险控制措施 / 应急处置措施），深色标题条 + 白底正文
* 页脚：签发单位（enterprise_name）/ 编制日期（generated_at 本地化）/ 版本（snapshot ? V1.{version} : V1.0）
* 样式：CSS（可内联 <style> 或 CSS Module / css 文件，与项目风格一致）；用 `.rnc-*` 前缀避免冲突
* 空正文兜底：「暂无，请先完善风险评估数据」

### 预览页（`RiskNoticeCardPreviewPage.tsx`，设计规格 §10.2）

* `useParams` 取 `:id`/`:objectId`；`useQuery(["risk-notice-card", id, objectId], fetchCardDetail)`
* 顶部：返回列表按钮（`/enterprises/:id/risk-notice-cards`）+ 版本 Tag（snapshot ? `V1.{version} · AI 优化` : `V1.0 · 规则生成`）+ stale 时 Alert「风险数据已变更，建议重新生成」
* 工具栏：复制公开链接（`{origin}{card.public_url}`，clipboard）+ 导出单张 Word（跳转管理页并带选中？简化：直接调 exportCards(id, [objectId]) → window.open 下载）+「AI 优化」按钮（loading 态）
* 卡片渲染：`<RiskNoticeCard card={card} />`
* AI 优化流程（设计规格 §12）：
  * 点击「AI 优化」→ `aiOptimize(id, objectId)` → 返回 `{original, optimized}` → 显示左右对比面板（左「原版（当前版本）」右「优化版（AI 生成）」，右栏三块：危险因素/管控措施/应急处置；差异可用黄色高亮块）
  * 底部「采用优化版并保存快照（版本 +1）」（调 `saveSnapshot(id, objectId, optimized)` → message.success → refetch 刷新卡片 + 关闭面板）与「放弃，保留原版」（关闭面板）
  * 失败 → message.error「AI 优化失败，已保留原版」
* `?ai=1` 参数：进入页面时 `useSearchParams` 检测 ai=1 自动触发 AI 优化（从管理页行操作跳转）
* 事故类型不参与优化（对比面板只显示三块）

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npx tsc -b` 0 错误
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend && npx vitest run` 全部通过（无回归）
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净
* 提交 commit，消息：`feat(risk-notice-card): add card preview and ai optimize compare`，只含上述文件

### 范围与限制

* 只创建卡片组件、填充预览页。
* 不修改路由/service（如需小调整请说明）。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）。
* 任务 1-11 已完成（最新 HEAD：5cd597f）。
* service：fetchCardDetail/aiOptimize/saveSnapshot/exportCards/resetToken 已就绪。
* 路由：`/enterprises/:id/risk-notice-cards/:objectId`（预览页，占位已注册）。
* 设计规格：`docs/superpowers/specs/2026-08-11-risk-notice-card-design.md` §4（版式 v5）、§10.2（预览交互）、§12（AI 优化流程）。
