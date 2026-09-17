"""GB 18218-2018 R 值法计算引擎单测。"""

import pytest

from app.services.major_hazard_calc import (
    FORMULA_VERSION,
    CalcInputError,
    ChemicalInput,
    alpha_for_population,
    compute,
    level_for_r,
)


def _chem(name="氯", q=1.0, Q=5.0, beta=4.0):
    return ChemicalInput(name=name, q_design_max=q, critical_quantity=Q, beta=beta)


def test_alpha_table5_boundaries():
    """表5 暴露人员校正系数 α 的分档边界。"""
    assert alpha_for_population(0) == 0.5
    assert alpha_for_population(1) == 1.0
    assert alpha_for_population(29) == 1.0
    assert alpha_for_population(30) == 1.2
    assert alpha_for_population(49) == 1.2
    assert alpha_for_population(50) == 1.5
    assert alpha_for_population(99) == 1.5
    assert alpha_for_population(100) == 2.0
    assert alpha_for_population(5000) == 2.0


def test_level_for_r_table6_boundaries():
    """表6 分级标准：一级 R>=100；二级 100>R>=50；三级 50>R>=10；四级 R<10。"""
    assert level_for_r(100.0) == "一级"
    assert level_for_r(99.999) == "二级"
    assert level_for_r(50.0) == "二级"
    assert level_for_r(49.999) == "三级"
    assert level_for_r(10.0) == "三级"
    assert level_for_r(9.999) == "四级"
    assert level_for_r(0.0) == "四级"


def test_single_chemical_below_threshold_is_not_major_hazard():
    """式(1) 单品种：q<Q 时不构成重大危险源，等级为空。"""
    r = compute([_chem(q=4.9, Q=5.0)], exposed_population=0)
    assert r.is_major_hazard is False
    assert r.level is None
    assert r.s_value == pytest.approx(0.98)


def test_single_chemical_equal_threshold_is_major_hazard():
    """式(1)：q 等于临界量即构成（"等于或超过"）。"""
    r = compute([_chem(q=5.0, Q=5.0)], exposed_population=0)
    assert r.is_major_hazard is True
    assert r.s_value == pytest.approx(1.0)


def test_multi_chemical_s_exactly_one():
    """式(1) 多品种：s 恰好等于 1 构成重大危险源。"""
    r = compute(
        [_chem("氯", q=2.5, Q=5.0), _chem("氨", q=5.0, Q=10.0)],
        exposed_population=0,
    )
    assert r.s_value == pytest.approx(1.0)
    assert r.is_major_hazard is True


def test_r_value_uses_alpha_and_beta():
    """式(2)：R = α × Σ βi × (qi/Qi)。"""
    # α=0.5（0 人），氯 β=4 q/Q=1.0 -> 4.0；氨 β=2 q/Q=0.5 -> 1.0；Σ=5.0；R=2.5
    r = compute(
        [_chem("氯", q=5.0, Q=5.0, beta=4.0), _chem("氨", q=5.0, Q=10.0, beta=2.0)],
        exposed_population=0,
    )
    assert r.alpha == 0.5
    assert r.r_value == pytest.approx(2.5)
    assert r.level == "四级"


def test_r_value_crosses_level_1():
    """暴露人员 100 人以上（α=2.0）时 R 翻四倍，跨到一级。"""
    r = compute([_chem("氯", q=250.0, Q=5.0, beta=4.0)], exposed_population=100)
    # q/Q = 50；β=4 -> 200；α=2.0 -> R=400
    assert r.r_value == pytest.approx(400.0)
    assert r.level == "一级"


def test_items_detail_is_recorded_for_each_chemical():
    """快照明细逐品种记录 q/Q/β/qQ 与结论依据。"""
    r = compute([_chem("氯", q=5.0, Q=5.0, beta=4.0)], exposed_population=0)
    assert len(r.items) == 1
    item = r.items[0]
    assert item["name"] == "氯"
    assert item["q"] == pytest.approx(5.0)
    assert item["Q"] == pytest.approx(5.0)
    assert item["beta"] == pytest.approx(4.0)
    assert item["q_over_Q"] == pytest.approx(1.0)
    assert item["beta_times_q_over_Q"] == pytest.approx(4.0)


def test_formula_version_is_pinned():
    assert FORMULA_VERSION == "GB18218-2018"


@pytest.mark.parametrize(
    "bad",
    [
        [_chem(q=-1.0)],
        [_chem(Q=0.0)],
        [_chem(beta=0.0)],
    ],
)
def test_invalid_input_raises(bad):
    """q 为负、Q 为 0、β 为 0 均属输入错误，必须显式报错而不是静默出结果。"""
    with pytest.raises(CalcInputError):
        compute(bad, exposed_population=0)


def test_empty_chemical_list_raises():
    """单元内没有品种时不能计算——空单元不是"不构成重大危险源"，是数据未填。"""
    with pytest.raises(CalcInputError):
        compute([], exposed_population=0)


def test_negative_population_raises():
    with pytest.raises(CalcInputError):
        compute([_chem()], exposed_population=-1)
