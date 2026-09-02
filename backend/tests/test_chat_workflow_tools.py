"""test_chat_workflow_tools.py — 阶段3 任务6：工作流/偏好聊天工具注册与实现（mock 验证）。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import (
    _FUNCTIONS,
    _get_preferences,
    _get_workflow_progress,
    _run_workflow,
    _set_preferences,
)


def test_workflow_tools_registered_in_dispatch():
    for name in ("run_workflow", "get_workflow_progress",
                 "get_preferences", "set_preferences"):
        assert name in _FUNCTIONS


@pytest.mark.asyncio
async def test_run_workflow_calls_start_workflow():
    """_run_workflow 必须调 WorkflowRunner.start_workflow（后台执行）。"""
    db = AsyncMock()
    user = MagicMock(id="u1")
    captured = {}

    class FakeRunner:
        def __init__(self, db):
            self.received_db = db

        async def start_workflow(self, user, workflow_name, params=None, background=True):
            run = MagicMock(id="wf-1", status="running", current_step=None)
            captured["called"] = (user.id, workflow_name, params, background)
            return run

    with patch("app.services.chat_dispatch.WorkflowRunner", FakeRunner):
        out = await _run_workflow(db, user, {
            "workflow_name": "create_enterprise_plan",
            "params": {"name": "测试公司"},
        })

    assert out["run_id"] == "wf-1"
    assert out["status"] == "running"
    assert out["verified"] is True
    assert captured["called"] == (
        "u1", "create_enterprise_plan", {"name": "测试公司"}, True)


@pytest.mark.asyncio
async def test_run_workflow_requires_workflow_name():
    out = await _run_workflow(AsyncMock(), MagicMock(id="u1"), {})
    assert out == {"error": "请提供 workflow_name", "verified": False}


@pytest.mark.asyncio
async def test_get_workflow_progress_returns_run_and_steps():
    db = AsyncMock()
    run = MagicMock(id="wf-1", workflow_name="create_enterprise_plan",
                    status="paused", current_step="generate_plan")
    step_done = MagicMock(step_name="create_enterprise", status="completed", error=None)
    step_wait = MagicMock(step_name="generate_plan", status="pending", error=None)

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    steps_result = MagicMock()
    steps_result.scalars.return_value.all.return_value = [step_done, step_wait]
    db.execute = AsyncMock(side_effect=[run_result, steps_result])

    out = await _get_workflow_progress(db, MagicMock(id="u1"), {"run_id": "wf-1"})
    assert out["run_id"] == "wf-1"
    assert out["status"] == "paused"
    assert out["current_step"] == "generate_plan"
    assert [s["step_name"] for s in out["steps"]] == ["create_enterprise", "generate_plan"]
    assert out["steps"][1]["status"] == "pending"
    assert out["verified"] is True


@pytest.mark.asyncio
async def test_get_workflow_progress_rejects_unowned_run():
    db = AsyncMock()
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=run_result)

    out = await _get_workflow_progress(db, MagicMock(id="u1"), {"run_id": "wf-x"})
    assert out == {"error": "工作流不存在或无权访问", "verified": False}


@pytest.mark.asyncio
async def test_get_workflow_progress_requires_run_id():
    out = await _get_workflow_progress(AsyncMock(), MagicMock(id="u1"), {})
    assert out == {"error": "请提供 run_id", "verified": False}


@pytest.mark.asyncio
async def test_get_preferences_returns_service_values():
    db = AsyncMock()
    user = MagicMock(id="u1")
    prefs = {"style_preference": "practical", "detail_level": None,
             "report_topics": None, "common_enterprise_ids": None, "extra": None}
    with patch("app.services.chat_dispatch.get_preferences",
               new=AsyncMock(return_value=prefs)) as svc:
        out = await _get_preferences(db, user, {})

    svc.assert_awaited_once_with(db, "u1")
    assert out["preferences"]["style_preference"] == "practical"
    assert out["verified"] is True


@pytest.mark.asyncio
async def test_set_preferences_calls_service_and_commits():
    db = AsyncMock()
    updated = {"style_preference": "practical", "detail_level": None,
               "report_topics": None, "common_enterprise_ids": None, "extra": None}
    with patch("app.services.chat_dispatch.set_preferences",
               new=AsyncMock(return_value=updated)) as svc:
        out = await _set_preferences(db, MagicMock(id="u1"),
                                     {"key": "style_preference", "value": "practical"})

    svc.assert_awaited_once_with(db, "u1", {"style_preference": "practical"})
    db.commit.assert_awaited_once()
    assert out["verified"] is True
    assert out["preferences"]["style_preference"] == "practical"


@pytest.mark.asyncio
async def test_set_preferences_parses_json_array_for_list_keys():
    db = AsyncMock()
    with patch("app.services.chat_dispatch.set_preferences",
               new=AsyncMock(return_value={})) as svc:
        out = await _set_preferences(db, MagicMock(id="u1"), {
            "key": "report_topics",
            "value": '["风险分布", "资源覆盖"]',
        })
    svc.assert_awaited_once_with(db, "u1", {"report_topics": ["风险分布", "资源覆盖"]})
    assert out["verified"] is True


@pytest.mark.asyncio
async def test_set_preferences_rejects_unknown_key():
    out = await _set_preferences(AsyncMock(), MagicMock(id="u1"),
                                 {"key": "hacker_key", "value": "x"})
    assert "未知偏好键" in out["error"]
