"""test_chat_regulation_search.py — 语义检索 + 图谱补全 + fallback。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _search_regulation_articles


@pytest.mark.asyncio
async def test_vector_hit_with_graph_enrichment():
    hits = [{
        "text": "储存危险化学品应当设置明显标志。",
        "metadata": {"regulation_id": "aq3013_2008", "article_number": "第七条"},
        "distance": 0.12,
    }]
    node = {"full_name": "危险化学品从业单位安全标准化通用规范", "code": "AQ3013-2008", "status": "active"}
    with patch("app.services.chat_dispatch.get_vector_store") as mock_vs, \
         patch("app.services.chat_dispatch.get_graph") as mock_graph:
        mock_vs.return_value.search_articles.return_value = hits
        mock_graph.return_value.get_node.return_value = node
        out = await _search_regulation_articles(AsyncMock(), MagicMock(id="u1"),
                                                {"query": "危化品储存标志", "top_k": 8})
    assert out["source"] == "vector"
    assert out["count"] == 1
    assert out["articles"][0]["regulation_full_name"].startswith("危险化学品")
    assert out["articles"][0]["article_number"] == "第七条"


@pytest.mark.asyncio
async def test_fallback_when_vector_empty():
    with patch("app.services.chat_dispatch.get_vector_store") as mock_vs:
        mock_vs.return_value.search_articles.return_value = []
        out = await _search_regulation_articles(AsyncMock(), MagicMock(id="u1"),
                                                {"query": "安全生产法 第一条", "top_k": 8})
    assert out["source"] == "graph_fallback"


@pytest.mark.asyncio
async def test_fallback_when_vector_raises():
    with patch("app.services.chat_dispatch.get_vector_store") as mock_vs:
        mock_vs.return_value.search_articles.side_effect = RuntimeError("chroma down")
        out = await _search_regulation_articles(AsyncMock(), MagicMock(id="u1"),
                                                {"query": "消防通道要求", "top_k": 8})
    assert out["source"] == "graph_fallback"
