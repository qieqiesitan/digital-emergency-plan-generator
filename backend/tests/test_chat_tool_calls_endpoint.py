"""test_chat_tool_calls_endpoint.py — 工具轨迹回放端点。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.routers.chat import list_tool_calls


@pytest.mark.asyncio
async def test_list_tool_calls_requires_own_conv():
    db = AsyncMock()
    result = MagicMock()  # AsyncSession.execute 返回的 Result 的 scalar_one_or_none 是同步方法
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    with pytest.raises(Exception):
        await list_tool_calls("c1", MagicMock(id="u1"), db)


@pytest.mark.asyncio
async def test_list_tool_calls_returns_rows():
    db = AsyncMock()
    conv = MagicMock(id="c1", user_id="u1")
    row = MagicMock(id="t1", round_no=1, fn_name="list_enterprises",
                    status="success", duration_ms=120, created_at=None)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.side_effect = [conv, None]
    exec_result.scalars.return_value.all.return_value = [row]
    db.execute.return_value = exec_result
    out = await list_tool_calls("c1", MagicMock(id="u1"), db)
    assert out[0]["fn_name"] == "list_enterprises"
    assert out[0]["status"] == "success"
