# Codex Custom Subagents task handoff v1

Task: task_b24_review_spec

## 任务：规格合规审查——task_b24_onboarding_routes

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `7b31f6d`：

git show 7b31f6d --stat 与 git show 7b31f6d

### 要求的内容（任务 B2-4 原文摘要）

1. onboarding.py 追加：CandidatesBody（enterprise_id/module/overview/existing_keys）、ImportResult（module/candidates/source）、build_candidates_request、POST /onboarding/candidates（org 走 generate_org_candidates 且企业归属校验非本人 404；非 org 400 提示）、POST /onboarding/import（module=auto 时 classify 取首模块；解析失败 400）、POST /onboarding/import/batch（多文件循环，无识别模块跳过）。
2. onboarding_service.py 追加 get_enterprise_brief。
3. 测试：test_build_candidates_request_wraps_overview。
4. Commit：feat(onboarding): candidate orchestration and file import endpoints。
5. 只改 3 个文件；completion 端点保留。

### 实现者声称构建了什么

- 三端点 + helper + 测试；272 passed；TestClient 冒烟 8 项（org 200/404、非 org 400、import auto/显式、损坏 400、batch 两条）
- 提交 7b31f6d（3 文件 123+/2-）
- org 归属校验（id+user_id 双条件 404）

### 你的工作

阅读实际代码验证：三端点实现与要求一致？org 企业归属校验到位？import/batch 错误语义（400）与循环正确？get_enterprise_brief 实现正确？completion 保留？只改 3 文件？测试有效？

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
