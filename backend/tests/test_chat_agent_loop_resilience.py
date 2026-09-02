"""test_chat_agent_loop_resilience.py — B8：agent_loop 工具执行异常兜底。

工具结果解析（json.loads）/result_obj.get 等任一异常时，生成器不得崩溃：
必须继续 yield error + conv_id + done，并把已收集的工具轨迹保存入库。
"""
import asyncio
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chat import chat
from app.schemas.chat import ChatRequest


def _sse_events(raw: str):
    return [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]


@pytest.mark.asyncio
async def test_agent_loop_yields_error_done_and_saves_on_tool_parse_failure():
    user = MagicMock(id="u1")
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []  # 无历史消息
    body = ChatRequest(conversation_id="c1", message="查询一下")

    first_llm = {"choices": [{"message": {"tool_calls": [
        {"id": "t1", "type": "function",
         "function": {"name": "get_dashboard", "arguments": "{}"}},
        {"id": "t2", "type": "function",
         "function": {"name": "list_enterprises", "arguments": "{}"}},
    ]}}]}

    # 第 1 条工具正常（进入 trace），第 2 条结果非法 JSON → json.loads 抛异常
    tool_results = [
        ({"id": "t1", "function": {"name": "get_dashboard", "arguments": "{}"}},
         '{"ok": true}'),
        ({"id": "t2", "function": {"name": "list_enterprises", "arguments": "{}"}},
         "not-json"),
    ]

    with patch("app.services.ai_config_service.get_system_ai_config",
               return_value=MagicMock()), \
         patch("app.routers.chat._call_llm", return_value=first_llm), \
         patch("app.routers.chat._execute_pending_tools", return_value=tool_results), \
         patch("app.routers.chat._save_messages", new=AsyncMock()) as save_mock:
        resp = await chat(body, user, db)
        raw = "".join([chunk async for chunk in resp.body_iterator])

    events = _sse_events(raw)
    types = [e["type"] for e in events]
    assert "error" in types, "异常时必须有 error 事件"
    assert "conv_id" in types
    assert "done" in types, "异常时必须有 done 事件（生成器不能静默崩溃）"

    # 已收集轨迹（第 1 条成功工具）随最终消息保存
    await asyncio.sleep(0)
    assert save_mock.await_count == 1, "异常兜底路径必须 _save_messages"
    _args, kwargs = save_mock.call_args
    assert kwargs.get("tool_trace") and len(kwargs["tool_trace"]) == 1
    assert kwargs["tool_trace"][0]["fn_name"] == "get_dashboard"


@pytest.mark.asyncio
async def test_agent_loop_error_keeps_conversation_and_message_text():
    user = MagicMock(id="u1")
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []
    body = ChatRequest(conversation_id="c1", message="执行工具")

    first_llm = {"choices": [{"message": {"tool_calls": [
        {"id": "t1", "type": "function",
         "function": {"name": "get_dashboard", "arguments": "{}"}},
    ]}}]}

    with patch("app.services.ai_config_service.get_system_ai_config",
               return_value=MagicMock()), \
         patch("app.routers.chat._call_llm", return_value=first_llm), \
         patch("app.routers.chat._execute_pending_tools",
               side_effect=RuntimeError("工具执行器崩溃")), \
         patch("app.routers.chat._save_messages", new=AsyncMock()) as save_mock:
        resp = await chat(body, user, db)
        raw = "".join([chunk async for chunk in resp.body_iterator])

    events = _sse_events(raw)
    types = [e["type"] for e in events]
    assert types[-1] == "done"
    error_event = events[types.index("error")]
    assert "工具执行器崩溃" in error_event["message"]

    await asyncio.sleep(0)
    assert save_mock.await_count == 1
    _args, kwargs = save_mock.call_args
    assert kwargs["tool_trace"] == []  # 无成功工具，轨迹为空但不丢消息
