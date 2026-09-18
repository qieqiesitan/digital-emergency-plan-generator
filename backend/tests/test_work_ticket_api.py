"""作业票 API 测试。"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import work_ticket


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
    app.include_router(work_ticket.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        yield db

    async def _user():
        return MagicMock(id="u1")

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_list_tickets_filters_by_type():
    t = MagicMock()
    t.id = "wt1"
    t.code = "DHZY-A-20260917-0001"
    t.ticket_type = "DHZY"
    t.level = "一级"
    t.status = "approving"
    t.current_node_key = "approve"
    t.values = {}
    t.valid_from = None
    t.valid_to = None
    t.created_at = None

    async def handler(stmt, *a, **k):
        return _Result([t])

    client = _client(handler)
    resp = client.get(
        "/api/v1/work-ticket/tickets", params={"enterprise_id": "e1", "ticket_type": "DHZY"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["ticket_type"] == "DHZY"


def test_open_ticket_rejects_unimplemented_type():
    """本计划只开放动火/受限空间两类，其余类型必须被 schema 拒掉。"""
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post(
        "/api/v1/work-ticket/tickets",
        json={
            "enterprise_id": "e1",
            "enterprise_code": "A",
            "ticket_type": "GCZY",
            "template_id": "t1",
        },
    )
    assert resp.status_code == 422


def test_submit_returns_422_on_validation_failure():
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post("/api/v1/work-ticket/tickets/missing/submit")
    assert resp.status_code in (409, 422)
