"""法规体系链端点 `/regulations/{id}/lineage`。

图里的边是"子→父"方向（子 --下位法--> 父），所以：
· up   = 沿出边的**上位法链**（不含自己）
· down = 入边（**直接下级**，剔除自环噪声——真实数据里存在 X--下位法-->X）
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import regulations as regulations_router


class _FakeGraph:
    """只实现端点用到的三个方法，避免依赖真实图谱文件。"""

    def __init__(self, nodes: dict, chain: list[str], lower: list[str]):
        self._nodes = nodes
        self._chain = chain
        self._lower = lower

    def get_node(self, nid):
        return self._nodes.get(nid)

    def trace_chain(self, nid, relation="下位法"):
        return list(self._chain)

    def lower_laws(self, nid, relation="下位法"):
        return list(self._lower)


def _client(fake_graph, monkeypatch):
    # 注意：端点内部是**直接调用** get_graph()（不走 Depends），
    # 因此必须 monkeypatch 模块属性，dependency_overrides 对它无效。
    monkeypatch.setattr(regulations_router, "get_graph", lambda: fake_graph)
    app = FastAPI()
    app.include_router(regulations_router.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield


NODES = {
    "reg_child": {"title": "生产安全事故应急条例", "code": "国务院令第708号", "status": "effective"},
    "law_parent": {"full_name": "中华人民共和国安全生产法", "code": "主席令第88号", "status": "effective"},
    "reg_lower": {"title": "某省实施细则", "status": "abolished"},
}


def test_lineage_returns_up_chain_without_self(monkeypatch):
    g = _FakeGraph(NODES, chain=["reg_child", "law_parent", "reg_child"], lower=[])
    r = _client(g, monkeypatch).get("/api/v1/regulations/reg_child/lineage")
    assert r.status_code == 200
    data = r.json()["data"]
    assert [x["id"] for x in data["up"]] == ["law_parent"], "起点自身不得出现在上位法链里"
    assert data["up"][0]["full_name"] == "中华人民共和国安全生产法"
    assert data["self"]["id"] == "reg_child" and data["self"]["title"] == "生产安全事故应急条例"


def test_lineage_down_lists_children_with_status(monkeypatch):
    g = _FakeGraph(NODES, chain=["law_parent"], lower=["reg_lower"])
    r = _client(g, monkeypatch).get("/api/v1/regulations/law_parent/lineage")
    data = r.json()["data"]
    assert [x["id"] for x in data["down"]] == ["reg_lower"]
    assert data["down"][0]["status"] == "abolished"
    assert data["up"] == []


def test_lineage_unknown_regulation_404(monkeypatch):
    g = _FakeGraph(NODES, chain=[], lower=[])
    r = _client(g, monkeypatch).get("/api/v1/regulations/not_exist/lineage")
    assert r.status_code == 404
    assert "法规不存在" in r.json()["detail"]


def test_lower_laws_drops_self_loop_and_dedups():
    """真实图里存在自环与重复边，下级列表必须干净。"""
    import networkx as nx

    from app.regulations.graph import RegulationGraph

    graph = RegulationGraph.__new__(RegulationGraph)   # 只测纯方法，不触发文件加载
    g = nx.MultiDiGraph()
    g.add_node("a", title="A")
    g.add_node("b", title="B")
    g.add_edge("b", "a", relation="下位法")     # b 是 a 的下级
    g.add_edge("a", "a", relation="下位法")     # 自环噪声
    g.add_edge("b", "a", relation="下位法")     # 重复边
    graph._g = g

    assert graph.lower_laws("a") == ["b"], "下级要去重且不含自环"
    assert graph.trace_chain("b", "下位法") == ["b", "a"]
