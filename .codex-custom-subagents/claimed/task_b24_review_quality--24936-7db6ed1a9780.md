# Codex Custom Subagents task handoff v1

Task: task_b24_review_quality

## 任务：代码质量审查——task_b24_onboarding_routes（规格审查已通过）

你是一个代码质量审查子智能体。目的：验证实现是否构建良好。规格合规性已由前序审查通过，本任务只关注代码质量。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。

BASE_SHA：60f5ba6；HEAD_SHA：7b31f6d。

审查命令：cd 到 worktree 后运行 git diff 60f5ba6..7b31f6d 并阅读实际代码。

### 实现内容

- onboarding.py 三端点（candidates/import/import-batch）+ CandidatesBody/ImportResult/build_candidates_request
- onboarding_service.py get_enterprise_brief
- 提交 7b31f6d（3 文件 123+/2-），272 passed + 冒烟 8 项

### 审查重点

1. 端点设计是否遵循项目路由风格（鉴权、错误语义、UploadFile 处理）？
2. 潜在问题：batch fail-fast vs 单文件跳过？import module 非 auto 未校验已知模块？文件大小限制缺失（UploadFile 无大小上限）？多文件并发/内存？
3. get_enterprise_brief 与 compute_completion 的 enterprise 参数模式一致性？
4. 有无明显缺陷（异常处理、类型、pydantic 兼容）？

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复
