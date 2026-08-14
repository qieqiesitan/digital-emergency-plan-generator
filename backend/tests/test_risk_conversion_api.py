from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.risk_management import RiskEvent
from app.routers import risk_management
from app.services import data_dict_service


THRESHOLDS = [
    {"min": 1, "max": 9, "level": "低"},
    {"min": 10, "max": 14, "level": "一般"},
    {"min": 15, "max": 19, "level": "较大"},
    {"min": 20, "max": 25, "level": "重大"},
]


def _method(config: dict):
    m = MagicMock()
    m.method_type = "LS"
    m.config = config
    return m


def _app(event, method=None):
    app = FastAPI()
    app.include_router(risk_management.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()

        async def execute(stmt, *a, **k):
            res = MagicMock()
            text = str(stmt)
            if "risk_events" in text and "id =" in text:
                res.scalar_one_or_none.return_value = event
            elif "enterprises" in text:
                ent = MagicMock()
                ent.id = "e1"
                ent.user_id = "u1"
                res.scalar_one_or_none.return_value = ent
            elif "risk_assessment_methods" in text:
                res.scalar_one_or_none.return_value = method
            else:
                res.scalar_one_or_none.return_value = None
            return res

        db.execute = AsyncMock(side_effect=execute)
        db.get = AsyncMock(return_value=event)
        return db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="u1")
    return TestClient(app)


def test_conversion_reference_endpoint(monkeypatch):
    event = RiskEvent(
        id="ev1",
        accident_type="火灾",
        method_type="LS",
        method_params={"l": 4, "s": 5},
        risk_level="重大",
        risk_score="R=20",
        inherent_risk_level="重大",
        inherent_risk_score="R=20",
    )
    factors = {
        "engineering": {"value": {"factor": 0.5}},
        "mode": {"value": {"mode": "min"}},
    }
    monkeypatch.setattr(data_dict_service, "get_dict_map", AsyncMock(return_value=factors))
    client = _app(event, method=_method({"risk_thresholds": THRESHOLDS}))

    resp = client.get("/api/v1/enterprises/e1/risk-management/events/ev1/conversion-reference")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["factor"] == 0.5
    assert data["reference_score"] == 10.0
    assert data["reference_level"] == "一般"


def test_conversion_reference_missing_event_returns_404():
    client = _app(None)
    resp = client.get("/api/v1/enterprises/e1/risk-management/events/missing/conversion-reference")
    assert resp.status_code == 404
    assert "事件不存在" in resp.json()["detail"]


def test_preview_method_echoes_scenario(monkeypatch):
    monkeypatch.setattr(data_dict_service, "get_dict_map", AsyncMock(return_value={}))
    client = _app(None, method=_method({"risk_thresholds": THRESHOLDS}))

    resp = client.post(
        "/api/v1/enterprises/e1/risk-management/methods/preview",
        json={"method_id": "m1", "params": {"l": 4, "s": 5}, "scenario": "inherent"},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["scenario"] == "inherent"
