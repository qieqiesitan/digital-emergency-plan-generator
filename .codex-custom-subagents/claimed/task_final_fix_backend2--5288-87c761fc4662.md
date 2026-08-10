# Codex Custom Subagents task handoff v1

Task: task_final_fix_backend2

## 任务：修复批次 1 质量审查重要问题（draft+跳过 → 生成/合并 500）

你是实现子智能体。批次 1 后端收敛修复的质量审查发现 1 项重要问题，请修复并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 2f3a2f0）。必须 cd 到该目录操作，不要动主工作区。

### 问题描述

`skip_risk_assessment`（backend/app/routers/risk_assessment.py:43）与 `skip_resource_investigation`（backend/app/routers/resource_investigation.py:39）只拦截 generating/completed，不拦截 **draft**。draft 是生成完成后的正常状态（生成流程显式 `status = "draft"`）。用户「生成 → 未合并 → 点跳过」会新建第二条 skipped 记录；此后再生成（risk_assessment.py:446 / resource_investigation.py:318）或合并（risk_assessment.py:578 / resource_investigation.py:466）走无状态过滤的 `scalar_one_or_none()` → MultipleResultsFound → 500。

### 修法（择一并保持两处对称）

方案 A（推荐）：skip 接口遇已有记录（任意状态）时**改写该行状态为 skipped** 而非新增（upsert 语义：有记录则更新 status，无记录则插入），从根上杜绝重复行；或
方案 B：skip 遇 draft 时明确拒绝（400 提示「报告已生成，请先合并或删除」）。

两种方案都必须同时：
1. 给生成/合并查询加状态过滤（只查 generating/draft 等有效状态，不查 skipped），使历史脏数据（已有重复行）也不再触发 500。
2. 补测试：draft + skip → 不再产生重复行（或明确拒绝）；随后生成/合并不 500；已有重复行场景（手动构造两条）生成/合并不 500。

### 质量门禁（必须全部通过）

1. `cd backend && .\.venv\Scripts\python -m pytest -q --ignore=_docker_test.py` 全绿
2. `git diff --check` 干净
3. 单提交、提交信息如 `fix(report): handle skip-after-draft and harden generate/merge queries`，只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、修法简述、测试验证输出摘要。

