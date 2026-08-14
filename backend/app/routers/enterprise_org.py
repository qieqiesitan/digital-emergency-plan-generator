from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.enterprise_org import (
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    OrgTreeUpdate,
)
from app.services.enterprise_org_service import sync_org_structure, validate_org_tree

router = APIRouter(prefix="/enterprises/{enterprise_id}/org", tags=["Enterprise Org"])


async def _get_ent(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    """读路径企业归属校验：企业存在且属于当前用户。

    契约要求读权限放开给登录用户（企业主或成员），但本项目企业均为单个
    user 所有、尚无成员归属关系，因此读写统一按
    enterprise.user_id == current_user.id 校验归属（成员场景后续扩展）。
    """
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == user_id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent


async def _get_owned_ent(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    """写路径：企业不存在 → 404；存在但非当前用户所有 → 403（仅企业主可写）。"""
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    if ent.user_id != user_id:
        raise HTTPException(403, "无权限操作该企业")
    return ent


async def _get_member(enterprise_id: str, member_id: str, db: AsyncSession) -> EnterpriseMember:
    member = (await db.execute(
        select(EnterpriseMember).where(
            EnterpriseMember.id == member_id,
            EnterpriseMember.enterprise_id == enterprise_id,
        )
    )).scalar_one_or_none()
    if not member:
        raise HTTPException(404, "成员不存在")
    return member


@router.get("/nodes", response_model=ApiResponse[list])
async def get_org_nodes(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    return ApiResponse(data=ent.org_structure or [])


@router.put("/nodes", response_model=ApiResponse[list])
async def update_org_nodes(
    enterprise_id: str,
    body: OrgTreeUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = await _get_owned_ent(enterprise_id, current_user.id, db)
    nodes = [n.model_dump() for n in body.nodes]
    errors = validate_org_tree(nodes)
    if errors:
        raise HTTPException(422, detail={"code": "ORG_TREE_INVALID", "message": "；".join(errors)})
    sync_org_structure(ent, nodes)
    await db.commit()
    return ApiResponse(data=ent.org_structure)


@router.post("/members", response_model=ApiResponse[MemberResponse], status_code=201)
async def create_member(
    enterprise_id: str,
    body: MemberCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_owned_ent(enterprise_id, current_user.id, db)
    user = (await db.execute(select(User).where(User.id == body.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    exists = (await db.execute(
        select(EnterpriseMember.id).where(
            EnterpriseMember.enterprise_id == enterprise_id,
            EnterpriseMember.user_id == body.user_id,
        )
    )).first()
    if exists:
        raise HTTPException(409, "该用户已是企业成员")
    member = EnterpriseMember(enterprise_id=enterprise_id, **body.model_dump(exclude_none=True))
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return ApiResponse(data=MemberResponse.model_validate(member))


@router.put("/members/{member_id}", response_model=ApiResponse[MemberResponse])
async def update_member(
    enterprise_id: str,
    member_id: str,
    body: MemberUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_owned_ent(enterprise_id, current_user.id, db)
    member = await _get_member(enterprise_id, member_id, db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(member, key, value)
    await db.commit()
    await db.refresh(member)
    return ApiResponse(data=MemberResponse.model_validate(member))


@router.delete("/members/{member_id}")
async def delete_member(
    enterprise_id: str,
    member_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_owned_ent(enterprise_id, current_user.id, db)
    member = await _get_member(enterprise_id, member_id, db)
    await db.delete(member)
    await db.commit()
    return {"code": 0, "message": "已删除"}


@router.get("/members", response_model=ApiResponse[list[MemberResponse]])
async def list_members(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    rows = (await db.execute(
        select(EnterpriseMember, User)
        .join(User, User.id == EnterpriseMember.user_id)
        .where(EnterpriseMember.enterprise_id == enterprise_id)
        .order_by(EnterpriseMember.created_at)
    )).all()
    items = [
        MemberResponse(
            id=m.id,
            enterprise_id=m.enterprise_id,
            user_id=m.user_id,
            email=u.email,
            name=u.name,
            org_node_id=m.org_node_id,
            position=m.position,
            role=m.role,
            enabled=m.enabled,
        )
        for m, u in rows
    ]
    return ApiResponse(data=items)
