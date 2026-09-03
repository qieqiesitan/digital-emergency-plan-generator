"""test_plan_review_routes.py — 审查路由。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
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
    assert out.data["issues"][0]["section_key"] == "sec_1"


@pytest.mark.asyncio
async def test_apply_review_rules_fixes_placeholder():
    from app.routers.review import apply_plan_review
    db = AsyncMock()
    plan = MagicMock(id="p1", user_id="u1", plan_type="comprehensive",
                     current_version=1, style_preference=None,
                     advanced_prompt_overrides=None)
    sec = MagicMock(section_key="sec_1", title="总则", content="<p>（待补充）</p>")
    result = MagicMock()
    result.scalar_one_or_none.side_effect = [plan, None]
    result.scalars.return_value.all.return_value = [sec]
    db.execute.return_value = result
    db.add = MagicMock()
    with patch("app.routers.review.review_plan", return_value={
        "issues": [{"section_key": "sec_1", "section_title": "总则",
                    "issue": "存在待补充占位符"}],
        "warnings": []}), \
         patch("app.routers.review._apply_llm_revision",
               new=AsyncMock(return_value="<p>修订后内容</p>")):
        out = await apply_plan_review("p1", MagicMock(id="u1"), db, mode="llm")
    assert out.data["applied"] == ["sec_1"]
    assert sec.content == "<p>修订后内容</p>"
    db.commit.assert_awaited()


def _apply_setup(sections):
    """构造 apply_plan_review 的 mock db/plan 环境。"""
    db = AsyncMock()
    plan = MagicMock(id="p1", user_id="u1", plan_type="comprehensive",
                     current_version=1, style_preference=None,
                     advanced_prompt_overrides=None)
    result = MagicMock()
    result.scalar_one_or_none.side_effect = [plan, None]
    result.scalars.return_value.all.return_value = sections
    db.execute.return_value = result
    db.add = MagicMock()
    return db, plan


_VALID_REVISION = "<p>这是一段超过三十个字符的完整修订内容，满足校验要求，可正常写入。</p>"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_content", [
    "   ",
    "短内容",
    "AI调用失败，请检查模型配置后重试",
    "<p>内容被截断",
])
async def test_apply_review_llm_skips_invalid_revision(bad_content):
    from app.routers.review import apply_plan_review
    sec_bad = MagicMock(section_key="sec_1", title="总则", content="<p>原内容</p>")
    sec_ok = MagicMock(section_key="sec_2", title="应急组织", content="<p>组织架构</p>")
    db, plan = _apply_setup([sec_bad, sec_ok])
    with patch("app.routers.review.review_plan", return_value={
            "issues": [
                {"section_key": "sec_1", "section_title": "总则", "issue": "章节质量不足"},
                {"section_key": "sec_2", "section_title": "应急组织", "issue": "章节质量不足"},
            ],
            "warnings": []}), \
         patch("app.services.ai_config_service.get_system_ai_config",
               new=AsyncMock(return_value=MagicMock())), \
         patch("app.routers.generation._stream_llm",
               new=AsyncMock(side_effect=[bad_content, _VALID_REVISION])):
        out = await apply_plan_review("p1", MagicMock(id="u1"), db, mode="llm")
    assert out.data["applied"] == ["sec_2"]
    assert [s["section_key"] for s in out.data["skipped"]] == ["sec_1"]
    assert out.data["skipped"][0]["reason"]
    assert sec_bad.content == "<p>原内容</p>"          # 校验失败不写库
    assert sec_ok.content == _VALID_REVISION
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_apply_review_llm_all_invalid_returns_400():
    from app.routers.review import apply_plan_review
    sec = MagicMock(section_key="sec_1", title="总则", content="<p>原内容</p>")
    db, plan = _apply_setup([sec])
    with patch("app.routers.review.review_plan", return_value={
            "issues": [{"section_key": "sec_1", "section_title": "总则",
                        "issue": "章节质量不足"}],
            "warnings": []}), \
         patch("app.services.ai_config_service.get_system_ai_config",
               new=AsyncMock(return_value=MagicMock())), \
         patch("app.routers.generation._stream_llm",
               new=AsyncMock(return_value="AI调用失败")):
        with pytest.raises(HTTPException) as exc:
            await apply_plan_review("p1", MagicMock(id="u1"), db, mode="llm")
    assert exc.value.status_code == 400
    assert sec.content == "<p>原内容</p>"
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_apply_review_llm_valid_revision_applies():
    from app.routers.review import apply_plan_review
    sec = MagicMock(section_key="sec_1", title="总则", content="<p>原内容</p>")
    db, plan = _apply_setup([sec])
    with patch("app.routers.review.review_plan", return_value={
            "issues": [{"section_key": "sec_1", "section_title": "总则",
                        "issue": "章节质量不足"}],
            "warnings": []}), \
         patch("app.services.ai_config_service.get_system_ai_config",
               new=AsyncMock(return_value=MagicMock())), \
         patch("app.routers.generation._stream_llm",
               new=AsyncMock(return_value=_VALID_REVISION)):
        out = await apply_plan_review("p1", MagicMock(id="u1"), db, mode="llm")
    assert out.data["applied"] == ["sec_1"]
    assert out.data["skipped"] == []
    assert sec.content == _VALID_REVISION
    db.commit.assert_awaited()
