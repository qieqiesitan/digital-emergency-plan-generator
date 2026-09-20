"""风险事件统计服务，统一新旧 UI 的统计口径。"""
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.enterprise import RiskSource
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent

# 说明（D-1 修复）：全项目的「风险源数」口径统一为**新五层事件数**
# （设计决策见 docs/superpowers/specs/2026-08-06-only-risk-management-design.md
# 「统计口径 = 新「风险事件数」替代旧「风险源数」」）。
# 旧表 `risk_sources` 仅作兼容/迁移备份，其条数只在"是否还有待迁移数据"这类
# 迁移提示场景下使用，不再进入任何统计口径。


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


async def count_enterprise_legacy_risk_sources(db: AsyncSession, enterprise_id: str) -> int:
    """旧版 risk_sources 表条数。仅用于迁移提示与 has-risk 兜底，不作统计口径。"""
    return (
        await db.execute(
            select(func.count(RiskSource.id)).where(RiskSource.enterprise_id == enterprise_id)
        )
    ).scalar() or 0


async def enterprise_has_risk(db: AsyncSession, enterprise_id: str) -> bool:
    """企业是否有风险数据：新五层事件 **或** 未迁移的旧风险源，任一存在即为有。

    只认新五层会让尚未跑迁移向导的企业被判为「无风险」，从而让预案质检里
    以「有风险点」为前提的告警（E3 资源数量为 0）静默不触发——这是漏检，
    比误报更危险。因此导出/质检统一走本函数。
    """
    if await count_enterprise_risk_events(db, enterprise_id):
        return True
    return bool(await count_enterprise_legacy_risk_sources(db, enterprise_id))


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
