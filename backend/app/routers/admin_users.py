from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.role import Role
from app.schemas.role import AdminUserCreate, AdminUserUpdate, AdminUserResponse, AdminResetPassword
from app.schemas.common import ApiResponse
from app.services.auth_service import hash_password
from app.dependencies import require_admin, require_super_admin, get_current_user

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


@router.get("", response_model=ApiResponse[dict])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if search:
        q = q.where(
            (User.email.ilike(f"%{search}%")) | (User.name.ilike(f"%{search}%"))
        )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    rows = (await db.execute(q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return ApiResponse(data={
        "items": [AdminUserResponse.model_validate(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/{user_id}", response_model=ApiResponse[AdminUserResponse])
async def get_user(
    user_id: str,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    return ApiResponse(data=AdminUserResponse.model_validate(user))


@router.post("", response_model=ApiResponse[AdminUserResponse], status_code=201)
async def create_user(
    data: AdminUserCreate,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "该邮箱已存在")
    role_exists = (await db.execute(select(Role).where(Role.code == data.role))).scalar_one_or_none()
    if not role_exists:
        raise HTTPException(400, f"角色 {data.role} 不存在")
    user = User(email=data.email, name=data.name, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return ApiResponse(data=AdminUserResponse.model_validate(user))


@router.put("/{user_id}", response_model=ApiResponse[AdminUserResponse])
async def update_user(
    user_id: str,
    data: AdminUserUpdate,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    if data.name is not None:
        user.name = data.name
    if data.role is not None:
        role_exists = (await db.execute(select(Role).where(Role.code == data.role))).scalar_one_or_none()
        if not role_exists:
            raise HTTPException(400, f"角色 {data.role} 不存在")
        user.role = data.role
    await db.commit()
    await db.refresh(user)
    return ApiResponse(data=AdminUserResponse.model_validate(user))


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    _=Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(400, "不能删除自己")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    await db.delete(user)
    await db.commit()
    return {"code": 0, "message": "已删除"}


@router.post("/{user_id}/reset-password", response_model=ApiResponse[AdminUserResponse])
async def reset_user_password(
    user_id: str,
    data: AdminResetPassword,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    await db.refresh(user)
    return ApiResponse(data=AdminUserResponse.model_validate(user))
