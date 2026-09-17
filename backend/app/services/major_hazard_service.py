"""重大危险源计算编排：读常量 → 调纯函数引擎 → 写不可变快照。

与 app/services/major_hazard_calc.py 的分工：
- calc 模块只做数学，不认识数据库；
- 本模块负责把 DB 里的临界量 Q 与校正系数 β 取出来喂给引擎，并落快照。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.major_hazard import (
    MajorHazardCalculation,
    MajorHazardUnit,
    MajorHazardUnitChemical,
)
from app.models.standard_constants import HazardBetaFactor
from app.services.major_hazard_calc import (
    FORMULA_VERSION,
    CalcInputError,
    ChemicalInput,
    compute,
)

STANDARD = "GB18218-2018"


class MajorHazardRuleError(ValueError):
    """标准规则无法套用（如 β 查不到）或数据不完整，必须显式失败而不是取默认值。"""


def resolve_beta(
    rows: Sequence[HazardBetaFactor],
    *,
    chemical_name: str,
    hazard_symbol: str | None,
) -> tuple[Decimal, str]:
    """按 GB 18218 4.3.2 选取校正系数 β：先查表3（按名称），再查表4（按类别符号）。"""
    for r in rows:
        if r.source_table == "3" and r.chemical_name == chemical_name:
            return Decimal(r.beta), "table3"
    if hazard_symbol:
        for r in rows:
            if r.source_table == "4" and r.symbol == hazard_symbol:
                return Decimal(r.beta), "table4"
    raise MajorHazardRuleError(
        f"危险化学品「{chemical_name}」在表3/表4 中均查不到校正系数 β，请先补齐危险性类别"
    )


async def _next_seq(db: AsyncSession, unit_id: str) -> int:
    res = await db.execute(
        select(func.max(MajorHazardCalculation.seq)).where(MajorHazardCalculation.unit_id == unit_id)
    )
    current = res.scalar()
    return int(current or 0) + 1


async def compute_unit_snapshot(
    db: AsyncSession,
    *,
    unit_id: str,
    exposed_population: int,
    user_id: str | None = None,
) -> dict:
    """对指定单元执行一次计算并写入不可变快照，返回快照内容。"""
    unit_res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = unit_res.scalar_one_or_none()
    if unit is None:
        raise MajorHazardRuleError("重大危险源单元不存在")

    chem_res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    chemicals = list(chem_res.scalars().all())
    if not chemicals:
        raise MajorHazardRuleError("该单元尚未录入危险化学品，无法计算")

    try:
        result = compute(
            [
                ChemicalInput(
                    name=c.chemical_name,
                    q_design_max=float(c.q_design_max),
                    critical_quantity=float(c.critical_quantity_t),
                    beta=float(c.beta),
                )
                for c in chemicals
            ],
            exposed_population=exposed_population,
        )
    except CalcInputError as exc:
        raise MajorHazardRuleError(str(exc)) from exc

    seq = await _next_seq(db, unit_id)
    snapshot = {
        "seq": seq,
        "s_value": round(result.s_value, 6),
        "r_value": round(result.r_value, 6),
        "alpha": result.alpha,
        "exposed_population": exposed_population,
        "is_major_hazard": result.is_major_hazard,
        "level": result.level,
        "formula_version": FORMULA_VERSION,
        "standard": STANDARD,
        "chemicals": list(result.items),
    }
    db.add(
        MajorHazardCalculation(
            unit_id=unit_id,
            seq=seq,
            s_value=Decimal(str(snapshot["s_value"])),
            r_value=Decimal(str(snapshot["r_value"])),
            alpha=Decimal(str(result.alpha)),
            exposed_population=exposed_population,
            is_major_hazard=result.is_major_hazard,
            level=result.level,
            formula_version=FORMULA_VERSION,
            inputs_snapshot=snapshot,
            calculated_by=user_id,
        )
    )
    await db.commit()
    return snapshot


def replay_snapshot(snapshot: dict) -> dict:
    """用快照里保存的输入重算一遍（审计核对用）。结果应与快照一致。"""
    result = compute(
        [
            ChemicalInput(
                name=item["name"],
                q_design_max=float(item["q"]),
                critical_quantity=float(item["Q"]),
                beta=float(item["beta"]),
            )
            for item in snapshot.get("chemicals", [])
        ],
        exposed_population=int(snapshot["exposed_population"]),
    )
    return {
        "s_value": round(result.s_value, 6),
        "r_value": round(result.r_value, 6),
        "is_major_hazard": result.is_major_hazard,
        "level": result.level,
    }
