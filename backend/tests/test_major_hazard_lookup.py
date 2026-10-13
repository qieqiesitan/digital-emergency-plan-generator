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


def _cq(name, q, table="1", symbol=None, category=None):
    c = MagicMock()
    c.chemical_name = name
    c.critical_t = q
    c.critical_note = None
    c.table_no = table
    c.alias = None
    c.cas_no = None
    # 表2 的行按危险性类别符号索引（表2/表4 是同一套 J/W 符号）
    c.symbol = symbol
    c.category = category
    return c


def _beta(name=None, symbol=None, category=None, beta="4.0", table="3"):
    b = MagicMock()
    b.chemical_name = name
    b.symbol = symbol
    b.category = category
    b.beta = beta
    b.source_table = table
    return b


def _db(critical=None, betas=None, table2=None):
    db = MagicMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "critical_quantities" in text:
            # 表2 查询按 table_no 过滤、表1 按 chemical_name 过滤。
            # 必须认**带冒号的绑定参数名**：select(Model) 会把所有列名都渲染进
            # SELECT 列表，裸列名两条查询里都有，拿它判断会串（实测踩过）。
            if ":table_no_" in text:
                return _Result(table2 or [])
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


# --- 表2：未在表1列举的品种，Q 按危险性类别取 --------------------------------
# 背景：GB 18218 的取值顺序是「Q 先表1、不在表1 则表2；β 先表3、不在表3 则表4」。
# 表2 与表4 用同一套符号（J1~J5、W1.1~W11），所以用户选一次危险性类别
# 就应该把 Q 和 β 一起定下来，而不是两列各选一次。


def _table2_w51():
    """表2 里易燃液体 W5.1 那行：Q=10t（标准原文符号与表4 一致）。"""
    return _cq(
        "—类别1—类别2和3,工作温度高于沸点",
        10,
        table="2",
        symbol="W5.1",
        category="易燃液体",
    )


@pytest.mark.asyncio
async def test_symbol_options_carry_table2_critical_quantity():
    """选项里要同时给出 Q 与 β——用户看得到自己选完会得到什么。"""
    db = _db(
        betas=[
            _beta(symbol="W5.1", category="易燃液体", beta="1.5", table="4"),
            _beta(symbol="J3", category="急性毒性", beta="2", table="4"),
        ],
        table2=[_table2_w51()],
    )
    out = await lookup_chemical_definition(db, name="汽油")
    assert out["critical_quantity_t"] is None  # 表1 未列举
    opts = {o["symbol"]: o for o in out["hazard_symbol_options"]}
    assert float(opts["W5.1"]["critical_quantity_t"]) == 10.0
    assert float(opts["W5.1"]["beta"]) == 1.5
    # 表2 里没有的符号只能给空值，不能让前端以为"选了就有 Q"
    assert opts["J3"]["critical_quantity_t"] is None


@pytest.mark.asyncio
async def test_picking_symbol_fills_q_from_table2_and_beta_from_table4():
    """汽油选 W5.1 → Q 取表2 的 10t、β 取表4 的 1.5，一次选择补齐两列。"""
    db = _db(
        betas=[_beta(symbol="W5.1", category="易燃液体", beta="1.5", table="4")],
        table2=[_table2_w51()],
    )
    out = await lookup_chemical_definition(db, name="汽油", hazard_symbol="W5.1")
    assert float(out["critical_quantity_t"]) == 10.0
    assert out["critical_source"] == "table2"
    assert float(out["beta"]) == 1.5
    assert out["beta_source"] == "table4"
    assert out["needs_hazard_symbol"] is False


@pytest.mark.asyncio
async def test_needs_symbol_when_only_q_is_missing():
    """β 在表3 命中、但表1 没这个品种 → 仍要请用户选类别，因为 Q 还得从表2 取。"""
    db = _db(
        critical=None,
        # 表3 命中（β 有了），同时给出表4 的类别行——用户要选的是表4 的符号，
        # 表2 只是拿这个符号去反查 Q
        betas=[
            _beta(name="磷化氢", beta="20"),
            _beta(symbol="J1", category="急性毒性", beta="4", table="4"),
        ],
        table2=[_cq("类别1,所有暴露途径,气体", 5, table="2", symbol="J1", category="急性毒性")],
    )
    out = await lookup_chemical_definition(db, name="磷化氢")
    assert float(out["beta"]) == 20.0
    assert out["critical_quantity_t"] is None
    assert out["needs_hazard_symbol"] is True
    assert [o["symbol"] for o in out["hazard_symbol_options"]] == ["J1"]


@pytest.mark.asyncio
async def test_table1_hit_marks_critical_source_as_table1():
    """表1 命中时来源标 table1，且不因表2 有同符号行而串味。"""
    db = _db(
        critical=_cq("氯", 5),
        betas=[_beta(name="氯", beta="4.0")],
        table2=[_table2_w51()],
    )
    out = await lookup_chemical_definition(db, name="氯")
    assert float(out["critical_quantity_t"]) == 5.0
    assert out["critical_source"] == "table1"
    assert out["needs_hazard_symbol"] is False
