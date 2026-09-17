"""抽取相关端点测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import extraction


def _client(handler):
    app = FastAPI()
    app.include_router(extraction.router, prefix="/api/v1")

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


def test_suggest_mapping_endpoint():
    async def handler(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        return res

    client = _client(handler)
    with patch(
        "app.routers.extraction.suggest_mapping",
        new=AsyncMock(return_value={"mapping": {"品名": "chemical_name"}, "source": "ai"}),
    ):
        resp = client.post(
            "/api/v1/extraction/suggest-mapping",
            json={"headers": ["品名"], "target_entity": "major_hazard_unit_chemical"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["mapping"]["品名"] == "chemical_name"


def test_extract_endpoint_rejects_unknown_target():
    async def handler(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        return res

    client = _client(handler)
    resp = client.post(
        "/api/v1/extraction/run",
        json={"job_id": "j1", "source_id": "s1", "target_entity": "no_such", "text": "x", "filename": "f.pdf"},
    )
    assert resp.status_code == 422


def test_extract_endpoint_returns_queued_counts():
    async def handler(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = MagicMock()  # 有 AI 配置
        return res

    client = _client(handler)
    with patch(
        "app.routers.extraction.extract_candidates",
        new=AsyncMock(return_value={"queued": 5, "skipped": 1, "invalid": 0}),
    ):
        resp = client.post(
            "/api/v1/extraction/run",
            json={
                "job_id": "j1",
                "source_id": "s1",
                "target_entity": "major_hazard_unit",
                "text": "罐区A",
                "filename": "报告.pdf",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["queued"] == 5
