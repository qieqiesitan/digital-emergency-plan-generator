"""test_chat_save_trace.py — 保存完整对话轮次（含工具轨迹）。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.routers.chat import _save_messages


@pytest.mark.asyncio
async def test_save_messages_with_tool_trace():
    db = AsyncMock()
    db.get.return_value = AsyncMock(title="新对话")
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    with patch("app.routers.chat.async_session", return_value=ctx):
        await _save_messages(
            "u1", "c1", "列出企业",
            "共 3 家企业",
            tool_trace=[{"round_no": 1, "fn_name": "list_enterprises",
                         "result": '{"enterprises":[]}'}],
        )
    added = [c.args[0] for c in db.add.call_args_list]
    roles = [getattr(m, "role", None) for m in added]
    assert roles == ["user", "assistant", "assistant", "tool"]
    assert getattr(added[2], "content") == ""
    assert getattr(added[3], "name") == "list_enterprises"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_messages_without_trace_keeps_legacy_shape():
    db = AsyncMock()
    db.get.return_value = AsyncMock(title="新对话")
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    with patch("app.routers.chat.async_session", return_value=ctx):
        await _save_messages("u1", "c1", "hi", "hello", tool_trace=None)
    added = [c.args[0] for c in db.add.call_args_list]
    assert [getattr(m, "role") for m in added] == ["user", "assistant"]
