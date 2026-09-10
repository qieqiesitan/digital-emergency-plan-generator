"""test_report_authority_merge.py"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers import risk_assessment as ra


@pytest.mark.asyncio
async def test_merge_writes_data_conflicts(monkeypatch):
    ent = MagicMock(id="e1")
    report = MagicMock(id="r1", summary={}, style_preference=None, content="")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(first=lambda: report)),
    ])
    monkeypatch.setattr(
        ra, "build_risk_management_context",
        AsyncMock(return_value={"risk_sources": [
            {"name": "燃气灶台", "risk_level": "较大", "categories": "火灾"},
        ]}),
    )
    monkeypatch.setattr(ra, "_schedule_enterprise_index_rebuild", lambda *a, **k: None)
    from app.services import report_four_color_service
    monkeypatch.setattr(
        report_four_color_service, "render_enterprise_four_color_images",
        AsyncMock(return_value=[]),
    )
    request = MagicMock()
    request.custom_instruction = json.dumps([
        {
            "key": "ch5_conclusion", "title": "五、结论",
            "content": (
                "正文内容\n"
                '{"risk_source_count":0,"risk_level_distribution":'
                '{"重大":0,"较大":0,"一般":0,"低":0},"key_findings":[],'
                '"overall_assessment":"无较大风险"}'
            ),
        }
    ])
    await ra.merge_risk_assessment(
        "e1", request, current_user=MagicMock(id="u1"), db=db,
    )
    conflicts = report.summary["data_conflicts"]
    assert any(c["type"] == "count_mismatch" for c in conflicts)
    assert any(c["type"] == "level_mismatch" for c in conflicts)
