import asyncio
from unittest.mock import MagicMock, AsyncMock, Mock

import pytest

from app.services.onboarding_service import compute_completion


def test_completion_all_done_returns_100():
    db = AsyncMock()
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = "地址"; ent.industry = "化工"
    ent.org_structure = [{"group_key": "cmd", "group_name": "指挥部",
                          "members": [{"name": "张三", "role": "chief", "phone": "138"}]}]
    ent.surrounding_info = {"nearby_units": [{"name": "加油站"}], "sensitive_targets": []}
    ent.risk_method_config = None

    def fake_execute(stmt):
        res = Mock()
        text = str(stmt)
        if "enterprises" in text:
            res.scalar_one_or_none.return_value = ent
        elif "risk_events" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="e1", chemical_id="c1")]
        elif "hazardous_chemicals" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="c1")]
        elif "emergency_resources" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="r1")]
        elif "risk_assessment_reports" in text:
            res.scalars.return_value.all.return_value = [MagicMock(status="completed")]
        elif "resource_investigation_reports" in text:
            res.scalars.return_value.all.return_value = [MagicMock(status="completed")]
        else:
            res.scalars.return_value.all.return_value = []
        return res

    db.execute.side_effect = fake_execute
    result = asyncio.run(compute_completion("e1", db))
    assert result["percent"] == 100
    assert all(m["done"] for m in result["modules"])


def test_completion_empty_enterprise():
    db = AsyncMock()
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = ""; ent.industry = ""
    ent.org_structure = []
    ent.surrounding_info = {"nearby_units": [], "sensitive_targets": []}
    ent.risk_method_config = None
    db.execute.side_effect = lambda stmt: Mock(
        scalar_one_or_none=lambda: ent,
        scalars=lambda: Mock(all=lambda: []),
    )
    result = asyncio.run(compute_completion("e1", db))
    assert result["percent"] == 0
