from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent, RiskUnit
from app.routers import risk_management
from app.services.risk_method_engine import validate_dual_level
from app.services.risk_mapping_service import max_risk_level
from app.schemas.risk_management import RiskEventCreate, RiskEventResponse, RiskEventUpdate


def test_validate_dual_level_ok():
    validate_dual_level("一般", "重大")  # 不抛异常


def test_validate_dual_level_raises():
    with pytest.raises(ValueError, match="不应高于"):
        validate_dual_level("重大", "一般")


def test_migration_contains_columns():
    sql_path = Path(__file__).resolve().parents[1] / "db_migration_risk_control_enhancement.sql"
    sql = sql_path.read_text(encoding="utf-8")
    assert "inherent_risk_level" in sql
    assert "inherent_risk_score" in sql
    assert "control_level" in sql
    assert "public_risk_token" in sql


def test_risk_event_schemas_have_inherent_fields():
    fields = set(RiskEventCreate.model_fields) | set(RiskEventResponse.model_fields)
    assert {"inherent_risk_level", "inherent_risk_score", "control_level"} <= fields


def test_risk_event_schemas_have_explicit_level_override_fields():
    """Create/Update 支持显式 risk_level/risk_score（「采用折算参考」落库入口）。"""
    assert "risk_level" in RiskEventCreate.model_fields
    assert "risk_score" in RiskEventCreate.model_fields
    assert "risk_level" in RiskEventUpdate.model_fields
    assert "risk_score" in RiskEventUpdate.model_fields


def test_risk_event_schemas_reject_invalid_level_enum():
    """risk_level/inherent_risk_level/control_level 非空时必须属于允许枚举。"""
    with pytest.raises(ValidationError, match="风险等级必须是"):
        RiskEventCreate(accident_type="火灾", risk_level="高")
    with pytest.raises(ValidationError, match="风险等级必须是"):
        RiskEventCreate(accident_type="火灾", inherent_risk_level="严重")
    with pytest.raises(ValidationError, match="管控层级必须是"):
        RiskEventCreate(accident_type="火灾", control_level="全厂")
    with pytest.raises(ValidationError, match="风险等级必须是"):
        RiskEventUpdate(risk_level="未知")
    with pytest.raises(ValidationError, match="管控层级必须是"):
        RiskEventUpdate(inherent_risk_level="一般", control_level="车间")


def test_risk_event_schemas_allow_valid_or_empty_level_enum():
    """合法等级与空值放行。"""
    create = RiskEventCreate(
        accident_type="火灾",
        risk_level="低",
        inherent_risk_level=None,
        control_level="岗位",
    )
    assert create.risk_level == "低"
    assert create.inherent_risk_level is None
    assert create.control_level == "岗位"
    update = RiskEventUpdate(accident_type="火灾", inherent_risk_level="较大", control_level="部门")
    assert update.inherent_risk_level == "较大"
    assert update.control_level == "部门"
    assert RiskEventUpdate(accident_type="火灾").risk_level is None


def test_max_risk_level_by_mode():
    from app.models.risk_management import RiskZone, RiskObject, RiskEvent
    zone = RiskZone(id="z1", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o1", enterprise_id="e1", zone_id="z1", name="1#储罐")
    obj.events = [RiskEvent(accident_type="火灾", risk_level="一般", inherent_risk_level="重大")]
    zone.objects = [obj]
    assert max_risk_level(zone, "current") == "一般"
    assert max_risk_level(zone, "inherent") == "重大"


def test_max_risk_level_by_mode_unit_branch():
    from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent
    zone = RiskZone(id="z2", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o2", enterprise_id="e1", zone_id="z2", name="1#储罐")
    unit = RiskUnit(id="u1", object_id="o2", name="阀门组")
    unit.events = [RiskEvent(accident_type="泄漏", risk_level="较大", inherent_risk_level="重大")]
    obj.units = [unit]
    zone.objects = [obj]
    assert max_risk_level(zone, "current") == "较大"
    assert max_risk_level(zone, "inherent") == "重大"


def test_max_risk_level_defaults_to_current():
    from app.models.risk_management import RiskZone, RiskObject, RiskEvent
    zone = RiskZone(id="z3", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o3", enterprise_id="e1", zone_id="z3", name="1#储罐")
    obj.events = [RiskEvent(accident_type="火灾", risk_level="一般", inherent_risk_level="重大")]
    zone.objects = [obj]
    assert max_risk_level(zone) == "一般"  # 默认 current 向后兼容


def test_max_risk_level_aggregates_object_and_unit():
    from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent
    zone = RiskZone(id="z4", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o4", enterprise_id="e1", zone_id="z4", name="1#储罐")
    obj.events = [RiskEvent(accident_type="火灾", risk_level="一般", inherent_risk_level="重大")]
    unit = RiskUnit(id="u4", object_id="o4", name="阀门组")
    unit.events = [RiskEvent(accident_type="泄漏", risk_level="较大", inherent_risk_level="重大")]
    obj.units = [unit]
    zone.objects = [obj]
    assert max_risk_level(zone, "current") == "较大"   # 对象 一般 + 单元 较大 → 较大
    assert max_risk_level(zone, "inherent") == "重大"


def _event(**overrides):
    ev = RiskEvent(
        id="ev1",
        accident_type="火灾",
        risk_level="重大",
        inherent_risk_level="重大",
        method_type="LS",
        method_params={},
    )
    for key, value in overrides.items():
        setattr(ev, key, value)
    ev.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ev.sort_order = 0
    return ev


def _risk_db(ent, ev, unit=None):
    db = AsyncMock()

    def fake_execute(stmt):
        text = str(stmt)
        if "FROM enterprises" in text:
            res = MagicMock()
            res.scalar_one_or_none.return_value = ent
            return res
        if "FROM risk_events" in text:
            res = MagicMock()
            res.scalar_one_or_none.return_value = ev
            return res
        if "FROM risk_units" in text:
            res = MagicMock()
            res.scalar_one_or_none.return_value = unit
            return res
        return MagicMock()

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(risk_management.router)
    app.dependency_overrides[get_db] = lambda: _risk_db(None, None)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    with TestClient(app) as test_client:
        yield test_client


def test_update_event_rejects_inherent_above_current(client):
    """仅改固有等级（不重算方法参数）也必须被双等级约束拦截。"""
    ent = Enterprise(id="e1", user_id="u1", name="甲公司")
    ev = _event()
    client.app.dependency_overrides[get_db] = lambda: _risk_db(ent, ev)
    resp = client.put(
        "/enterprises/e1/risk-management/events/ev1",
        json={"inherent_risk_level": "一般"},
    )
    assert resp.status_code == 422
    assert "不应高于" in resp.json()["detail"]


def test_update_event_no_overwrite_omitted_params(client, monkeypatch):
    """未改动保存：载荷仅含 accident_type/description（无 method_*/risk_*/inherent_*）
    时不重算、不置空，已存等级与参数保持不变。"""
    ent = Enterprise(id="e1", user_id="u1", name="甲公司")
    ev = _event(
        method_type="LS",
        method_params={"l": 4, "s": 5},
        risk_level="重大",
        risk_score="R=20",
        inherent_risk_level="重大",
        inherent_risk_score="R=20",
    )
    db = _risk_db(ent, ev)
    client.app.dependency_overrides[get_db] = lambda: db
    compute = AsyncMock()
    monkeypatch.setattr(risk_management, "compute_risk", compute)

    resp = client.put(
        "/enterprises/e1/risk-management/events/ev1",
        json={"accident_type": "火灾", "description": "仅改描述"},
    )

    assert resp.status_code == 200
    compute.assert_not_awaited()
    assert ev.risk_level == "重大"
    assert ev.risk_score == "R=20"
    assert ev.inherent_risk_level == "重大"
    assert ev.inherent_risk_score == "R=20"
    assert ev.method_params == {"l": 4, "s": 5}
    assert resp.json()["data"]["risk_level"] == "重大"


def test_update_event_no_overwrite_direct(client, monkeypatch):
    """DIRECT 未改动保存：已存「重大」（method_params.risk_level）不被覆盖为默认「一般」。"""
    ent = Enterprise(id="e1", user_id="u1", name="甲公司")
    ev = _event(
        method_type="DIRECT",
        method_params={"risk_level": "重大"},
        risk_level="重大",
        inherent_risk_level="重大",
    )
    db = _risk_db(ent, ev)
    client.app.dependency_overrides[get_db] = lambda: db
    compute = AsyncMock()
    monkeypatch.setattr(risk_management, "compute_risk", compute)

    resp = client.put(
        "/enterprises/e1/risk-management/events/ev1",
        json={"accident_type": "火灾", "description": "未改动保存"},
    )

    assert resp.status_code == 200
    compute.assert_not_awaited()
    assert ev.risk_level == "重大"
    assert ev.method_params == {"risk_level": "重大"}
    assert resp.json()["data"]["risk_level"] == "重大"


def test_create_event_explicit_risk_level_overrides(client, monkeypatch):
    """显式 risk_level/risk_score：create 路径不调用 compute_risk，当前等级取请求值。"""
    ent = Enterprise(id="e1", user_id="u1", name="甲公司")
    unit = RiskUnit(id="u1", object_id="o1", name="单元")
    db = _risk_db(ent, None, unit=unit)

    async def fake_refresh(instance):
        instance.id = "ev-new"
        instance.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        instance.sort_order = 0

    db.add = MagicMock()
    db.refresh = AsyncMock(side_effect=fake_refresh)
    client.app.dependency_overrides[get_db] = lambda: db
    compute = AsyncMock()
    monkeypatch.setattr(risk_management, "compute_risk", compute)

    resp = client.post(
        "/enterprises/e1/risk-management/units/u1/events",
        json={
            "accident_type": "火灾",
            "method_type": "LS",
            "method_params": {"l": 4, "s": 5},
            "risk_level": "一般",
            "risk_score": "R=10",
        },
    )

    assert resp.status_code == 201
    compute.assert_not_awaited()
    created = db.add.call_args[0][0]
    assert created.risk_level == "一般"
    assert created.risk_score == "R=10"
    data = resp.json()["data"]
    assert data["risk_level"] == "一般"
    assert data["risk_score"] == "R=10"


def test_update_event_explicit_risk_level_overrides(client, monkeypatch):
    """显式 risk_level/risk_score：update 路径不重算，直接落库覆盖当前等级。"""
    ent = Enterprise(id="e1", user_id="u1", name="甲公司")
    ev = _event(method_type="LS", method_params={"l": 4, "s": 5},
                risk_level="重大", risk_score="R=20", inherent_risk_level="重大")
    db = _risk_db(ent, ev)
    client.app.dependency_overrides[get_db] = lambda: db
    compute = AsyncMock()
    monkeypatch.setattr(risk_management, "compute_risk", compute)

    resp = client.put(
        "/enterprises/e1/risk-management/events/ev1",
        json={"risk_level": "一般", "risk_score": "R=10"},
    )

    assert resp.status_code == 200
    compute.assert_not_awaited()
    assert ev.risk_level == "一般"
    assert ev.risk_score == "R=10"
    assert resp.json()["data"]["risk_level"] == "一般"
    assert resp.json()["data"]["risk_score"] == "R=10"


def test_create_event_explicit_risk_level_still_validates_dual_level(client, monkeypatch):
    """显式覆盖仍执行双等级校验：现有等级高于固有等级 → 422。"""
    ent = Enterprise(id="e1", user_id="u1", name="甲公司")
    unit = RiskUnit(id="u1", object_id="o1", name="单元")
    db = _risk_db(ent, None, unit=unit)
    client.app.dependency_overrides[get_db] = lambda: db
    compute = AsyncMock()
    monkeypatch.setattr(risk_management, "compute_risk", compute)

    resp = client.post(
        "/enterprises/e1/risk-management/units/u1/events",
        json={
            "accident_type": "火灾",
            "method_type": "LS",
            "method_params": {"l": 4, "s": 5},
            "risk_level": "重大",
            "inherent_risk_level": "一般",
        },
    )

    assert resp.status_code == 422
    assert "不应高于" in resp.json()["detail"]
