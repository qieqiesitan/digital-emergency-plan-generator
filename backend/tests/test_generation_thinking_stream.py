"""test_generation_thinking_stream.py"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers import generation as gen


@pytest.mark.asyncio
async def test_stream_llm_chunks_forwards_reasoning_cb(monkeypatch):
    captured = {}

    async def fake_completion(messages, ai_config, stream=True, timeout=120,
                              payload_overrides=None, reasoning_cb=None):
        captured["reasoning_cb"] = reasoning_cb

        async def _gen():
            yield "正文"

        return _gen()

    monkeypatch.setattr(gen, "llm_chat_completion", fake_completion)
    cb = lambda piece: None
    chunks = []
    async for c in gen._stream_llm_chunks("p", MagicMock(), reasoning_cb=cb):
        chunks.append(c)
    assert chunks == ["正文"]
    assert captured["reasoning_cb"] is cb


@pytest.mark.asyncio
async def test_collect_stream_text_concatenates_chunks(monkeypatch):
    calls = {"n": 0}

    async def fake_chunks(prompt, ai_config, plan_type="*", style_preference=None,
                          advanced_overrides=None, payload_overrides=None, reasoning_cb=None):
        calls["n"] += 1
        for piece in ("<p>一", "段</p>"):
            yield piece

    monkeypatch.setattr(gen, "_stream_llm_chunks", fake_chunks)
    text = await gen._collect_stream_text("p", MagicMock(), "comprehensive")
    assert text == "<p>一段</p>"
    assert calls["n"] == 1
