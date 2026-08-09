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


def test_org_requires_commander_name():
    db = AsyncMock()
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = "地址"; ent.industry = "化工"
    ent.org_structure = [{"group_key": "rescue", "group_name": "抢险救援组",
                          "members": [{"name": "李四", "role": "组长"}]}]
    ent.surrounding_info = {"nearby_units": [], "sensitive_targets": []}
    ent.risk_method_config = None

    def fake_execute(stmt):
        res = Mock()
        text = str(stmt)
        if "enterprises" in text:
            res.scalar_one_or_none.return_value = ent
        elif "hazardous_chemicals" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="c1")]
        else:
            res.scalars.return_value.all.return_value = []
        return res

    db.execute.side_effect = fake_execute
    result = asyncio.run(compute_completion("e1", db))
    org = next(m for m in result["modules"] if m["key"] == "org_structure")
    assert not org["done"]
    risk = next(m for m in result["modules"] if m["key"] == "risk_chemical")
    assert not risk["done"]


def test_unit_level_event_counts_for_risk_chemical():
    db = AsyncMock()
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = "地址"; ent.industry = "化工"
    ent.org_structure = [{"group_key": "cmd", "group_name": "指挥部",
                          "members": [{"name": "张三", "role": "chief"}]}]
    ent.surrounding_info = {"nearby_units": [], "sensitive_targets": []}

    def fake_execute(stmt):
        res = Mock()
        text = str(stmt)
        if "enterprises" in text:
            res.scalar_one_or_none.return_value = ent
        elif "risk_units" in text:
            # 仅 unit 级事件存在，object 级事件为空
            res.scalars.return_value.all.return_value = [MagicMock(id="e1", chemical_id=None)]
        else:
            res.scalars.return_value.all.return_value = []
        return res

    db.execute.side_effect = fake_execute
    result = asyncio.run(compute_completion("e1", db))
    risk = next(m for m in result["modules"] if m["key"] == "risk_chemical")
    assert risk["done"]


def _completion_ent():
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = "地址"; ent.industry = "化工"
    ent.org_structure = [{"group_key": "cmd", "group_name": "指挥部",
                          "members": [{"name": "张三", "role": "chief", "phone": "138"}]}]
    ent.surrounding_info = {"nearby_units": [{"name": "加油站"}], "sensitive_targets": []}
    ent.risk_method_config = None
    return ent


def _skip_fake_execute(ent, ra_status, ri_status):
    """报告查询按 completed/skipped 分流，其余模块全部完成。"""
    ra_calls = {"n": 0}
    ri_calls = {"n": 0}

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
            # compute_completion 对每张报告表依次执行 completed、skipped 两次查询
            ra_calls["n"] += 1
            status = "completed" if ra_calls["n"] == 1 else "skipped"
            rows = [MagicMock(status=status)] if status == ra_status else []
            res.scalars.return_value.all.return_value = rows
        elif "resource_investigation_reports" in text:
            ri_calls["n"] += 1
            status = "completed" if ri_calls["n"] == 1 else "skipped"
            rows = [MagicMock(status=status)] if status == ri_status else []
            res.scalars.return_value.all.return_value = rows
        else:
            res.scalars.return_value.all.return_value = []
        return res
    return fake_execute


def test_reports_all_skipped_redistributes_weights_and_percent_100():
    db = AsyncMock()
    db.execute.side_effect = _skip_fake_execute(_completion_ent(), "skipped", "skipped")
    result = asyncio.run(compute_completion("e1", db))
    modules = {m["key"]: m for m in result["modules"]}
    assert result["percent"] == 100
    assert modules["risk_chemical"]["weight"] == 40
    assert modules["resources"]["weight"] == 25
    assert modules["reports"]["weight"] == 0
    assert modules["reports"]["done"] is True


def test_risk_report_skipped_only_redistributes():
    db = AsyncMock()
    db.execute.side_effect = _skip_fake_execute(_completion_ent(), "skipped", "completed")
    result = asyncio.run(compute_completion("e1", db))
    modules = {m["key"]: m for m in result["modules"]}
    assert result["percent"] == 100
    assert modules["risk_chemical"]["weight"] == 40
    assert modules["resources"]["weight"] == 15
    assert modules["reports"]["weight"] == 10
    assert modules["reports"]["done"] is True


def test_reports_skipped_then_generated_reverts_weights():
    """先跳过后来又生成 completed 报告时，跳过自动失效，权重不调整。"""
    db = AsyncMock()
    db.execute.side_effect = _skip_fake_execute(_completion_ent(), "completed", "completed")
    result = asyncio.run(compute_completion("e1", db))
    modules = {m["key"]: m for m in result["modules"]}
    assert result["percent"] == 100
    assert modules["risk_chemical"]["weight"] == 30
    assert modules["resources"]["weight"] == 15
    assert modules["reports"]["weight"] == 20
