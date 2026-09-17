"""DataHub 目标实体写入器。

这些函数是**唯一**会把确认后的数据写进正式业务表的代码。
由确认流程调用，因此必须做完整的入参校验——走到这里的数据已经过人工确认，
失败意味着数据本身有问题或映射配错了，要显式报错而不是静默跳过。
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.major_hazard import MajorHazardUnit, MajorHazardUnitChemical
from app.services.ingest_service import register_target_writer

logger = logging.getLogger("ingest_writers")


class WriterPayloadError(ValueError):
    """确认后的载荷缺少写库所需字段。"""


async def write_major_hazard_unit(db: AsyncSession, payload: dict, item) -> str:
    enterprise_id = payload.get("enterprise_id")
    if not enterprise_id:
        raise WriterPayloadError("写入重大危险源单元需要 enterprise_id")
    name = payload.get("name")
    if not name:
        raise WriterPayloadError("写入重大危险源单元需要 name")
    unit_type = payload.get("unit_type")
    if unit_type not in ("production", "storage"):
        raise WriterPayloadError(f"unit_type 取值非法：{unit_type!r}")

    unit = MajorHazardUnit(
        enterprise_id=enterprise_id,
        name=name,
        unit_type=unit_type,
        boundary_desc=payload.get("boundary_desc"),
        address=payload.get("address"),
    )
    db.add(unit)
    await db.flush()
    return unit.id


async def write_major_hazard_unit_chemical(db: AsyncSession, payload: dict, item) -> str:
    unit_name = payload.get("unit_name")
    if not unit_name:
        raise WriterPayloadError("写入单元品种需要 unit_name 以确定归属单元")
    unit = await _find_unit(
        db, unit_name=unit_name, enterprise_id=payload.get("enterprise_id")
    )

    if payload.get("critical_quantity_t") is None:
        raise WriterPayloadError(
            f"「{payload.get('chemical_name')}」的临界量未确定，请先指定危险性类别"
        )
    if payload.get("beta") is None:
        raise WriterPayloadError(
            f"「{payload.get('chemical_name')}」的校正系数 β 未确定，请先指定危险性类别"
        )
    q = payload.get("q_design_max")
    if q is None:
        raise WriterPayloadError("缺少设计最大量 q_design_max")

    row = MajorHazardUnitChemical(
        unit_id=unit.id,
        chemical_name=payload["chemical_name"],
        physical_state=payload.get("physical_state"),
        q_design_max=Decimal(str(q)),
        critical_quantity_t=Decimal(str(payload["critical_quantity_t"])),
        beta=Decimal(str(payload["beta"])),
        beta_source=payload.get("beta_source") or "table3",
    )
    db.add(row)
    await db.flush()
    return row.id


_REGISTERED = False


async def _find_unit(
    db: AsyncSession, *, unit_name: str, enterprise_id: str | None = None
) -> MajorHazardUnit:
    """按名称找归属单元；多企业同名时**不猜**。

    多企业部署下「罐区A」这种名字必然重名。原实现用 scalar_one_or_none()，
    多命中会抛 MultipleResultsFound（技术错误暴露给用户）；这里改为显式报错，
    提示补充 enterprise_id——宁可让人再确认一次，也不能把品种写到别的企业去。
    """
    stmt = select(MajorHazardUnit).where(MajorHazardUnit.name == unit_name)
    if enterprise_id:
        stmt = stmt.where(MajorHazardUnit.enterprise_id == enterprise_id)
    res = await db.execute(stmt)
    units = list(res.scalars().all())
    if not units:
        raise WriterPayloadError(f"未找到名称为「{unit_name}」的重大危险源单元")
    if len(units) > 1:
        raise WriterPayloadError(
            f"存在 {len(units)} 个名称为「{unit_name}」的单元，无法确定归属；"
            "请在载荷中补充 enterprise_id 或改用唯一名称"
        )
    return units[0]


def register_default_writers() -> None:
    """注册内置写入器。应用启动时调用一次即可，重复调用无害。"""
    global _REGISTERED
    register_target_writer("major_hazard_unit", write_major_hazard_unit)
    register_target_writer("major_hazard_unit_chemical", write_major_hazard_unit_chemical)
    _REGISTERED = True
    logger.info("DataHub 目标写入器已注册：major_hazard_unit / major_hazard_unit_chemical")
