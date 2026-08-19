from unittest.mock import AsyncMock, MagicMock
import pytest


def test_build_section_prompt_forbids_inline_heading_numbering():
    """提示词不再要求正文使用 “N.” 编号，改为由导出自动生成，避免正文与导出标题重复。"""
    from app.routers.generation import _build_section_prompt

    prompt = _build_section_prompt("总则", {"name": "甲公司"}, section_number=2)
    assert "请在正文中使用" not in prompt
    assert "不要在正文中输出章节标题或编号" in prompt


def test_strip_section_heading_removes_leading_chapter_title():
    from app.services.plan_section_content import strip_section_heading

    assert strip_section_heading("第一章 总则\n\n正文内容") == "正文内容"
    assert strip_section_heading("<h1>第一章 总则</h1>\n\n正文内容") == "正文内容"
    assert strip_section_heading("1. 总则\n\n正文内容") == "正文内容"
    assert strip_section_heading("正文内容") == "正文内容"


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


def test_clear_generation_state_resets_active_flag(monkeypatch):
    import app.routers.generation as gen

    gen._active_generations["p1"] = True
    gen._failed_sections["p1"] = [{"section_key": "sec_1", "title": "总则"}]
    try:
        gen._clear_generation_state("p1")
        assert gen._active_generations.get("p1", False) is False
        assert gen._failed_sections.get("p1") == [{"section_key": "sec_1", "title": "总则"}]
    finally:
        gen._active_generations.pop("p1", None)
        gen._failed_sections.pop("p1", None)


@pytest.mark.asyncio
async def test_run_batch_generation_section_number_toggle(monkeypatch):
    """background 原行为：use_section_number=False 时不传 section_number 编号提示。"""
    from app.routers import generation as gen

    bg_db = AsyncMock()
    sec1 = MagicMock()
    sec1.section_key = "sec_1"
    sec2 = MagicMock()
    sec2.section_key = "sec_2"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [sec1, sec2]
    bg_db.execute.return_value = result

    captured = {}

    def fake_build(section_title, enterprise_data, **kwargs):
        captured["kwargs"] = kwargs
        return "prompt"

    async def fake_stream(prompt, cfg, plan_type, style=None, advanced=None):
        return "<p>ok</p>"

    monkeypatch.setattr(gen, "_build_section_prompt", fake_build)
    out = await gen._run_batch_generation(
        bg_db=bg_db,
        plan_id="p1",
        section_tuples=[("sec_1", "总则"), ("sec_2", "风险")],
        ai_config=MagicMock(),
        ent_data={},
        plan_type="comprehensive",
        accident_type=None,
        style_preference=None,
        advanced_overrides=None,
        stream_fn=fake_stream,
        use_section_number=False,
    )
    assert "section_number" not in captured["kwargs"]

    captured.clear()
    out = await gen._run_batch_generation(
        bg_db=bg_db,
        plan_id="p1",
        section_tuples=[("sec_1", "总则"), ("sec_2", "风险")],
        ai_config=MagicMock(),
        ent_data={},
        plan_type="comprehensive",
        accident_type=None,
        style_preference=None,
        advanced_overrides=None,
        stream_fn=fake_stream,
    )
    assert captured["kwargs"].get("section_number") == 2

    assert out["completed"] == 2
    assert out["failed"] == 0


@pytest.mark.asyncio
async def test_run_batch_generation_on_section_done_counts():
    """SSE 契约：每章完成后回调携带当前 completed/failed 计数。"""
    from app.routers import generation as gen

    bg_db = AsyncMock()
    secs = []
    for key in ("sec_1", "sec_2"):
        s = MagicMock()
        s.section_key = key
        secs.append(s)
    result = MagicMock()
    result.scalars.return_value.all.return_value = secs
    bg_db.execute.return_value = result

    done_events = []

    async def fake_stream(prompt, cfg, plan_type, style=None, advanced=None):
        return "<p>ok</p>"

    async def on_section_done(section_key, section_title, completed, failed):
        done_events.append((section_key, completed, failed))

    out = await gen._run_batch_generation(
        bg_db=bg_db,
        plan_id="p1",
        section_tuples=[("sec_1", "总则"), ("sec_2", "风险")],
        ai_config=MagicMock(),
        ent_data={},
        plan_type="comprehensive",
        accident_type=None,
        style_preference=None,
        advanced_overrides=None,
        stream_fn=fake_stream,
        on_section_done=on_section_done,
    )
    assert done_events == [("sec_1", 1, 0), ("sec_2", 2, 0)]
    assert out["completed"] == 2
    assert out["failed"] == 0


@pytest.mark.asyncio
async def test_run_batch_generation_cancel_not_counted_as_failure():
    """取消信号（_GenerationCancelled）应中断剩余章节且不计数失败。"""
    from app.routers import generation as gen

    bg_db = AsyncMock()
    secs = []
    for key in ("sec_1", "sec_2", "sec_3"):
        s = MagicMock()
        s.section_key = key
        secs.append(s)
    result = MagicMock()
    result.scalars.return_value.all.return_value = secs
    bg_db.execute.return_value = result

    calls = {"n": 0}

    async def fake_stream(prompt, cfg, plan_type, style=None, advanced=None):
        calls["n"] += 1
        return "<p>ok</p>"

    async def on_progress(section_key, section_title, i):
        if i == 1:
            raise gen._GenerationCancelled()

    with pytest.raises(gen._GenerationCancelled):
        await gen._run_batch_generation(
            bg_db=bg_db,
            plan_id="p1",
            section_tuples=[("sec_1", "总则"), ("sec_2", "风险"), ("sec_3", "措施")],
            ai_config=MagicMock(),
            ent_data={},
            plan_type="comprehensive",
            accident_type=None,
            style_preference=None,
            advanced_overrides=None,
            stream_fn=fake_stream,
            on_progress=on_progress,
        )
    # 只有第 1 章实际生成；取消未被当作失败
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_finalize_batch_result_sets_status_and_snapshot():
    """收尾公共函数：状态判定 + 自动版本快照 + commit，两个端点复用。"""
    from app.routers import generation as gen

    bg_db = AsyncMock()
    bg_db.add = MagicMock()  # 真实 add 为同步方法，避免 AsyncMock 协程警告
    p2 = MagicMock()
    p2.status = "generating"
    p2.current_version = 3
    p2.title = "预案"
    p2.style_preference = {}
    p2.advanced_prompt_overrides = {}

    sec = MagicMock()
    sec.content = "<p>ok</p>"
    sec_result = MagicMock()
    sec_result.scalars.return_value.all.return_value = [sec]
    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = p2
    bg_db.execute.side_effect = [sec_result, plan_result]

    out = await gen._finalize_batch_result(
        bg_db, "p1", completed=1, failed=0, failed_sections=[],
    )
    assert p2.status == "completed"
    assert p2.current_version == 4
    assert out == {
        "completed": 1,
        "failed": 0,
        "failed_sections": [],
        "version": 4,
    }
    bg_db.add.assert_called_once()
    bg_db.commit.assert_awaited_once()
