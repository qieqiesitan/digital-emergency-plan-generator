"""test_prompt_layering.py — 单配置下的任务分层参数（D3：不引入多模型）。"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent.agents import LAYER_PARAMS


def test_layer_params_exist():
    assert "review" in LAYER_PARAMS
    assert "generate" in LAYER_PARAMS


def test_review_more_precise_than_generate():
    assert LAYER_PARAMS["review"]["temperature"] < LAYER_PARAMS["generate"]["temperature"]


@pytest.mark.asyncio
async def test_review_revision_passes_review_layer_overrides(monkeypatch):
    """审查修订的 LLM 调用必须携带 LAYER_PARAMS['review']（温度 0.2 覆盖）。"""
    from app.routers import generation as gen
    from app.routers import review

    captured = {}

    async def fake_stream_llm(prompt, ai_config, plan_type="*", style_preference=None,
                              advanced_overrides=None, payload_overrides=None):
        captured["payload_overrides"] = payload_overrides
        return "<p>修订后的章节内容，已经足够长，满足审查修订校验的最低长度要求。</p>"

    monkeypatch.setattr(gen, "_stream_llm", fake_stream_llm)
    monkeypatch.setattr(
        "app.services.ai_config_service.get_system_ai_config",
        AsyncMock(return_value=MagicMock()),
    )
    section = MagicMock()
    section.content = "<p>原内容</p>"
    plan = MagicMock()
    plan.plan_type = "comprehensive"

    content = await review._apply_llm_revision(
        section, "问题描述", plan, {"name": "甲公司"}, AsyncMock()
    )
    assert content
    assert captured["payload_overrides"] == LAYER_PARAMS["review"]


@pytest.mark.asyncio
async def test_generate_default_branch_passes_generate_layer_overrides(monkeypatch):
    """批量生成默认（内部流式）分支必须向 _collect_stream_text 传 LAYER_PARAMS['generate']。"""
    from app.routers import generation as gen
    from app.services import plan_generation_service as svc

    bg_db = AsyncMock()
    sec1 = MagicMock()
    sec1.section_key = "sec_1"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [sec1]
    bg_db.execute.return_value = result

    captured = {}

    async def fake_collect(prompt, ai_config, plan_type="*", style_preference=None,
                           advanced_overrides=None, payload_overrides=None,
                           reasoning_cb=None, on_content_start=None):
        captured["payload_overrides"] = payload_overrides
        return "<p>ok</p>"

    monkeypatch.setattr(gen, "_collect_stream_text", fake_collect)
    monkeypatch.setattr(gen, "_build_section_prompt", lambda *a, **k: "prompt")
    monkeypatch.setattr(gen, "_collect_previous_context", lambda *a, **k: None)
    monkeypatch.setattr(gen, "_pre_render_mermaid_svgs", AsyncMock(return_value=[]))
    monkeypatch.setattr(gen, "_attach_diagrams", lambda *a, **k: None)

    out = await svc.run_batch_generation(
        bg_db=bg_db,
        plan_id="p1",
        section_tuples=[("sec_1", "总则")],
        ai_config=MagicMock(),
        ent_data={},
        plan_type="comprehensive",
        accident_type=None,
        style_preference=None,
        advanced_overrides=None,
        use_section_number=False,
    )
    assert out["completed"] == 1
    assert captured["payload_overrides"] == LAYER_PARAMS["generate"]


def test_layer_params_do_not_force_max_tokens():
    """推理型模型下硬性 max_tokens 会让 reasoning 耗尽预算、正文为空；
    输出长度应交给 AI 配置（admin 可控），分层只保留温度等风格差异。"""
    for params in LAYER_PARAMS.values():
        assert "max_tokens" not in params
