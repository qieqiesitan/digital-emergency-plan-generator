import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.resource_investigation import ResourceInvestigationReport
from app.models.risk_assessment import RiskAssessmentReport
from app.routers.resource_investigation import (
    generate_resource_investigation,
    merge_resource_investigation,
    skip_resource_investigation,
)
from app.routers.risk_assessment import (
    generate_risk_assessment,
    merge_risk_assessment,
    skip_risk_assessment,
)
from app.schemas.resource_investigation import ResourceInvestigationGenerateRequest
from app.schemas.risk_assessment import RiskAssessmentGenerateRequest


def _ent_result():
    return MagicMock(scalar_one_or_none=lambda: MagicMock(id="e1", user_id="u1"))


def _empty_result():
    return MagicMock(scalar_one_or_none=lambda: None)


def _first_result(obj=None):
    return MagicMock(scalars=lambda: MagicMock(first=lambda: obj))


@pytest.mark.parametrize(
    "func, report_cls",
    [
        (skip_risk_assessment, RiskAssessmentReport),
        (skip_resource_investigation, ResourceInvestigationReport),
    ],
)
def test_skip_report_creates_skipped_record(func, report_cls):
    db = AsyncMock()
    db.add = MagicMock()  # db.add 是同步方法
    db.execute.side_effect = [
        _ent_result(),      # 企业
        _empty_result(),    # generating
        _empty_result(),    # completed
        _first_result(None),  # 非 skipped 记录（无）
        _first_result(None),  # skipped 记录（无）
    ]
    resp = asyncio.run(func("e1", MagicMock(id="u1"), db))
    assert "已跳过" in resp.message
    added = db.add.call_args[0][0]
    assert isinstance(added, report_cls)
    assert added.enterprise_id == "e1"
    assert added.status == "skipped"
    db.commit.assert_awaited_once()


@pytest.mark.parametrize(
    "func",
    [skip_risk_assessment, skip_resource_investigation],
)
def test_skip_report_idempotent_when_already_skipped(func):
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [
        _ent_result(),
        _empty_result(),
        _empty_result(),
        _first_result(None),
        _first_result(MagicMock(id="r1", status="skipped")),
    ]
    resp = asyncio.run(func("e1", MagicMock(id="u1"), db))
    assert "已跳过" in resp.message
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.parametrize(
    "func",
    [skip_risk_assessment, skip_resource_investigation],
)
def test_skip_report_rejects_when_completed(func):
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [_ent_result(), _empty_result(), _ent_result()]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(func("e1", MagicMock(id="u1"), db))
    assert exc.value.status_code == 400
    assert "无需跳过" in str(exc.value.detail)
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "func",
    [skip_risk_assessment, skip_resource_investigation],
)
def test_skip_report_rejects_when_generating(func):
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [_ent_result(), _ent_result()]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(func("e1", MagicMock(id="u1"), db))
    assert exc.value.status_code == 400
    assert "生成中" in str(exc.value.detail)
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "func, report_cls",
    [
        (skip_risk_assessment, RiskAssessmentReport),
        (skip_resource_investigation, ResourceInvestigationReport),
    ],
)
def test_skip_report_rewrites_draft_to_skipped_without_duplicate(func, report_cls):
    """draft（生成完成未合并）+ skip → 改写该行状态，不再新增第二条记录。"""
    db = AsyncMock()
    db.add = MagicMock()
    draft = MagicMock(id="r1", enterprise_id="e1", status="draft")
    db.execute.side_effect = [
        _ent_result(),
        _empty_result(),
        _empty_result(),
        _first_result(draft),
    ]
    resp = asyncio.run(func("e1", MagicMock(id="u1"), db))
    assert "已跳过" in resp.message
    assert draft.status == "skipped"
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_risk_assessment_no_500_with_duplicate_rows(monkeypatch):
    """已有脏数据（draft + skipped 两行）时生成不再 MultipleResultsFound。"""
    from app.routers import risk_assessment as ra

    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    draft = MagicMock(id="r1", enterprise_id="e1", title="旧", status="draft")
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalar_one_or_none=lambda: None),  # generating 检查
        _first_result(draft),  # 报告查询：skipped 被过滤，仅命中 draft
    ]
    monkeypatch.setattr(ra, "build_risk_management_context", AsyncMock(return_value={"total_events": 1}))
    monkeypatch.setattr("app.services.ai_config_service.get_system_ai_config", AsyncMock(return_value=MagicMock()))
    resp = await generate_risk_assessment("e1", RiskAssessmentGenerateRequest(), MagicMock(id="u1"), db)
    assert isinstance(resp, EventSourceResponse)
    assert draft.status == "generating"


@pytest.mark.asyncio
async def test_generate_resource_investigation_no_500_with_duplicate_rows(monkeypatch):
    from app.routers import resource_investigation as ri

    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    draft = MagicMock(id="r1", enterprise_id="e1", title="旧", status="draft")
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [MagicMock()])),  # 资源检查
        MagicMock(scalar_one_or_none=lambda: None),  # generating 检查
        _first_result(draft),  # 报告查询：skipped 被过滤，仅命中 draft
    ]
    monkeypatch.setattr("app.services.ai_config_service.get_system_ai_config", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(ri, "build_resource_investigation_context", AsyncMock(return_value={}))
    resp = await generate_resource_investigation("e1", ResourceInvestigationGenerateRequest(), MagicMock(id="u1"), db)
    assert isinstance(resp, EventSourceResponse)
    assert draft.status == "generating"


@pytest.mark.asyncio
async def test_merge_risk_assessment_no_500_with_duplicate_rows():
    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    draft = MagicMock(id="r1", enterprise_id="e1", title="旧", status="draft", summary={})
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        _first_result(draft),
    ]
    req = RiskAssessmentGenerateRequest(custom_instruction='[{"title": "第一章", "content": "内容"}]')
    resp = await merge_risk_assessment("e1", req, MagicMock(id="u1"), db)
    assert resp.data["status"] == "completed"


@pytest.mark.asyncio
async def test_merge_resource_investigation_no_500_with_duplicate_rows():
    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    draft = MagicMock(id="r1", enterprise_id="e1", title="旧", status="draft", summary={})
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        _first_result(draft),
    ]
    req = ResourceInvestigationGenerateRequest(custom_instruction='[{"title": "第一章", "content": "内容"}]')
    resp = await merge_resource_investigation("e1", req, MagicMock(id="u1"), db)
    assert resp.data["status"] == "completed"


@pytest.mark.asyncio
async def test_generate_risk_assessment_after_skip_creates_new_row(monkeypatch):
    """跳过（仅剩 skipped 行）后再生成 → 新建行，不 500。"""
    from app.routers import risk_assessment as ra

    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalar_one_or_none=lambda: None),  # generating 检查
        _first_result(None),  # skipped 被过滤，未命中
    ]
    monkeypatch.setattr(ra, "build_risk_management_context", AsyncMock(return_value={"total_events": 1}))
    monkeypatch.setattr("app.services.ai_config_service.get_system_ai_config", AsyncMock(return_value=MagicMock()))
    resp = await generate_risk_assessment("e1", RiskAssessmentGenerateRequest(), MagicMock(id="u1"), db)
    assert isinstance(resp, EventSourceResponse)
    added = db.add.call_args[0][0]
    assert isinstance(added, RiskAssessmentReport)
    assert added.status == "generating"


@pytest.mark.asyncio
async def test_generate_resource_investigation_after_skip_creates_new_row(monkeypatch):
    from app.routers import resource_investigation as ri

    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [MagicMock()])),  # 资源检查
        MagicMock(scalar_one_or_none=lambda: None),  # generating 检查
        _first_result(None),  # skipped 被过滤，未命中
    ]
    monkeypatch.setattr("app.services.ai_config_service.get_system_ai_config", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(ri, "build_resource_investigation_context", AsyncMock(return_value={}))
    resp = await generate_resource_investigation("e1", ResourceInvestigationGenerateRequest(), MagicMock(id="u1"), db)
    assert isinstance(resp, EventSourceResponse)
    added = db.add.call_args[0][0]
    assert isinstance(added, ResourceInvestigationReport)
    assert added.status == "generating"


@pytest.mark.asyncio
async def test_merge_risk_assessment_after_skip_no_500():
    """跳过后再合并：无有效行时新建 draft 并完成，不 500。"""
    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        _first_result(None),
    ]
    req = RiskAssessmentGenerateRequest(custom_instruction='[{"title": "第一章", "content": "内容"}]')
    resp = await merge_risk_assessment("e1", req, MagicMock(id="u1"), db)
    assert resp.data["status"] == "completed"


@pytest.mark.asyncio
async def test_merge_resource_investigation_after_skip_no_500():
    """跳过后再合并：无有效行时返回 404（而非 500）。"""
    db = AsyncMock()
    db.add = MagicMock()
    ent = MagicMock(id="e1", user_id="u1", name="测试企业")
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        _first_result(None),
    ]
    req = ResourceInvestigationGenerateRequest(custom_instruction='[{"title": "第一章", "content": "内容"}]')
    with pytest.raises(HTTPException) as exc:
        await merge_resource_investigation("e1", req, MagicMock(id="u1"), db)
    assert exc.value.status_code == 404
