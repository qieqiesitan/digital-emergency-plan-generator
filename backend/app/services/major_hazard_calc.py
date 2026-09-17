"""GB 18218-2018 危险化学品重大危险源 R 值法计算引擎（纯函数，无 IO）。

依据《危险化学品重大危险源辨识》GB 18218-2018：
- 4.2.1 辨识指标 式(1)：s = q1/Q1 + q2/Q2 + … + qn/Qn，s >= 1 即构成重大危险源
- 4.3.2 分级指标 式(2)：R = α × Σ βi × (qi/Qi)
- 4.3.3 分级标准 表6：一级 R>=100；二级 100>R>=50；三级 50>R>=10；四级 R<10
- 4.2.2 储罐及其他容器、设备或仓储区的实际存在量按设计最大量确定

本模块刻意不做任何数据库访问：临界量 Q 与校正系数 β 由调用方从常量表读出后注入，
以便离线单测，并满足"计算结果必须可复算"的审计要求。
"""

from __future__ import annotations

from dataclasses import dataclass

FORMULA_VERSION = "GB18218-2018"


class CalcInputError(ValueError):
    """计算输入不合法（数据未填或填错），与"不构成重大危险源"是两回事。"""


@dataclass(frozen=True)
class ChemicalInput:
    """单元内一种危险化学品的计算输入。q 与 Q 单位均为吨。"""

    name: str
    q_design_max: float
    critical_quantity: float
    beta: float


@dataclass(frozen=True)
class CalcResult:
    s_value: float
    r_value: float
    alpha: float
    is_major_hazard: bool
    level: str | None
    items: tuple[dict, ...]


def alpha_for_population(population: int) -> float:
    """表5 暴露人员校正系数 α（按厂区边界外扩 500m 内可能暴露人员数量）。"""
    if population < 0:
        raise CalcInputError("厂外可能暴露人员数量不能为负")
    if population >= 100:
        return 2.0
    if population >= 50:
        return 1.5
    if population >= 30:
        return 1.2
    if population >= 1:
        return 1.0
    return 0.5


def level_for_r(r_value: float) -> str:
    """表6 重大危险源级别与 R 值的对应关系。"""
    if r_value >= 100:
        return "一级"
    if r_value >= 50:
        return "二级"
    if r_value >= 10:
        return "三级"
    return "四级"


def _validate(chemicals: list[ChemicalInput], exposed_population: int) -> None:
    if not chemicals:
        raise CalcInputError("单元内没有任何危险化学品，无法计算")
    if exposed_population < 0:
        raise CalcInputError("厂外可能暴露人员数量不能为负")
    for c in chemicals:
        if not c.name:
            raise CalcInputError("危险化学品名称不能为空")
        if c.q_design_max < 0:
            raise CalcInputError(f"{c.name}：设计最大量不能为负")
        if c.critical_quantity <= 0:
            raise CalcInputError(f"{c.name}：临界量必须大于 0")
        if c.beta <= 0:
            raise CalcInputError(f"{c.name}：校正系数 β 必须大于 0")


def compute(
    chemicals: list[ChemicalInput],
    exposed_population: int,
) -> CalcResult:
    """按式(1) 辨识、式(2) 分级。返回结论与逐品种明细（供快照落库）。"""
    _validate(chemicals, exposed_population)

    items: list[dict] = []
    s_value = 0.0
    weighted = 0.0
    for c in chemicals:
        q_over_q = c.q_design_max / c.critical_quantity
        beta_term = c.beta * q_over_q
        s_value += q_over_q
        weighted += beta_term
        items.append(
            {
                "name": c.name,
                "q": c.q_design_max,
                "Q": c.critical_quantity,
                "beta": c.beta,
                "q_over_Q": q_over_q,
                "beta_times_q_over_Q": beta_term,
            }
        )

    alpha = alpha_for_population(exposed_population)
    r_value = alpha * weighted
    is_major_hazard = s_value >= 1.0
    return CalcResult(
        s_value=s_value,
        r_value=r_value,
        alpha=alpha,
        is_major_hazard=is_major_hazard,
        level=level_for_r(r_value) if is_major_hazard else None,
        items=tuple(items),
    )
