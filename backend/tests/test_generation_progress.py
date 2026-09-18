"""test_generation_progress.py —— W2：进度状态跨 worker（异步读、同步写 + 去抖落库）。"""
import pytest

from app.services import generation_progress as gp


@pytest.mark.asyncio
async def test_set_get_clear_roundtrip():
    await gp.clear_progress("p1")
    assert await gp.get_progress("p1") == {}
    gp.set_progress("p1", phase="thinking", section_key="sec_1", index=1, total=7)
    state = await gp.get_progress("p1")
    assert state["phase"] == "thinking"
    assert state["section_key"] == "sec_1"
    assert state["index"] == 1 and state["total"] == 7
    assert "updated_at" in state
    await gp.clear_progress("p1")
    assert await gp.get_progress("p1") == {}


@pytest.mark.asyncio
async def test_set_merges_fields_and_refreshes_updated_at():
    await gp.clear_progress("p1")
    gp.set_progress("p1", phase="thinking")
    first = (await gp.get_progress("p1"))["updated_at"]
    gp.set_progress("p1", thinking_brief="要点")
    state = await gp.get_progress("p1")
    assert state["phase"] == "thinking"
    assert state["thinking_brief"] == "要点"
    assert state["updated_at"] >= first
    await gp.clear_progress("p1")
