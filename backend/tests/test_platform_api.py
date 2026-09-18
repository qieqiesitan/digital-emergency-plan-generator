"""平台级端点测试。"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.routers import platform


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._items[0] if self._items else 0


def _client(handler):
    app = FastAPI()
    app.include_router(platform.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_list_capabilities():
    cap = MagicMock()
    cap.id = "c1"
    cap.code = "hazard_grade"
    cap.module = "隐患排查治理"
    cap.name = "隐患分级建议"
    cap.description = None
    cap.prompt_ref = None
    cap.model_override = None
    cap.is_enabled = True
    cap.allow_manual = True

    async def handler(stmt, *a, **k):
        return _Result([cap])

    client = _client(handler)
    resp = client.get("/api/v1/platform/capabilities")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["code"] == "hazard_grade"


def test_update_capability_404_when_missing():
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.put("/api/v1/platform/capabilities/nope", json={"is_enabled": False})
    assert resp.status_code == 404


def test_overview_endpoint_returns_all_sections():
    async def handler(stmt, *a, **k):
        return _Result([1])

    client = _client(handler)
    resp = client.get("/api/v1/platform/overview")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "enterprises" in data
    assert "major_hazard_level_1_2" in data
