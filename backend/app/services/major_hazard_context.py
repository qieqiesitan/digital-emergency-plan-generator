"""预案生成上下文：重大危险源摘要。

预案编制必须基于重大危险源辨识结果（编制导则要求预案建立在风险评估与
危险源辨识结论之上）。这里把清单与最近一次结论提供给生成链路。

一条硬规则：**没有计算快照的单元标「尚未辨识」，不得写成「不构成」**。
把"没算过"说成"算过且安全"，会让整份预案建立在错误前提上。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.major_hazard import MajorHazardCalculation, MajorHazardUnit

UNIT_TYPE_LABEL = {"production": "生产单元", "storage": "储存单元"}


async def build_major_hazard_brief(db: AsyncSession, *, enterprise_id: str) -> dict:
    """返回 {units: [...], text: 供提示词注入的纯文本}。没有单元时 text 为空串。"""
    res = await db.execute(
        select(MajorHazardUnit).where(MajorHazardUnit.enterprise_id == enterprise_id)
    )
    units = list(res.scalars().all())
    if not units:
        return {"units": [], "text": ""}

    rows: list[dict] = []
    for u in units:
        calc_res = await db.execute(
            select(MajorHazardCalculation)
            .where(MajorHazardCalculation.unit_id == u.id)
            .order_by(MajorHazardCalculation.seq.desc())
            .limit(1)
        )
        latest = calc_res.scalar_one_or_none()
        if latest is None:
            conclusion, level = "尚未辨识", None
        elif latest.is_major_hazard:
            conclusion, level = "构成重大危险源", latest.level
        else:
            conclusion, level = "不构成重大危险源", None
        rows.append(
            {
                "id": u.id,
                "name": u.name,
                "unit_type": UNIT_TYPE_LABEL.get(u.unit_type, u.unit_type),
                "level": level,
                "conclusion": conclusion,
                "r_value": (
                    float(latest.r_value)
                    if latest is not None and latest.is_major_hazard
                    else None
                ),
            }
        )

    lines = ["【重大危险源清单】"]
    for r in rows:
        level_part = f"，{r['level']}" if r["level"] else ""
        lines.append(f"- {r['name']}（{r['unit_type']}）：{r['conclusion']}{level_part}")
    lines.append(
        "说明：清单中标注「尚未辨识」的单元不得在预案中作出构成或不构成的判断。"
    )
    return {"units": rows, "text": "\n".join(lines)}
