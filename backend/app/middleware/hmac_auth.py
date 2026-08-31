"""HMAC-SHA256 签名验证中间件 — 保护 /api/external/* 端点"""
import hashlib, hmac, time, logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import settings
from app.services.third_party_config import get_third_party_config

logger = logging.getLogger("hmac_auth")

MAX_CLOCK_SKEW = 300  # 5 minutes


def _build_signature(method: str, path: str, timestamp: str, body: str, secret: str) -> str:
    payload = f"{method}\n{path}\n{timestamp}\n{body}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


class HmacAuthMiddleware(BaseHTTPMiddleware):
    """对 /api/external/* 路径强制 HMAC 签名验证"""

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/external"):
            return await call_next(request)

        # 中间件为 async（BaseHTTPMiddleware.dispatch），可直接 await 配置查询；
        # DB 有值优先，其次环境变量，最后回退 settings 默认（空）。
        # 配置读取异常（DB 不可达/解密失败）时回退 env，保证 /api/external/* 不因读取故障 500。
        try:
            secret = await get_third_party_config("third_party.protego.hmac_secret") or settings.EXTERNAL_API_HMAC_SECRET
        except Exception as exc:
            logger.warning("Failed to read HMAC secret from config, falling back to env: %s", exc)
            secret = settings.EXTERNAL_API_HMAC_SECRET
        if not secret:
            logger.warning("EXTERNAL_API_HMAC_SECRET not configured, rejecting external request")
            return JSONResponse({"detail": "External API not configured"}, status_code=503)

        sig = request.headers.get("X-Signature", "")
        ts = request.headers.get("X-Timestamp", "")
        if not sig or not ts:
            return JSONResponse({"detail": "Missing HMAC headers"}, status_code=401)

        try:
            t = int(ts)
            if abs(time.time() - t) > MAX_CLOCK_SKEW:
                return JSONResponse({"detail": "Timestamp expired"}, status_code=401)
        except ValueError:
            return JSONResponse({"detail": "Invalid timestamp"}, status_code=401)

        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""
        expected = _build_signature(request.method, request.url.path, ts, body_str, secret)

        if not hmac.compare_digest(expected, sig):
            return JSONResponse({"detail": "Invalid signature"}, status_code=401)

        # Reconstruct request body for downstream consumers
        async def receive():
            return {"type": "http.request", "body": body_bytes}
        request._receive = receive

        return await call_next(request)
