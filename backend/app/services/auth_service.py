from datetime import datetime, timedelta, timezone
import secrets
import threading
import time
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings, is_weak_secret_key

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 密码找回令牌有效期（分钟）
RESET_TOKEN_TTL_MINUTES = 30

# 登出撤销表：jti -> 过期时间戳（进程内；多 worker/重启后失效，注释见 logout 路由）
_revoked_tokens: dict[str, float] = {}
_revoke_lock = threading.Lock()

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
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    jti = payload.get("jti")
    now = time.time()
    with _revoke_lock:
        if jti:
            if _revoked_tokens.get(jti, 0) > now:
                raise JWTError("Token has been revoked")
            # 惰性清理过期条目
            expired = [k for k, exp in _revoked_tokens.items() if exp <= now]
            for k in expired:
                _revoked_tokens.pop(k, None)
    return payload


def revoke_token(token: str) -> None:
    """将 token 加入撤销表（按其 exp 到期自动失效）。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        with _revoke_lock:
            _revoked_tokens[jti] = float(exp)


def generate_password_reset_token() -> str:
    """生成密码找回令牌（随机 URL 安全串）。"""
    return secrets.token_urlsafe(32)


def send_password_reset_email(email: str, token: str) -> None:
    """发送密码重置邮件（骨架：待 SMTP 接入后实现，本次不发送）。"""
    return None
