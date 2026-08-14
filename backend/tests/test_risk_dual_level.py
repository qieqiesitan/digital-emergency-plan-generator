from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent, RiskUnit
from app.routers import risk_management
from app.services.risk_method_engine import validate_dual_level
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
