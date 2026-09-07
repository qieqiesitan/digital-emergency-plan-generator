"""test_report_thinking.py"""
from unittest.mock import MagicMock

import pytest

from app.routers import risk_assessment as ra
from app.services.thinking_brief import CaptionThrottle


@pytest.mark.asyncio
async def test_stream_chapter_events_emits_caption_then_chunks(monkeypatch):
    async def fake_chunked(messages, ai_config, reasoning_cb=None):
        if reasoning_cb:
            reasoning_cb("需要结合风险源分布确定辨识范围。")
        yield "第一段"
        yield "第二段"

    monkeypatch.setattr(ra, "_stream_llm_with_messages_chunked", fake_chunked)
    events = []
    async for kind, payload in ra._stream_chapter_events(
        [], MagicMock(), CaptionThrottle("风险辨识"), "ch1",
    ):
        events.append((kind, payload))
    kinds = [k for k, _ in events]
    assert kinds[0] == "thinking"
    assert "chunk" in kinds
    assert ("end", "第一段第二段") in events


@pytest.mark.asyncio
async def test_stream_chapter_events_propagates_error(monkeypatch):
    async def boom(messages, ai_config, reasoning_cb=None):
        raise RuntimeError("boom")
        yield  # pragma: no cover - async generator 形态

    monkeypatch.setattr(ra, "_stream_llm_with_messages_chunked", boom)
    with pytest.raises(RuntimeError):
        async for _ in ra._stream_chapter_events(
            [], MagicMock(), CaptionThrottle("风险辨识"), "ch1",
        ):
            pass
