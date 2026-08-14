from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent
from app.routers import risk_management
from app.services.risk_method_engine import validate_dual_level
from app.schemas.risk_management import RiskEventCreate, RiskEventResponse


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
    return ev


def _risk_db(ent, ev):
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
