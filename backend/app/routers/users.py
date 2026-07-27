from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UpdateProfileRequest, ChangePasswordRequest
from app.schemas.common import ApiResponse
from app.services.auth_service import hash_password, verify_password
from app.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_profile(current_user: User = Depends(get_current_user)):
    return ApiResponse(data=UserResponse.model_validate(current_user))

@router.put("/me", response_model=ApiResponse[UserResponse])
async def update_profile(data: UpdateProfileRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    current_user.name = data.name
    await db.commit()
    await db.refresh(current_user)
    return ApiResponse(data=UserResponse.model_validate(current_user))

@router.put("/me/password")
async def change_password(data: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if data.new_password != data.new_password_confirm:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")
    current_user.password_hash = hash_password(data.new_password)
    await db.commit()
    return {"code": 0, "message": "密码修改成功"}

# ── 用户默认创作风格 ──

class StylePreferenceUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}
    formality: str = "standard"
    detail_level: str = "balanced"
    table_preference: str = "moderate"
    diagram_preference: str = "mermaid"


@router.get("/me/style-preference", response_model=ApiResponse[dict])
async def get_style_preference(current_user=Depends(get_current_user)):
    """获取当前用户的默认创作风格"""
    return ApiResponse(data=current_user.default_style_preference or {
        "formality": "standard",
        "detail_level": "balanced",
        "table_preference": "moderate",
        "diagram_preference": "mermaid",
    })


@router.put("/me/style-preference", response_model=ApiResponse[dict])
async def update_style_preference(
    data: StylePreferenceUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户的默认创作风格"""
    current_user.default_style_preference = data.model_dump()
    await db.commit()
    return ApiResponse(data=current_user.default_style_preference, message="默认风格已更新")

