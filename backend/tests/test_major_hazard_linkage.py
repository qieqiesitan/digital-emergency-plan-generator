"""跨模块关联：风险点、危化品台账。

核心约束是**同企业校验**——关联一旦跨企业，A 企业用户就能通过界面看到
B 企业的对象名称；在多企业部署下这是数据越界，属于安全事故级别的 bug，
不是"边界情况"。
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.major_hazard_linkage import (
    LinkageError,
    link_risk_object,
    list_linkable_risk_objects,
    suggest_design_max_from_ledger,
)


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


def _db(unit=None, objects=None, chem=None):
    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit] if unit else [])
        if "risk_objects" in text:
            return _Result(objects or [])
        if "hazardous_chemicals" in text:
            return _Result([chem] if chem else [])
        return _Result([])

    db.execute = execute
    return db


def _unit(ent="e1"):
    u = MagicMock()
    u.id = "u1"
    u.enterprise_id = ent
    u.risk_object_id = None
    return u


def _obj(oid="o1", ent="e1"):
    o = MagicMock()
    o.id = oid
    o.enterprise_id = ent
    o.name = "罐区A风险点"
    o.zone_id = "z1"
    o.floor_id = "f1"
    return o


# --- 任务 1：单元 ↔ 风险点 -------------------------------------------------


@pytest.mark.asyncio
async def test_link_risk_object_sets_field():
    unit = _unit()
    db = _db(unit=unit, objects=[_obj()])
    await link_risk_object(db, unit_id="u1", risk_object_id="o1")
    assert unit.risk_object_id == "o1"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_link_risk_object_rejects_cross_enterprise():
    unit = _unit(ent="e1")
    db = _db(unit=unit, objects=[_obj(oid="o2", ent="e2")])
    with pytest.raises(LinkageError) as ei:
        await link_risk_object(db, unit_id="u1", risk_object_id="o2")
    assert "企业" in str(ei.value)


@pytest.mark.asyncio
async def test_link_risk_object_allows_clearing():
    unit = _unit()
    unit.risk_object_id = "o1"
    db = _db(unit=unit)
    await link_risk_object(db, unit_id="u1", risk_object_id=None)
    assert unit.risk_object_id is None


@pytest.mark.asyncio
async def test_link_risk_object_rejects_missing_unit():
    db = _db(unit=None)
    with pytest.raises(LinkageError):
        await link_risk_object(db, unit_id="nope", risk_object_id="o1")


@pytest.mark.asyncio
async def test_list_linkable_objects_returns_zone_and_floor():
    db = _db(objects=[_obj()])
    out = await list_linkable_risk_objects(db, enterprise_id="e1")
    assert out[0]["id"] == "o1"
    assert out[0]["zone_id"] == "z1"
    assert out[0]["floor_id"] == "f1"


# --- 任务 2：单元品种 ↔ 危化品台账 -----------------------------------------


def _chem(cid="c1", ent="e1", amount=None, unit=None, text=None):
    c = MagicMock()
    c.id = cid
    c.enterprise_id = ent
    c.name = "甲醇"
    c.storage_amount = amount
    c.storage_unit = unit
    c.max_storage = text
    return c


@pytest.mark.asyncio
async def test_suggest_design_max_prefers_structured_amount():
    """优先用已结构化的存量，并且**必须**标注需人工确认。"""
    db = _db(chem=_chem(amount=Decimal("40"), unit="t", text="最大储存量 40 吨"))
    out = await suggest_design_max_from_ledger(db, chemical_id="c1", enterprise_id="e1")
    assert out["suggested_q"] == 40.0
    assert out["source"] == "structured"
    assert out["requires_confirmation"] is True
    assert "设计最大量" in out["hint"]


@pytest.mark.asyncio
async def test_suggest_design_max_parses_text_when_structured_missing():
    db = _db(chem=_chem(amount=None, text="5t"))
    out = await suggest_design_max_from_ledger(db, chemical_id="c2", enterprise_id="e1")
    assert out["suggested_q"] == 5.0
    assert out["source"] == "text"


@pytest.mark.asyncio
async def test_suggest_design_max_returns_none_when_unparseable():
    """解析不出来就返回 None，不猜测——与存量解析器的策略一致。"""
    db = _db(chem=_chem(amount=None, text="见台账"))
    out = await suggest_design_max_from_ledger(db, chemical_id="c3", enterprise_id="e1")
    assert out["suggested_q"] is None
    assert out["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_suggest_design_max_rejects_cross_enterprise():
    db = _db(chem=_chem(ent="e2"))
    with pytest.raises(LinkageError):
        await suggest_design_max_from_ledger(db, chemical_id="c4", enterprise_id="e1")
