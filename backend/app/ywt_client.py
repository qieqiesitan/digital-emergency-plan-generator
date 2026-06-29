import httpx
import logging
import time
from app.config import settings

logger = logging.getLogger("ywt_client")

YWT_TIMEOUT = 30.0  # seconds


def _headers() -> dict:
    """构建带 apiKey 鉴权的请求头"""
    return {
        "X-Api-Key": settings.YWT_API_KEY,
        "Content-Type": "application/json",
    }


def _gateway(path: str) -> str:
    return f"{settings.YWT_GATEWAY_URL}{path}"


# ponytail: one _request instead of four _get/_post/_put/_delete (identical try/except)
async def _request(method: str, path: str, body: dict | None = None,
                   params: dict | None = None) -> dict:
    name = method.upper()
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            req = client.build_request(method, _gateway(path), json=body, params=params,
                                       headers=_headers())
            resp = await client.send(req)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT {name} {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT {name} {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}


# ── JWT Token 管理 ──
_jwt_token: str | None = None
_jwt_expires_at: float = 0


async def _ensure_jwt() -> str:
    """获取有效的 JWT token（自动登录+刷新）"""
    global _jwt_token, _jwt_expires_at
    if _jwt_token and time.time() < _jwt_expires_at - 60:
        return _jwt_token

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.YWT_GATEWAY_URL}/auth/login",
                json={"username": "admin", "password": "admin123"},
                headers={"Content-Type": "application/json", "X-Api-Key": settings.YWT_API_KEY},
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                _jwt_token = result["data"]["accessToken"]
                expires_in = result["data"].get("expiresIn", 7200)
                _jwt_expires_at = time.time() + expires_in
                logger.info("YWT JWT token refreshed")
                return _jwt_token
    except Exception as e:
        logger.error(f"YWT JWT login failed: {e}")

    return settings.YWT_API_KEY


# ponytail: one _ai_request instead of three _ai_get/_ai_post/_ai_put
async def _ai_request(method: str, path: str, body: dict | None = None,
                      params: dict | None = None) -> dict:
    token = await _ensure_jwt()
    name = method.upper()
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            req = client.build_request(method, _gateway(path), json=body, params=params,
                                       headers={"Authorization": f"Bearer {token}",
                                                "Content-Type": "application/json"})
            resp = await client.send(req)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT AI {name} {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT AI {name} {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}


# ── 原有方法 ──

async def upload_oper_log(log_data: dict) -> bool:
    result = await _request("POST", "/system/log/oper", body=log_data)
    return result.get("code") == 200


async def get_user_permissions(sys_code: str, username: str) -> list:
    token = await _ensure_jwt()
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.get(
                f"{settings.YWT_GATEWAY_URL}/system/user/permissions",
                params={"sysCode": sys_code, "username": username},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result.get("data", [])
            logger.warning(f"YWT permissions query returned: {result}")
            return []
    except httpx.HTTPError as e:
        logger.error(f"YWT permissions query failed: {e}")
        return []


# ── 字典 API ──

async def fetch_dict_items(dict_type: str) -> list[dict]:
    result = await _ai_request("GET", f"/system/dict/data/type/{dict_type}")
    return result.get("data", []) or []


async def fetch_all_dict_types() -> list[dict]:
    """GET /system/dict/type/all → 获取所有字典类型"""
    result = await _ai_request("GET", "/system/dict/type/all")
    return result.get("data", []) or []


# ── 提示词 API ──

async def fetch_prompts(category: str | None = None) -> list[dict]:
    params = {"category": category} if category else {}
    result = await _ai_request("GET", "/ai/prompt/list", params=params)
    items = result.get("data", []) or []

    enriched = []
    for item in items:
        pid = item.get("id")
        if pid:
            detail = await fetch_prompt(pid)
            if detail:
                normalized = {}
                for k, v in detail.items():
                    if k == "system_prompt": normalized["systemPrompt"] = v
                    elif k == "user_prompt_template": normalized["userPromptTemplate"] = v
                    elif k == "template_code": normalized["templateCode"] = v
                    elif k == "template_name": normalized["templateName"] = v
                    elif k == "max_tokens": normalized["maxTokens"] = v
                    else: normalized[k] = v
                enriched.append({**item, **normalized})
            else:
                enriched.append(item)
        else:
            enriched.append(item)
    return enriched


async def fetch_prompt(prompt_id: int) -> dict | None:
    result = await _ai_request("GET", f"/ai/prompt/{prompt_id}")
    return result.get("data")


async def create_prompt(data: dict) -> dict:
    return await _ai_request("POST", "/ai/prompt", body=data)


async def update_prompt(data: dict) -> dict:
    return await _ai_request("PUT", "/ai/prompt", body=data)


async def test_prompt(prompt_id: int, variables: dict) -> dict:
    return await _ai_request("POST", f"/ai/prompt/{prompt_id}/test", body={"variables": variables})


# ── 菜单 API ──

async def fetch_menu_tree(sys_code: str | None = None, app_id: int | None = None) -> list[dict]:
    params = {}
    if sys_code:
        params["sysCode"] = sys_code
    if app_id:
        params["appId"] = app_id
    result = await _ai_request("GET", "/system/menu/list", params=params)
    return result.get("data", []) or []