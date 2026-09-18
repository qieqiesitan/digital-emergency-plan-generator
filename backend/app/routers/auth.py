from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
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
    RESET_TOKEN_TTL_MINUTES, revoke_token, is_token_revoked, hash_reset_token,
)
from jose import JWTError
from app.middleware.rate_limit import rate_limited

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _: None = rate_limited(limit=10, window_seconds=3600, scope="register"),
):
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
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _: None = rate_limited(limit=30, window_seconds=900, scope="login"),
):
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
        if await is_token_revoked(payload.get("jti")):
            raise HTTPException(status_code=401, detail="Invalid refresh token")
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
async def logout(data: LogoutRequest, request: Request):
    """撤销 refresh/access token（进程内 jti 黑名单）。

    限制：单 worker 内存实现；多 worker/重启后黑名单失效，
    token 在自然过期前仍可用——生产多 worker 部署需换共享存储。
    """
    if data.refresh_token:
        await revoke_token(data.refresh_token)
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        await revoke_token(auth_header[7:].strip())
    return {"code": 0, "message": "ok"}


@router.post("/forgot-password", response_model=ApiResponse[dict])
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _: None = rate_limited(limit=10, window_seconds=900, scope="forgot_password"),
):
    """申请密码找回（骨架）：生成令牌并落库，邮件发送留空待 SMTP 接入。

    W2：系统未接 SMTP，管理员重置是唯一可用闭环——这里不再签发死令牌、
    也不再声称"将发送邮件"（原实现让用户空等）。无论邮箱是否存在返回同一提示。
    """
    return ApiResponse(
        data={},
        message="请联系企业管理员在「设置 → 用户管理」中重置密码",
    )


@router.post("/reset-password", response_model=ApiResponse[dict])
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """使用找回令牌重置密码：按哈希查令牌，校验有效/未过期/未使用后更新密码。"""
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == hash_reset_token(data.token))
    )
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
