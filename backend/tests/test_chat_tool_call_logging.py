"""test_chat_tool_call_logging.py — 工具执行记录写入。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chat import _record_tool_call


@pytest.mark.asyncio
async def test_record_tool_call_success():
    db = AsyncMock()
    db.add = MagicMock()  # AsyncSession.add 是同步方法（计划实现本身未 await），断言用 assert_called_once
    await _record_tool_call(db, "c1", 1, "list_enterprises", {"keyword": "a"},
                            '{"enterprises":[]}', "success", 120)
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    rec = db.add.call_args.args[0]
    assert rec.conversation_id == "c1"
    assert rec.round_no == 1
    assert rec.fn_name == "list_enterprises"
    assert rec.status == "success"
    assert rec.duration_ms == 120


@pytest.mark.asyncio
async def test_record_tool_call_error_status():
    db = AsyncMock()
    db.add = MagicMock()
    await _record_tool_call(db, "c1", 2, "delete_plan", {"plan_id": "p1"},
                            '{"error":"预案不存在"}', "error", 50)
    rec = db.add.call_args.args[0]
    assert rec.status == "error"
    assert rec.result.startswith('{"error"')
