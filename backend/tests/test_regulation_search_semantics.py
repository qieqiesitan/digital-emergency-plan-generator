"""法规检索结果的 recall/similarity_score 语义（2026-09-20 真实模型验收发现）。

现象：词面召回的命中项被算出 `similarity_score=0.0`（因为 distance 兜底为 1），
真实模型据此在回答里写"多数条文相似度为 0.0"，用户看了会以为检索坏了。
修复：标记 recall 来源，词面命中 similarity_score 置 null，并在工具描述里说明。
"""
from types import SimpleNamespace

import pytest

from app.services import chat_dispatch as cd


class _Store:
    def __init__(self, hits):
        self._hits = hits

    def search_articles(self, _query, top_k=0):  # noqa: ARG002
        return list(self._hits)


class _Graph:
    def get_node(self, _reg_id):
        return {"full_name": "测试法规", "code": "TEST-1", "status": "live"}


def _patch(monkeypatch, vector_hits, lexical_hits):
    monkeypatch.setattr(cd, "get_vector_store", lambda: _Store(vector_hits))
    monkeypatch.setattr(cd, "get_graph", lambda: _Graph())
    monkeypatch.setattr(cd, "_extract_regulation_keywords", lambda _q: ["储存"])
    monkeypatch.setattr(
        cd, "_corpus_lexical_matches",
        lambda _store, _kw: (lexical_hits, {}, len(lexical_hits)) if lexical_hits else None,
    )


@pytest.mark.asyncio
async def test_lexical_hits_report_null_score(monkeypatch):
    _patch(
        monkeypatch,
        vector_hits=[],
        lexical_hits=[{
            "text": "危险化学品应当储存在专用仓库内。",
            "metadata": {"regulation_id": "reg1", "article_number": "第二十条"},
            "distance": 1.0,
            "recall": "lexical",
        }],
    )
    out = await cd._search_regulation_articles(None, SimpleNamespace(id="u1"), {"query": "储存"})
    art = out["articles"][0]
    assert art["recall"] == "lexical"
    assert art["similarity_score"] is None, "词面命中不得报 0.0（会被模型当成“不相关”）"


@pytest.mark.asyncio
async def test_vector_hits_keep_score(monkeypatch):
    _patch(
        monkeypatch,
        vector_hits=[{
            "text": "危险化学品储存场所应设置明显标志。",
            "metadata": {"regulation_id": "reg1", "article_number": "第二十一条"},
            "distance": 0.2,
        }],
        lexical_hits=None,
    )
    out = await cd._search_regulation_articles(None, SimpleNamespace(id="u1"), {"query": "储存"})
    art = out["articles"][0]
    assert art["recall"] == "vector"
    assert art["similarity_score"] == 0.8
