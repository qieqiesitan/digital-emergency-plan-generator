"""test_plan_review_routes.py — 审查路由。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.review import get_plan_review


@pytest.mark.asyncio
async def test_get_plan_review_requires_ownership():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    with pytest.raises(Exception):
        await get_plan_review("p1", MagicMock(id="u1"), db)


@pytest.mark.asyncio
async def test_get_plan_review_returns_issues():
    db = AsyncMock()
    plan = MagicMock(id="p1", user_id="u1", plan_type="comprehensive")
    ent = MagicMock()
    sec = MagicMock(section_key="sec_1", title="总则", content="")
    result = MagicMock()
    result.scalar_one_or_none.side_effect = [plan, ent]
    result.scalars.return_value.all.return_value = [sec]
    db.execute.return_value = result
    with patch("app.routers.review.review_plan",
               return_value={"issues": [{"section_key": "sec_1", "issue": "章节内容为空"}],
                             "warnings": []}):
        out = await get_plan_review("p1", MagicMock(id="u1"), db)
    assert out["issues"][0]["section_key"] == "sec_1"
