# Codex Custom Subagents task handoff v1

Task: task_06_fix_test

## 目标

按任务 6 规格审查建议，给 `test_max_risk_level_by_mode` 补单元事件分支覆盖，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`f99d4b3`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 文件

- 修改：`backend/tests/test_risk_dual_level.py`

## 步骤

- [ ] **步骤 1：扩展测试**（在 `test_max_risk_level_by_mode` 内或新增用例）

补单元事件分支：对象下有 `RiskUnit`，其 `events` 含 `risk_level`/`inherent_risk_level` 不同值，断言两模式分别取单元事件的最大等级：

```python
def test_max_risk_level_by_mode_unit_branch():
    from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent
    zone = RiskZone(id="z2", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o2", enterprise_id="e1", zone_id="z2", name="1#储罐")
    unit = RiskUnit(id="u1", object_id="o2", name="阀门组")
    unit.events = [RiskEvent(accident_type="泄漏", risk_level="较大", inherent_risk_level="重大")]
    obj.units = [unit]
    zone.objects = [obj]
    assert max_risk_level(zone, "current") == "较大"
    assert max_risk_level(zone, "inherent") == "重大"
```

- [ ] **步骤 2：验证**

在 `backend` 目录 `python -m pytest tests/test_risk_dual_level.py -v`，预期 15 passed；`python -m pytest tests/ -q` 无回归；`git diff --check` 干净。

- [ ] **步骤 3：Commit**

在 `.worktrees\dual-prevention` 内：

```bash
git add backend/tests/test_risk_dual_level.py
git commit -m "test(risk): cover unit-event branch in max_risk_level mode test"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_06_fix_test --claim-id <claim_id> --exit-code 0 --summary "任务6单元分支测试补充完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果。

## 规则

- 用 `apply_patch` 编辑；只改列出的 1 个文件；阻塞时停下汇报。
