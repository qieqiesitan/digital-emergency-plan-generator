from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enterprise import Enterprise, EnterpriseFloor
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure


async def delete_enterprise_risk_mapping(db: AsyncSession, enterprise_id: str):
    object_ids = (await db.execute(select(RiskObject.id).where(RiskObject.enterprise_id == enterprise_id))).scalars().all()
    zone_ids = (await db.execute(select(RiskZone.id).where(RiskZone.enterprise_id == enterprise_id))).scalars().all()
    if object_ids:
        await db.execute(delete(RiskMeasure).where(RiskMeasure.event_id.in_(select(RiskEvent.id).where(RiskEvent.object_id.in_(object_ids)))))
        await db.execute(delete(RiskEvent).where(RiskEvent.object_id.in_(object_ids)))
        await db.execute(delete(RiskUnit).where(RiskUnit.object_id.in_(object_ids)))
    await db.execute(delete(RiskObject).where(RiskObject.enterprise_id == enterprise_id))
    if zone_ids:
        await db.execute(delete(RiskZone).where(RiskZone.id.in_(zone_ids)))
    await db.execute(delete(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id))


def _floor_object_ids(floor_id: str):
    """楼层删除用：分区 id + 对象 id（含挂在楼层但未绑分区的对象）。"""
    zone_ids = select(RiskZone.id).where(RiskZone.floor_id == floor_id)
    object_ids = select(RiskObject.id).where(
        or_(RiskObject.floor_id == floor_id, RiskObject.zone_id.in_(zone_ids))
    )
    return zone_ids, object_ids


async def delete_floor_risk_mapping(db: AsyncSession, floor_id: str):
    """按依赖顺序级联清理楼层下全部风险分级数据（措施→事件→单元→对象→分区）。"""
    zone_ids, object_ids = _floor_object_ids(floor_id)
    unit_ids = select(RiskUnit.id).where(RiskUnit.object_id.in_(object_ids))
    event_ids = select(RiskEvent.id).where(
        or_(RiskEvent.object_id.in_(object_ids), RiskEvent.unit_id.in_(unit_ids))
    )
    await db.execute(delete(RiskMeasure).where(RiskMeasure.event_id.in_(event_ids)))
    await db.execute(delete(RiskEvent).where(RiskEvent.id.in_(event_ids)))
    await db.execute(delete(RiskUnit).where(RiskUnit.id.in_(unit_ids)))
    await db.execute(delete(RiskObject).where(RiskObject.id.in_(object_ids)))
    await db.execute(delete(RiskZone).where(RiskZone.id.in_(zone_ids)))


async def floor_delete_counts(db: AsyncSession, floor_id: str) -> dict:
    """统计楼层下待级联删除的风险数据数量，供前端二次确认。"""
    zone_ids, object_ids = _floor_object_ids(floor_id)
    unit_ids = select(RiskUnit.id).where(RiskUnit.object_id.in_(object_ids))
    event_ids = select(RiskEvent.id).where(
        or_(RiskEvent.object_id.in_(object_ids), RiskEvent.unit_id.in_(unit_ids))
    )
    counts = {
        "zones": (await db.execute(select(func.count(RiskZone.id)).where(RiskZone.floor_id == floor_id))).scalar() or 0,
        "objects": (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.id.in_(object_ids)))).scalar() or 0,
        "units": (await db.execute(select(func.count(RiskUnit.id)).where(RiskUnit.object_id.in_(object_ids)))).scalar() or 0,
        "events": (await db.execute(select(func.count(RiskEvent.id)).where(RiskEvent.id.in_(event_ids)))).scalar() or 0,
        "measures": (await db.execute(select(func.count(RiskMeasure.id)).where(RiskMeasure.event_id.in_(event_ids)))).scalar() or 0,
    }
    counts["total"] = sum(counts.values())
    return counts


async def _cleanup_counts(db: AsyncSession, enterprise_id: str) -> dict:
    """统计待清理的风险分级与楼层数据数量，供前端二次确认。"""
    object_ids = select(RiskObject.id).where(RiskObject.enterprise_id == enterprise_id)
    unit_ids = select(RiskUnit.id).where(RiskUnit.object_id.in_(object_ids))
    event_ids = select(RiskEvent.id).where(or_(RiskEvent.object_id.in_(object_ids), RiskEvent.unit_id.in_(unit_ids)))
    counts = {
        "floors": (await db.execute(select(func.count(EnterpriseFloor.id)).where(EnterpriseFloor.enterprise_id == enterprise_id))).scalar() or 0,
        "zones": (await db.execute(select(func.count(RiskZone.id)).where(RiskZone.enterprise_id == enterprise_id))).scalar() or 0,
        "objects": (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.enterprise_id == enterprise_id))).scalar() or 0,
        "units": (await db.execute(select(func.count(RiskUnit.id)).where(RiskUnit.object_id.in_(object_ids)))).scalar() or 0,
        "events": (await db.execute(select(func.count(RiskEvent.id)).where(or_(RiskEvent.object_id.in_(object_ids), RiskEvent.unit_id.in_(unit_ids))))).scalar() or 0,
        "measures": (await db.execute(select(func.count(RiskMeasure.id)).where(RiskMeasure.event_id.in_(event_ids)))).scalar() or 0,
    }
    counts["total"] = sum(counts.values())
    return counts


async def delete_enterprise_complete(db: AsyncSession, enterprise_id: str) -> dict:
    """同一事务内按依赖顺序清理风险分级数据并删除企业，返回待清理数量。"""
    counts = await _cleanup_counts(db, enterprise_id)
    await delete_enterprise_risk_mapping(db, enterprise_id)
    await db.execute(delete(Enterprise).where(Enterprise.id == enterprise_id))
    return counts
