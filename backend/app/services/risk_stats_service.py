"""风险事件统计服务，统一新旧 UI 的统计口径。"""
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent


async def count_enterprise_risk_events(db: AsyncSession, enterprise_id: str) -> int:
    return (
        await db.execute(
            select(func.count(func.distinct(RiskEvent.id)))
            .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
            .join(
                RiskObject,
                or_(
                    RiskEvent.object_id == RiskObject.id,
                    RiskUnit.object_id == RiskObject.id,
                ),
            )
            .join(RiskZone, RiskObject.zone_id == RiskZone.id)
            .where(RiskZone.enterprise_id == enterprise_id)
        )
    ).scalar() or 0


async def count_user_risk_events(db: AsyncSession, user_id: str) -> int:
    return (
        await db.execute(
            select(func.count(func.distinct(RiskEvent.id)))
            .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
            .join(
                RiskObject,
                or_(
                    RiskEvent.object_id == RiskObject.id,
                    RiskUnit.object_id == RiskObject.id,
                ),
            )
            .join(RiskZone, RiskObject.zone_id == RiskZone.id)
            .join(Enterprise, RiskZone.enterprise_id == Enterprise.id)
            .where(Enterprise.user_id == user_id)
        )
    ).scalar() or 0


async def count_enterprises_risk_events(
    db: AsyncSession,
    enterprise_ids: list[str],
) -> dict[str, int]:
    if not enterprise_ids:
        return {}
    rows = (
        await db.execute(
            select(
                RiskZone.enterprise_id,
                func.count(func.distinct(RiskEvent.id)),
            )
            .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
            .join(
                RiskObject,
                or_(
                    RiskEvent.object_id == RiskObject.id,
                    RiskUnit.object_id == RiskObject.id,
                ),
            )
            .join(RiskZone, RiskObject.zone_id == RiskZone.id)
            .where(RiskZone.enterprise_id.in_(enterprise_ids))
            .group_by(RiskZone.enterprise_id)
        )
    ).all()
    return {row[0]: row[1] for row in rows}
