"""test_chat_generate_plan.py — 聊天触发后台生成。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _generate_plan_content, _get_generation_progress


@pytest.mark.asyncio
async def test_generate_plan_content_starts_background():
    db = AsyncMock()
    p = MagicMock(id="p1", title="综合预案", status="draft", user_id="u1",
                  sections=[MagicMock(section_key="sec_1", content="")])
    result = MagicMock()
    result.scalar_one_or_none.return_value = p
    db.execute.return_value = result
    with patch("app.services.chat_dispatch.start_batch_generation",
               new=AsyncMock(return_value={"started": True, "empty": 1, "total": 8,
                                            "message": "已开始后台生成"})):
        out = await _generate_plan_content(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert out["verified"] is True
    assert "后台生成" in out["message"]


@pytest.mark.asyncio
async def test_generate_plan_content_missing_plan():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    out = await _generate_plan_content(db, MagicMock(id="u1"), {"plan_id": "nope"})
    assert "error" in out


@pytest.mark.asyncio
async def test_generation_progress_ownership():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    out = await _get_generation_progress(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert "error" in out


@pytest.mark.asyncio
async def test_generation_progress_completed():
    db = AsyncMock()
    p = MagicMock(id="p1", title="综合预案", status="completed", user_id="u1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = p
    db.execute.return_value = result
    with patch("app.services.chat_dispatch._failed_sections", {"p1": []}):
        out = await _get_generation_progress(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert out["status"] == "completed"
