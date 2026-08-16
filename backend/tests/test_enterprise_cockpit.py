from datetime import date, timedelta

import pytest

from app.services.enterprise_cockpit_service import (
    _classify_level,
    _risk_index,
    aggregate_events,
    derive_todos,
)


class FakeEvent:
    def __init__(self, level="一般", score="60", zone="生产车间", obj="反应釜区", unit=None, responsible=None):
        self.risk_level = level
        self.risk_score = score
        self._zone = zone
        self._obj = obj
        self._unit = unit
        self._responsible = responsible

    @property
    def zone(self):
        return type("Z", (), {"name": self._zone})()

    @property
    def object(self):
        o = type("O", (), {"name": self._obj, "responsible_unit": self._responsible})
        o.zone = self.zone
        return o

    @property
    def unit(self):
        if self._unit is None:
            return None
        u = type("U", (), {"name": self._unit})
        u.object = self.object
        return u


def test_classify_level():
    assert _classify_level("重大") == "major"
    assert _classify_level("较大") == "larger"
    assert _classify_level("一般") == "general"
    assert _classify_level("低") == "low"
    assert _classify_level(None) == "general"
    assert _classify_level("未知") == "general"


def test_risk_index_formula_and_clamp():
    assert _risk_index({"major": 2, "larger": 4, "general": 18, "low": 10}) == 38
    assert _risk_index({"major": 5, "larger": 0, "general": 0, "low": 0}) == 100


def test_aggregate_events_counts_zones_and_top():
    events = [
        FakeEvent("重大", "82", "生产车间", "反应釜区", responsible="生产部"),
        FakeEvent("较大", "74", "生产车间", "反应釜区"),
        FakeEvent("一般", "45", "生产车间", "烘干车间"),
        FakeEvent("低", "20", "办公楼", "办公室"),
    ]
    out = aggregate_events(events)
    assert out["risk_counts"] == {"major": 1, "larger": 1, "general": 1, "low": 1, "total": 4}
    assert out["risk_index"] == 55
    assert out["zone_risks"][0]["zone_name"] == "生产车间"
    assert out["zone_risks"][0]["total"] == 3
    assert out["top_risks"][0]["name"] == "反应釜区"
    assert out["top_risks"][0]["score"] == 82
    assert out["top_risks"][0]["responsible_unit"] == "生产部"


def test_derive_todos_reports_hazard_surrounding():
    todos = derive_todos(
        reports={"assessment": False, "investigation": True},
        open_hazard_count=3,
        due_hazard_count=2,
        overdue_hazard_count=0,
        completion_modules=[
            {"key": "surrounding", "label": "周边环境", "done": False},
            {"key": "reports", "label": "报告", "done": False},
        ],
    )
    assert todos[0]["title"] == "风险评估报告未生成"
    assert todos[0]["priority"] == "high"
    assert any(t["title"].startswith("2 条隐患整改即将到期") for t in todos)
    assert len(todos) == 3


def test_derive_todos_empty():
    todos = derive_todos(
        reports={"assessment": True, "investigation": True},
        open_hazard_count=0,
        due_hazard_count=0,
        overdue_hazard_count=0,
        completion_modules=[],
    )
    assert todos == []


from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.routers import enterprises


def _make_client(db_session):
    app = FastAPI()
    app.include_router(enterprises.router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="a@b.com", name="测试", password_hash="x"
    )
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_cockpit_summary_returns_404_for_missing_enterprise():
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    client = _make_client(session)
    resp = client.get("/enterprises/nope/cockpit-summary")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "企业不存在"


@patch("app.routers.enterprises.build_cockpit_summary", new_callable=AsyncMock)
def test_cockpit_summary_returns_payload(mock_build):
    mock_build.return_value = {
        "risk_counts": {"major": 1, "larger": 1, "general": 1, "low": 1, "total": 4},
        "zone_risks": [],
        "top_risks": [],
        "risk_index": 55,
        "hazard_counts": {"open": 3, "due": 2, "overdue": 0},
        "todos": [],
        "completion": {"percent": 50, "modules": []},
        "recent_activities": [],
    }
    enterprise = MagicMock(id="e1", user_id="u1")
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=enterprise)))
    client = _make_client(session)
    resp = client.get("/enterprises/e1/cockpit-summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["risk_index"] == 55
    assert data["completion"]["percent"] == 50


def test_aggregate_events_empty():
    out = aggregate_events([])
    assert out["risk_counts"] == {"major": 0, "larger": 0, "general": 0, "low": 0, "total": 0}
    assert out["zone_risks"] == []
    assert out["top_risks"] == []
    assert out["risk_index"] == 0


def test_aggregate_events_unit_level_fallback_and_bad_values():
    events = [
        FakeEvent(level=None, score="abc", zone="储罐区", obj="球罐区", unit="1#球罐", responsible="生产部"),
        FakeEvent(level="低", score="10", zone="办公楼", obj="办公室"),
    ]
    out = aggregate_events(events)
    assert out["risk_counts"]["general"] == 1
    assert out["risk_counts"]["low"] == 1
    ball = next(t for t in out["top_risks"] if t["name"] == "球罐区")
    assert ball["score"] == 0.0
    assert ball["responsible_unit"] == "生产部"
    zone_names = [z["zone_name"] for z in out["zone_risks"]]
    assert "储罐区" in zone_names and "办公楼" in zone_names
