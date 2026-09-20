"""D-3：消费 plan_sections.data_dependencies，标记「依赖数据已变更、正文未更新」。

覆盖：打点 upsert、域名映射、按依赖域判断待更新、章节列表接口返回 stale_domains、
以及删除端点必须打点（删除不更新任何行的时间戳）。修复前应失败。
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models.enterprise import PlanProject, PlanSection
from app.models.user import User
from app.services.data_marks import (
    DOMAIN_ORG,
    DOMAIN_RESOURCES,
    DOMAIN_RISK,
    TRACKED_DOMAINS,
    mark_data_changed,
    stale_domains_for_sections,
)


class _Rows:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows if rows is not None else []

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        m = MagicMock()
        m.all.return_value = self._rows
        return m

    def all(self):
        return self._rows


NOW = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)


def _sec(key, deps, content="正文", updated_at=NOW):
    s = PlanSection(
        id=f"s-{key}", plan_project_id="p1", section_key=key, title=key,
        content=content, level=1, sort_order=0, data_dependencies=deps,
        ai_generated=False,
    )
    s.updated_at = updated_at
    return s


# ---------- 打点 ----------

def test_mark_rejects_unknown_domain():
    db = AsyncMock()
    try:
        asyncio.run(mark_data_changed(db, "e1", "not-a-domain"))
    except ValueError as exc:
        assert "未知数据域" in str(exc)
    else:
        raise AssertionError("未知域应报错，避免打点写进无人消费的域")


def test_mark_upserts_row():
    db = AsyncMock()
    asyncio.run(mark_data_changed(db, "e1", DOMAIN_RISK))
    stmt = str(db.execute.await_args.args[0])
    assert "enterprise_data_marks" in stmt
    assert "ON CONFLICT" in stmt.upper()


def test_tracked_domains_match_dependency_vocabulary():
    # 与真实 plan_sections.data_dependencies 取值保持一致
    assert set(TRACKED_DOMAINS) == {DOMAIN_RISK, DOMAIN_RESOURCES, DOMAIN_ORG}


# ---------- 待更新判定 ----------

def test_stale_when_dependency_changed_after_section():
    db = AsyncMock()
    # marks: 风险域在章节更新之后变更过
    db.execute.side_effect = [
        _Rows(rows=[(DOMAIN_RISK, NOW + timedelta(hours=1))]),   # load_marks
        _Rows(scalar=NOW - timedelta(days=1)),                    # 表时间戳（更早）
    ]
    sections = [_sec("sec_3", [DOMAIN_RISK])]

    out = asyncio.run(stale_domains_for_sections(db, "e1", sections))

    assert out == {"sec_3": [DOMAIN_RISK]}


def test_not_stale_when_section_newer_than_data():
    db = AsyncMock()
    db.execute.side_effect = [
        _Rows(rows=[]),
        _Rows(scalar=NOW - timedelta(hours=2)),
    ]
    sections = [_sec("sec_3", [DOMAIN_RESOURCES])]

    assert asyncio.run(stale_domains_for_sections(db, "e1", sections)) == {}


def test_empty_section_and_unknown_domain_ignored():
    db = AsyncMock()
    sections = [
        _sec("sec_1", [DOMAIN_RISK], content="   "),      # 空正文：不算待更新
        _sec("sec_2", ["some_future_domain"]),             # 未跟踪域：不查库
    ]
    assert asyncio.run(stale_domains_for_sections(db, "e1", sections)) == {}
    db.execute.assert_not_called()


def test_section_without_dependencies_never_stale():
    db = AsyncMock()
    db.execute.side_effect = [
        _Rows(rows=[]),
        _Rows(scalar=NOW + timedelta(days=1)),
    ]
    sections = [_sec("sec_1", []), _sec("sec_2", [DOMAIN_RISK])]
    out = asyncio.run(stale_domains_for_sections(db, "e1", sections))
    assert "sec_1" not in out


# ---------- 章节列表接口 ----------

def _sections_db(sections):
    db = AsyncMock()
    plan = PlanProject(id="p1", user_id="u1", enterprise_id="e1",
                       plan_type="综合应急预案", title="预案", status="draft")

    def fake_execute(stmt, *a, **kw):
        t = str(stmt)
        if "FROM plan_projects" in t:
            return _Rows(scalar=plan)
        if "FROM plan_sections" in t:
            return _Rows(rows=sections)
        if "enterprise_data_marks" in t:
            return _Rows(rows=[(DOMAIN_ORG, NOW + timedelta(hours=3))])
        if "greatest" in t:
            return _Rows(scalar=NOW - timedelta(days=3))
        return _Rows(scalar=None, rows=[])

    db.execute.side_effect = fake_execute
    return db


def test_list_sections_returns_stale_domains():
    sections = [_sec("sec_2", [DOMAIN_ORG]), _sec("sec_3", [DOMAIN_RISK])]
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="u@t.com", role="user", password_hash="x"
    )
    app.dependency_overrides[get_db] = lambda: _sections_db(sections)
    try:
        resp = asyncio.run(_get("/api/v1/plans/p1/sections"))
        assert resp.status_code == 200, resp.text
        by_key = {s["section_key"]: s["stale_domains"] for s in resp.json()["data"]}
        assert by_key["sec_2"] == [DOMAIN_ORG], "应急组织变更后，依赖它的章节应标记待更新"
        assert by_key["sec_3"] == [], "表时间戳早于章节更新时间 → 不算待更新"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


# ---------- 删除端点必须打点 ----------

def test_delete_risk_event_marks_data_changed():
    db = AsyncMock()
    ent = MagicMock()
    event = MagicMock()

    def fake_execute(stmt, *a, **kw):
        t = str(stmt)
        if "FROM enterprises" in t:
            return _Rows(scalar=ent)
        if "FROM risk_events" in t:
            return _Rows(scalar=event)
        return _Rows(scalar=None, rows=[])

    db.execute.side_effect = fake_execute
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="u@t.com", role="user", password_hash="x"
    )
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = asyncio.run(_delete("/api/v1/enterprises/e1/risk-management/events/ev1"))
        assert resp.status_code == 200, resp.text
        executed = [str(c.args[0]) for c in db.execute.await_args_list if c.args]
        assert any("enterprise_data_marks" in s for s in executed), (
            "删除风险事件必须打点：删除不会更新任何父行时间戳，否则章节不会提示待更新"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


async def _get(path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


async def _delete(path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.delete(path)
