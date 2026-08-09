from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, LogoutRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
)
from app.schemas.user import UserResponse
from app.schemas.common import ApiResponse
from app.services.auth_service import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, generate_password_reset_token, send_password_reset_email,
    RESET_TOKEN_TTL_MINUTES,
)
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邮箱已被注册")
    if data.password != data.password_confirm:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")
    user = User(email=data.email, password_hash=hash_password(data.password), name=data.name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return ApiResponse(data=UserResponse.model_validate(user))

@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    from app.config import settings
    return ApiResponse(data=TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    ))

@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="User not found")
    from app.config import settings
    return ApiResponse(data=TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    ))

@router.post("/logout")
async def logout(data: LogoutRequest):
    return {"code": 0, "message": "ok"}


@router.post("/forgot-password", response_model=ApiResponse[dict])
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """申请密码找回（骨架）：生成令牌并落库，邮件发送留空待 SMTP 接入。

    无论邮箱是否存在均返回相同成功提示，不泄露用户是否存在。
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user:
        token = generate_password_reset_token()
        db.add(PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        ))
        await db.commit()
        send_password_reset_email(user.email, token)
    return ApiResponse(data={}, message="如果该邮箱已注册，我们将发送密码重置邮件")


@router.post("/reset-password", response_model=ApiResponse[dict])
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """使用找回令牌重置密码：校验令牌有效/未过期/未使用后更新密码。"""
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == data.token))
    reset = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not reset or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(status_code=400, detail="重置链接无效或已过期")
    user_result = await db.execute(select(User).where(User.id == reset.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="重置链接无效或已过期")
    user.password_hash = hash_password(data.new_password)
    reset.used_at = now
    await db.commit()
    return ApiResponse(data={}, message="密码已重置，请使用新密码登录")
