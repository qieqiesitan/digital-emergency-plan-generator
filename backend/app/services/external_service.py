"""封装对 PROTEGO 的回调 HTTP 调用（HMAC 签名 + 重试）"""
import hashlib, hmac, json, logging, time, httpx
from app.config import settings
from app.services.third_party_config import get_third_party_config

logger = logging.getLogger("external_service")

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def _build_signature(method: str, path: str, timestamp: str, body: str, secret: str) -> str:
    payload = f"{method}\n{path}\n{timestamp}\n{body}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def _signed_request(method: str, url: str, body: dict | None = None) -> tuple[int, str]:
    """发送带 HMAC 签名的 HTTP 请求"""
    # 签名与验签同一来源：DB 有值优先，其次环境变量，最后回退 settings。
    # 配置读取异常时回退 env，保证出站回调不因读取故障而失败。
    try:
        secret = await get_third_party_config("third_party.protego.hmac_secret") or settings.EXTERNAL_API_HMAC_SECRET
    except Exception as exc:
        logger.warning("Failed to read HMAC secret from config, falling back to env: %s", exc)
        secret = settings.EXTERNAL_API_HMAC_SECRET

    ts = str(int(time.time()))
    body_str = json.dumps(body, ensure_ascii=False) if body else ""
    sig = _build_signature(
        method, url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url, ts, body_str, secret
    )

    headers = {
        "Content-Type": "application/json",
        "X-Signature": sig,
        "X-Timestamp": ts,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        if method == "POST":
            resp = await client.post(url, content=body_str, headers=headers)
        else:
            resp = await client.get(url, headers=headers)
        return resp.status_code, resp.text


async def notify_callback(callback_url: str, payload: dict) -> bool:
    """回调通知 PROTEGO，最多重试 3 次。返回是否成功。"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            status, body = await _signed_request("POST", callback_url, payload)
            if 200 <= status < 300:
                logger.info(f"Callback succeeded: {callback_url}")
                return True
            logger.warning(f"Callback attempt {attempt}/{MAX_RETRIES}: HTTP {status}: {body[:200]}")
        except Exception as e:
            logger.warning(f"Callback attempt {attempt}/{MAX_RETRIES} error: {e}")
        if attempt < MAX_RETRIES:
            await __import__("asyncio").sleep(RETRY_DELAY * attempt)
    logger.error(f"Callback failed after {MAX_RETRIES} attempts: {callback_url}")
    return False
