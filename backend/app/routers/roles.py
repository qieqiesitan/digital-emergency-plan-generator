from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.role import Role, Permission, RolePermission
from app.models.user import User
from app.schemas.role import RoleResponse, RoleCreate, RoleUpdate, PermissionResponse
from app.schemas.common import ApiResponse
from app.dependencies import require_admin, require_super_admin, get_current_user

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("", response_model=ApiResponse[list[RoleResponse]])
async def list_roles(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Role).options(selectinload(Role.permissions)).order_by(Role.created_at)
    )).scalars().all()
    return ApiResponse(data=[RoleResponse.model_validate(r) for r in rows])


@router.get("/my-menus", response_model=ApiResponse[list[str]])
async def my_menus(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前用户角色有权访问的菜单 code 列表"""
    role = (await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.code == current_user.role)
    )).scalar_one_or_none()
    if not role:
        return ApiResponse(data=[])
    codes = [p.code for p in role.permissions if p.category == "menu"]
    return ApiResponse(data=codes)


@router.get("/{role_id}", response_model=ApiResponse[RoleResponse])
async def get_role(
    role_id: str,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "角色不存在")
    return ApiResponse(data=RoleResponse.model_validate(row))


@router.post("", response_model=ApiResponse[RoleResponse], status_code=201)
async def create_role(
    data: RoleCreate,
    _=Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = (await db.execute(select(Role).where(Role.code == data.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"角色标识 {data.code} 已存在")
    role = Role(name=data.name, code=data.code, description=data.description)
    if data.permission_ids:
        perm_rows = (await db.execute(select(Permission).where(Permission.id.in_(data.permission_ids)))).scalars().all()
        role.permissions = list(perm_rows)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    role = (await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role.id)
    )).scalar_one()
    return ApiResponse(data=RoleResponse.model_validate(role))


@router.put("/{role_id}", response_model=ApiResponse[RoleResponse])
async def update_role(
    role_id: str,
    data: RoleUpdate,
    _=Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    role = (await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )).scalar_one_or_none()
    if not role:
        raise HTTPException(404, "角色不存在")
    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permission_ids is not None:
        perm_rows = (await db.execute(select(Permission).where(Permission.id.in_(data.permission_ids)))).scalars().all()
        role.permissions = list(perm_rows)
    await db.commit()
    await db.refresh(role)
    return ApiResponse(data=RoleResponse.model_validate(role))


@router.delete("/{role_id}")
async def delete_role(
    role_id: str,
    _=Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(404, "角色不存在")
    if role.is_system:
        raise HTTPException(400, "系统内置角色不可删除")
    await db.delete(role)
    await db.commit()
    return {"code": 0, "message": "已删除"}


@router.get("/permissions/list", response_model=ApiResponse[list[PermissionResponse]])
async def list_permissions(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Permission).order_by(Permission.category, Permission.resource, Permission.action))).scalars().all()
    return ApiResponse(data=[PermissionResponse.model_validate(r) for r in rows])
