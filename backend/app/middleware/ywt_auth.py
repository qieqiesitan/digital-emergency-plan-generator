from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.user import User
import logging

logger = logging.getLogger("ywt_auth")

def verify_ywt_token(token: str) -> dict:
    return jwt.decode(token, settings.YWT_JWT_SECRET, algorithms=["HS256"])

def is_ywt_request(request: Request) -> bool:
    return bool(request.headers.get("X-User-Id") and request.headers.get("X-Username"))

class YwtAuthMiddleware(BaseHTTPMiddleware):
    """中台认证中间件：三种方式识别中台用户
    1. 网关注入头 X-User-Id + X-Username（优先）
    2. Authorization Bearer 中台JWT（子应用直连后端）
    3. 降级到独立模式 Bearer token
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        whitelist = [p.strip() for p in settings.YWT_AUTH_WHITELIST.split(",") if p.strip()]
        if path in whitelist:
            return await call_next(request)

        if is_ywt_request(request):
            uid = request.headers.get("X-User-Id")
            uname = request.headers.get("X-Username")
            return await self._setup_ywt_user(request, call_next, int(uid), uname)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            try:
                p = verify_ywt_token(token)
                uid = p.get("userId")
                uname = p.get("sub")
                if uid and uname:
                    return await self._setup_ywt_user(request, call_next, int(uid), uname)
            except Exception:
                pass

        request.state.is_ywt = False
        return await call_next(request)

    async def _setup_ywt_user(self, request, call_next, ywt_user_id, ywt_username):
        try:
            async with async_session() as db:
                result = await db.execute(select(User).where(User.ywt_user_id == ywt_user_id))
                user = result.scalar_one_or_none()
                if not user:
                    user = User(
                        email=f"{ywt_username}@ywt.local",
                        password_hash="",
                        name=ywt_username,
                        role="user",
                        ywt_user_id=ywt_user_id,
                        ywt_username=ywt_username,
                    )
                    db.add(user)
                    await db.commit()
                    await db.refresh(user)
                    logger.info(f"Auto-created YWT user: {ywt_username} (id={ywt_user_id})")
                request.state.user = user
                request.state.is_ywt = True
        except Exception as e:
            logger.error(f"YWT setup error: {e}")
        return await call_next(request)
