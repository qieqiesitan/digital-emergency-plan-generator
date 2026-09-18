from datetime import datetime, timedelta, timezone
import secrets
import time
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings, is_weak_secret_key
from app.services.runtime_state import get_state, set_state

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 密码找回令牌有效期（分钟）
RESET_TOKEN_TTL_MINUTES = 30

# W2：登出撤销表改跨 worker 共享（app_runtime_state，TTL=token 剩余有效期）。
# 原进程内实现在 4 worker 下只有 1/4 概率命中，登出形同虚设。

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str) -> str:
    if is_weak_secret_key(settings.SECRET_KEY):
        raise ValueError("JWT SECRET_KEY 未配置或过弱，禁止签发 token")
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access", "jti": secrets.token_urlsafe(16)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )

def create_refresh_token(user_id: str) -> str:
    if is_weak_secret_key(settings.SECRET_KEY):
        raise ValueError("JWT SECRET_KEY 未配置或过弱，禁止签发 token")
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(16)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )

def decode_token(token: str) -> dict:
    """解码并校验签名（撤销状态由 is_token_revoked 异步查询）。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


async def is_token_revoked(jti: str | None) -> bool:
    """token 是否已被登出撤销（跨 worker 共享）。"""
    if not jti:
        return False
    return (await get_state(f"revoked:{jti}")) is not None


async def revoke_token(token: str) -> None:
    """将 token 加入共享撤销表（按其 exp 到期自动失效）。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        ttl_seconds = max(1, int(float(exp) - time.time()))
        await set_state(f"revoked:{jti}", {"revoked": True}, ttl_seconds=ttl_seconds)


def generate_password_reset_token() -> str:
    """生成密码找回令牌（随机 URL 安全串）。"""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """找回令牌只存哈希（SHA-256）：数据库泄露也无法直接重置账号。"""
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()


def send_password_reset_email(email: str, token: str) -> None:
    """邮件发送（未实现）。

    W2 决策：本系统当前支持的是"管理员在用户管理中重置密码"闭环；
    未接入 SMTP 前不再声称已发送邮件（原实现是空函数 + 前端提示已发送，误导用户）。
    接入 SMTP 后在此实现，并把 forgot_password 改回签发令牌（存 hash_reset_token 结果）。
    """
    return None
