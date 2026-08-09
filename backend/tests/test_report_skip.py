import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.resource_investigation import ResourceInvestigationReport
from app.models.risk_assessment import RiskAssessmentReport
from app.routers.resource_investigation import skip_resource_investigation
from app.routers.risk_assessment import skip_risk_assessment


def _ent_result():
    return MagicMock(scalar_one_or_none=lambda: MagicMock(id="e1", user_id="u1"))


def _empty_result():
    return MagicMock(scalar_one_or_none=lambda: None)


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
    db.execute.side_effect = [_ent_result(), _empty_result(), _empty_result(), _empty_result()]
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
    db.execute.side_effect = [_ent_result(), _empty_result(), _empty_result(), _ent_result()]
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
    with pytest.raises(Exception) as exc:
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
    with pytest.raises(Exception) as exc:
        asyncio.run(func("e1", MagicMock(id="u1"), db))
    assert exc.value.status_code == 400
    assert "生成中" in str(exc.value.detail)
    db.add.assert_not_called()
