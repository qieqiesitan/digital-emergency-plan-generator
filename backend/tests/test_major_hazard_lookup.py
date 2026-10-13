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


def _cq(name, q, table="1", symbol=None, category=None, cas_no=None):
    c = MagicMock()
    c.chemical_name = name
    c.critical_t = q
    c.critical_note = None
    c.table_no = table
    c.alias = None
    c.cas_no = cas_no
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


def _db(critical=None, betas=None, table2=None, by_cas=None):
    db = MagicMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "critical_quantities" in text:
            # 表2 按 table_no 过滤、按名字查用 chemical_name、CAS 兜底用 cas_no。
            # 必须认**带冒号的绑定参数名**：select(Model) 会把所有列名都渲染进
            # SELECT 列表，裸列名两条查询里都有，拿它判断会串（实测踩过）。
            if ":table_no_" in text:
                return _Result(table2 or [])
            if ":cas_no_" in text:
                return _Result(by_cas or [])
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


# --- CAS 兜底：台账里的名字与标准写法对不上时 ------------------------------------
# 真库实例：台账「汽油」↔ 表1「汽油(乙醇汽油、甲醇汽油)」（CAS 86290-81-5(汽油)）；
# 台账「盐酸」↔ 表1「氯化氢(无水)」；台账「乙醇（酒精）」↔ 表1「乙醇」。
# 标准原文一个格子里可能塞多个 CAS 并带括号注名，所以要按分号切分、剥掉括号后缀。


def test_cas_tokens_normalizes_messy_standard_values():
    from app.services.major_hazard_lookup import _cas_tokens

    assert _cas_tokens("86290-81-5(汽油)") == {"86290-81-5"}
    assert _cas_tokens("68476-85-7；74-98-6(丙烷)；106-97-8(丁烷)") == {
        "68476-85-7",
        "74-98-6",
        "106-97-8",
    }
    assert _cas_tokens("74-82-8(甲烷);8006-14-2(天然气)") == {"74-82-8", "8006-14-2"}
    assert _cas_tokens(None) == set()
    assert _cas_tokens("  ") == set()


@pytest.mark.asyncio
async def test_lookup_by_cas_when_name_does_not_match():
    """台账名「汽油」对不上标准名，靠 CAS 兜底命中，Q 才能带出来。"""
    db = _db(
        critical=None,  # 精确名字查不到
        by_cas=[_cq("汽油(乙醇汽油、甲醇汽油)", 200, table="1", cas_no="86290-81-5(汽油)")],
    )
    out = await lookup_chemical_definition(db, name="汽油", cas_no="86290-81-5")
    assert float(out["critical_quantity_t"]) == 200.0
    assert out["critical_source"] == "table1"
    # chemical_name 回报的是调用方传进来的名字（前端表格里显示的就是它）
    assert out["chemical_name"] == "汽油"


@pytest.mark.asyncio
async def test_cas_fallback_rejects_partial_substring():
    """SQL 的 LIKE 只是粗筛：`81-5` 能在 `86290-81-5` 里当子串，
    但切分后的 CAS 必须整体相等才算命中，否则会挂到错误的品种上。"""
    db = _db(
        critical=None,
        by_cas=[_cq("汽油(乙醇汽油、甲醇汽油)", 200, table="1", cas_no="86290-81-5(汽油)")],
    )
    out = await lookup_chemical_definition(db, name="汽油", cas_no="81-5")
    assert out["critical_quantity_t"] is None
    assert out["needs_hazard_symbol"] is True


@pytest.mark.asyncio
async def test_no_cas_query_when_name_hits():
    """名字精确命中时就用它，不必再走 CAS（也就不会串到别的行）。"""
    db = _db(
        critical=_cq("甲醇", 500),
        by_cas=[_cq("汽油(乙醇汽油、甲醇汽油)", 200, table="1", cas_no="86290-81-5(汽油)")],
    )
    out = await lookup_chemical_definition(db, name="甲醇", cas_no="86290-81-5")
    assert float(out["critical_quantity_t"]) == 500.0
