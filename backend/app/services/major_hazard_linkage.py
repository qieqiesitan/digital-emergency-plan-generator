"""重大危险源与既有模块的关联读写。

所有关联操作都必须做**同企业校验**——跨企业关联会造成数据越界，
在多企业部署下是安全事故级别的 bug。

本模块只做"建立引用"，不改业务数值：例如把单元品种关联到台账条目时
只写 chemical_id，不改 q_design_max。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hazardous_chemicals import HazardousChemical
from app.models.major_hazard import MajorHazardUnit, MajorHazardUnitChemical
from app.models.risk_management import RiskObject
from app.services.chemical_storage_parser import parse_storage_text


class LinkageError(ValueError):
    """关联操作非法（跨企业、目标不存在等）。"""


DESIGN_MAX_HINT = (
    "设计最大量按 GB 18218-2018 4.2.2 确定：储罐及其他容器、设备或仓储区的"
    "实际存在量按设计最大量计，通常 >= 台账登记的最大储存量。请核对后确认。"
)


async def link_risk_object(
    db: AsyncSession,
    *,
    unit_id: str,
    risk_object_id: Optional[str],
) -> dict:
    """把单元关联到风险点；传 None 表示解除关联。"""
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise LinkageError("重大危险源单元不存在")

    if risk_object_id is None:
        unit.risk_object_id = None
        await db.commit()
        return {"unit_id": unit_id, "risk_object_id": None}

    await ensure_risk_object_in_enterprise(
        db, enterprise_id=unit.enterprise_id, risk_object_id=risk_object_id
    )
    unit.risk_object_id = risk_object_id
    await db.commit()
    return {"unit_id": unit_id, "risk_object_id": risk_object_id}


async def ensure_risk_object_in_enterprise(
    db: AsyncSession,
    *,
    enterprise_id: str,
    risk_object_id: str,
) -> None:
    """校验风险点存在且属于该企业；非法时抛 LinkageError。

    抽成独立函数的原因：不只 `link_risk_object` 需要它，单元的新建/编辑接口
    也必须过同一道门——否则构造请求就能把别家企业的风险点 id 写进来。
    """
    obj_res = await db.execute(select(RiskObject).where(RiskObject.id == risk_object_id))
    obj = obj_res.scalar_one_or_none()
    if obj is None:
        raise LinkageError("风险点不存在")
    if getattr(obj, "enterprise_id", None) != enterprise_id:
        raise LinkageError("风险点与单元不属于同一企业，禁止关联")


async def list_linkable_risk_objects(db: AsyncSession, *, enterprise_id: str) -> list[dict]:
    """列出可关联的风险点（本企业、且标记为风险点的对象）。"""
    res = await db.execute(
        select(RiskObject).where(
            RiskObject.enterprise_id == enterprise_id,
            RiskObject.is_risk_point.is_(True),
        )
    )
    return [
        {
            "id": o.id,
            "name": o.name,
            "zone_id": getattr(o, "zone_id", None),
            "floor_id": getattr(o, "floor_id", None),
            # 供单元表单带出默认值；不含坐标与分区多边形——见规格 §2.4
            "location": getattr(o, "location", None),
            "responsible_unit": getattr(o, "responsible_unit", None),
            "responsible_person": getattr(o, "responsible_person", None),
            "contact_phone": getattr(o, "contact_phone", None),
        }
        for o in res.scalars().all()
    ]


async def suggest_design_max_from_ledger(
    db: AsyncSession,
    *,
    chemical_id: str,
    enterprise_id: str,
) -> dict:
    """从危化品台账给设计最大量一个**建议初值**，由界面人工确认。

    本函数不写库。为什么只给建议：设计最大量与台账最大储存量在标准里是两个口径
    （前者按设备设计容积/额定充装量），直接采用会算小导致漏判。
    """
    res = await db.execute(select(HazardousChemical).where(HazardousChemical.id == chemical_id))
    chem = res.scalar_one_or_none()
    if chem is None:
        raise LinkageError("危化品台账条目不存在")
    if getattr(chem, "enterprise_id", None) != enterprise_id:
        raise LinkageError("危化品台账条目与单元不属于同一企业，禁止关联")

    if getattr(chem, "storage_amount", None) is not None:
        suggested = float(chem.storage_amount)
        source = "structured"
    else:
        value, _unit = parse_storage_text(getattr(chem, "max_storage", None))
        suggested = value
        source = "text"

    return {
        "chemical_id": chemical_id,
        "chemical_name": chem.name,
        "suggested_q": suggested,
        "ledger_text": getattr(chem, "max_storage", None),
        "source": source,
        "hint": DESIGN_MAX_HINT,
        "requires_confirmation": True,
    }


async def link_unit_chemical_to_ledger(
    db: AsyncSession,
    *,
    unit_chemical_id: str,
    chemical_id: Optional[str],
) -> dict:
    """把单元品种行关联到危化品台账条目（只写引用，**不改数量**）。"""
    res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.id == unit_chemical_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise LinkageError("单元品种行不存在")
    row.chemical_id = chemical_id
    await db.commit()
    return {"unit_chemical_id": unit_chemical_id, "chemical_id": chemical_id}
