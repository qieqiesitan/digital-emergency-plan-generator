# Codex Custom Subagents task handoff v1

Task: task_c16_review_spec

## 任务：规格合规审查——task_c16_import_completion

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `174d400`：

git show 174d400 --stat 与 git show 174d400

### 要求的内容（任务 C1-6 原文摘要）

1. ImportDrawer.tsx：Drawer + Upload.Dragger（多文件/格式）→ importOnboardingBatch → onImported + 反馈 + loading。
2. CompletionCard.tsx：useCurrentEnterprise + getEnterpriseCompletion → 进度条 + 未完成列表 + 跳转（未完成→onboarding、完成→plans/new）。
3. DashboardPage 嵌入 CompletionCard（统计卡后、快捷新建前）。
4. tsc + eslint 通过（无 any）。
5. Commit：feat(onboarding): import drawer and dashboard completion card。

### 实现者声称构建了什么

- 3 文件 89+/2-；ImportDrawer 删未用导入、CompletionCard、Dashboard 嵌入 + 顺带消 2 处既有 any
- tsc + eslint 通过；提交 174d400

### 你的工作

阅读实际代码验证：ImportDrawer 可用（批量/候选/反馈/loading）？CompletionCard 显示/跳转正确？Dashboard 嵌入位置？只改 3 文件？无 any？

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
