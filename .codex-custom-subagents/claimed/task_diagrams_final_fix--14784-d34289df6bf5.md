# Codex Custom Subagents task handoff v1

Task: task_diagrams_final_fix

## 任务：修复最终审查发现的阻断级 bug 与测试环境污染

你是一个实现子智能体。最终审查发现 2 个问题，请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

当前 HEAD 应为 `e8649f9`。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令（必须挂 2_chroma_cache 卷）

```powershell
docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_diagram_service.py tests/test_plan_diagrams_api.py tests/test_risk_mapping_workbench.py -v
```

### 问题 1（阻断级）：RiskEvent 无 name 字段

`backend\app\services\risk_context_builder.py` 约 136 行使用了 `event.name`，但 `RiskEvent` 模型没有 `name` 字段（只有 `accident_type`/`description`），运行时 AttributeError。

修复：将 `risk_events` 展平项中的 name 改为组合描述，保证非空：

```python
        "risk_events": [
            {
                "name": event.accident_type or (event.description or "")[:20] or "未命名风险",
                "likelihood": event.method_params.get("l", 3) if event.method_params else 3,
                "severity": event.method_params.get("s", 3) if event.method_params else 3,
                "risk_level": event.risk_level or "",
            }
            for zone in zones
            for obj in zone.objects
            for event in list(obj.events) + [e for u in obj.units for e in u.events]
        ],
```

同时确认该文件其它 event 引用（如 `_risk_source_item` 内 `event.accident_type` 等）都是模型真实字段。

追加测试：`backend\tests\test_plan_diagram_service.py` 中验证 risk_context_builder 返回的 risk_events 无 AttributeError（用一个最小 zones/objects/units/events mock 树调用 `build_risk_management_context` 或直接构造 event mock 断言取值逻辑）——实现者按实际可测方式处理，确保 `event.name` 不再被引用。

### 问题 2（测试环境污染）：test_clear_generation_state 污染全局状态

`backend\tests\test_generation_batch_refactor.py::test_clear_generation_state_resets_active_flag` 修改模块级 `gen._active_generations`/`gen._failed_sections` 后未清理，可能影响同进程其他测试。

修复：测试改用 monkeypatch 或 finally 清理：

```python
def test_clear_generation_state_resets_active_flag(monkeypatch):
    import app.routers.generation as gen
    gen._active_generations["p1"] = True
    gen._failed_sections["p1"] = [{"section_key": "sec_1", "title": "总则"}]
    try:
        gen._clear_generation_state("p1")
        assert gen._active_generations.get("p1", False) is False
        assert gen._failed_sections.get("p1") == [{"section_key": "sec_1", "title": "总则"}]
    finally:
        gen._active_generations.pop("p1", None)
        gen._failed_sections.pop("p1", None)
```

### 完成标准

1. 两个问题修复
2. 相关测试通过
3. 全量回归：`docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py` 全部通过

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams
git add backend/app/services/risk_context_builder.py backend/tests/test_plan_diagram_service.py backend/tests/test_generation_batch_refactor.py
git commit -m "fix(plan): use accident_type for risk event name, clean global state in tests (diagrams final)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. 两个问题修复方式
3. pytest 结果
4. commit SHA

不要提交其他文件；不要推送；不要动 TASKS.md。
