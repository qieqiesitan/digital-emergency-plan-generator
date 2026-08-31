"""test_chat_parallel_tools.py — 读工具并行、写工具串行。"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chat import _execute_pending_tools, READ_TOOL_NAMES


def _tc(fn_name, tc_id="t1"):
    return {"id": tc_id, "function": {"name": fn_name, "arguments": "{}"}}


@pytest.mark.asyncio
async def test_read_tools_run_in_parallel():
    events = []

    async def fake_isolated(fn_name, fn_args, user_id):
        events.append(("start", fn_name))
        await asyncio.sleep(0.05)
        events.append(("end", fn_name))
        return '{"ok": true}'

    db = AsyncMock()
    with patch("app.routers.chat._run_tool_isolated", new=fake_isolated):
        out = await _execute_pending_tools(
            [_tc("list_enterprises", "t1"), _tc("get_dashboard", "t2")],
            db, MagicMock(id="u1"), 1, "c1")
    starts = [e for e in events if e[0] == "start"]
    ends = [e for e in events if e[0] == "end"]
    assert len(starts) == 2 and len(ends) == 2
    # 并行：第二个 start 出现在第一个 end 之前
    assert events.index(("start", "get_dashboard")) < events.index(("end", "list_enterprises"))
    assert len(out) == 2
    assert out[0][0]["id"] == "t1"               # 结果按原始顺序
    assert out[1][0]["id"] == "t2"


@pytest.mark.asyncio
async def test_write_tools_run_serial():
    calls = []

    async def fake_dispatch(db, user, fn_name, fn_args):
        calls.append(("start", fn_name))
        await asyncio.sleep(0.03)
        calls.append(("end", fn_name))
        return '{"ok": true}'

    db = AsyncMock()
    with patch("app.routers.chat.dispatch", new=fake_dispatch):
        await _execute_pending_tools(
            [_tc("create_enterprise", "t1"), _tc("update_enterprise", "t2")],
            db, MagicMock(id="u1"), 1, "c1")
    assert calls[0] == ("start", "create_enterprise")
    assert calls[1] == ("end", "create_enterprise")
    assert calls[2] == ("start", "update_enterprise")
    assert calls[3] == ("end", "update_enterprise")


def test_read_tool_names_include_reads_only():
    assert "list_enterprises" in READ_TOOL_NAMES
    assert "get_dashboard" in READ_TOOL_NAMES
    assert "create_enterprise" not in READ_TOOL_NAMES
    assert "delete_plan" not in READ_TOOL_NAMES
