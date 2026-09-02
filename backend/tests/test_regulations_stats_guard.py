"""法规 stats 接口异常兜底单测（审查报告 P0-2/F1）。

ChromaDB collection 缺失/损坏时，`collection_count` 抛异常：
- `/regulations/stats/data` 应返回 503 业务错误而非 500，并记录日志；
- `GET /regulations`（列表内嵌索引计数）应降级 indexed_articles=0 而非 500。
"""

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.regulations as regulations_router
from app.dependencies import get_current_user
from app.models.user import User


class _BrokenCollection:
    """模拟 ChromaDB 不可用：collection_count 抛异常。"""

    def collection_count(self):
        raise RuntimeError("Collection does not exist (simulated chroma failure)")


class _CountingCollection:
    def __init__(self, count):
        self._count = count

    def collection_count(self):
        return self._count


class _FakeGraph:
    def stats(self):
        return {"total": 12, "effective": 10, "abolished": 2}

    def list_nodes(self, **kwargs):
        return {"items": [], "total": 0, "page": 1, "page_size": 15}


def _make_client(monkeypatch, vs):
    def _override_user():
        return User(id="u1", email="admin@example.com", name="管理员", role="admin")

    monkeypatch.setattr(regulations_router, "get_graph", lambda: _FakeGraph())
    monkeypatch.setattr(regulations_router, "get_vector_store", lambda: vs)

    app = FastAPI()
    app.include_router(regulations_router.router)
    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app)


def test_stats_data_returns_503_when_collection_raises(monkeypatch, caplog):
    """ChromaDB 异常时 stats/data 返回 503 业务错误（非 500）并记录日志。"""
    client = _make_client(monkeypatch, _BrokenCollection())

    with caplog.at_level(logging.ERROR, logger="app.routers.regulations"):
        resp = client.get("/regulations/stats/data")

    assert resp.status_code == 503
    body = resp.json()
    assert body.get("detail") == "法规库索引未初始化或不可用"
    assert "法规库索引" in caplog.text


def test_stats_data_ok_when_collection_available(monkeypatch):
    """collection_count 正常时 stats/data 返回 200 且带 indexed_articles。"""
    client = _make_client(monkeypatch, _CountingCollection(7))

    resp = client.get("/regulations/stats/data")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["indexed_articles"] == 7
    assert body["data"]["total"] == 12


def test_stats_data_ok_when_vector_store_none(monkeypatch):
    """未初始化向量库（get_vector_store 返回 None）时保持原有 0 降级。"""
    client = _make_client(monkeypatch, None)

    resp = client.get("/regulations/stats/data")

    assert resp.status_code == 200
    assert resp.json()["data"]["indexed_articles"] == 0


def test_list_regulations_degrades_when_collection_raises(monkeypatch):
    """列表接口 collection_count 异常时降级 indexed_articles=0，不抛 500。"""
    client = _make_client(monkeypatch, _BrokenCollection())

    resp = client.get("/regulations?page=1&page_size=15")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["indexed_articles"] == 0


def test_list_regulations_ok_when_collection_available(monkeypatch):
    """列表接口 collection_count 正常时返回真实索引计数。"""
    client = _make_client(monkeypatch, _CountingCollection(7))

    resp = client.get("/regulations?page=1&page_size=15")

    assert resp.status_code == 200
    assert resp.json()["data"]["indexed_articles"] == 7
