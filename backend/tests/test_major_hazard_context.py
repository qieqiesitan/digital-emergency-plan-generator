"""预案上下文应包含重大危险源摘要。"""

from unittest.mock import MagicMock

import pytest

from app.services.major_hazard_context import build_major_hazard_brief


def _db(units, latest):
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        text = str(stmt)
        if "major_hazard_units" in text:
            res.scalars.return_value.all.return_value = units
        else:
            res.scalar_one_or_none.return_value = latest
        return res

    db.execute = execute
    return db


def _unit(name="罐区A", utype="storage"):
    u = MagicMock()
    u.id = "u1"
    u.name = name
    u.unit_type = utype
    return u


def _latest(level="二级", is_major=True, r=62.5):
    c = MagicMock()
    c.level = level
    c.is_major_hazard = is_major
    c.r_value = r
    c.seq = 3
    return c


@pytest.mark.asyncio
async def test_brief_lists_units_with_level():
    brief = await build_major_hazard_brief(_db([_unit()], _latest()), enterprise_id="e1")
    assert "罐区A" in brief["text"]
    assert "二级" in brief["text"]
    assert "构成重大危险源" in brief["text"]
    assert brief["units"][0]["level"] == "二级"
    assert brief["units"][0]["r_value"] == 62.5


@pytest.mark.asyncio
async def test_brief_marks_unidentified_units():
    """没有计算快照的单元必须标「尚未辨识」。

    绝不能默认成「不构成」——那是把"没算过"说成"算过且安全"，
    会让预案在错误前提上编制。
    """
    brief = await build_major_hazard_brief(_db([_unit("锅炉房", "production")], None), enterprise_id="e1")
    assert "尚未辨识" in brief["text"]
    # 断言要落在"单元那一行"上，而不是整段文本——文末的说明句里本来就有"不构成"三个字。
    unit_line = next(l for l in brief["text"].splitlines() if l.startswith("- "))
    assert "不构成" not in unit_line
    assert brief["units"][0]["conclusion"] == "尚未辨识"
    assert brief["units"][0]["level"] is None


@pytest.mark.asyncio
async def test_brief_marks_non_major_units():
    brief = await build_major_hazard_brief(
        _db([_unit("库房")], _latest(level=None, is_major=False, r=2.0)), enterprise_id="e1"
    )
    assert "不构成重大危险源" in brief["text"]
    assert brief["units"][0]["r_value"] is None, "不构成时不该给出 R 值"


@pytest.mark.asyncio
async def test_brief_empty_when_no_units():
    brief = await build_major_hazard_brief(_db([], None), enterprise_id="e1")
    assert brief["units"] == []
    assert brief["text"] == ""
