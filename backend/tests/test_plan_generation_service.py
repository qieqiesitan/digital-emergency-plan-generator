"""test_plan_generation_service.py — service 抽取后仍可用。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.selectable import Select

from app.services.plan_generation_service import (
    _run_background, collect_batch_context, start_batch_generation,
)


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


@pytest.mark.asyncio
async def test_start_batch_generation_atomic_update_race_lost():
    """B24：并发双开时原子 UPDATE rowcount=0，应返回"正在生成中"且不创建后台任务。"""
    db = AsyncMock()
    p = MagicMock(enterprise_id="e1", plan_type="comprehensive", status="draft")
    db.execute = AsyncMock(return_value=MagicMock(rowcount=0))
    with patch("app.services.plan_generation_service.collect_batch_context",
               new=AsyncMock(return_value=(p, MagicMock(), {}, [MagicMock(
                   section_key="sec_1", title="章一", content="", )]))), \
         patch("app.services.plan_generation_service.asyncio.create_task",
               new=MagicMock()) as create_task:
        out = await start_batch_generation("p1", db, MagicMock(id="u1"), keys=None)
    assert out["started"] is False
    assert "正在生成中" in out["message"]
    create_task.assert_not_called()
    db_result = db.execute.call_args.args[0]
    assert isinstance(db_result, Update)


@pytest.mark.asyncio
async def test_start_batch_generation_atomic_update_acquired():
    """B24：原子 UPDATE rowcount=1 时正常置位并注册后台任务。"""
    db = AsyncMock()
    p = MagicMock(enterprise_id="e1", plan_type="comprehensive", status="draft",
                  accident_type=None, style_preference=None, advanced_prompt_overrides=None)
    cfg = MagicMock()
    ent_data = {"name": "企业A"}
    db.execute = AsyncMock(return_value=MagicMock(rowcount=1))
    with patch("app.services.plan_generation_service.collect_batch_context",
               new=AsyncMock(return_value=(p, cfg, ent_data, [MagicMock(
                   section_key="sec_1", title="章一", content="", )]))), \
         patch("app.services.plan_generation_service.asyncio.create_task",
               new=MagicMock()) as create_task:
        out = await start_batch_generation("p1", db, MagicMock(id="u1"), keys=None)
    assert out["started"] is True
    create_task.assert_called_once()
    db_result = db.execute.call_args.args[0]
    assert isinstance(db_result, Update)


@pytest.mark.asyncio
async def test_run_background_exception_resets_status_to_draft():
    """B5：后台生成异常后用独立 async_session 把 status 回滚为 draft。"""
    plan_id = "p1"
    cancel_db = AsyncMock()
    p_cancel = MagicMock(status="generating")
    cancel_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: p_cancel))

    class FakeAsyncSession:
        def __call__(self):
            return self

        async def __aenter__(self):
            return cancel_db

        async def __aexit__(self, *args):
            return False

    with patch("app.services.plan_generation_service.run_batch_generation",
               new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("app.services.plan_generation_service.async_session",
               new=FakeAsyncSession()):
        await _run_background(
            plan_id, "comprehensive", None, None, None, [], MagicMock(), {},
        )
    assert p_cancel.status == "draft"
    cancel_db.commit.assert_awaited()
    executed_stmt = cancel_db.execute.call_args.args[0]
    assert isinstance(executed_stmt, Select)
