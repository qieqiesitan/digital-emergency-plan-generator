# Codex Custom Subagents task handoff v1

Task: task_04_review_spec

## 规格合规审查：任务 4（schemas + ai-review-signs 端点）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 4 规格 + 设计规格 §7.1/§10）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\schemas\risk_notice_card.py`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\routers\risk_notice_card.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\tests\test_risk_notice_card_api.py`

**要求：**

* schemas：SignSuggestion（remove/add: list[str]、reasons: list[dict]）、AiSignReviewResponse（original_signs: list[SignItem]、suggestion）
* 端点 POST /{object_id}/ai-review-signs：企业+风险点归属（404）；当前标志=快照 signs 优先否则 match_signs；候选库 SIGN_GROUPS+DEFAULT_SIGN_GROUP 去重；事件数据组装；调 review_signs；HTTPException 透传、其余 502「AI 审查失败，请稍后重试或保留原版」；返回 ApiResponse[AiSignReviewResponse]

**实现者适配：** 计划样例测试 URL 带 /api/v1 前缀但夹具直接挂载 router 无前缀，改用无前缀 URL；补 DB 覆盖避免恒 404。请核实合理性。

**范围限制：** 只改 3 文件；commit 消息 `feat(risk-notice-card): add ai sign review endpoint`。

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show dcbc54d` 逐行核对。
2. 核对：schemas 结构、端点归属校验/当前标志/候选库/事件组装/AI 调用/错误处理/响应、测试夹具适配、提交范围与消息。
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_api.py -v`（预期全 PASS）+ 全量回归。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line）。

### 上下文

* worktree 独立分支 codex/ai-sign-review，审查只读，不修改文件、不提交。
* 任务 5 会扩展快照端点透传 signs。
