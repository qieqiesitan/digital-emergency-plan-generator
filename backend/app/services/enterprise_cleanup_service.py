from sqlalchemy import delete, select
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

async def delete_enterprise_complete(db: AsyncSession, enterprise_id: str):
    await delete_enterprise_risk_mapping(db, enterprise_id)
    await db.execute(delete(Enterprise).where(Enterprise.id == enterprise_id))
