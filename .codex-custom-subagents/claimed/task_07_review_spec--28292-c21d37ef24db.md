# Codex Custom Subagents task handoff v1

Task: task_07_review_spec

## 规格合规审查：任务 7（AI 优化 + 快照端点）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 7 规格 + 设计规格 §12）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\services\risk_notice_card_ai.py`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\routers\risk_notice_card.py`（追加 POST /{object_id}/ai-optimize 与 PUT /{object_id}/snapshot）
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_risk_notice_card_api.py`（追加）+ service 测试

**AI 服务要求**（设计规格 §12）：
* optimize_right_column(db, user_id, enterprise_name, object_name, original)：调 llm_text_completion（timeout=60）输出 JSON；优化 hazard_description/control_measures/emergency_measures；accident_types 不变；字段缺失回落原值；措施 ①②③ 编号

**端点要求**：
* POST ai-optimize：企业/风险点归属校验（404）→ original = build_right_column → 成功返回 AiOptimizeResponse(original, optimized)；异常 → 502「AI 优化失败，请稍后重试或保留原版」
* PUT snapshot：企业归属校验 → save_snapshot → ApiResponse({version, source:"ai"})

**范围限制**：只创建 AI 服务、追加 2 端点、追加测试；不实现导出/token/公开端点；commit 消息 `feat(risk-notice-card): add ai optimize and snapshot endpoints`。

### 实现者声称构建了什么

* commit `0901c75`（4 文件 205+/2-），全量 390 passed
* AI 服务 + 2 端点 + 4 测试（AI 成功/失败 502/快照 PUT/save_snapshot 版本递增）
* 修复了 git save 带入的 TASKS.md 误提交（rebase 清理，分支干净）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 0901c75` 逐行核对。
2. 核对：
* AI 服务签名与行为（prompt 内容、JSON 解析、accident_types 不变、字段回落）
* 端点归属校验、错误处理（502）、响应模型
* save_snapshot 调用正确（SOURCE_AI、版本递增）
* 提交范围与消息、分支历史干净（无 TASKS.md 误入）
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_api.py tests/test_risk_notice_card_service.py -v`（预期全 PASS）+ 全量回归
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-6 已过审；任务 8-9 会追加导出与公开端点。
