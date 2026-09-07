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


@pytest.mark.asyncio
async def test_run_batch_generation_default_branch_updates_progress(monkeypatch):
    from app.services import generation_progress as gp
    from app.services.plan_generation_service import run_batch_generation
    from app.routers import generation as gen

    gp.clear_progress("p-progress")
    bg_db = AsyncMock()
    sec1 = MagicMock()
    sec1.section_key = "sec_1"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [sec1]
    bg_db.execute.return_value = result

    async def fake_collect(prompt, ai_config, plan_type="*", style_preference=None,
                           advanced_overrides=None, payload_overrides=None, reasoning_cb=None,
                           on_content_start=None):
        if reasoning_cb:
            reasoning_cb("需要结合火灾风险源分布确定分工。")
        return "<p>ok</p>"

    monkeypatch.setattr(gen, "_collect_stream_text", fake_collect)
    monkeypatch.setattr(gen, "_build_section_prompt", lambda *a, **k: "prompt")
    monkeypatch.setattr(gen, "_collect_previous_context", lambda *a, **k: None)
    monkeypatch.setattr(gen, "_pre_render_mermaid_svgs", AsyncMock(return_value=[]))
    monkeypatch.setattr(gen, "_attach_diagrams", lambda *a, **k: None)

    await run_batch_generation(
        bg_db=bg_db, plan_id="p-progress",
        section_tuples=[("sec_1", "总则")], ai_config=MagicMock(), ent_data={},
        plan_type="comprehensive", use_section_number=False,
    )
    state = gp.get_progress("p-progress")
    assert state.get("section_key") == "sec_1"
    assert state.get("thinking_brief")
    gp.clear_progress("p-progress")
