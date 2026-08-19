# Codex Custom Subagents task handoff v1

Task: task_06_dual_mode

## 目标

实现「风险分级管控增强（A 阶段）」任务 6：`max_risk_level(zone, mode)` 双模式 + 分区/层级响应双等级字段（inherent_max_level/inherent_effective_color），按 TDD 完成并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`c05d820`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 背景

任务 3 已给 RiskEvent 加 inherent_risk_level；本任务让 `max_risk_level` 支持 `mode="inherent"|"current"`，并在 Zone/Hierarchy 响应中带双等级与双颜色（现有 `max_risk_level`/`effective_color` 语义 = current，保持兼容）。测试约定：纯函数测试（构造内存对象，无需 DB）、async 需 `@pytest.mark.asyncio`。

## 文件

- 修改：`backend/app/services/risk_mapping_service.py`
- 修改：`backend/app/schemas/risk_management.py`（RiskZoneResponse / HierarchyZoneResponse）
- 修改：`backend/app/routers/risk_management.py`（zone/hierarchy 组装处）
- 测试：`backend/tests/test_risk_dual_level.py`（追加）

## 步骤（TDD）

- [ ] **步骤 1：追加失败测试**（`backend/tests/test_risk_dual_level.py` 末尾）

```python
def test_max_risk_level_by_mode():
    from app.models.risk_management import RiskZone, RiskObject, RiskEvent
    zone = RiskZone(id="z1", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o1", enterprise_id="e1", zone_id="z1", name="1#储罐")
    obj.events = [RiskEvent(accident_type="火灾", risk_level="一般", inherent_risk_level="重大")]
    zone.objects = [obj]
    assert max_risk_level(zone, "current") == "一般"
    assert max_risk_level(zone, "inherent") == "重大"
```

（`max_risk_level` 从 `app.services.risk_mapping_service` 导入；文件顶部 import 已有则复用。）

- [ ] **步骤 2：运行测试验证失败**

在 `backend` 目录 `python -m pytest tests/test_risk_dual_level.py::test_max_risk_level_by_mode -v`
预期：FAIL（max_risk_level 无 mode 参数）

- [ ] **步骤 3：改造 `max_risk_level`**（`backend/app/services/risk_mapping_service.py`）

```python
def max_risk_level(zone: RiskZone, mode: str = "current") -> str:
    level = "未评估"
    for obj in zone.objects:
        for ev in obj.events:
            value = ev.inherent_risk_level if mode == "inherent" else ev.risk_level
            if value and LEVEL_ORDER.get(value, 0) > LEVEL_ORDER.get(level, 0):
                level = value
        for unit in obj.units:
            for ev in unit.events:
                value = ev.inherent_risk_level if mode == "inherent" else ev.risk_level
                if value and LEVEL_ORDER.get(value, 0) > LEVEL_ORDER.get(level, 0):
                    level = value
    return level
```

`backend/app/schemas/risk_management.py`：`RiskZoneResponse` 与 `HierarchyZoneResponse` 增加 `inherent_max_level: str | None = None`、`inherent_effective_color: str | None = None`。

`backend/app/routers/risk_management.py`：在 zone/hierarchy 组装处（计算 `max_risk_level`/`effective_color` 的地方，含 list_zones/hierarchy/overview 等）同步计算并填充 `inherent_max_level = max_risk_level(z, "inherent")`、`inherent_effective_color = effective_color(z.floor_plan_polygon, inherent_max_level)`。

- [ ] **步骤 4：运行测试验证通过**

在 `backend` 目录 `python -m pytest tests/test_risk_dual_level.py -v`，预期全部 PASS；`python -m pytest tests/ -q` 无回归。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_mapping_service.py backend/app/schemas/risk_management.py backend/app/routers/risk_management.py backend/tests/test_risk_dual_level.py
git commit -m "feat(risk): support inherent/current mode in zone risk level and colors"
```

在 `.worktrees\dual-prevention` 内执行；不要提交 TASKS.md；消息精确匹配；`git diff --check` 干净。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_06_dual_mode --claim-id <claim_id> --exit-code 0 --summary "四色图双模式后端完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、自审结论。

## 规则

- 严格 TDD；用 `apply_patch` 编辑；只改列出的 4 个文件；阻塞时停下汇报。
