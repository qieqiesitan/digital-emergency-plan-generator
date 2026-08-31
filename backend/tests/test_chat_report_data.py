"""test_chat_report_data.py — 报告主题采集器。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _collect_risk_distribution, _collect_resource_coverage


@pytest.mark.asyncio
async def test_collect_risk_distribution_groups_by_level():
    ctx = {"risk_sources": [
        {"name": "锅炉", "risk_level": "重大风险"},
        {"name": "配电柜", "risk_level": "重大风险"},
        {"name": "化学品库", "risk_level": "较大风险"},
    ]}
    db = AsyncMock()
    ents = [MagicMock(id="e1")]
    result = MagicMock()
    result.scalars.return_value.all.return_value = ents
    db.execute.return_value = result
    with patch("app.services.chat_dispatch.build_risk_management_context",
               new=AsyncMock(return_value=ctx)):
        out = await _collect_risk_distribution(db, MagicMock(id="u1"))
    assert out["重大风险"] == 2
    assert out["较大风险"] == 1


@pytest.mark.asyncio
async def test_collect_resource_coverage_counts_categories():
    rows = [MagicMock(category="灭火器"), MagicMock(category="灭火器"),
            MagicMock(category="急救箱")]
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result
    out = await _collect_resource_coverage(db, MagicMock(id="u1"))
    assert out["灭火器"] == 2
    assert out["急救箱"] == 1
