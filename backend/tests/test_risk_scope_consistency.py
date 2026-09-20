"""D-1：风险统计口径统一到新五层（依据 docs/superpowers/specs/2026-08-06-only-risk-management-design.md
「统计口径 = 新「风险事件数」替代旧「风险源数」」的既有决策）。

三处断点（文档 4.2 已点名）：dashboard 统计、enterprises 企业详情/列表、导出质检 has_risk。
修复前本文件应当失败。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models.enterprise import EmergencyResource, Enterprise, PlanProject, PlanSection
from app.models.user import User
from app.services.risk_stats_service import enterprise_has_risk


def _user():
    return User(id="u1", email="u@t.com", role="user", password_hash="x")


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


class _Rows:
    """最小结果替身：同时支持 scalar / scalar_one_or_none / scalars().all()。"""

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


# ---------- 1. enterprise_has_risk：新五层与旧表取「或」 ----------

def test_has_risk_true_when_only_new_events():
    db = AsyncMock()
    db.execute.side_effect = [_Rows(scalar=2), _Rows(scalar=0)]
    assert asyncio.run(enterprise_has_risk(db, "e1")) is True


def test_has_risk_true_when_only_legacy_rows():
    db = AsyncMock()
    db.execute.side_effect = [_Rows(scalar=0), _Rows(scalar=7)]
    assert asyncio.run(enterprise_has_risk(db, "e1")) is True


def test_has_risk_false_when_neither():
    db = AsyncMock()
    db.execute.side_effect = [_Rows(scalar=0), _Rows(scalar=0)]
    assert asyncio.run(enterprise_has_risk(db, "e1")) is False


# ---------- 2. dashboard：risk_source_count 走新口径 ----------

def _dashboard_db():
    db = AsyncMock()

    def fake_execute(stmt, *a, **kw):
        t = str(stmt)
        if "FROM risk_events" in t:
            return _Rows(scalar=3)          # 新五层真实事件数
        if "FROM risk_sources" in t:
            return _Rows(scalar=99)         # 旧表残留 99 行（不应再被统计）
        if "count(" in t and "FROM plan_projects" in t:
            return _Rows(scalar=5)
        if "count(" in t and "FROM enterprises" in t:
            return _Rows(scalar=1)
        if "FROM plan_projects" in t:
            return _Rows(rows=[])
        if "FROM enterprises" in t:
            return _Rows(rows=[])
        return _Rows(scalar=0, rows=[])

    db.execute.side_effect = fake_execute
    return db


def test_dashboard_risk_counts_use_new_model():
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = _dashboard_db
    try:
        resp = asyncio.run(_get("/api/v1/dashboard"))
        assert resp.status_code == 200
        stats = resp.json()["data"]["stats"]
        assert stats["risk_event_count"] == 3
        assert stats["risk_source_count"] == 3, "risk_source_count 应改用新五层口径（设计文档决策）"
    finally:
        _teardown()


# ---------- 3. 企业详情：risk_sources_count 走新口径 ----------

def _enterprise_db(legacy_rows: int, new_events: int):
    db = AsyncMock()
    # 真 ORM 实例：未指定字段为 None，Pydantic 校验才能通过
    ent = Enterprise(id="e1", user_id="u1", name="测试企业")
    ent.risk_sources = []

    def fake_execute(stmt, *a, **kw):
        t = str(stmt)
        if "FROM enterprises" in t:
            return _Rows(scalar=ent)
        if "FROM risk_events" in t:
            return _Rows(scalar=new_events)
        return _Rows(scalar=0, rows=[])

    db.execute.side_effect = fake_execute
    return db


def test_enterprise_detail_counts_use_new_model():
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: _enterprise_db(legacy_rows=12, new_events=34)
    try:
        resp = asyncio.run(_get("/api/v1/enterprises/e1"))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["risk_events_count"] == 34
        assert data["risk_sources_count"] == 34, "risk_sources_count 应改用新五层口径"
    finally:
        _teardown()


# ---------- 4. 导出质检：has_risk 覆盖新五层（否则 E3 告警静默不触发） ----------

def _export_db(resources_quantity_zero: bool = True):
    db = AsyncMock()
    plan = PlanProject(
        id="p1", enterprise_id="e1", user_id="u1", plan_type="综合应急预案",
        title="测试预案", plan_number="X-1", version_number="1.0", status="draft",
    )
    ent = Enterprise(id="e1", user_id="u1", name="测试企业")
    ent.risk_sources = []          # 旧表为空：只有新五层数据的企业
    sec = PlanSection(
        plan_project_id="p1", section_key="sec_1", title="总则",
        content="有效正文内容", level=1, sort_order=0,
    )
    res = EmergencyResource(
        enterprise_id="e1", category="消防设施", name="干粉灭火器",
        quantity=0 if resources_quantity_zero else 10,
    )

    def fake_execute(stmt, *a, **kw):
        t = str(stmt)
        if "FROM plan_projects" in t:
            return _Rows(scalar=plan)
        if "FROM enterprises" in t:
            return _Rows(scalar=ent)
        if "FROM plan_sections" in t:
            return _Rows(rows=[sec])
        if "FROM emergency_resources" in t:
            return _Rows(rows=[res])
        if "FROM risk_events" in t:
            return _Rows(scalar=1)     # 新五层有 1 条风险事件
        if "FROM risk_sources" in t:
            return _Rows(scalar=0)     # 旧表为空
        return _Rows(scalar=None, rows=[])

    db.execute.side_effect = fake_execute
    return db


def test_export_validate_has_risk_uses_new_model():
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: _export_db(resources_quantity_zero=True)
    try:
        resp = asyncio.run(_post("/api/v1/plans/p1/export/validate"))
        assert resp.status_code == 200
        warnings = [w["warning"] for w in resp.json()["data"]["warnings"]]
        assert any("应急资源数量均为 0" in w for w in warnings), (
            "只有新五层风险数据时，E3「资源数量为 0」告警也必须触发：" + str(warnings)
        )
    finally:
        _teardown()


def test_export_validate_no_zero_warning_when_quantity_positive():
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: _export_db(resources_quantity_zero=False)
    try:
        resp = asyncio.run(_post("/api/v1/plans/p1/export/validate"))
        warnings = [w["warning"] for w in resp.json()["data"]["warnings"]]
        assert not any("应急资源数量均为 0" in w for w in warnings)
    finally:
        _teardown()


async def _get(path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


async def _post(path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(path)
