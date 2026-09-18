"""跨企业总览聚合。

与 enterprise_cockpit_service 的分工：那个是单企业驾驶舱，这个是平台级视角。
"""

from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.hazard_management import HazardRecord
from app.models.major_hazard import MajorHazardCalculation, MajorHazardUnit
from app.models.risk_management import RiskObject
from app.models.work_ticket import WorkTicketInstance


async def _count(db: AsyncSession, stmt) -> int:
    res = await db.execute(stmt)
    return int(res.scalar() or 0)


async def overview_totals(db: AsyncSession) -> dict:
    """平台级总量。每项一个 count 查询，够用且直观。"""
    enterprises = await _count(db, select(func.count()).select_from(Enterprise))
    risk_points = await _count(
        db,
        select(func.count()).select_from(RiskObject).where(RiskObject.is_risk_point.is_(True)),
    )
    hazards = await _count(db, select(func.count()).select_from(HazardRecord))
    major_units = await _count(db, select(func.count()).select_from(MajorHazardUnit))
    # 一、二级重大危险源是监管重点，单独计数。
    # 一个单元可能有多轮计算，历史快照不能重复计入：先按单元取最大 seq 的最新快照，
    # 再在最新快照上筛等级，否则"先算出二级、后算出不构成"的单元会被误算成二级。
    latest_snapshot = (
        select(
            MajorHazardCalculation.unit_id.label("unit_id"),
            func.max(MajorHazardCalculation.seq).label("max_seq"),
        )
        .group_by(MajorHazardCalculation.unit_id)
        .subquery()
    )
    level_1_2 = await _count(
        db,
        select(func.count())
        .select_from(MajorHazardCalculation)
        .join(
            latest_snapshot,
            and_(
                MajorHazardCalculation.unit_id == latest_snapshot.c.unit_id,
                MajorHazardCalculation.seq == latest_snapshot.c.max_seq,
            ),
        )
        .where(MajorHazardCalculation.is_major_hazard.is_(True))
        .where(MajorHazardCalculation.level.in_(["一级", "二级"])),
    )
    work_tickets = await _count(db, select(func.count()).select_from(WorkTicketInstance))
    return {
        "enterprises": enterprises,
        "risk_points": risk_points,
        "hazards": hazards,
        "major_hazard_units": major_units,
        "major_hazard_level_1_2": level_1_2,
        "work_tickets": work_tickets,
    }
