from unittest.mock import MagicMock, AsyncMock
import pytest


@pytest.mark.asyncio
async def test_regenerate_missing_diagrams_counts():
    from app.routers.diagrams import regenerate_missing_diagrams
    db = AsyncMock()
    sec = MagicMock()
    sec.section_key = "sec_2"
    sec.diagram_svgs = {"risk_matrix": {"placeholder": True}}
    plan = MagicMock()
    plan.plan_type = "comprehensive"
    result = await regenerate_missing_diagrams(db, plan, [sec], {"risk_events": [
        {"name": "火灾", "likelihood": 3, "severity": 4, "risk_level": "较大"}
    ]})
    assert result["regenerated"] == 1
    assert result["placeholders_remaining"] == 0
