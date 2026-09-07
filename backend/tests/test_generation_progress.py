"""test_generation_progress.py"""
from app.services import generation_progress as gp


def test_set_get_clear_roundtrip():
    gp.clear_progress("p1")
    assert gp.get_progress("p1") == {}
    gp.set_progress("p1", phase="thinking", section_key="sec_1", index=1, total=7)
    state = gp.get_progress("p1")
    assert state["phase"] == "thinking"
    assert state["section_key"] == "sec_1"
    assert state["index"] == 1 and state["total"] == 7
    assert "updated_at" in state
    gp.clear_progress("p1")
    assert gp.get_progress("p1") == {}


def test_set_merges_fields_and_refreshes_updated_at():
    gp.clear_progress("p1")
    gp.set_progress("p1", phase="thinking")
    first = gp.get_progress("p1")["updated_at"]
    gp.set_progress("p1", thinking_brief="要点")
    state = gp.get_progress("p1")
    assert state["phase"] == "thinking"
    assert state["thinking_brief"] == "要点"
    assert state["updated_at"] >= first
    gp.clear_progress("p1")
