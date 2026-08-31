"""test_plan_generation_service.py — service 抽取后仍可用。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.plan_generation_service import collect_batch_context, start_batch_generation


@pytest.mark.asyncio
async def test_collect_batch_context_returns_tuple():
    db = AsyncMock()
    p = MagicMock(enterprise_id="e1", plan_type="comprehensive", accident_type=None,
                  style_preference=None, advanced_prompt_overrides=None)
    cfg = MagicMock()
    ent_data = {"name": "企业A"}
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: p),                              # PlanProject
        MagicMock(scalar_one_or_none=lambda: MagicMock(enterprise_id="e1")),  # Enterprise
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),                 # EmergencyResource
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),                 # HazardousChemical
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),                 # PlanSection
    ])
    with patch("app.services.plan_generation_service.get_system_ai_config",
               new=AsyncMock(return_value=cfg)), \
         patch("app.services.plan_generation_service.build_risk_management_context",
               new=AsyncMock(return_value={})), \
         patch("app.routers.generation._collect_enterprise_data",
               return_value=ent_data), \
         patch("app.routers.generation._enrich_with_reports",
               new=AsyncMock(return_value=ent_data)), \
         patch("app.routers.generation._load_org_members",
               new=AsyncMock(return_value=[])):
        result = await collect_batch_context("p1", db, keys=None)
    assert result[0] is p
    assert result[1] is cfg
    assert result[2] == ent_data


@pytest.mark.asyncio
async def test_start_batch_generation_no_empty_sections():
    db = AsyncMock()
    p = MagicMock(enterprise_id="e1", plan_type="comprehensive", status="draft",
                  sections=[MagicMock(section_key="sec_1", content="<p>有内容</p>")])
    with patch("app.services.plan_generation_service.collect_batch_context",
               new=AsyncMock(return_value=(p, MagicMock(), {}, []))):
        out = await start_batch_generation("p1", db, MagicMock(id="u1"), keys=None)
    assert out["started"] is False
