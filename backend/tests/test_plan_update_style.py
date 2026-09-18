"""P1 回归：PUT /plans/{id} 必须落库 style_preference / advanced_prompt_overrides。

背景（2026-09-18 诊断发现）：前端「创作风格」与「高级模式提示词覆盖」保存都走
``PUT /plans/{id}``，但后端只应用了 ``title``，用户选择被静默丢弃——重新打开创作
风格弹窗会回到默认值。本测试锁定修复：三个字段都应写回模型。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.enterprise import Enterprise, PlanProject


def _setup():
    user = User(id="u1", email="u@t.com", role="user", password_hash="x")
    app.dependency_overrides[get_current_user] = lambda: user

    db = AsyncMock()
    plan = MagicMock(spec=PlanProject)
    plan.id = "p1"
    plan.user_id = "u1"
    plan.enterprise_id = "e1"
    plan.title = "旧标题"
    plan.plan_type = "comprehensive"
    plan.accident_type = None
    plan.status = "draft"
    plan.current_version = 1
    plan.style_preference = None
    plan.advanced_prompt_overrides = None
    plan.plan_number = None
    plan.version_number = None
    plan.created_at = None
    plan.updated_at = None
    plan.sections = []

    ent = MagicMock(spec=Enterprise)
    ent.id = "e1"
    ent.name = "测试企业"

    def fake_execute(stmt, *params, **kwargs):
        r = MagicMock()
        text = str(stmt)
        if "FROM plan_projects" in text:
            r.scalar_one_or_none.return_value = plan
        elif "FROM enterprises" in text:
            # 更新接口只查企业名字（select(Enterprise.name)）
            r.scalar_one_or_none.return_value = ent.name
        else:
            r.scalar_one_or_none.return_value = None
            r.scalars.return_value.all.return_value = []
        return r

    db.execute.side_effect = fake_execute
    app.dependency_overrides[get_db] = lambda: db
    return plan


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def _put(payload: dict):
    async def run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.put("/api/v1/plans/p1", json=payload)

    return asyncio.run(run())


def test_update_plan_persists_style_and_advanced_overrides():
    plan = _setup()
    try:
        resp = _put({
            "title": "新标题",
            "style_preference": {"formality": "practical", "mode": "advanced"},
            "advanced_prompt_overrides": {
                "system_prompt_override": "你是预案专家",
                "section_overrides": {"overview": "写详细些"},
            },
        })
    finally:
        _teardown()

    assert resp.status_code == 200, resp.text
    assert plan.title == "新标题"
    assert plan.style_preference == {"formality": "practical", "mode": "advanced"}
    assert plan.advanced_prompt_overrides["section_overrides"] == {"overview": "写详细些"}


def test_update_plan_tolerates_missing_style_fields():
    """只传 title 时不应把已有风格清空。"""
    plan = _setup()
    plan.style_preference = {"formality": "formal"}
    try:
        resp = _put({"title": "只改标题"})
    finally:
        _teardown()

    assert resp.status_code == 200, resp.text
    assert plan.title == "只改标题"
    assert plan.style_preference == {"formality": "formal"}
