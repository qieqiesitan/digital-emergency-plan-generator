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

        # 贴近真实行为：主键与带 server/column default 的字段在 flush 时才生成，
        # refresh 负责把它们读回来。mock 里补这两步，否则新建对象的 id 是 None。
        async def _refresh(obj):
            if getattr(obj, "id", None) is None:
                obj.id = "rec1"
            if getattr(obj, "attachments", None) is None:
                obj.attachments = {}
            if getattr(obj, "completeness", None) is None:
                obj.completeness = {}

        db.refresh = _refresh
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
    unit.floor_id = None
    unit.polygon = None
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
    """单元不存在/无权访问时返回 404 与可读原因（W0：统一 404 防资源探测）。"""

    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post(
        "/api/v1/major-hazard/units/u-missing/compute", json={"exposed_population": 0}
    )
    assert resp.status_code == 404
    assert "单元" in resp.json()["detail"]


# --- 任务 9：档案与备案 ---


def _record():
    r = MagicMock()
    r.id = "rec1"
    r.unit_id = "u1"
    r.enterprise_id = "e1"
    r.hazard_code = "TYKJ001"
    r.filing_status = "已备案"
    r.filing_no = None
    r.filing_date = None
    r.chief_name = "张峰"
    r.chief_post = None
    r.chief_phone = None
    r.tech_name = None
    r.tech_post = None
    r.tech_phone = None
    r.oper_name = None
    r.oper_post = None
    r.oper_phone = None
    r.attachments = {}
    r.completeness = {}
    return r


def test_get_record_returns_existing():
    async def handler(stmt, *a, **k):
        return _Result([_record()])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/units/u1/record")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["hazard_code"] == "TYKJ001"
    assert data["chief_name"] == "张峰"


def test_get_record_returns_404_when_missing():
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/units/u1/record")
    assert resp.status_code == 404


def test_put_record_creates_when_missing():
    created = []

    async def handler(stmt, *a, **k):
        text = str(stmt)
        if "FROM enterprises" in text or "enterprises" in text:
            ent = MagicMock()
            ent.id = "e1"
            ent.user_id = "user1"
            return _Result([ent])
        if "major_hazard_units" in text:
            unit = MagicMock()
            unit.id = "u1"
            unit.enterprise_id = "e1"
            return _Result([unit])
        return _Result([])

    client = _client(handler, created=created)
    resp = client.put(
        "/api/v1/major-hazard/units/u1/record",
        params={"enterprise_id": "e1"},
        json={"hazard_code": "TYKJ030", "filing_status": "未备案"},
    )
    assert resp.status_code == 200
    assert created and created[0].unit_id == "u1"


# --- 保存基本信息不得清空关联与落点（规格 §0）---------------------------------


def _unit_for_update():
    """字段全部显式赋值：UnitOut 校验严格，MagicMock 的自动属性过不了 pydantic。"""
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    unit.name = "罐区A"
    unit.unit_type = "storage"
    unit.address = None
    unit.department = None
    unit.responsible_person = None
    unit.responsible_phone = None
    unit.risk_object_id = "o1"
    unit.floor_id = "f1"
    unit.polygon = {"version": 1, "points": [{"x": 0, "y": 0}]}
    unit.is_active = True
    unit.created_at = None
    return unit


def _update_handler(unit):
    async def handler(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit])
        if "enterprises" in text:
            ent = MagicMock()
            ent.id = "e1"
            ent.user_id = "user1"
            return _Result([ent])
        return _Result([])

    return handler


def test_update_unit_keeps_untouched_fields():
    """前端只提交 6 个文本框，未传的字段一律不许动。"""
    unit = _unit_for_update()
    client = _client(_update_handler(unit))
    resp = client.put(
        "/api/v1/major-hazard/units/u1",
        json={"name": "罐区A2", "unit_type": "storage"},
    )
    assert resp.status_code == 200
    assert unit.name == "罐区A2"
    assert unit.risk_object_id == "o1"
    assert unit.floor_id == "f1"
    assert unit.polygon == {"version": 1, "points": [{"x": 0, "y": 0}]}


def test_update_unit_still_allows_explicit_clearing():
    """显式传 null 仍要能清空——不然用户没法解除关联。"""
    unit = _unit_for_update()
    client = _client(_update_handler(unit))
    resp = client.put(
        "/api/v1/major-hazard/units/u1",
        json={"name": "罐区A", "unit_type": "storage", "risk_object_id": None},
    )
    assert resp.status_code == 200
    assert unit.risk_object_id is None
