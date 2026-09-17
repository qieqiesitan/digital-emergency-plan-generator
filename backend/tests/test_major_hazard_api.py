"""重大危险源 API 测试（TestClient + 依赖覆盖，沿用 test_risk_conversion_api.py 范式）。"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import major_hazard


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
        return self._items[0] if self._items else None


def _client(handler, created=None):
    app = FastAPI()
    app.include_router(major_hazard.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock() if created is None else (lambda obj: created.append(obj))
        db.delete = AsyncMock()
        yield db

    async def _user():
        u = MagicMock()
        u.id = "user1"
        u.is_admin = True
        return u

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_list_units_returns_items():
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    unit.name = "罐区 A"
    unit.unit_type = "storage"
    unit.is_active = True
    unit.address = None
    unit.department = None
    unit.responsible_person = None
    unit.responsible_phone = None
    unit.risk_object_id = None
    unit.created_at = None

    async def handler(stmt, *a, **k):
        return _Result([unit])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/units", params={"enterprise_id": "e1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"][0]["name"] == "罐区 A"


def test_critical_quantity_lookup_filters_by_keyword():
    row = MagicMock()
    row.chemical_name = "氯"
    row.alias = "液氯；氯气"
    row.cas_no = "7782-50-5"
    row.critical_t = 5
    row.critical_note = None
    row.table_no = "1"
    row.source_page = 5

    async def handler(stmt, *a, **k):
        return _Result([row])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/definitions/critical-quantities", params={"keyword": "氯"})
    assert resp.status_code == 200
    item = resp.json()["data"][0]
    assert item["chemical_name"] == "氯"
    # FastAPI 默认把 Decimal 序列化为字符串以保留精度（临界量有 0.3 / 0.75 这类值），
    # 前端按字符串接收后自行转数值。这是有意行为，不是 bug。
    assert item["critical_t"] == "5"
    assert float(item["critical_t"]) == 5.0


def test_compute_returns_rule_error_as_422():
    """单元不存在时返回 422 与可读原因，不返回 500。"""

    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post(
        "/api/v1/major-hazard/units/u-missing/compute", json={"exposed_population": 0}
    )
    assert resp.status_code == 422
    assert "单元" in resp.json()["detail"]
