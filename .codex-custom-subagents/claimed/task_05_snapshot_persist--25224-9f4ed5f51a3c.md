# Codex Custom Subagents task handoff v1

Task: task_05_snapshot_persist

## 实现任务 5：快照端点透传 signs（含人工微调）

### 任务描述（来自实现计划 2026-08-15-ai-sign-review.md 任务 5）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\schemas\risk_notice_card.py`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\services\risk_notice_card_service.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\tests\test_risk_notice_card_api.py`（+ service 测试）

### 步骤 1：编写失败测试

在 `backend/tests/test_risk_notice_card_api.py` 追加：

```python
def test_snapshot_save_with_signs(client):
    resp = client.put("/enterprises/e1/risk-notice-cards/o1/snapshot", json={
        "content": {
            "hazard_description": "x", "accident_types": ["火灾"],
            "control_measures": [], "emergency_measures": [],
            "signs": [{"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"}],
            "signs_source": "manual",
        }
    })
    assert resp.status_code == 200
    # save_snapshot 收到 content 含规范化 signs（经 mock 断言或探针）
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py::test_snapshot_save_with_signs -v`
预期：FAIL（RightColumn 校验拒绝 signs 键 → 422）

### 步骤 2：实现

1. `schemas/risk_notice_card.py`：`RightColumn` 增加可选字段 `signs: list[SignItem] = []` 与 `signs_source: Literal["rule", "ai", "manual"] | None = None`（signs_source 用 `Literal` 或宽松 str，保存时 service 校验）。注意：`CardData(RightColumn)` 已含 signs，字段冲突？——`CardData` 自身已有 `signs: list[SignItem] = []`，若 RightColumn 也加会继承覆盖，需处理（CardData 重新声明即可，或 RightColumn 只加 signs_source；signs 由 CardData 声明）。实现时注意不破坏 CardData 结构。
2. `risk_notice_card_service.py` 的 `save_snapshot`：保存前若 `content.get("signs")` 为 list → `content["signs"] = normalize_signs(content["signs"])`；`signs_source` 不在 ("rule","ai","manual") → 回退 "rule"。
3. 保持现有右栏保存行为不变（无 signs 时 content 原样）。

### 步骤 3：运行测试验证通过

`cd backend && python -m pytest tests/test_risk_notice_card_api.py tests/test_risk_notice_card_service.py -v` 预期 PASS

### 步骤 4：Commit

```bash
git add backend/app/schemas/risk_notice_card.py backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_api.py
git commit -m "feat(risk-notice-card): persist signs in snapshot with normalization"
```

### 范围与限制

* 只改 schemas、service、测试。
* 不修改路由/AI 服务/前端。
* 提交前确认 `git status` 只含上述文件。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review，HEAD=06191b3）。
* normalize_signs 已就绪（任务 2）；snapshot_content/snapshot_signs helper 已就绪（任务 4 修复）。
* 设计规格：`docs/superpowers/specs/2026-08-15-ai-sign-review-design.md` §7.2（快照端点扩展）。
