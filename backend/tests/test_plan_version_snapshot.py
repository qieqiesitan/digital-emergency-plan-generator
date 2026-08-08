from unittest.mock import MagicMock


def test_snapshot_includes_style_and_mermaid():
    from app.routers.versions import _build_snapshot
    plan = MagicMock()
    plan.title = "测试预案"
    plan.style_preference = {"formality": "formal"}
    plan.advanced_prompt_overrides = {"system_prompt_override": "x"}
    sec = MagicMock()
    sec.section_key = "sec_1"
    sec.title = "总则"
    sec.content = "<p>内容</p>"
    sec.ai_generated = True
    sec.mermaid_svgs = {"abc": "<svg/>"}
    snap = _build_snapshot(plan, [sec])
    assert snap["style_preference"] == {"formality": "formal"}
    assert snap["advanced_prompt_overrides"] == {"system_prompt_override": "x"}
    assert snap["sections"][0]["mermaid_svgs"] == {"abc": "<svg/>"}


def test_rollback_restores_style_and_mermaid():
    from app.routers.versions import _apply_snapshot
    plan = MagicMock()
    sec = MagicMock()
    sec.section_key = "sec_1"
    snap = {
        "style_preference": {"formality": "practical"},
        "advanced_prompt_overrides": None,
        "sections": [{"section_key": "sec_1", "content": "<p>旧</p>", "mermaid_svgs": {"h": "<svg/>"}}],
    }
    _apply_snapshot(plan, {"sec_1": sec}, snap)
    assert plan.style_preference == {"formality": "practical"}
    assert sec.content == "<p>旧</p>"
    assert sec.mermaid_svgs == {"h": "<svg/>"}


def test_rollback_legacy_snapshot_without_new_fields():
    from app.routers.versions import _apply_snapshot
    plan = MagicMock()
    sec = MagicMock()
    sec.section_key = "sec_1"
    snap = {"sections": [{"section_key": "sec_1", "content": "<p>旧</p>"}]}
    _apply_snapshot(plan, {"sec_1": sec}, snap)
    assert sec.content == "<p>旧</p>"
