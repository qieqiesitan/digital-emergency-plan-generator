# Codex Custom Subagents task handoff v1

Task: task_d2_t3_fix

## 任务：修复疏散图 resources key 不匹配

你是一个实现子智能体。规格审查发现 `backend\app\routers\generation.py::_attach_diagrams` 读取 `ent_data.get("resources", [])`，但 `_collect_enterprise_data` 返回的应急资源 key 是 `emergency_resources`，导致疏散图的消防设施标记永远为空。请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

当前 HEAD 应为 `6b8d66f`。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令（必须挂 2_chroma_cache 卷）

```powershell
docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_diagram_service.py -v
```

### 步骤 1：追加失败测试

在 `backend\tests\test_plan_diagram_service.py` 末尾追加：

```python
def test_attach_diagrams_passes_resources_to_evacuation():
    from unittest.mock import MagicMock
    from app.routers.generation import _attach_diagrams
    s = MagicMock()
    s.section_key = "sec_3_3"
    s.diagram_svgs = None
    ent_data = {
        "emergency_resources": [{"category": "消防", "name": "灭火器", "location": "东墙"}],
        "zones": [],
        "risk_objects": [{"name": "储罐", "location_x": 50, "location_y": 50}],
    }
    _attach_diagrams(s, "onsite", ent_data)
    svg = s.diagram_svgs.get("evacuation", {}).get("svg", "")
    assert "灭火器" in svg
```

### 步骤 2：运行测试验证失败

运行 pytest 命令。
预期：新增测试 FAIL（`"灭火器" not in svg`，当前 resources 为空）

### 步骤 3：实现修复

`_attach_diagrams` 中 evacuation 分支改为：

```python
        section.diagram_svgs["evacuation"] = build_evacuation_svg(
            floor_plan_url=ent_data.get("floor_plan_url"),
            zones=ent_data.get("zones", []),
            objects=ent_data.get("risk_objects", []),
            resources=ent_data.get("emergency_resources", ent_data.get("resources", [])),
        )
```

（兼容 `emergency_resources` 主 key，`resources` 兜底。）

### 步骤 4：运行测试验证通过

运行 pytest 命令。
预期：PASS（14 passed）

### 步骤 5：全量回归

```powershell
docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py
```

预期：全部通过

### 步骤 6：Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams
git add backend/app/routers/generation.py backend/tests/test_plan_diagram_service.py
git commit -m "fix(plan): pass emergency_resources to evacuation diagram (diagrams batch2)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. pytest 最终输出与全量回归结果
3. commit SHA
4. 如有疑虑，说明具体内容

不要提交其他文件；不要推送；不要动 TASKS.md。
