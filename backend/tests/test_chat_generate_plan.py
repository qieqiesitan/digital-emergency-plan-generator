"""test_chat_generate_plan.py — 聊天触发后台生成。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _generate_plan_content, _get_generation_progress
from app.services import plan_generation_service
from app.services.plan_generation_service import _run_background, get_failed_sections


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
    failed = [{"section_key": "sec_1", "title": "总则"}]
    with patch("app.services.chat_dispatch.get_failed_sections", return_value=failed):
        out = await _get_generation_progress(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert out["status"] == "completed"
    assert out["failed_sections"] == failed


@pytest.mark.asyncio
async def test_generation_progress_shows_failed_sections():
    """B4：聊天问进度必须能看到后台生成失败章节（不再恒为空）。"""
    db = AsyncMock()
    p = MagicMock(id="p1", title="综合预案", status="draft", user_id="u1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = p
    db.execute.return_value = result
    failed = [{"section_key": "sec_2", "title": "应急组织"}, {"section_key": "sec_3", "title": "保障措施"}]
    with patch("app.services.chat_dispatch.get_failed_sections", return_value=failed):
        out = await _get_generation_progress(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert out["failed_sections"] == failed


def test_get_failed_sections_returns_recorded():
    plan_generation_service._failed_sections["p1"] = [{"section_key": "sec_1", "title": "总则"}]
    try:
        assert get_failed_sections("p1") == [{"section_key": "sec_1", "title": "总则"}]
        assert get_failed_sections("unknown_plan") == []
    finally:
        plan_generation_service._failed_sections.pop("p1", None)


@pytest.mark.asyncio
async def test_run_background_records_failed_sections():
    """B4：_run_background 完成后把失败章节写入 service 模块级 _failed_sections。"""
    bg_db = AsyncMock()
    bg_db.__aenter__ = AsyncMock(return_value=bg_db)
    bg_db.__aexit__ = AsyncMock(return_value=False)
    failed = [{"section_key": "sec_2", "title": "应急组织"}]
    with patch("app.services.plan_generation_service.async_session", return_value=bg_db), \
         patch("app.services.plan_generation_service.run_batch_generation",
               new=AsyncMock(return_value={"completed": 1, "failed": 1,
                                           "failed_sections": failed})), \
         patch("app.services.plan_generation_service.finalize_batch_result", new=AsyncMock()):
        await _run_background("p1", "comprehensive", "火灾", None, None,
                              [("sec_1", "总则"), ("sec_2", "应急组织")], None, {})
    try:
        assert plan_generation_service._failed_sections.get("p1") == failed
    finally:
        plan_generation_service._failed_sections.pop("p1", None)
