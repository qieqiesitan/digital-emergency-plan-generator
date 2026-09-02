"""企业画像索引过期修复回归测试（B16 三连：删除触发重建 / 短文本清旧向量 / 风险源+评估写挂点）。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.enterprise_sub import create_risk_source, update_risk_source
from app.routers.risk_assessment import generate_risk_assessment, merge_risk_assessment
from app.schemas.risk_source import RiskSourceCreate, RiskSourceUpdate
from app.schemas.risk_assessment import RiskAssessmentGenerateRequest
from app.services.chat_dispatch import _generic_delete, _RES_CFG
from app.services.enterprise_knowledge_service import build_enterprise_index


def _risk_source_obj(**overrides):
    base = dict(
        id="rs1", enterprise_id="e1", name="锅炉", categories="火灾",
        location=None, description=None, likelihood=None, severity=None,
        risk_level="较大风险", control_measures=None, sort_order=0,
        created_at="2026-01-01T00:00:00",
    )
    base.update(overrides)
    return MagicMock(**base)


@pytest.mark.asyncio
async def test_generic_delete_resource_triggers_index_rebuild():
    """删除应急资源成功后必须触发企业画像重建（a）。"""
    db = AsyncMock()
    res = MagicMock(id="res1", enterprise_id="e1", name="灭火器")
    result = MagicMock()
    result.scalar_one_or_none.return_value = res
    db.execute.return_value = result
    with patch("app.services.chat_dispatch._schedule_enterprise_index_rebuild") as mock_schedule:
        out = await _generic_delete(db, MagicMock(id="u1"),
                                    {"resource_id": "res1"}, _RES_CFG)
    assert out["verified"] is True
    db.delete.assert_awaited_once_with(res)
    db.commit.assert_awaited_once()
    mock_schedule.assert_called_once_with("e1")


@pytest.mark.asyncio
async def test_build_index_short_text_clears_old_vectors(monkeypatch):
    """企业画像文本不足 20 字时删除旧向量，不残留过期数据（b）。"""
    db = AsyncMock()
    ent = MagicMock(id="e1")
    ent.name = "A"
    ent_result = MagicMock()
    ent_result.scalar_one_or_none.return_value = ent
    ctx_result = MagicMock()
    ctx_result.scalar_one_or_none.return_value = ent
    empty_scalars = MagicMock()
    empty_scalars.scalars.return_value.all.return_value = []
    db.execute.side_effect = [ent_result, ctx_result, empty_scalars, empty_scalars]
    monkeypatch.setattr(
        "app.services.risk_context_builder.build_risk_management_context",
        AsyncMock(return_value={"risk_sources": []}),
    )

    with patch("app.services.enterprise_knowledge_service.EnterpriseKnowledgeStore") as mock_store_cls:
        mock_store = mock_store_cls.return_value
        result = await build_enterprise_index("e1", db)
    assert result == 0
    mock_store.delete_enterprise.assert_called_once_with("e1")
    mock_store.index_enterprise.assert_not_called()


@pytest.mark.asyncio
async def test_create_risk_source_triggers_index_rebuild():
    """风险源 REST 创建后触发画像重建挂点（c）。"""
    db = AsyncMock()
    ent_result = MagicMock()
    ent_result.scalar_one_or_none.return_value = MagicMock(id="e1", user_id="u1")
    db.execute.return_value = ent_result
    created = []

    def _fake_add(obj):
        obj.id = "rs-new"
        obj.sort_order = 0
        obj.created_at = "2026-01-01T00:00:00"
        created.append(obj)

    db.add = MagicMock(side_effect=_fake_add)
    db.refresh.side_effect = lambda obj: None
    with patch("app.routers.enterprise_sub._schedule_enterprise_index_rebuild") as mock_schedule:
        resp = await create_risk_source(
            "e1", RiskSourceCreate(name="锅炉", categories=["火灾"]),
            MagicMock(id="u1"), db,
        )
    # 只校验挂点触发与 commit；响应模型字段由 DB 真实值填充，mock 不逐字段断言
    assert resp.data is not None
    db.commit.assert_awaited_once()
    mock_schedule.assert_called_once_with("e1")


@pytest.mark.asyncio
async def test_update_risk_source_triggers_index_rebuild():
    """风险源 REST 更新后触发画像重建挂点（c）。"""
    db = AsyncMock()
    src = _risk_source_obj()
    result = MagicMock()
    result.scalar_one_or_none.return_value = src
    db.execute.return_value = result
    db.refresh.side_effect = lambda obj: None
    with patch("app.routers.enterprise_sub._schedule_enterprise_index_rebuild") as mock_schedule:
        resp = await update_risk_source(
            "e1", "rs1", RiskSourceUpdate(name="新锅炉"),
            MagicMock(id="u1"), db,
        )
    assert resp.data is not None
    db.commit.assert_awaited_once()
    mock_schedule.assert_called_once_with("e1")


@pytest.mark.asyncio
async def test_merge_risk_assessment_triggers_index_rebuild():
    """评估报告合并（completed 写库）后触发画像重建挂点（c）。"""
    db = AsyncMock()
    db.add = MagicMock()
    ent_result = MagicMock()
    ent_result.scalar_one_or_none.return_value = MagicMock(id="e1", user_id="u1", name="测试企业")
    draft = MagicMock(id="r1", enterprise_id="e1", title="旧", status="draft",
                      content="", summary={}, generated_at=None)
    report_result = MagicMock()
    report_result.scalars.return_value.first.return_value = draft
    db.execute.side_effect = [ent_result, report_result]
    req = RiskAssessmentGenerateRequest(custom_instruction='[{"title": "第一章", "content": "内容"}]')
    with patch("app.routers.risk_assessment._schedule_enterprise_index_rebuild") as mock_schedule:
        resp = await merge_risk_assessment("e1", req, MagicMock(id="u1"), db)
    assert resp.data["status"] == "completed"
    db.commit.assert_awaited()
    mock_schedule.assert_called_once_with("e1")


@pytest.mark.asyncio
async def test_generate_risk_assessment_triggers_index_rebuild(monkeypatch):
    """评估报告生成（generating 建行）后触发画像重建挂点（c）。"""
    from app.routers import risk_assessment as ra

    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalar_one_or_none=lambda: None),  # generating 检查
        MagicMock(scalars=lambda: MagicMock(first=lambda: None)),  # 报告查询
    ]
    monkeypatch.setattr(ra, "build_risk_management_context", AsyncMock(return_value={"total_events": 1}))
    monkeypatch.setattr("app.services.ai_config_service.get_system_ai_config", AsyncMock(return_value=MagicMock()))
    with patch("app.routers.risk_assessment._schedule_enterprise_index_rebuild") as mock_schedule:
        resp = await generate_risk_assessment("e1", RiskAssessmentGenerateRequest(), MagicMock(id="u1"), db)
    assert resp is not None
    mock_schedule.assert_called_once_with("e1")
