# Codex Custom Subagents task handoff v1

Task: task_08_review_quality

## 代码质量审查：任务 8（docx 导出 + 二维码）

你正在审查一个已通过规格合规审查的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `61458ff`：

* `backend/app/services/risk_notice_card_docx.py`（新建）
* `backend/app/routers/risk_notice_card.py`（追加 POST /export）
* `backend/app/schemas/risk_notice_card.py`（ExportResponse.warnings）
* `backend/requirements.txt`（qrcode）
* `backend/tests/test_risk_notice_card_docx.py`（新建）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 61458ff` 通读。
2. 对照项目既有导出模式（`export.py`、`docx_template.py`、`export_tasks.py`）检查：
* docx 渲染代码质量（表格/段落样式、字体设置、颜色使用、资源释放）
* svg_to_png 占位回退策略是否合理（失败静默占位 vs 记录警告）
* 导出端点的效率（逐卡 build_card_data 的查询次数、warnings 语义）
* qrcode 依赖版本（未 pin，项目惯例是 pin）
* 测试质量（是否真实断言 docx 内容、占位 PNG 是否掩盖真实渲染问题）
* `git show --check` 干净度
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 9 会追加公开 API 与 token 重置。
* 已知：规格审查已确认 warnings 字段变更合理；SVG→PNG 走 Playwright 通道（复用 mermaid_renderer）。
