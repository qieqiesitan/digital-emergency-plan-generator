# Codex Custom Subagents task handoff v1

Task: task_c11_review_quality

## 任务：代码质量审查——task_c11_types_service_route（规格审查已通过）

你是一个代码质量审查子智能体。目的：验证实现是否构建良好。规格合规性已由前序审查通过，本任务只关注代码质量。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。

BASE_SHA：382ce76；HEAD_SHA：c234d60。

审查命令：cd 到 worktree 后运行 git diff 382ce76..c234d60 并阅读实际代码。

### 实现内容

- types/onboarding.ts、services/onboardingService.ts、OnboardingPage 占位、routes 挂载
- 提交 c234d60（4 文件 41 增）

### 审查重点

1. 类型定义是否清晰、与后端响应结构一致（completion percent/modules；import 结果 module/candidates/source）？
2. 服务封装是否符合项目模式（api.ts 前缀、Promise 返回、错误处理）？
3. CandidateItem 索引签名是否合理？
4. 占位/路由是否有明显问题？

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复
