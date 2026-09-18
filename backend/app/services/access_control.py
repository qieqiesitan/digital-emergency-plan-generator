"""企业归属校验（多模块共用的租户隔离入口）。

约定：企业数据（含作业票、重大危险源单元等子实体）只有企业所有者可访问；
校验失败统一返回 404，避免通过状态码探测资源是否存在。
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise


async def ensure_enterprise_owned(
    db: AsyncSession,
    user,
    enterprise_id: str,
    *,
    detail: str = "企业不存在或无权访问",
) -> Enterprise:
    user_id = getattr(user, "id", None)
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id,
            Enterprise.user_id == user_id,
        )
    )).scalar_one_or_none()
    if ent is None:
        raise HTTPException(404, detail)
    return ent


async def ensure_ticket_owned(db: AsyncSession, user, ticket_id: str):
    """校验作业票存在且其所属企业归当前用户所有。"""
    from app.models.work_ticket import WorkTicketInstance

    instance = (await db.execute(
        select(WorkTicketInstance).where(WorkTicketInstance.id == ticket_id)
    )).scalar_one_or_none()
    if instance is None:
        raise HTTPException(404, "作业票不存在")
    await ensure_enterprise_owned(db, user, instance.enterprise_id, detail="作业票不存在")
    return instance


async def ensure_major_hazard_unit_owned(db: AsyncSession, user, unit_id: str):
    """校验重大危险源单元存在且其所属企业归当前用户所有。"""
    from app.models.major_hazard import MajorHazardUnit

    unit = (await db.execute(
        select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id)
    )).scalar_one_or_none()
    if unit is None:
        raise HTTPException(404, "重大危险源单元不存在")
    await ensure_enterprise_owned(db, user, unit.enterprise_id, detail="重大危险源单元不存在")
    return unit
