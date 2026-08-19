# Codex Custom Subagents task handoff v1

Task: task_01_snapshot_signs

## 实现任务 1：快照 content 扩展 + build_card_data 支持 signs

### 任务描述（来自实现计划 2026-08-15-ai-sign-review.md 任务 1）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\services\risk_notice_card_service.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\tests\test_risk_notice_card_service.py`

### 步骤 1：编写失败测试

在 `backend/tests/test_risk_notice_card_service.py` 追加：

```python
def test_build_card_data_prefers_snapshot_signs():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from app.models.risk_management import RiskObject, RiskEvent
    from app.models.enterprise import Enterprise
    from app.services.risk_notice_card_service import build_card_data

    async def run():
        snap = MagicMock()
        snap.content = {
            "hazard_description": "x", "accident_types": ["火灾"],
            "control_measures": [], "emergency_measures": [],
            "signs": [{"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"}],
            "signs_source": "ai",
        }
        snap.version = 1
        snap.source = "ai"
        snap.updated_at = None
        db = AsyncMock()
        db.execute.return_value = MagicMock()
        db.execute.return_value.scalars.return_value.first.return_value = snap
        ent = Enterprise(name="测试公司", safety_officer="李四", safety_officer_phone="13900000000")
        obj = RiskObject(id="o1", name="会议室", category="工作场所")
        events = [RiskEvent(id="e1", accident_type="火灾", risk_level="较大",
                            trigger_conditions="线路老化", consequences="火灾",
                            method_type="LS", method_params={"l": 3, "s": 3})]
        card = await build_card_data(db, ent, obj, [obj], events, [])
        assert card.signs[0].svg_name == "warning-fire"
        assert card.signs[0].name == "当心火灾"

    asyncio.run(run())
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py::test_build_card_data_prefers_snapshot_signs -v`
预期：FAIL（build_card_data 忽略快照 signs）

### 步骤 2：实现

在 `backend/app/services/risk_notice_card_service.py` 的 `build_card_data` 中：从快照 content 读取 `signs`，有则用快照标志（dict 列表，CardData 校验时自动转 SignItem），无则用 `match_signs(col.accident_types)`。

关键逻辑：

```python
snapshot_signs = None
if snapshot and isinstance(snapshot.content, dict) and snapshot.content.get("signs"):
    snapshot_signs = snapshot.content["signs"]
...
signs = snapshot_signs if snapshot_signs is not None else match_signs(col.accident_types)
```

注意：保持无快照/无 signs 时行为不变（仍用规则 match_signs）；不要破坏现有测试。

### 步骤 3：运行测试验证通过

`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v` 预期 PASS（新增 + 既有全部）

### 步骤 4：Commit

```bash
git add backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_service.py
git commit -m "feat(risk-notice-card): support snapshot signs in card data"
```

### 范围与限制

* 只改 service 与测试文件。
* 不修改 schemas/路由/前端。
* 提交前确认 worktree 内 `git status` 只含上述 2 个文件（TASKS.md 除外）。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review，HEAD=e105d83）。
* 设计规格：`docs/superpowers/specs/2026-08-15-ai-sign-review-design.md` §6（快照 content 扩展 signs/signs_source）。
* 后续任务 2-5 会在此基础上扩展（normalize_signs/端点/快照透传），本任务只做第一步。
