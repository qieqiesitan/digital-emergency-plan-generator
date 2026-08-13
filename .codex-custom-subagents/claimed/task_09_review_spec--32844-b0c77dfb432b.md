# Codex Custom Subagents task handoff v1

Task: task_09_review_spec

## 规格合规审查：任务 9（公开 API + token 重置）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 9 规格 + 设计规格 §9/§13）

**文件：**
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\routers\public_risk_notice.py`（填充完整实现）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\routers\risk_notice_card.py`（POST /{object_id}/token/reset）
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_public_risk_notice.py`（+ api 测试追加）

**公开 API**（设计规格 §9/§13）：
* GET /public/risk-notice-cards/{token}：无鉴权；按 public_token 查对象；无 → 404「卡片不存在或链接已失效」；有 → build_card_data → ApiResponse[CardData]
* token 无效/过期返回 404，不泄露卡片内容

**token 重置**：
* POST /{object_id}/token/reset：企业归属 + 对象归属（id + enterprise_id）→ secrets.token_hex(32) → commit → {"public_url": "/r/{token}"}

**范围限制**：commit 消息 `feat(risk-notice-card): add public read api and token reset`。

### 实现者声称构建了什么

* commit `563e08f`（4 文件 254+），全量 405 passed
* 公开 API（无鉴权、404 语义、build_card_data）+ token 重置（secrets.token_hex(32)）
* 5 个测试（未知 token 404/有效 token 200 全字段/企业被删 404/重置新 URL/对象不存在 404）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 563e08f` 逐行核对。
2. 核对：
* 公开端点无鉴权、404 语义（token 无效不泄露）、CardData 组装正确
* token 重置端点归属校验、随机 token 生成、commit
* 提交范围与消息
3. 门禁实测：`cd backend && python -m pytest tests/test_public_risk_notice.py tests/test_risk_notice_card_api.py -v`（预期全 PASS）+ 全量回归
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-8 已过审；任务 10 起进入前端实现。
