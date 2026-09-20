"""D-4：厂区平面图是企业字段与「默认楼层」的双存镜像，必须双向同步。

反向（楼层 → 企业）在 risk_management.py 有多处同步；本文件覆盖缺失的正向
（企业档案改动 → 默认楼层），修复前应失败。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models.enterprise import Enterprise, EnterpriseFloor
from app.models.user import User
from app.services.floor_plan_storage_service import sync_default_floor_plan


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


def test_sync_updates_default_floor():
    db = AsyncMock()
    ent = Enterprise(id="e1", user_id="u1", name="企业")
    floor = EnterpriseFloor(enterprise_id="e1", name="默认总图", is_default=True,
                            floor_plan_url="/uploads/old.png")
    db.execute.side_effect = lambda stmt, *a, **kw: _Rows(scalar=floor)

    changed = asyncio.run(sync_default_floor_plan(db, ent, "/uploads/new.png"))

    assert changed is True
    assert floor.floor_plan_url == "/uploads/new.png"


def test_sync_noop_when_same_url():
    db = AsyncMock()
    ent = Enterprise(id="e1", user_id="u1", name="企业")
    floor = EnterpriseFloor(enterprise_id="e1", name="默认总图", is_default=True,
                            floor_plan_url="/uploads/same.png")
    db.execute.side_effect = lambda stmt, *a, **kw: _Rows(scalar=floor)

    assert asyncio.run(sync_default_floor_plan(db, ent, "/uploads/same.png")) is False
    assert floor.floor_plan_url == "/uploads/same.png"


def test_sync_noop_without_default_floor():
    db = AsyncMock()
    ent = Enterprise(id="e1", user_id="u1", name="企业")
    db.execute.side_effect = lambda stmt, *a, **kw: _Rows(scalar=None)

    assert asyncio.run(sync_default_floor_plan(db, ent, "/uploads/new.png")) is False


def _put_db():
    db = AsyncMock()
    ent = Enterprise(id="e1", user_id="u1", name="测试企业",
                     floor_plan_url="/uploads/old.png")
    floor = EnterpriseFloor(enterprise_id="e1", name="默认总图", is_default=True,
                            floor_plan_url="/uploads/old.png")

    def fake_execute(stmt, *a, **kw):
        t = str(stmt)
        if "FROM enterprise_floors" in t:
            return _Rows(scalar=floor)
        if "FROM enterprises" in t:
            return _Rows(scalar=ent)
        if "FROM risk_events" in t:
            return _Rows(scalar=0)
        return _Rows(scalar=None, rows=[])

    db.execute.side_effect = fake_execute
    return db, ent, floor


def test_update_enterprise_syncs_default_floor():
    db, ent, floor = _put_db()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="u@t.com", role="user", password_hash="x"
    )
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = asyncio.run(_put("/api/v1/enterprises/e1",
                                {"floor_plan_url": "/uploads/enterprises/e1/floors/f1/new.png"}))
        assert resp.status_code == 200, resp.text
        assert ent.floor_plan_url == "/uploads/enterprises/e1/floors/f1/new.png"
        assert floor.floor_plan_url == "/uploads/enterprises/e1/floors/f1/new.png", (
            "企业档案改图后，默认楼层必须同步，否则四色图工作台/报告仍用旧图"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


async def _put(path: str, body: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.put(path, json=body)
