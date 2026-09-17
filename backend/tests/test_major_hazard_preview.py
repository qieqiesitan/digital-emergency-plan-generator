"""预览端点：只计算、不写快照。

这是"实时预览 + 手动固化"交互的后端支撑：前端改数字时调 preview（不落库），
点"固化"才调 compute（写不可变快照）。快照是审计凭证，不能被预览污染。
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.major_hazard_service import preview_unit_calculation


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


def _db(unit, chemicals, added):
    db = MagicMock()
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit] if unit else [])
        if "major_hazard_unit_chemicals" in text:
            return _Result(chemicals)
        return _Result([])

    db.execute = execute
    return db


def _unit():
    u = MagicMock()
    u.id = "u1"
    return u


def _chem(name, q, Q, beta):
    c = MagicMock()
    c.chemical_name = name
    c.q_design_max = Decimal(str(q))
    c.critical_quantity_t = Decimal(str(Q))
    c.beta = Decimal(str(beta))
    return c


@pytest.mark.asyncio
async def test_preview_returns_result_without_writing_snapshot():
    """预览必须算出结果，且一行都不写库——这是"手动固化"语义的前提。"""
    added = []
    db = _db(_unit(), [_chem("氯", 5, 5, 4), _chem("氨", 5, 10, 2)], added)

    out = await preview_unit_calculation(db, unit_id="u1", exposed_population=60)

    assert out["s_value"] == 1.5
    assert out["r_value"] == 7.5
    assert out["alpha"] == 1.5
    assert out["is_major_hazard"] is True
    assert out["level"] == "四级"
    assert out["formula_version"] == "GB18218-2018"
    assert len(out["chemicals"]) == 2
    assert added == [], "预览绝不能写快照"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_rejects_empty_unit():
    from app.services.major_hazard_service import MajorHazardRuleError

    added = []
    db = _db(_unit(), [], added)
    with pytest.raises(MajorHazardRuleError):
        await preview_unit_calculation(db, unit_id="u1", exposed_population=0)
    assert added == []


@pytest.mark.asyncio
async def test_preview_rejects_missing_unit():
    from app.services.major_hazard_service import MajorHazardRuleError

    added = []
    db = _db(None, [], added)
    with pytest.raises(MajorHazardRuleError):
        await preview_unit_calculation(db, unit_id="nope", exposed_population=0)
