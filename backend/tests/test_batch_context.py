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
        MagicMock(scalars=lambda: MagicMock(all=lambda: [sec1, sec2])),
    ])
    request = MagicMock()
    request.json = AsyncMock(side_effect=Exception("no body"))
    p = MagicMock(enterprise_id="e1")

    _, _, _, target = await _collect_batch_context("p1", p, request, db, MagicMock(id="u1"))
    assert [s.section_key for s in target] == ["sec_1", "sec_2"]
