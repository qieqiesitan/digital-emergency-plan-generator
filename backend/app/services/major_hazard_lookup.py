"""常量表查物质：临界量 Q + 校正系数 β + 危险性类别选项。

GB 18218 的取值顺序是**先查表**、不是"读出来"：
- Q：表1 按品种名查；不在表1 则按危险性类别查表2
- β：表3 按毒性气体名称查；不在表3 则按危险性类别查表4

所以录入品种时能自动带的就只有 Q 和 β 两项，别的都得人工确认。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.standard_constants import CriticalQuantity, HazardBetaFactor

STANDARD = "GB18218-2018"


async def lookup_chemical_definition(
    db: AsyncSession,
    *,
    name: str,
    hazard_symbol: Optional[str] = None,
) -> dict:
    """按品种名查 Q 与 β；β 查不到时返回表4 的类别清单供用户选择。"""
    cq_res = await db.execute(
        select(CriticalQuantity)
        .where(
            CriticalQuantity.standard == STANDARD,
            CriticalQuantity.chemical_name == name,
        )
        .limit(1)
    )
    cq = cq_res.scalar_one_or_none()

    beta_res = await db.execute(
        select(HazardBetaFactor).where(HazardBetaFactor.standard == STANDARD)
    )
    betas = list(beta_res.scalars().all())

    beta = None
    beta_source = None

    # 表3：按名称（毒性气体逐个列名）
    for b in betas:
        if b.source_table == "3" and b.chemical_name == name:
            beta = float(b.beta)
            beta_source = "table3"
            break

    # 表4：按危险性类别符号
    if beta is None and hazard_symbol:
        for b in betas:
            if b.source_table == "4" and b.symbol == hazard_symbol:
                beta = float(b.beta)
                beta_source = "table4"
                break

    symbol_options = [
        {
            "symbol": b.symbol,
            "category": b.category,
            "beta": float(b.beta) if b.beta is not None else None,
        }
        for b in betas
        if b.source_table == "4" and b.symbol
    ]

    return {
        "chemical_name": name,
        "alias": getattr(cq, "alias", None) if cq else None,
        "cas_no": getattr(cq, "cas_no", None) if cq else None,
        "table_no": getattr(cq, "table_no", None) if cq else None,
        "critical_quantity_t": (
            float(cq.critical_t) if cq is not None and cq.critical_t is not None else None
        ),
        "critical_note": getattr(cq, "critical_note", None) if cq else None,
        "beta": beta,
        "beta_source": beta_source,
        # β 未能确定（表3 未命中且用户还没选类别）时为 True，前端据此提示选择
        "needs_hazard_symbol": beta is None,
        "hazard_symbol_options": symbol_options,
    }
