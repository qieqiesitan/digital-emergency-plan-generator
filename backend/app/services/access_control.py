"""企业归属校验（多模块共用的租户隔离入口）。

约定：企业数据（含作业票、重大危险源单元等子实体）只有企业所有者可访问；
校验失败统一返回 404，避免通过状态码探测资源是否存在。
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember

# 报告「可读」状态：生成中也要能看进度与预览，草稿可看，已完成可看
READABLE_REPORT_STATUSES = ["completed", "draft", "generating"]


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


async def load_report_for_owner(
    db: AsyncSession,
    user,
    enterprise_id: str,
    model,
    *,
    report_detail: str,
    enterprise_detail: str = "企业不存在或无权访问",
    required: bool = True,
) -> tuple[Enterprise, object | None]:
    """企业归属校验 + 取回该企业的可读报告。

    返回 (企业, 报告)：调用方常用企业名生成导出文件名。
    企业不存在/无权访问始终 404；报告缺失时默认也 404，传 required=False 则返回
    (企业, None)——用于「报告还没生成」属于正常空态的读取端点（导出/预览等仍需
    required=True，因为缺报告就真的做不了事）。
    """
    ent = await ensure_enterprise_owned(db, user, enterprise_id, detail=enterprise_detail)
    report = (await db.execute(
        select(model).where(
            model.enterprise_id == enterprise_id,
            model.status.in_(READABLE_REPORT_STATUSES),
        )
    )).scalar_one_or_none()
    if report is None and required:
        raise HTTPException(404, report_detail)
    return ent, report


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


async def ensure_enterprise_visible(
    db: AsyncSession,
    user,
    enterprise_id: str,
    *,
    detail: str = "企业不存在或无权访问",
) -> tuple[Enterprise, bool]:
    """读路径可见性：所有者 → (企业, True)；有效成员 → (企业, False)；其余 → 404。

    成员口径：`enterprise_members` 里 `user_id` 已绑定且 `enabled=True`。
    作业票审批需要非企业主的法定审批人参与，因此这条"成员可见"入口是必要的；
    具体可见哪些资源由调用方收窄（作业票：仅轮到自己签或自己签过的票）。
    """
    user_id = getattr(user, "id", None)
    if not user_id:
        raise HTTPException(404, detail)
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id)
    )).scalar_one_or_none()
    if ent is None:
        raise HTTPException(404, detail)
    if ent.user_id == user_id:
        return ent, True
    member_id = (await db.execute(
        select(EnterpriseMember.id).where(
            EnterpriseMember.enterprise_id == enterprise_id,
            EnterpriseMember.user_id == user_id,
            EnterpriseMember.enabled.is_(True),
        ).limit(1)
    )).scalar_one_or_none()
    if member_id is None:
        raise HTTPException(404, detail)
    return ent, False
