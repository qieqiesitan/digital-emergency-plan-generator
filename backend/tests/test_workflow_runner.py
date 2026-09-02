"""test_workflow_runner.py — 状态机/重试/确认门控。"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.workflow.runner import WorkflowRunner
from app.services.workflow.models import WorkflowRun, WorkflowRunStep


@pytest.mark.asyncio
async def test_runner_success_path():
    db = AsyncMock()
    run = MagicMock(id="r1", user_id="u1", workflow_name="create_enterprise_plan",
                    params={"name": "测试公司"}, status="pending", current_step=None)
    runner = WorkflowRunner(db)
    calls = []

    async def fake_step(step, ctx):
        calls.append(step["name"])
        if step["name"] == "create_enterprise":
            return {"id": "e1", "verified": True}
        if step["name"] == "generate_plan":
            return {"plan_id": "p1", "verified": True}
        return {"verified": True}

    runner._execute_step = fake_step
    # 直接驱动模板步骤（不走 DB 持久化细节）验证顺序与门控语义
    template = {"steps": [
        {"name": "create_enterprise"},
        {"name": "generate_plan", "confirm": True},
        {"name": "export_docx"},
    ]}
    # generate_plan/export_docx 为确认门控步：预先确认后走完整成功路径
    await runner._run_steps(run, template, {
        "create_enterprise": {"id": "e1"},
        "confirmed_steps": {"generate_plan": True, "export_docx": True},
    })
    assert calls == ["create_enterprise", "generate_plan", "export_docx"]


@pytest.mark.asyncio
async def test_runner_retry_on_failure():
    db = AsyncMock()
    run = MagicMock(id="r1", workflow_name="x", params={})
    runner = WorkflowRunner(db)
    attempts = {"n": 0}

    async def flaky(step, ctx):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("boom")
        return {"ok": True}

    runner._execute_step = flaky
    template = {"steps": [{"name": "s1"}]}
    out = await runner._run_steps(run, template, {}, max_retries=2)
    assert out["s1"]["ok"] is True
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_runner_confirmation_gate_halts_then_resumes():
    db = AsyncMock()
    run = MagicMock(id="r1", user_id="u1", workflow_name="create_enterprise_plan",
                    params={"name": "测试公司"}, status="running", current_step=None)
    runner = WorkflowRunner(db)
    calls = []

    async def fake_step(step, ctx):
        calls.append(step["name"])
        if step["name"] == "create_enterprise":
            return {"id": "e1", "verified": True}
        return {"verified": True}

    runner._execute_step = fake_step
    template = {"steps": [
        {"name": "create_enterprise"},
        {"name": "generate_plan", "confirm": True},
        {"name": "export_docx"},
    ]}
    ctx = {"params": {"name": "测试公司"}}
    # 未确认：停在 generate_plan，export_docx 不放行
    await runner._run_steps(run, template, ctx)
    assert calls == ["create_enterprise"]
    assert run.status == "paused"
    assert run.current_step == "generate_plan"
    # 确认 generate_plan 后恢复（沿用暂停时的 ctx）：generate_plan 与 export_docx 放行
    ctx["confirmed_steps"] = {"generate_plan": True}
    ctx["_pending_gates"] = {"generate_plan"}
    await runner._run_steps(run, template, ctx)
    assert calls == ["create_enterprise", "generate_plan", "export_docx"]


@pytest.mark.asyncio
async def test_runner_failure_exhausts_retries():
    db = AsyncMock()
    run = MagicMock(id="r1", workflow_name="x", params={})
    runner = WorkflowRunner(db)
    attempts = {"n": 0}

    async def always_fail(step, ctx):
        attempts["n"] += 1
        raise RuntimeError("boom")

    runner._execute_step = always_fail
    template = {"steps": [{"name": "s1"}]}
    with pytest.raises(RuntimeError, match="步骤 s1 失败"):
        await runner._run_steps(run, template, {}, max_retries=1)
    assert attempts["n"] == 2  # 初始尝试 1 + 重试 1


@pytest.mark.asyncio
async def test_start_workflow_creates_run_and_schedules_background(monkeypatch):
    db = AsyncMock()
    user = MagicMock(id="u1")
    runner = WorkflowRunner(db)
    spawned = []

    def capture(coro):
        spawned.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(asyncio, "create_task", capture)
    created = []
    db.add = MagicMock(side_effect=lambda obj: created.append(obj))
    run = await runner.start_workflow(user, "create_enterprise_plan", {"name": "测试公司"})
    assert isinstance(run, WorkflowRun)
    assert run.workflow_name == "create_enterprise_plan"
    assert run.status == "running"
    assert run.user_id == "u1"
    assert run.params == {"name": "测试公司"}
    # 步骤记录全部创建（run 无 id 时仍按模板名称建齐）
    assert len(created) == 6
    step_rows = [o for o in created if isinstance(o, WorkflowRunStep)]
    assert len(step_rows) == 5
    assert {s.step_name for s in step_rows} == {
        "create_enterprise", "create_plan", "generate_plan", "review_plan", "export_docx"}
    assert all(s.run_id == run.id for s in step_rows)
    # 后台执行被调度（mock 验证）
    assert len(spawned) == 1
    assert spawned[0].cr_code is not None


@pytest.mark.asyncio
async def test_confirm_workflow_step_rejects_non_paused_run():
    db = AsyncMock()
    runner = WorkflowRunner(db)
    run = MagicMock(id="r1", status="running", current_step="generate_plan")
    db.execute.return_value.scalar_one_or_none = MagicMock(return_value=run)
    with pytest.raises(ValueError, match="未在等待"):
        await runner.confirm_workflow_step("r1", "generate_plan")


@pytest.mark.asyncio
async def test_confirm_workflow_step_marks_confirmed_and_resumes(monkeypatch):
    db = AsyncMock()
    runner = WorkflowRunner(db)
    run = MagicMock(id="r1", status="paused", current_step="generate_plan")
    step_rec = MagicMock(step_name="generate_plan")
    db.execute.return_value.scalar_one_or_none = MagicMock(side_effect=[run, step_rec])
    spawned = []

    def capture(coro):
        spawned.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(asyncio, "create_task", capture)
    out = await runner.confirm_workflow_step("r1", "generate_plan")
    assert out is run
    assert step_rec.status == "confirmed"
    assert run.status == "running"
    assert len(spawned) == 1
