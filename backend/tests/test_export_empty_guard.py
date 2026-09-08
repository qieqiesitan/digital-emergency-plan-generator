"""P3：空预案导出 DOCX 拦截回归（QA 报告 §3.4）。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.enterprise import Enterprise
from app.models.enterprise import PlanProject, PlanSection


def _setup(empty_sections: bool = True):
    user = User(id="u1", email="u@t.com", role="user", password_hash="x")
    app.dependency_overrides[get_current_user] = lambda: user

    db = AsyncMock()
    plan = MagicMock(spec=PlanProject)
    plan.id = "p1"
    plan.enterprise_id = "e1"
    plan.user_id = "u1"
    ent = MagicMock(spec=Enterprise)
    ent.id = "e1"

    def fake_execute(stmt, *params, **kwargs):
        text = str(stmt)
        if "FROM plan_projects" in text:
            r = MagicMock()
            r.scalar_one_or_none.return_value = plan
            return r
        if "FROM enterprises" in text:
            r = MagicMock()
            r.scalar_one_or_none.return_value = ent
            return r
        if "FROM plan_sections" in text:
            sec = MagicMock(spec=PlanSection)
            sec.content = "   " if empty_sections else "有效内容"
            r = MagicMock()
            r.scalars.return_value.all.return_value = [sec]
            return r
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        r.scalars.return_value.all.return_value = []
        return r

    db.execute.side_effect = fake_execute
    app.dependency_overrides[get_db] = lambda: db


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_export_docx_blocked_when_all_sections_empty():
    _setup(empty_sections=True)
    try:
        resp = asyncio.run(_post())
        assert resp.status_code == 400
        assert "无法导出" in resp.text
    finally:
        _teardown()


async def _post():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post("/api/v1/plans/p1/export/docx")
