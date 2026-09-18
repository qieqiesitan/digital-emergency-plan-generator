"""报告导出端点测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import major_hazard
from app.services.major_hazard_report_data import ReportNotReadyError


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


def _client(handler):
    app = FastAPI()
    app.include_router(major_hazard.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        yield db

    async def _user():
        u = MagicMock()
        u.id = "user1"
        return u

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_report_returns_422_when_no_snapshot():
    """没有快照时返回 422 + 可读原因，而不是 500，也不要出一个空报告。"""
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    enterprise = MagicMock()
    enterprise.name = "某公司"

    async def handler(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit])
        if "enterprises" in text:
            return _Result([enterprise])
        if "major_hazard_unit_chemicals" in text:
            return _Result([MagicMock()])
        if "major_hazard_calculations" in text:
            return _Result([])  # 没有快照
        return _Result([])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/units/u1/report.docx")
    assert resp.status_code == 422
    assert "辨识计算" in resp.json()["detail"]


def test_report_returns_docx_when_ready(tmp_path):
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    unit.name = "罐区A"
    enterprise = MagicMock()
    enterprise.name = "某公司"
    snap = MagicMock()
    snap.inputs_snapshot = {
        "s_value": 1.5,
        "r_value": 7.5,
        "alpha": 1.5,
        "exposed_population": 60,
        "is_major_hazard": True,
        "level": "四级",
        "chemicals": [{"name": "氯", "q": 5.0, "Q": 5.0, "beta": 4.0,
                       "q_over_Q": 1.0, "beta_times_q_over_Q": 4.0}],
    }
    written = {}

    async def handler(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit])
        if "enterprises" in text:
            return _Result([enterprise])
        if "major_hazard_unit_chemicals" in text:
            chem = MagicMock()
            chem.chemical_name = "氯"
            chem.q_design_max = 5
            chem.critical_quantity_t = 5
            chem.beta = 4
            chem.beta_source = "table3"
            chem.physical_state = "液态"
            return _Result([chem])
        if "major_hazard_calculations" in text:
            return _Result([snap])
        return _Result([])

    class _FakeDoc:
        def save(self, path):
            written["path"] = path
            open(path, "wb").write(b"PK\x03\x04fake")

    with patch(
        "app.routers.major_hazard.generate_report_docx", return_value=_FakeDoc()
    ):
        client = _client(handler)
        resp = client.get("/api/v1/major-hazard/units/u1/report.docx")

    assert resp.status_code == 200
    assert "application/vnd.openxmlformats" in resp.headers["content-type"]
    assert written.get("path"), "必须落盘"
