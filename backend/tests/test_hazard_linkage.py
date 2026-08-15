"""隐患任务 9 测试：未闭环隐患派生计数 + 风险视图联动回写。

覆盖：
- 派生计数函数 `open_hazard_count`：object/measure 维度、未 closed 计数、
  closed 排除、or 语义、双空返回 0；闭环后归零（mock 状态变化后重算）。
- 批量计数 `open_hazard_count_by_objects`：多风险点一次查询避免 N+1、
  按对象分组、measure 经事件归属、空列表返回空 dict。
- 端点字段：workbench / overview / hierarchy / 管控清单 / 告知卡列表与详情
  响应含 open_hazard_count / has_open_hazard 且值正确。

测试风格与 test_risk_control_list.py / test_risk_notice_card_api.py 一致：
无 db fixture，用 FastAPI TestClient + dependency_overrides + SQL 文本分发
mock；async 服务函数用 @pytest.mark.asyncio。
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.data_dict import DataDict
from app.models.enterprise import Enterprise, EnterpriseFloor
from app.models.hazard_management import HazardRecord
from app.models.risk_management import RiskEvent, RiskMeasure, RiskObject, RiskZone
from app.models.user import User
from app.routers import risk_management, risk_notice_card
from app.services.hazard_service import (
    open_hazard_count,
    open_hazard_count_by_objects,
)


# ── mock 工具 ──

def _scalar_result(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _count_result(value):
    res = MagicMock()
    res.scalar.return_value = value
    return res


def _rows_result(rows):
    res = MagicMock()
    res.scalars.return_value.all.return_value = list(rows)
    return res


def _all_result(rows):
    res = MagicMock()
    res.all.return_value = list(rows)
    return res


def _ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _floor(**kw):
    now = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)
    f = EnterpriseFloor(
        id=kw.pop("id", "f1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        name=kw.pop("name", "默认总图"),
        sort_order=kw.pop("sort_order", 0),
        is_default=kw.pop("is_default", True),
        canvas_texts=kw.pop("canvas_texts", []),
        created_at=now,
        updated_at=now,
    )
    for k, v in kw.items():
        setattr(f, k, v)
    return f


def _dict_row(code, label, value):
    return DataDict(dict_type="control_level_map", code=code, label=label,
                    value=value, scope="system", sort_order=1, enabled=True)


def _zone(**kw):
    now = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)
    z = RiskZone(
        id=kw.pop("id", "z1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        floor_id=kw.pop("floor_id", "f1"),
        name=kw.pop("name", "储罐区"),
        description=kw.pop("description", None),
        sort_order=kw.pop("sort_order", 0),
        created_at=now,
        updated_at=now,
    )
    for k, v in kw.items():
        setattr(z, k, v)
    return z


def _obj(**kw):
    now = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)
    o = RiskObject(
        id=kw.pop("id", "o1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        zone_id=kw.pop("zone_id", "z1"),
        floor_id=kw.pop("floor_id", "f1"),
        name=kw.pop("name", "1#储罐"),
        category=kw.pop("category", "危险化学品"),
        location=kw.pop("location", None),
        location_x=kw.pop("location_x", 10.0),
        location_y=kw.pop("location_y", 20.0),
        description=kw.pop("description", None),
        responsible_unit=kw.pop("responsible_unit", None),
        responsible_person=kw.pop("responsible_person", None),
        contact_phone=kw.pop("contact_phone", None),
        is_risk_point=kw.pop("is_risk_point", True),
        sort_order=kw.pop("sort_order", 0),
        public_token=kw.pop("public_token", f"tok-{kw.get('id', 'o1')}"),
        created_at=now,
        updated_at=now,
    )
    o.events = kw.pop("events", [])
    o.units = kw.pop("units", [])
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def _event(**kw):
    ev = RiskEvent(
        id=kw.pop("id", "ev1"),
        object_id=kw.pop("object_id", "o1"),
        accident_type=kw.pop("accident_type", "泄漏"),
        description=kw.pop("description", None),
        method_type=kw.pop("method_type", "LS"),
        method_params=kw.pop("method_params", {"l": 3, "s": 3}),
        risk_level=kw.pop("risk_level", "重大"),
        inherent_risk_level=kw.pop("inherent_risk_level", "重大"),
        control_level=kw.pop("control_level", "企业"),
    )
    ev.measures = kw.pop("measures", [])
    for k, v in kw.items():
        setattr(ev, k, v)
    return ev


def _measure(**kw):
    return RiskMeasure(
        id=kw.pop("id", "m1"),
        event_id=kw.pop("event_id", "ev1"),
        measure_category=kw.pop("measure_category", "工程技术"),
        measure_type=kw.pop("measure_type", None),
        description=kw.pop("description", "报警器年检"),
        responsible_person=kw.pop("responsible_person", None),
        deadline=kw.pop("deadline", None),
        check_items=kw.pop("check_items", []),
        sort_order=kw.pop("sort_order", 0),
    )


def _hazard_record(**kw):
    return HazardRecord(
        id=kw.pop("id", "r1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        code=kw.pop("code", "HD-001"),
        source_type=kw.pop("source_type", "manual"),
        object_id=kw.pop("object_id", "o1"),
        measure_id=kw.pop("measure_id", None),
        title=kw.pop("title", "储罐区泄漏隐患"),
        description=kw.pop("description", "现场存在泄漏"),
        status=kw.pop("status", "rectifying"),
    )


def _hazard_db(
    ent=None,
    *,
    floor=None,
    zones=None,
    risk_points=None,
    dict_rows=None,
    open_counts=None,
    count_value=None,
):
    """按 SQL 文本特征分发（参照 test_risk_control_list.py 的 _db）。

    open_counts：批量计数（GROUP BY）返回 [(object_id, count), ...]；
    count_value：单对象计数（.scalar()）返回值，未给默认 0。
    """
    floor = floor or _floor()
    dict_rows = dict_rows or [
        _dict_row("major", "重大→企业", {"level": "重大", "control_level": "企业"}),
        _dict_row("large", "较大→部门", {"level": "较大", "control_level": "部门"}),
        _dict_row("general", "一般→班组", {"level": "一般", "control_level": "班组"}),
        _dict_row("low", "低→岗位", {"level": "低", "control_level": "岗位"}),
    ]
    db = AsyncMock()
    db.add = MagicMock()

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar_result(ent)
        if "FROM enterprise_floors" in text:
            if "enterprise_floors.id =" in text:
                return _scalar_result(floor)
            return _scalar_result(floor)
        if "FROM data_dicts" in text:
            return _rows_result(dict_rows)
        if "FROM risk_objects" in text:
            if "count(risk_objects.id)" in text:
                return _count_result(len(risk_points or []))
            if "ORDER BY" in text:
                return _rows_result(risk_points or [])
            # 详情归属查询（含 id + enterprise_id 等值条件）→ scalar_one_or_none
            if "risk_objects.id =" in text:
                return _scalar_result(risk_points[0] if risk_points else None)
            # 多风险点列表查询（workbench/overview 的 OR 归属条件）→ scalars().all()
            if "enterprise_id =" in text:
                return _rows_result(risk_points or [])
            return _rows_result(risk_points or [])
        # risk_zones 分支放最后：风险点查询里的 zone_id IN (子查询) 也含
        # "FROM risk_zones"，若提前命中会把风险点查询误判成分区查询
        if "FROM risk_zones" in text:
            if "count(risk_zones.id)" in text:
                return _count_result(len(zones or []))
            return _rows_result(zones or [])
        if "FROM hazard_records" in text:
            if "GROUP BY" in text:
                return _all_result(open_counts or [])
            return _count_result(count_value if count_value is not None else 0)
        if "risk_notice_cards" in text:
            res = MagicMock()
            res.scalars.return_value.first.return_value = None
            return res
        return _rows_result([])

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(risk_management.router)
    app.include_router(risk_notice_card.router)

    def _override_user():
        return User(id="u1", email="a@b.c", name="A", role="admin")

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _hazard_db(_ent())
    with TestClient(app) as test_client:
        yield test_client


# ── 派生计数函数 ──

@pytest.mark.asyncio
async def test_open_hazard_count_both_empty_returns_zero():
    db = _hazard_db()
    assert await open_hazard_count(db) == 0
    assert await open_hazard_count(db, object_id=None, measure_id=None) == 0
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_hazard_count_by_object_counts_non_closed():
    db = _hazard_db(_ent(), count_value=3)
    assert await open_hazard_count(db, object_id="o1") == 3
    assert "FROM hazard_records" in str(db.execute.await_args_list[0].args[0])


@pytest.mark.asyncio
async def test_open_hazard_count_by_measure_counts_non_closed():
    db = _hazard_db(_ent(), count_value=2)
    assert await open_hazard_count(db, measure_id="m1") == 2


@pytest.mark.asyncio
async def test_open_hazard_count_or_semantics_for_both():
    """同时传 object_id 与 measure_id 按 or 计数：mock 返回 4（不计具体拆分）。"""
    db = _hazard_db(_ent(), count_value=4)
    assert await open_hazard_count(db, object_id="o1", measure_id="m1") == 4


@pytest.mark.asyncio
async def test_open_hazard_count_zero_after_closed():
    """闭环后归零语义：mock 状态变化后重新计数返回 0。"""
    db = _hazard_db(_ent(), count_value=0)
    assert await open_hazard_count(db, object_id="o1") == 0


@pytest.mark.asyncio
async def test_open_hazard_count_by_objects_groups_and_or_measure():
    """批量计数：按对象分组；measure 经事件归属同一风险点时计入该对象。"""
    db = _hazard_db(
        _ent(),
        open_counts=[("o1", 2), ("o2", 1)],
    )
    counts = await open_hazard_count_by_objects(db, "e1", ["o1", "o2"])
    assert counts == {"o1": 2, "o2": 1}
    executed = str(db.execute.await_args_list[0].args[0])
    assert "GROUP BY" in executed
    assert "hazard_records.object_id" in executed
    # 关联条件含 measure_id IN (子查询 risk_measures ← risk_events)
    assert "risk_measures.id" in executed


@pytest.mark.asyncio
async def test_open_hazard_count_by_objects_empty_input():
    db = _hazard_db(_ent())
    assert await open_hazard_count_by_objects(db, "e1", []) == {}
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_hazard_count_by_objects_filters_non_closed():
    """批量计数 SQL 必须过滤 status != 'closed'（闭环后归零的查询侧保证）。"""
    db = _hazard_db(_ent(), open_counts=[("o1", 1)])
    await open_hazard_count_by_objects(db, "e1", ["o1"])
    executed = str(db.execute.await_args_list[0].args[0])
    assert "hazard_records.status != :status_1" in executed or "!=" in executed


# ── workbench / overview / hierarchy 端点 ──

def _zone_tree():
    """含两个风险点的分区树：o1 未闭环 2 条、o2 未闭环 0 条。"""
    z = _zone()
    o1 = _obj(id="o1", name="1#储罐", events=[_event(id="ev1", object_id="o1")])
    o2 = _obj(id="o2", name="2#储罐", events=[_event(id="ev2", object_id="o2", risk_level="一般")])
    z.objects = [o1, o2]
    return z, [o1, o2]


def test_workbench_zones_and_risk_points_carry_open_hazard_count(client):
    z, points = _zone_tree()
    db = _hazard_db(
        _ent(),
        zones=[z],
        risk_points=points,
        open_counts=[("o1", 2)],
    )
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/risk-management/workbench", params={"floor_id": "f1"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["zones"][0]["open_hazard_count"] == 2
    by_id = {o["id"]: o for o in data["zones"][0]["objects"]}
    assert by_id["o1"]["open_hazard_count"] == 2
    assert by_id["o2"]["open_hazard_count"] == 0
    points_by_id = {p["id"]: p for p in data["risk_points"]}
    assert points_by_id["o1"]["open_hazard_count"] == 2
    assert points_by_id["o2"]["open_hazard_count"] == 0


def test_workbench_no_open_hazard_defaults_zero(client):
    z, points = _zone_tree()
    db = _hazard_db(_ent(), zones=[z], risk_points=points, open_counts=[])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/risk-management/workbench", params={"floor_id": "f1"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["zones"][0]["open_hazard_count"] == 0
    assert all(o["open_hazard_count"] == 0 for o in data["zones"][0]["objects"])


def test_overview_carries_open_hazard_count(client):
    z, points = _zone_tree()
    db = _hazard_db(
        _ent(),
        zones=[z],
        risk_points=points,
        open_counts=[("o1", 2)],
    )
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/risk-management/overview")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["zones"][0]["open_hazard_count"] == 2
    points_by_id = {p["id"]: p for p in data["risk_points"]}
    assert points_by_id["o1"]["open_hazard_count"] == 2


def test_hierarchy_zone_and_object_carry_open_hazard_count(client):
    z, _points = _zone_tree()
    db = _hazard_db(_ent(), zones=[z], open_counts=[("o1", 2)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/risk-management/hierarchy")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["open_hazard_count"] == 2
    by_id = {o["id"]: o for o in data[0]["objects"]}
    assert by_id["o1"]["open_hazard_count"] == 2
    assert by_id["o2"]["open_hazard_count"] == 0


# ── 管控清单端点 ──

def _zone_with_events():
    z = _zone()
    o1 = _obj(
        id="o1",
        name="1#储罐",
        location="储罐区东侧",
        responsible_unit="生产部",
        responsible_person="李四",
        contact_phone="13800000000",
        events=[
            _event(id="ev1", accident_type="泄漏", measures=[_measure()]),
            _event(id="ev2", accident_type="火灾", risk_level="一般",
                   inherent_risk_level="较大", control_level="部门"),
        ],
    )
    z.objects = [o1]
    return z


def test_control_list_rows_carry_open_hazard_count(client):
    z = _zone_with_events()
    db = _hazard_db(_ent(), zones=[z], open_counts=[("o1", 2)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/risk-management/control-list")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert all(item["open_hazard_count"] == 2 for item in data["items"])
    # 内部筛选键仍被脱敏移除
    assert "zone_id" not in data["items"][0]
    assert "object_id" not in data["items"][0]


# ── 告知卡端点 ──

def _notice_zone_tree():
    z = _zone()
    zone_attr = MagicMock()
    zone_attr.name = "储罐区"
    o1 = _obj(id="o1", name="1#储罐", public_token="tok1")
    o1.zone = zone_attr
    o1.events = [_event(id="ev1", object_id="o1")]
    o2 = _obj(id="o2", name="2#储罐", public_token="tok2")
    o2.zone = zone_attr
    o2.events = [_event(id="ev2", object_id="o2", risk_level="一般")]
    z.objects = [o1, o2]
    return [o1, o2]


def test_notice_card_list_carries_has_open_hazard(client):
    objs = _notice_zone_tree()
    db = _hazard_db(
        _ent(),
        risk_points=objs,
        open_counts=[("o1", 3)],
    )
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/risk-notice-cards")
    assert resp.status_code == 200
    data = resp.json()["data"]
    by_id = {item["object_id"]: item for item in data}
    assert by_id["o1"]["has_open_hazard"] is True
    assert by_id["o2"]["has_open_hazard"] is False


def test_notice_card_detail_carries_has_open_hazard(client):
    obj = _notice_zone_tree()[0]
    db = _hazard_db(_ent(), risk_points=[obj], count_value=2)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/risk-notice-cards/o1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["object_id"] == "o1"
    assert data["has_open_hazard"] is True
