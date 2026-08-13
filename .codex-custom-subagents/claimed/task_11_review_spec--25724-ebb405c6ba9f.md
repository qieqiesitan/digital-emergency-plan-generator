# Codex Custom Subagents task handoff v1

Task: task_11_review_spec

## 规格合规审查：任务 11（卡片管理页）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 11 规格 + 设计规格 §10.1）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\Enterprise\RiskNoticeCardPage.tsx`

**功能要求**（设计规格 §10.1，交互原型已确认）：

* 顶部标题 + 刷新/批量导出按钮
* 筛选：等级下拉 + 关键词搜索
* 统计行：总数 + 四色分布
* Table：勾选列、名称（点击进预览）、分区、等级 Tag、事故类型、标志缩略（/signs/{svg_name}.svg）、责任单位、快照状态（stale 橙 Tag / 快照蓝 Tag）、操作列（预览 / AI 优化 ?ai=1 / 链接复制）
* 底部批量栏 + 导出（exportCards → window.open 下载 + warnings 提示）
* useParams 取 :id；空态提示

**范围限制**：只改该文件；commit 消息 `feat(risk-notice-card): add card management page`。

### 实现者声称构建了什么

* commit `7dab40e`（1 文件 234+/2-），tsc 0、vitest 61 通过
* 管理页完整实现（适配 :id、exportCards 返回 {file_key, warnings}、svg_name 补 .svg）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 7dab40e` 逐行核对。
2. 核对：
* 所有功能要素（标题/筛选/统计/Table 列/批量栏/导出/空态）
* 行操作（预览 URL、AI 优化 ?ai=1、链接复制 origin+public_url）
* 导出流程（exportCards → {file_key, warnings} → window.open 下载 → warnings 提示）
* useParams :id、svgs 补 .svg
* 提交范围与消息
3. 门禁实测：`cd frontend && npx tsc -b`（0 错误）+ `cd frontend && npx vitest run`（全通过）
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-10 已过审；任务 12 填充预览页。
