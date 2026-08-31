"""test_enterprise_knowledge.py — 企业画像索引。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.enterprise_knowledge_service import (
    _build_enterprise_text, EnterpriseKnowledgeStore,
)


def test_build_enterprise_text_assembles_sections():
    context = {"risk_sources": [
        {"name": "锅炉", "risk_level": "重大风险", "control_measures": "定期检测"},
    ]}
    text = _build_enterprise_text("企业A", context, [], [])
    assert "企业A" in text
    assert "锅炉" in text
    assert "重大风险" in text


def test_store_delete_then_add_is_idempotent():
    store = EnterpriseKnowledgeStore.__new__(EnterpriseKnowledgeStore)
    store._client = MagicMock()
    store._collection = MagicMock()
    store._collection.delete.return_value = None
    store._collection.add.return_value = None
    store.index_enterprise("e1", ["片段1", "片段2"])
    store._collection.delete.assert_called_once()
    store._collection.add.assert_called_once()
