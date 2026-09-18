"""删除法规必须级联删除条文子节点（2026-09-18 补）。

实测坑：`ingest_regulation` 为每条条文建 `art_{reg_id}_*` 子节点，而 DELETE 只删法规节点，
条文节点变成孤儿留在 graph.json（现网曾遗留 109 个）；孤儿虽不可检索，但让图谱持续膨胀，
连"删完节点数回到基线"都做不到。
"""

import json

from app.regulations import graph as graph_mod
from app.regulations.graph import RegulationGraph


def _graph(tmp_path, monkeypatch) -> RegulationGraph:
    monkeypatch.setattr(graph_mod, "GRAPH_PATH", str(tmp_path / "graph.json"))
    monkeypatch.setattr(graph_mod, "DATA_DIR", str(tmp_path))
    g = RegulationGraph()
    g.load()
    return g


def test_delete_regulation_removes_article_children(tmp_path, monkeypatch):
    g = _graph(tmp_path, monkeypatch)
    g.add_node({"id": "reg_x", "label": "X", "full_name": "X 法规", "node_type": "standard"})
    g.add_node({"id": "reg_y", "label": "Y", "full_name": "Y 法规", "node_type": "standard"})
    g.add_article_node("reg_x", {"number": "第一条", "text": "甲"})
    g.add_article_node("reg_x", {"number": "第二条", "text": "乙"})
    g.add_article_node("reg_y", {"number": "第一条", "text": "丙"})
    g.save()
    assert g._g.number_of_nodes() == 5

    removed = g.delete_regulation("reg_x")
    assert removed == {"regulation": 1, "articles": 2}
    ids = set(g._g.nodes)
    assert "reg_x" not in ids
    assert not [i for i in ids if i.startswith("art_reg_x_")]
    assert "reg_y" in ids and "art_reg_y_第一条" in ids, "不能误删别的法规条文"

    # 落盘结果同样干净（重新加载验证）
    reloaded = _graph(tmp_path, monkeypatch)
    assert reloaded._g.number_of_nodes() == 2


def test_delete_regulation_missing_returns_zero(tmp_path, monkeypatch):
    g = _graph(tmp_path, monkeypatch)
    assert g.delete_regulation("nope") == {"regulation": 0, "articles": 0}


def test_no_orphan_articles_after_delete(tmp_path, monkeypatch):
    g = _graph(tmp_path, monkeypatch)
    g.add_node({"id": "reg_z", "label": "Z", "full_name": "Z", "node_type": "law"})
    g.add_article_node("reg_z", {"number": "第一条", "text": "内容"})
    g.delete_regulation("reg_z")
    data = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
    orphans = [n for n in data["nodes"]
               if n.get("node_type") == "article" and n.get("parent_regulation") == "reg_z"]
    assert orphans == []
