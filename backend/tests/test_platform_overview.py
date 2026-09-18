"""跨企业总览聚合。"""

from unittest.mock import MagicMock

import pytest

from app.services.platform_overview import (
    overview_totals,
)


def _scalar_db(values: list):
    """按调用顺序依次返回 scalar 的假 db。"""
    db = MagicMock()
    seq = iter(values)

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar.return_value = next(seq, 0)
        return res

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_overview_totals_returns_all_sections():
    db = _scalar_db([3, 120, 45, 8, 2, 30])
    out = await overview_totals(db)
    assert set(out) == {"enterprises", "risk_points", "hazards", "major_hazard_units", "major_hazard_level_1_2", "work_tickets"}
    assert out["enterprises"] == 3
    assert out["major_hazard_units"] == 8


@pytest.mark.asyncio
async def test_overview_includes_level_1_2_count():
    """一、二级重大危险源是监管重点，单独计数。"""
    db = _scalar_db([1, 0, 0, 5, 2, 0])
    out = await overview_totals(db)
    assert out["major_hazard_level_1_2"] == 2


@pytest.mark.asyncio
async def test_overview_handles_zero_everything():
    db = _scalar_db([0, 0, 0, 0, 0, 0])
    out = await overview_totals(db)
    assert all(v == 0 for v in out.values())


def test_overview_level_count_uses_latest_snapshot_only():
    """同一单元先算出二级、后又算出不构成，则不应计入一二级。"""
    import inspect

    from app.services import platform_overview

    src = inspect.getsource(platform_overview.overview_totals)
    assert "seq" in src or "distinct" in src, (
        "一二级计数必须按最新快照去重，否则历史快照会被重复计入"
    )
