from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.enterprise_cleanup_service import delete_enterprise_complete, delete_enterprise_risk_mapping


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
