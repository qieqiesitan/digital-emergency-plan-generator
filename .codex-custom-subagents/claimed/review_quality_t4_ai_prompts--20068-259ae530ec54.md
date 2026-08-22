# Codex Custom Subagents task handoff v1

Task: review_quality_t4_ai_prompts

## 任务：代码质量审查 — AI 提示词更新（commit aaf57af + cd99674）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现是否**构建良好**。规格合规审查已通过。这是只读审查：不要修改任何源码。

### 审查对象

- 提交：`aaf57af`（+3 文件）+ 跟进提交 `cd99674`（+1 文件）
- 文件：`backend/app/services/risk_assessment_service.py`、`risk_ai_service.py`、`backend/seed_prompts_full.py`
- 规格：`.codex-custom-subagents\claimed\ai_prompts_seed_2025--8216-592da85d927e.md` 与 `.codex-custom-subagents\claimed\ai_prompts_followup_2025--10256-a227116e66d9.md`

### 审查关注点

- 提示词更新是否准确一致（27 类全文在多处出现，是否逐字一致）
- 结论示例正文是否语义通顺（示例里的风险等级表述）
- :133 七维度指令更新是否只改了目标句（无顺带改动）
- 是否有遗漏的旧标准引用（`rg -n "GB 6441-1986|6441-1986" backend` 扫描，排除历史对照文档）
- 提交卫生（每个提交的文件范围）

### 汇报格式

- 优点（列出）
- 问题（按 关键/重要/次要 分级，附 file:line）
- 评估结论：✅ 通过 | ❌ 需修复（列出必须修复项）
- task_id、claim_id、path（claim_task.py 输出）
