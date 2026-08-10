# Codex Custom Subagents task handoff v1

Task: task_c11_review_spec

## 任务：规格合规审查——task_c11_types_service_route

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `c234d60`：

git show c234d60 --stat 与 git show c234d60

### 要求的内容（任务 C1-1 原文摘要）

1. frontend/src/types/onboarding.ts：CompletionModule/CompletionResult/CandidateItem。
2. frontend/src/services/onboardingService.ts：getEnterpriseCompletion、importOnboardingFile、importOnboardingBatch（api 路径与后端一致）。
3. frontend/src/pages/Onboarding/OnboardingPage.tsx：最小占位。
4. routes/index.tsx 挂载 /onboarding。
5. tsc -p tsconfig.app.json 无类型错误。
6. Commit：feat(onboarding): types, service and route scaffolding。
7. 只改 4 个文件。

### 实现者声称构建了什么

- 4 文件（类型/服务/占位/路由），tsc 通过
- 提交 c234d60（4 文件 41 增）
- 自审：api 路径与后端一致（前缀由 api.ts 统一）

### 你的工作

阅读实际代码验证：类型/服务/路由与要求一致？api 路径正确？只改 4 文件？占位组件存在？

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
