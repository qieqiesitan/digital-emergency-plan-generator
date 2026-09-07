"""test_llm_reasoning_cb.py"""
from unittest.mock import MagicMock

import pytest

from app.services import llm_client


def test_delta_texts_extracts_reasoning_and_content():
    assert llm_client._delta_texts({"reasoning_content": "想", "content": "答"}) == ("想", "答")
    assert llm_client._delta_texts({}) == ("", "")


@pytest.mark.asyncio
async def test_llm_chat_completion_stream_passes_reasoning_cb(monkeypatch):
    captured = {}

    async def fake_stream(base, payload, ai_config, timeout=120, max_retries=2, reasoning_cb=None):
        captured["reasoning_cb"] = reasoning_cb
        yield

    monkeypatch.setattr(llm_client, "_stream_response", fake_stream)
    cb = lambda piece: None
    gen = await llm_client.llm_chat_completion(
        [{"role": "user", "content": "hi"}],
        MagicMock(provider="x", model_name="m", temperature=0.7, max_tokens=512, top_p=1),
        stream=True, reasoning_cb=cb,
    )
    async for _ in gen:
        pass
    assert captured["reasoning_cb"] is cb
