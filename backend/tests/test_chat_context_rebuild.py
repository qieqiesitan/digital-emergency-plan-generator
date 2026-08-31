"""test_chat_context_rebuild.py — 从 DB 历史重建 OpenAI 消息（含工具调用）。"""
import pytest
from unittest.mock import MagicMock

from app.routers.chat import _rebuild_messages_from_rows


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
