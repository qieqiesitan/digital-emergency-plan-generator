import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.onboarding_service import extract_candidates, classify_modules
from app.routers.onboarding import build_candidates_request


def test_extract_candidates_parses_llm_json(monkeypatch):
    async def fake_llm(messages, ai_config, timeout=120):
        return '{"items": [{"name": "甲醇", "cas_no": "67-56-1"}]}'
    monkeypatch.setattr("app.services.onboarding_service.llm_text_completion", fake_llm)

    async def fake_config(db):
        return object()  # 系统配置存在
    monkeypatch.setattr("app.services.onboarding_service.get_system_ai_config", fake_config)

    result = asyncio.run(extract_candidates("risk_chemical", "文本内容", AsyncMock()))
    assert result == [{"name": "甲醇", "cas_no": "67-56-1"}]


def test_classify_modules_parses_llm_json(monkeypatch):
    async def fake_llm(messages, ai_config, timeout=120):
        return '{"modules": ["enterprise_info", "risk_chemical"]}'
    monkeypatch.setattr("app.services.onboarding_service.llm_text_completion", fake_llm)

    async def fake_config(db):
        return object()  # 系统配置存在
    monkeypatch.setattr("app.services.onboarding_service.get_system_ai_config", fake_config)

    result = asyncio.run(classify_modules("含企业信息和危化品台账的文档", AsyncMock()))
    assert result == ["enterprise_info", "risk_chemical"]


def test_extract_raises_when_no_ai_config(monkeypatch):
    async def fake_config(db):
        return None
    monkeypatch.setattr("app.services.onboarding_service.get_system_ai_config", fake_config)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(extract_candidates("risk_chemical", "文本", AsyncMock()))
    assert exc_info.value.status_code == 400
    assert "系统未配置 AI 模型" in str(exc_info.value.detail)


def test_build_candidates_request_wraps_overview():
    req = build_candidates_request("企业概况", "生产甲醇、乙醇，有储罐区")
    assert req.answers[0].question == "企业概况"
    assert req.answers[0].answer == "生产甲醇、乙醇，有储罐区"
