# Codex Custom Subagents task handoff v1

Task: task_b23_review_quality2

## 任务：代码质量复审——task_b23_fix（测试卫生 + groups 守卫）

你是一个代码质量审查子智能体。目的：验证修复是否解决了前次审查的问题且无回归。规格合规性已通过。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。

BASE_SHA：f204355；HEAD_SHA：60f5ba6。

审查命令：cd 到 worktree 后运行 git diff f204355..60f5ba6 并阅读相关代码。

### 前次审查要求修复的问题

1. 必须：test_onboarding_org.py 的 RuntimeWarning（db=AsyncMock 裸用）→ 仿 extract 测试 monkeypatch get_system_ai_config。
2. 可选：generate_org_candidates groups 非 list 守卫（与 classify_modules 对称）。

### 实现者声称修复了什么

- fake_config monkeypatch（-W error::RuntimeWarning 通过）
- groups isinstance(list) 守卫
- 提交 60f5ba6（2 文件 8+/2-），全量 271 passed

### 你的工作

阅读实际代码验证：测试无 RuntimeWarning？groups 守卫正确且与 classify 对称？无回归？

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复
