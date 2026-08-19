# Codex Custom Subagents task handoff v1

Task: task_04_endpoint

## 实现任务 4：schemas + ai-review-signs 端点

### 任务描述（来自实现计划 2026-08-15-ai-sign-review.md 任务 4）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\schemas\risk_notice_card.py`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\routers\risk_notice_card.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\tests\test_risk_notice_card_api.py`

### 步骤 1：编写失败测试

在 `backend/tests/test_risk_notice_card_api.py` 追加：

```python
def test_ai_review_signs_endpoint_returns_suggestion(client, monkeypatch):
    from app.services import risk_notice_card_ai

    async def fake_review(*args, **kwargs):
        return {"remove": [], "add": ["warning-fall"], "reasons": [{"sign_name": "当心滑倒", "reason": "有滑倒风险"}]}

    monkeypatch.setattr(risk_notice_card_ai, "review_signs", fake_review)
    resp = client.post("/api/v1/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["suggestion"]["add"] == ["warning-fall"]
    assert data["original_signs"] is not None
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py::test_ai_review_signs_endpoint_returns_suggestion -v`
预期：FAIL（端点不存在 → 404/405）

### 步骤 2：schemas

在 `backend/app/schemas/risk_notice_card.py` 新增：

```python
class SignSuggestion(BaseModel):
    remove: list[str] = []
    add: list[str] = []
    reasons: list[dict] = []

class AiSignReviewResponse(BaseModel):
    original_signs: list[SignItem] = []
    suggestion: SignSuggestion
```

### 步骤 3：端点实现

在 `backend/app/routers/risk_notice_card.py` 新增 `POST /{object_id}/ai-review-signs`：

* 企业归属（`_get_ent`）+ 风险点归属（id + enterprise_id，无 → 404「风险点不存在」）
* `load_events_and_measures` → `build_right_column` → `match_signs` 或快照 signs 作为当前标志
* 组装候选库（SIGN_GROUPS 全组 + DEFAULT_SIGN_GROUP 去重）
* 组装事件数据（accident_type/trigger_conditions/consequences）
* 调 `review_signs`；`except HTTPException: raise`；其余 `logger.exception` + 502「AI 审查失败，请稍后重试或保留原版」
* 返回 `ApiResponse[AiSignReviewResponse](original_signs, suggestion)`

### 步骤 4：运行测试验证通过

`cd backend && python -m pytest tests/test_risk_notice_card_api.py -v` 预期 PASS

### 步骤 5：Commit

```bash
git add backend/app/schemas/risk_notice_card.py backend/app/routers/risk_notice_card.py backend/tests/test_risk_notice_card_api.py
git commit -m "feat(risk-notice-card): add ai sign review endpoint"
```

### 范围与限制

* 只改 schemas、路由、测试。
* 不修改 service/AI 服务/前端。
* 提交前确认 `git status` 只含上述 3 个文件。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review，HEAD=79f0f96）。
* 设计规格：`docs/superpowers/specs/2026-08-15-ai-sign-review-design.md` §7.1（端点响应结构）与 §10（错误处理）。
* review_signs 服务已就绪（任务 3）；快照 signs 优先读取逻辑已就绪（任务 1）。
