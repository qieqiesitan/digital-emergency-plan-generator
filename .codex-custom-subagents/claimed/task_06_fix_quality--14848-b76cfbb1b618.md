# Codex Custom Subagents task handoff v1

Task: task_06_fix_quality

## 目标

按任务 6 代码质量审查的 3 条建议修改修复，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`98a0c0a`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**1. 组装点提辅助函数（`backend/app/routers/risk_management.py`）**

在 `risk_mapping_service` 已有 `max_risk_level`/`effective_color` 基础上，路由内提取小辅助（放在 `_to_workbench_zone` 附近）：

```python
def _zone_dual_levels(zone):
    """返回 (max_level, effective_color, inherent_max_level, inherent_effective_color)。"""
    current = max_risk_level(zone)
    inherent = max_risk_level(zone, "inherent")
    return (current, effective_color(zone.floor_plan_polygon, current),
            inherent, effective_color(zone.floor_plan_polygon, inherent))
```

让 `_to_workbench_zone`、`list_zones`、`get_hierarchy` 三处统一调用（行为不变）。

**2. list_zones 消除逐分区 COUNT N+1（`backend/app/routers/risk_management.py`）**

已 selectinload `z.objects`，`cascade_counts` 或等效 count 查询若与 `len(z.objects)` 等价则改用后者；若 `cascade_counts` 还含 unit/event 计数（非仅 object），则保持现状并说明（不要为消除 N+1 引入新语义偏差）。以「行为等价 + 无回归」为准。

**3. 测试补断言（`backend/tests/test_risk_dual_level.py`）**

```python
def test_max_risk_level_defaults_to_current():
    from app.models.risk_management import RiskZone, RiskObject, RiskEvent
    zone = RiskZone(id="z3", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o3", enterprise_id="e1", zone_id="z3", name="1#储罐")
    obj.events = [RiskEvent(accident_type="火灾", risk_level="一般", inherent_risk_level="重大")]
    zone.objects = [obj]
    assert max_risk_level(zone) == "一般"  # 默认 current 向后兼容

def test_max_risk_level_aggregates_object_and_unit():
    from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent
    zone = RiskZone(id="z4", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o4", enterprise_id="e1", zone_id="z4", name="1#储罐")
    obj.events = [RiskEvent(accident_type="火灾", risk_level="一般", inherent_risk_level="重大")]
    unit = RiskUnit(id="u4", object_id="o4", name="阀门组")
    unit.events = [RiskEvent(accident_type="泄漏", risk_level="较大", inherent_risk_level="重大")]
    obj.units = [unit]
    zone.objects = [obj]
    assert max_risk_level(zone, "current") == "较大"   # 对象 一般 + 单元 较大 → 较大
    assert max_risk_level(zone, "inherent") == "重大"
```

## 验证

- 在 `backend` 目录 `python -m pytest tests/test_risk_dual_level.py tests/test_risk_mapping_workbench.py -v`，预期全部 PASS（25 个）；`python -m pytest tests/ -q` 无回归；
- `git diff --check` 干净。

## Commit

在 `.worktrees\dual-prevention` 内：

```bash
git add backend/app/routers/risk_management.py backend/tests/test_risk_dual_level.py
git commit -m "refactor(risk): dedupe zone dual-level assembly and cover aggregation tests"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_06_fix_quality --claim-id <claim_id> --exit-code 0 --summary "任务6质量建议修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明。

## 规则

- 用 `apply_patch` 编辑；只改列出的 2 个文件；阻塞时停下汇报。
