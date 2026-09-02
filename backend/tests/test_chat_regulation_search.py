"""test_chat_regulation_search.py — 语义检索 + 图谱补全 + fallback。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import (
    _extract_regulation_keywords,
    _rerank_regulation_articles,
    _search_regulation_articles,
)


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


def test_extract_regulation_keywords_covers_domain_terms():
    """无 jieba 场景：疑问词被剔除后仍能提取关键领域词。"""
    assert "储存距离" in _extract_regulation_keywords("危险化学品储存距离有什么要求")
    assert "备案" in _extract_regulation_keywords("应急预案编制后需要备案吗")
    kws = _extract_regulation_keywords("消防通道和安全出口有什么规定")
    assert "消防通道" in kws
    assert "安全出口" in kws
    kws2 = _extract_regulation_keywords("应急演练频次有什么规定")
    assert "演练频次" in kws2
    assert "有什么" not in kws2


def test_rerank_puts_keyword_rich_article_first():
    """命中关键词多的候选应排到纯向量高相似但无关键词命中之前。"""
    candidates = [
        {
            "article_text": "注册安全工程师应当严格执行国家法律、法规和本规定，恪守职业道德和执业准则。",
            "article_number": "第四条",
            "regulation_full_name": "注册安全工程师管理规定",
            "regulation_code": "",
            "status": "active",
            "similarity_score": 0.90,
        },
        {
            "article_text": "机关、团体、企业、事业单位应当保障疏散通道、安全出口畅通，消防通道不得占用、堵塞。",
            "article_number": "第五条",
            "regulation_full_name": "中华人民共和国消防法",
            "regulation_code": "",
            "status": "active",
            "similarity_score": 0.80,
        },
    ]
    reranked = _rerank_regulation_articles("消防通道和安全出口有什么规定", candidates)
    assert "消防通道" in reranked[0]["article_text"]


def test_rerank_more_keywords_rank_ahead():
    """同一批候选中，覆盖更多 query 关键词的条文排前。"""
    candidates = [
        {
            "article_text": "生产经营单位应当制定本单位应急预案，并定期组织演练。",
            "article_number": "第二十条",
            "regulation_full_name": "生产安全事故应急预案管理办法",
            "regulation_code": "",
            "status": "active",
            "similarity_score": 0.70,
        },
        {
            "article_text": "生产经营单位每年至少组织一次综合应急预案演练，专项应急预案每半年至少演练一次，演练频次应满足法规要求。",
            "article_number": "第二十一条",
            "regulation_full_name": "生产安全事故应急预案管理办法",
            "regulation_code": "",
            "status": "active",
            "similarity_score": 0.65,
        },
    ]
    reranked = _rerank_regulation_articles("应急演练频次有什么规定", candidates)
    assert "演练频次" in reranked[0]["article_text"]


def test_rerank_falls_back_to_similarity_without_keywords():
    """无关键词可提取（如纯外文/短查询）时按相似度降序保持原序。"""
    candidates = [
        {"article_text": "low sim", "article_number": "", "regulation_full_name": "x",
         "regulation_code": "", "status": "active", "similarity_score": 0.30},
        {"article_text": "high sim", "article_number": "", "regulation_full_name": "x",
         "regulation_code": "", "status": "active", "similarity_score": 0.90},
    ]
    reranked = _rerank_regulation_articles("abc", candidates)
    assert reranked[0]["similarity_score"] == 0.90


@pytest.mark.asyncio
async def test_vector_recall_expanded_before_rerank():
    """向量召回应扩大到 30 条候选，供关键词重排挑选。"""
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
        await _search_regulation_articles(AsyncMock(), MagicMock(id="u1"),
                                          {"query": "危化品储存标志", "top_k": 8})
    mock_vs.return_value.search_articles.assert_called_once_with("危化品储存标志", top_k=30)


@pytest.mark.asyncio
async def test_vector_path_reranks_mock_candidates():
    """端到端：向量命中含关键词条文时，关键词命中多者排在最前。"""
    hits = [
        {
            "text": "注册安全工程师管理规定 执业准则相关条文内容正文。",
            "metadata": {"regulation_id": "reg_a", "article_number": "第四条"},
            "distance": 0.10,
        },
        {
            "text": "有限空间作业前应当进行气体检测和通风，办理作业审批手续后方可作业。",
            "metadata": {"regulation_id": "reg_b", "article_number": "第六条"},
            "distance": 0.45,
        },
    ]
    nodes = {
        "reg_a": {"full_name": "注册安全工程师管理规定", "code": "", "status": "active"},
        "reg_b": {"full_name": "工贸企业有限空间作业安全管理与监督暂行规定", "code": "", "status": "active"},
    }
    with patch("app.services.chat_dispatch.get_vector_store") as mock_vs, \
         patch("app.services.chat_dispatch.get_graph") as mock_graph:
        mock_vs.return_value.search_articles.return_value = hits
        mock_graph.return_value.get_node.side_effect = lambda rid: nodes.get(rid)
        out = await _search_regulation_articles(AsyncMock(), MagicMock(id="u1"),
                                                {"query": "有限空间作业前应做什么安全措施", "top_k": 8})
    assert out["source"] == "vector"
    assert out["count"] == 2
    assert "气体检测" in out["articles"][0]["article_text"]
