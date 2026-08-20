"""批量生成准备块提取后的回归测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.routers.generation import _get_plan_or_404, _collect_batch_context


@pytest.mark.asyncio
async def test_get_plan_or_404_raises_when_missing():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    user = MagicMock(id="u1")
    with pytest.raises(HTTPException) as exc_info:
        await _get_plan_or_404("p-missing", user, db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_plan_or_404_returns_plan():
    db = AsyncMock()
    plan = MagicMock(id="p1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = plan
    db.execute.return_value = result
    user = MagicMock(id="u1")
    assert await _get_plan_or_404("p1", user, db) is plan


@pytest.mark.asyncio
async def test_collect_batch_context_requires_ai_config():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    p = MagicMock(enterprise_id="e1")
    with pytest.raises(HTTPException) as exc_info:
        await _collect_batch_context("p1", p, MagicMock(), db, MagicMock(id="u1"))
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
@patch("app.routers.generation._enrich_with_reports",
       new=AsyncMock(side_effect=lambda data, eid, db: data))
@patch("app.routers.generation.build_risk_management_context",
       new=AsyncMock(return_value={}))
async def test_collect_batch_context_filters_sections():
    db = AsyncMock()
    ai_cfg = MagicMock()
    ent = MagicMock()
    resources = [MagicMock()]
    sec1 = MagicMock(section_key="sec_1", title="总则")
    sec2 = MagicMock(section_key="sec_2", title="风险")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: ai_cfg),          # AIConfig
        MagicMock(scalar_one_or_none=lambda: ent),             # Enterprise
        MagicMock(scalars=lambda: MagicMock(all=lambda: resources)),          # EmergencyResource
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),                  # HazardousChemical
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),                  # EnterpriseMember
        MagicMock(scalars=lambda: MagicMock(all=lambda: [sec1, sec2])),       # PlanSection
    ])
    request = MagicMock()
    request.json = AsyncMock(return_value={"section_keys": ["sec_1"]})
    p = MagicMock(enterprise_id="e1")

    _, got_ai, ent_data, target = await _collect_batch_context("p1", p, request, db, MagicMock(id="u1"))
    assert got_ai is ai_cfg
    assert ent_data["name"] == ent.name
    assert [s.section_key for s in target] == ["sec_1"]


@pytest.mark.asyncio
@patch("app.routers.generation._enrich_with_reports",
       new=AsyncMock(side_effect=lambda data, eid, db: data))
@patch("app.routers.generation.build_risk_management_context",
       new=AsyncMock(return_value={}))
async def test_collect_batch_context_defaults_to_all_when_no_body():
    db = AsyncMock()
    ai_cfg = MagicMock()
    ent = MagicMock()
    sec1 = MagicMock(section_key="sec_1", title="总则")
    sec2 = MagicMock(section_key="sec_2", title="风险")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: ai_cfg),
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # HazardousChemical
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # EnterpriseMember
        MagicMock(scalars=lambda: MagicMock(all=lambda: [sec1, sec2])),
    ])
    request = MagicMock()
    request.json = AsyncMock(side_effect=Exception("no body"))
    p = MagicMock(enterprise_id="e1")

    _, _, _, target = await _collect_batch_context("p1", p, request, db, MagicMock(id="u1"))
    assert [s.section_key for s in target] == ["sec_1", "sec_2"]


@pytest.mark.asyncio
async def test_generate_batch_background_running_guard(monkeypatch):
    from app.routers import generation as gen
    db = AsyncMock()
    p = MagicMock(status="generating")
    result = MagicMock()
    result.scalar_one_or_none.return_value = p
    db.execute.return_value = result
    gen._active_generations["p1"] = True
    try:
        resp = await gen.generate_batch_background("p1", MagicMock(), MagicMock(id="u1"), db)
        assert resp == {"code": 0, "message": "正在生成中"}
    finally:
        gen._active_generations.pop("p1", None)


@pytest.mark.asyncio
@patch("app.routers.generation._enrich_with_reports",
       new=AsyncMock(side_effect=lambda data, eid, db: data))
@patch("app.routers.generation.build_risk_management_context",
       new=AsyncMock(return_value={}))
async def test_generate_batch_background_empty_sections():
    from app.routers import generation as gen
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: MagicMock(status="draft")),  # plan
        MagicMock(scalar_one_or_none=lambda: MagicMock()),                # ai_config
        MagicMock(scalar_one_or_none=lambda: MagicMock()),                # enterprise
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # resources
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # hazardous chemicals
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # enterprise members
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # sections -> empty
    ])
    request = MagicMock()
    request.json = AsyncMock(return_value=None)
    resp = await gen.generate_batch_background("p1", request, MagicMock(id="u1"), db)
    assert resp == {"code": 0, "message": "没有可生成的章节"}


@pytest.mark.asyncio
@patch("app.routers.generation._enrich_with_reports",
       new=AsyncMock(side_effect=lambda data, eid, db: data))
@patch("app.routers.generation.build_risk_management_context",
       new=AsyncMock(return_value={}))
async def test_generate_batch_sse_event_sequence(monkeypatch):
    from app.routers import generation as gen

    async def fake_run_batch_generation(**kwargs):
        # 模拟真实引擎：先发 progress，再发 section_done，返回统计
        await kwargs["on_progress"]("sec_1", "总则", 0)
        await kwargs["on_section_done"]("sec_1", "总则", 1, 0)
        return {"completed": 1, "failed": 0, "failed_sections": []}

    monkeypatch.setattr(gen, "_run_batch_generation", fake_run_batch_generation)
    monkeypatch.setattr(
        gen, "_finalize_batch_result",
        AsyncMock(return_value={"completed": 1, "failed": 0, "failed_sections": [], "version": 1}),
    )

    class _FakeSessionCtx:
        def __init__(self):
            self.bg_db = AsyncMock()

        async def __aenter__(self):
            return self.bg_db

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(gen, "async_session", lambda: _FakeSessionCtx())

    db = AsyncMock()
    sec1 = MagicMock(section_key="sec_1", title="总则")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: MagicMock(status="draft")),  # plan
        MagicMock(scalar_one_or_none=lambda: MagicMock()),                # ai_config
        MagicMock(scalar_one_or_none=lambda: MagicMock()),                # enterprise
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # resources
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # hazardous chemicals
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # enterprise members
        MagicMock(scalars=lambda: MagicMock(all=lambda: [sec1])),         # sections
    ])
    request = MagicMock()
    request.json = AsyncMock(return_value={"section_keys": ["sec_1"]})
    gen._failed_sections.pop("p1", None)
    try:
        resp = await gen.generate_batch("p1", request, MagicMock(id="u1"), db)
        body = "".join([c async for c in resp.body_iterator])
        assert '"type": "progress"' in body
        assert '"type": "section_done"' in body
        assert '"type": "batch_done"' in body
        assert "sec_1" in body
        assert "开始批量生成 1 个章节" in body
    finally:
        gen._active_generations.pop("p1", None)
        gen._failed_sections.pop("p1", None)
