"""test_chat_context_rebuild.py — 从 DB 历史重建 OpenAI 消息（含工具调用）。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.routers.chat import _load_history_rows, _rebuild_messages_from_rows


def _row(role, content, name=None):
    row = MagicMock()
    row.role = role
    row.content = content
    row.name = name
    return row


def test_rebuild_plain_text():
    rows = [_row("user", "你好"), _row("assistant", "你好！")]
    msgs = _rebuild_messages_from_rows(rows, "再见")
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"] == "再见"


def test_rebuild_with_tool_trace():
    rows = [
        _row("user", "列出企业"),
        _row("assistant", "共 3 家"),
        _row("assistant", ""),
        _row("tool", '{"enterprises":[]}', name="list_enterprises"),
        _row("user", "第一个企业"),
    ]
    msgs = _rebuild_messages_from_rows(rows, "继续")
    tool_assistant = [m for m in msgs if m.get("role") == "assistant" and "tool_calls" in m]
    assert len(tool_assistant) == 1
    assert tool_assistant[0]["tool_calls"][0]["function"]["name"] == "list_enterprises"
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    assert tool_msgs[0]["tool_call_id"].startswith("call_")
    assert tool_msgs[0]["content"] == '{"enterprises":[]}'


def test_rebuild_empty_assistant_without_tool_skipped():
    rows = [_row("assistant", ""), _row("user", "x")]
    msgs = _rebuild_messages_from_rows(rows, "y")
    assert [m["role"] for m in msgs if m["role"] != "system"] == ["user", "user"]


def test_rebuild_uses_real_tool_call_args():
    """B20：历史重建时从 chat_tool_calls.fn_args 补全 arguments，不再退化为 "{}"。"""
    rows = [
        _row("user", "列出企业"),
        _row("assistant", ""),
        _row("tool", '{"enterprises":[]}', name="list_enterprises"),
        _row("user", "继续"),
    ]
    tool_rows = [MagicMock(fn_name="list_enterprises", fn_args={"keyword": "化工"})]
    msgs = _rebuild_messages_from_rows(rows, "再查", tool_rows=tool_rows)
    tool_assistant = [m for m in msgs if m.get("role") == "assistant" and "tool_calls" in m][0]
    assert tool_assistant["tool_calls"][0]["function"]["arguments"] == '{"keyword": "化工"}'


@pytest.mark.asyncio
async def test_load_history_rows_includes_tool_call_records():
    """B20：_load_history_rows 同时查询 chat_tool_calls 映射供 arguments 补全。"""
    db = AsyncMock()
    msg_result = MagicMock()
    msg_result.scalars.return_value.all.return_value = [_row("user", "hi")]
    tool_result = MagicMock()
    tool_result.scalars.return_value.all.return_value = [
        MagicMock(fn_name="get_dashboard", fn_args={"q": 1}),
    ]
    db.execute.side_effect = [msg_result, tool_result]
    rows, tool_rows = await _load_history_rows(db, "c1")
    assert len(rows) == 1
    assert len(tool_rows) == 1
    assert tool_rows[0].fn_name == "get_dashboard"
