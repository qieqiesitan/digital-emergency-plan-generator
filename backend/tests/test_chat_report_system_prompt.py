"""test_chat_report_system_prompt.py — report_prompt 分支必须把 system_prompt 传给 LLM。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.routers.chat import _generate_report_text


@pytest.mark.asyncio
async def test_report_text_passes_system_prompt():
    captured = {}

    async def fake_collect(messages, ai_config):
        captured["messages"] = messages
        return "# 报告"

    with patch("app.routers.chat._collect_llm", new=fake_collect):
        out = await _generate_report_text(
            system_prompt="你是一位专业分析师", prompt="请生成报告",
            ai_config=AsyncMock(),
        )
    assert out == "# 报告"
    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][0]["content"] == "你是一位专业分析师"
    assert captured["messages"][1]["role"] == "user"


@pytest.mark.asyncio
async def test_report_text_without_system_prompt():
    captured = {}

    async def fake_collect(messages, ai_config):
        captured["messages"] = messages
        return "ok"

    with patch("app.routers.chat._collect_llm", new=fake_collect):
        await _generate_report_text(system_prompt="", prompt="hi", ai_config=AsyncMock())
    assert captured["messages"][0]["role"] == "user"
