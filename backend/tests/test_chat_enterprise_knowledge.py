"""test_chat_enterprise_knowledge.py — 聊天画像问答工具。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _query_enterprise_knowledge


@pytest.mark.asyncio
async def test_query_requires_ownership():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    out = await _query_enterprise_knowledge(db, MagicMock(id="u1"),
                                            {"enterprise_id": "e1", "question": "有哪些重大风险"})
    assert "error" in out


@pytest.mark.asyncio
async def test_query_returns_snippets():
    db = AsyncMock()
    ent = MagicMock(id="e1", user_id="u1", name="企业A")
    result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    db.execute.return_value = result
    with patch("app.services.chat_dispatch.EnterpriseKnowledgeStore") as mock_store:
        mock_store.return_value.search.return_value = [
            {"text": "风险源：锅炉，等级：重大风险", "distance": 0.1}]
        out = await _query_enterprise_knowledge(db, MagicMock(id="u1"),
                                                {"enterprise_id": "e1", "question": "有哪些重大风险"})
    assert out["hits"][0]["text"].startswith("风险源")
