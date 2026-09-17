"""计算编排服务测试：β 规则选取、快照递增、可复算。"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.major_hazard_service import (
    MajorHazardRuleError,
    compute_unit_snapshot,
    replay_snapshot,
    resolve_beta,
)


def _beta_row(name=None, symbol=None, beta="4.0", table="3"):
    r = MagicMock()
    r.chemical_name = name
    r.symbol = symbol
    r.beta = Decimal(beta)
    r.source_table = table
    return r


def test_resolve_beta_prefers_table3_by_name():
    """GB 18218 4.3.2：表3（毒性气体按名称）优先于表4（按危险性类别）。"""
    rows = [_beta_row(name="氯", beta="4.0", table="3")]
    beta, source = resolve_beta(rows, chemical_name="氯", hazard_symbol="W1.1")
    assert beta == Decimal("4.0")
    assert source == "table3"


def test_resolve_beta_falls_back_to_table4_by_symbol():
    rows = [
        _beta_row(name="氯", beta="4.0", table="3"),
        _beta_row(symbol="W5.1", beta="1.5", table="4"),
    ]
    beta, source = resolve_beta(rows, chemical_name="甲醇", hazard_symbol="W5.1")
    assert beta == Decimal("1.5")
    assert source == "table4"


def test_resolve_beta_raises_when_not_found():
    """两边都查不到必须显式报错，不能默认成 1.0 静默算错。"""
    with pytest.raises(MajorHazardRuleError):
        resolve_beta([], chemical_name="未知物质", hazard_symbol="W99")


def test_replay_snapshot_reproduces_result():
    """审计要求：用快照里的输入重算，结果必须与原结论一致。"""
    snapshot = {
        "exposed_population": 60,
        "chemicals": [
            {"name": "氯", "q": 5.0, "Q": 5.0, "beta": 4.0},
            {"name": "氨", "q": 5.0, "Q": 10.0, "beta": 2.0},
        ],
    }
    out = replay_snapshot(snapshot)
    # α=1.5；(4×1.0 + 2×0.5)=5.0；R=7.5 -> 四级
    assert out["s_value"] == 1.5
    assert out["r_value"] == 7.5
    assert out["level"] == "四级"


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

    def scalar(self):
        return self._items[0] if self._items else None


def _unit():
    u = MagicMock()
    u.id = "u1"
    u.enterprise_id = "e1"
    return u


def _chem():
    c = MagicMock()
    c.chemical_name = "氯"
    c.q_design_max = Decimal("5.0")
    c.critical_quantity_t = Decimal("5.0")
    c.beta = Decimal("4.0")
    c.beta_source = "table3"
    return c


def _db(added, unit=None, chemicals=None):
    db = MagicMock()
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit] if unit is not None else [])
        if "major_hazard_unit_chemicals" in text:
            return _Result(chemicals if chemicals is not None else [])
        if "major_hazard_calculations" in text:
            return _Result([])  # 尚无快照 -> seq 从 1 开始
        return _Result([])

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_compute_unit_snapshot_persists_snapshot():
    added = []
    db = _db(added, unit=_unit(), chemicals=[_chem()])
    snap = await compute_unit_snapshot(db, unit_id="u1", exposed_population=0, user_id="user1")

    assert snap["seq"] == 1
    assert snap["is_major_hazard"] is True
    assert snap["level"] == "四级"
    assert snap["formula_version"] == "GB18218-2018"
    assert added, "必须写入一条快照记录"
    assert added[0].unit_id == "u1"
    assert added[0].inputs_snapshot["chemicals"][0]["name"] == "氯"


@pytest.mark.asyncio
async def test_compute_unit_snapshot_rejects_empty_unit():
    added = []
    db = _db(added, unit=_unit(), chemicals=[])
    with pytest.raises(MajorHazardRuleError):
        await compute_unit_snapshot(db, unit_id="u1", exposed_population=0)


@pytest.mark.asyncio
async def test_compute_unit_snapshot_rejects_missing_unit():
    added = []
    db = _db(added, unit=None, chemicals=[_chem()])
    with pytest.raises(MajorHazardRuleError):
        await compute_unit_snapshot(db, unit_id="nope", exposed_population=0)
