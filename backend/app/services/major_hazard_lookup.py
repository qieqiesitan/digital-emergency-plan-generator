"""常量表查物质：临界量 Q + 校正系数 β + 危险性类别选项。

GB 18218 的取值顺序是**先查表**、不是"读出来"：
- Q：表1 按品种名查；不在表1 则按危险性类别查表2
- β：表3 按毒性气体名称查；不在表3 则按危险性类别查表4

表2（按类别取 Q）与表4（按类别取 β）用的是**同一套符号**（J1~J5、W1.1~W11），
所以未在表1/表3 列举的品种只需要用户选**一次**危险性类别，Q 和 β 就一起定下来了——
这是 `hazard_symbol_options` 里同时带 `critical_quantity_t` 与 `beta` 的原因。

所以录入品种时能自动带的就只有 Q 和 β 两项，别的都得人工确认。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.standard_constants import CriticalQuantity, HazardBetaFactor

STANDARD = "GB18218-2018"


def _q_by_symbol(rows) -> dict:
    """表2 的「类别符号 → 临界量」映射。符号为空的行（分组表头）不进映射。"""
    out: dict = {}
    for r in rows:
        symbol = getattr(r, "symbol", None)
        if not symbol:
            continue
        out[str(symbol)] = (
            float(r.critical_t) if getattr(r, "critical_t", None) is not None else None
        )
    return out


async def lookup_chemical_definition(
    db: AsyncSession,
    *,
    name: str,
    hazard_symbol: Optional[str] = None,
) -> dict:
    """按品种名查 Q 与 β。

    Q 或 β 任一查不到时，返回危险性类别清单供用户选择——选项里同时带该类别
    在表2 的 Q 与表4 的 β，选一次补齐两列。
    """
    cq_res = await db.execute(
        select(CriticalQuantity)
        .where(
            CriticalQuantity.standard == STANDARD,
            CriticalQuantity.chemical_name == name,
        )
        .limit(1)
    )
    cq = cq_res.scalar_one_or_none()

    # 表2 的分组表头（"J(健康危害性符号)"之类）与无符号行不参与取值
    table2_res = await db.execute(
        select(CriticalQuantity).where(
            CriticalQuantity.standard == STANDARD,
            CriticalQuantity.table_no == "2",
        )
    )
    table2_q = _q_by_symbol(table2_res.scalars().all())

    beta_res = await db.execute(
        select(HazardBetaFactor).where(HazardBetaFactor.standard == STANDARD)
    )
    betas = list(beta_res.scalars().all())

    critical = (
        float(cq.critical_t) if cq is not None and cq.critical_t is not None else None
    )
    critical_source = "table1" if critical is not None else None

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

    # 表2：Q 不在表1 时按同一个类别符号取——与表4 的 β 共用一次选择
    if critical is None and hazard_symbol:
        critical = table2_q.get(hazard_symbol)
        if critical is not None:
            critical_source = "table2"

    symbol_options = [
        {
            "symbol": b.symbol,
            "category": b.category,
            "beta": float(b.beta) if b.beta is not None else None,
            # 让用户选之前就看见"选这个能拿到多少 Q"
            "critical_quantity_t": table2_q.get(str(b.symbol)),
        }
        for b in betas
        if b.source_table == "4" and b.symbol
    ]

    return {
        "chemical_name": name,
        "alias": getattr(cq, "alias", None) if cq else None,
        "cas_no": getattr(cq, "cas_no", None) if cq else None,
        "table_no": getattr(cq, "table_no", None) if cq else None,
        "critical_quantity_t": critical,
        "critical_source": critical_source,
        "critical_note": getattr(cq, "critical_note", None) if cq else None,
        "beta": beta,
        "beta_source": beta_source,
        # Q 或 β 只要有一个还没定下来就要请用户选类别（表2/表4 共用这套符号）
        "needs_hazard_symbol": critical is None or beta is None,
        "hazard_symbol_options": symbol_options,
    }
