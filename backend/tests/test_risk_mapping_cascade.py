from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.enterprise_cleanup_service import (
    delete_enterprise_complete,
    delete_enterprise_risk_mapping,
    delete_floor_risk_mapping,
    floor_delete_counts,
)


def test_cleanup_service_imports():
    assert callable(delete_enterprise_risk_mapping)
    assert callable(delete_enterprise_complete)


def _scalar_result(n):
    m = MagicMock()
    m.scalar.return_value = n
    return m


def _ids_result(*ids):
    m = MagicMock()
    m.scalars.return_value.all.return_value = list(ids)
    return m


@pytest.mark.asyncio
async def test_delete_enterprise_complete_returns_counts():
    db = AsyncMock()
    db.execute.side_effect = [
        _scalar_result(1),  # floors
        _scalar_result(2),  # zones
        _scalar_result(3),  # objects
        _scalar_result(4),  # units
        _scalar_result(5),  # events
        _scalar_result(6),  # measures
        _ids_result(),      # object ids（为空，跳过下级删除）
        _ids_result(),      # zone ids（为空，跳过分区删除）
        MagicMock(),        # delete risk_objects
        MagicMock(),        # delete enterprise_floors
        MagicMock(),        # delete enterprise
    ]

    counts = await delete_enterprise_complete(db, "e-1")

    assert counts["floors"] == 1
    assert counts["zones"] == 2
    assert counts["objects"] == 3
    assert counts["units"] == 4
    assert counts["events"] == 5
    assert counts["measures"] == 6
    assert counts["total"] == 21


@pytest.mark.asyncio
async def test_delete_floor_risk_mapping_cascades_in_order():
    """楼层删除必须按 措施→事件→单元→对象→分区 依赖顺序级联清理。"""
    db = AsyncMock()

    await delete_floor_risk_mapping(db, "f-1")

    stmts = [str(c.args[0]) for c in db.execute.await_args_list]
    assert "risk_measures" in stmts[0]
    assert "risk_events" in stmts[1]
    assert "risk_units" in stmts[2]
    assert "risk_objects" in stmts[3]
    assert "risk_zones" in stmts[4]


@pytest.mark.asyncio
async def test_floor_delete_counts_summary():
    """删除确认需要展示待清理数量（分区/对象/单元/事件/措施）。"""
    db = AsyncMock()
    db.execute.side_effect = [
        _scalar_result(2),  # zones
        _scalar_result(3),  # objects
        _scalar_result(4),  # units
        _scalar_result(5),  # events
        _scalar_result(6),  # measures
    ]

    counts = await floor_delete_counts(db, "f-1")

    assert counts == {
        "zones": 2, "objects": 3, "units": 4, "events": 5, "measures": 6, "total": 20,
    }
