from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.mark.asyncio
async def test_run_batch_generation_collects_failures():
    from app.routers.generation import _run_batch_generation

    bg_db = AsyncMock()
    ai_config = MagicMock()
    ent_data = {}

    # 构造章节查询结果
    sec1 = MagicMock()
    sec1.section_key = "sec_1"
    sec2 = MagicMock()
    sec2.section_key = "sec_2"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [sec1, sec2]
    bg_db.execute.return_value = result

    calls = {"n": 0}

    async def fake_stream(prompt, cfg, plan_type, style=None, advanced=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return "<p>ok</p>"

    out = await _run_batch_generation(
        bg_db=bg_db,
        plan_id="p1",
        section_tuples=[("sec_1", "总则"), ("sec_2", "风险")],
        ai_config=ai_config,
        ent_data=ent_data,
        plan_type="comprehensive",
        accident_type=None,
        style_preference=None,
        advanced_overrides=None,
        stream_fn=fake_stream,
    )
    assert out["completed"] == 1
    assert out["failed"] == 1
    assert out["failed_sections"] == [{"section_key": "sec_1", "title": "总则"}]
