"""常量表查物质：临界量 + β + 危险性类别选项。

前端录入品种时要"选名称 → 自动带出 Q 与 β"。表1 给 Q，表3 按名称给 β；
表3 未命中（该物质不是列名的毒性气体）时要给用户表4 的类别清单自己选。
"""

from unittest.mock import MagicMock

import pytest

from app.services.major_hazard_lookup import lookup_chemical_definition


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


def _cq(name, q, table="1"):
    c = MagicMock()
    c.chemical_name = name
    c.critical_t = q
    c.critical_note = None
    c.table_no = table
    c.alias = None
    c.cas_no = None
    return c


def _beta(name=None, symbol=None, category=None, beta="4.0", table="3"):
    b = MagicMock()
    b.chemical_name = name
    b.symbol = symbol
    b.category = category
    b.beta = beta
    b.source_table = table
    return b


def _db(critical=None, betas=None):
    db = MagicMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "critical_quantities" in text:
            return _Result([critical] if critical else [])
        if "hazard_beta_factors" in text:
            return _Result(betas or [])
        return _Result([])

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_lookup_returns_q_and_beta_from_table3():
    """氯在表1（Q=5）也在表3（β=4），两个都应返回。"""
    db = _db(critical=_cq("氯", 5), betas=[_beta(name="氯", beta="4.0")])
    out = await lookup_chemical_definition(db, name="氯")
    assert out["chemical_name"] == "氯"
    assert float(out["critical_quantity_t"]) == 5.0
    assert float(out["beta"]) == 4.0
    assert out["beta_source"] == "table3"
    assert out["needs_hazard_symbol"] is False


@pytest.mark.asyncio
async def test_lookup_offers_symbol_options_when_beta_not_found():
    """甲醇不在表3（不是列名毒性气体），应给出表4 类别清单让用户选。"""
    db = _db(
        critical=_cq("甲醇", 500),
        betas=[
            _beta(name="氯", beta="4.0"),
            _beta(symbol="W5.1", category="易燃液体", beta="1.5", table="4"),
            _beta(symbol="J3", category="急性毒性", beta="2", table="4"),
        ],
    )
    out = await lookup_chemical_definition(db, name="甲醇")
    assert float(out["critical_quantity_t"]) == 500.0
    assert out["beta"] is None
    assert out["needs_hazard_symbol"] is True
    symbols = {o["symbol"] for o in out["hazard_symbol_options"]}
    assert symbols == {"W5.1", "J3"}
    assert all(o["beta"] is not None for o in out["hazard_symbol_options"])


@pytest.mark.asyncio
async def test_lookup_without_critical_quantity():
    """表1/表2 都查不到时 Q 为空，前端应提示人工指定。"""
    db = _db(critical=None, betas=[])
    out = await lookup_chemical_definition(db, name="某种混合物")
    assert out["critical_quantity_t"] is None
    assert out["beta"] is None
    assert out["needs_hazard_symbol"] is True


@pytest.mark.asyncio
async def test_lookup_resolves_beta_by_symbol_when_given():
    """用户选了类别符号后，按表4 解析 β。"""
    db = _db(
        critical=_cq("甲醇", 500),
        betas=[_beta(symbol="W5.1", category="易燃液体", beta="1.5", table="4")],
    )
    out = await lookup_chemical_definition(db, name="甲醇", hazard_symbol="W5.1")
    assert float(out["beta"]) == 1.5
    assert out["beta_source"] == "table4"
    assert out["needs_hazard_symbol"] is False
