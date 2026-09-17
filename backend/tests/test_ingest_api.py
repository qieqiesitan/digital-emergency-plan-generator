"""DataHub API 测试。"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import ingest


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
    app.include_router(ingest.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        db.add = MagicMock()
        yield db

    async def _user():
        u = MagicMock()
        u.id = "user1"
        return u

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_list_jobs_returns_rows():
    job = MagicMock()
    job.id = "j1"
    job.status = "running"
    job.total = 14
    job.imported = 0
    job.skipped = 3
    job.failed = 0
    job.pending_review = 11
    job.source_id = "s1"
    job.trigger = "manual"
    job.error_summary = None
    job.created_at = None

    async def handler(stmt, *a, **k):
        return _Result([job])

    client = _client(handler)
    resp = client.get("/api/v1/ingest/jobs")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["pending_review"] == 11


def test_review_list_defaults_low_confidence_unchecked():
    """低置信度默认不勾——这条是"整批默认全选+勾掉错的"的关键细节。"""
    hi = MagicMock()
    hi.id = "i1"
    hi.job_id = "j1"
    hi.confidence = "high"
    hi.status = "pending"
    hi.raw_payload = {"chemical_name": "氯"}
    hi.source_locator = "报告.pdf P12"
    hi.target_entity = "major_hazard_unit_chemical"
    hi.error = None
    hi.review_note = None
    lo = MagicMock()
    lo.id = "i2"
    lo.job_id = "j1"
    lo.confidence = "low"
    lo.status = "pending"
    lo.raw_payload = {"chemical_name": "?"}
    lo.source_locator = "报告.pdf P15"
    lo.target_entity = "major_hazard_unit_chemical"
    lo.error = None
    lo.review_note = None

    async def handler(stmt, *a, **k):
        return _Result([hi, lo])

    client = _client(handler)
    resp = client.get("/api/v1/ingest/items", params={"job_id": "j1"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["default_checked"] is True
    assert data[1]["default_checked"] is False


def test_confirm_endpoint_returns_counts():
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post("/api/v1/ingest/items/confirm", json={"item_ids": []})
    assert resp.status_code == 422  # 空选择应被拒


def test_skip_endpoint_rejects_empty_selection():
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post("/api/v1/ingest/items/skip", json={"item_ids": []})
    assert resp.status_code == 422
