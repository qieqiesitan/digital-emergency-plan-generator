# Codex Custom Subagents task handoff v1

Task: task_09_public

## 实现任务 9：公开 API + token 重置

### 任务描述（来自实现计划 2026-08-11-risk-notice-card.md 任务 9）

**文件：**
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\routers\public_risk_notice.py`（填充完整实现，替换占位空 router）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\routers\risk_notice_card.py`（追加 POST /{object_id}/token/reset）
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_public_risk_notice.py`

### 公开 API（`backend/app/routers/public_risk_notice.py`）

* `router = APIRouter(prefix="/public/risk-notice-cards", tags=["Public Risk Notice Card"])`
* `GET /{token}`：**无鉴权**。按 `RiskObject.public_token == token` 查对象（selectinload zone）；无 → 404「卡片不存在或链接已失效」；有 → 查企业 + 全企业 objects（compute_code 需要）+ load_events_and_measures → build_card_data → `ApiResponse[CardData]`

### token 重置端点（`risk_notice_card.py` 追加）

```python
@router.post("/{object_id}/token/reset", response_model=ApiResponse[dict])
async def reset_token(...):
    # 企业归属校验 + RiskObject 归属校验（id + enterprise_id，无 → 404「风险点不存在」）
    # obj.public_token = secrets.token_hex(32) → commit → ApiResponse({"public_url": f"/r/{obj.public_token}"})
```

### 测试（`backend/tests/test_public_risk_notice.py`）

按 mock DB 模式（可参考 test_risk_notice_card_api.py）：
* 未知 token → 404
* 有效 token → 200 且 CardData 字段齐全（企业名/名称/等级/public_url 等）
* token 重置端点（放 test_risk_notice_card_api.py）：200 返回新 public_url；风险点不存在 → 404

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/test_public_risk_notice.py tests/test_risk_notice_card_api.py -v` 全部 PASS
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/ -q` 无回归（全量 400+ passed）
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净
* 提交 commit，消息：`feat(risk-notice-card): add public read api and token reset`，只含上述文件

### 范围与限制

* 只填充公开路由、追加 token 重置端点、创建测试。
* 不修改 service/schemas（如 build_card_data 已满足需求）。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）。
* 任务 1-8 已完成（最新 HEAD：4558d7b）。
* 公开路由已在 main.py 注册（prefix /api/v1）；占位 router 已有。
* 设计规格：`docs/superpowers/specs/2026-08-11-risk-notice-card-design.md` §9（公开端点与 token 重置）与 §13（token 无效 404）。
