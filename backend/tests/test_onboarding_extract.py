import asyncio
from unittest.mock import AsyncMock

from app.services.onboarding_service import extract_candidates, classify_modules


def test_extract_candidates_parses_llm_json(monkeypatch):
    async def fake_llm(messages, ai_config, timeout=120):
        return '{"items": [{"name": "甲醇", "cas_no": "67-56-1"}]}'
    monkeypatch.setattr("app.services.onboarding_service.llm_text_completion", fake_llm)
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = object()  # 系统配置存在
    result = asyncio.run(extract_candidates("chemical", "文本内容", db))
    assert result == [{"name": "甲醇", "cas_no": "67-56-1"}]


def test_classify_modules_parses_llm_json(monkeypatch):
    async def fake_llm(messages, ai_config, timeout=120):
        return '{"modules": ["enterprise_info", "risk_chemical"]}'
    monkeypatch.setattr("app.services.onboarding_service.llm_text_completion", fake_llm)
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = object()
    result = asyncio.run(classify_modules("含企业信息和危化品台账的文档", db))
    assert result == ["enterprise_info", "risk_chemical"]
