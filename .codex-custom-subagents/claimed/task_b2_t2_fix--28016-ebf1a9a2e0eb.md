# Codex Custom Subagents task handoff v1

Task: task_b2_t2_fix

## 任务：修复 _build_plan 未带出编号字段（规格审查 FAIL）

你是一个实现子智能体。规格审查发现 `backend\app\routers\plans.py::_build_plan` 未将 `plan_number`/`version_number` 传入 `PlanResponse`，导致接口恒返回 None。请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

当前 HEAD 应为 `61c3faa`。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement\backend
.\.venv\Scripts\python.exe -m pytest tests\test_plan_number.py -v
```

### 步骤 1：追加失败的测试

在 `backend\tests\test_plan_number.py` 末尾追加：

```python
def test_build_plan_response_includes_numbers():
    from unittest.mock import MagicMock
    from app.routers.plans import _build_plan
    p = MagicMock()
    p.id = "p1"
    p.enterprise_id = "e1"
    p.style_preference = None
    p.advanced_prompt_overrides = None
    p.plan_type = "comprehensive"
    p.title = "测试预案"
    p.accident_type = None
    p.status = "draft"
    p.current_version = 1
    p.plan_number = "陕西宝岳-ZH-001"
    p.version_number = "A-2026-08"
    p.created_at = None
    p.updated_at = None
    p.sections = []
    resp = _build_plan(p, "陕西宝岳")
    assert resp.plan_number == "陕西宝岳-ZH-001"
    assert resp.version_number == "A-2026-08"
```

### 步骤 2：运行测试验证失败

运行 pytest 命令。
预期：新增测试 FAIL（`resp.plan_number` 为 None）。

### 步骤 3：实现修复

修改 `backend\app\routers\plans.py::_build_plan`（约 13-30 行），在 `PlanResponse(...)` 构造中追加：

```python
        plan_number=p.plan_number,
        version_number=p.version_number,
```

### 步骤 4：运行测试验证通过

运行 pytest 命令。
预期：PASS（5 passed）。

### 步骤 5：Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement
git add backend/app/routers/plans.py backend/tests/test_plan_number.py
git commit -m "fix(plan): expose plan_number/version_number in plan response (batch2)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. pytest 最终输出（几 passed）
3. commit SHA（`git rev-parse --short HEAD`）
4. 如有疑虑，说明具体内容

不要提交其他文件；不要推送；不要动 TASKS.md。
