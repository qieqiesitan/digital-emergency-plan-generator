import httpx
import logging
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


async def _get(path: str, params: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.get(_gateway(path), params=params, headers=_headers())
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT GET {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT GET {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}


async def _post(path: str, body: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.post(_gateway(path), json=body, headers=_headers())
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT POST {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT POST {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}


async def _put(path: str, body: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.put(_gateway(path), json=body, headers=_headers())
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT PUT {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT PUT {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}


async def _delete(path: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.delete(_gateway(path), headers=_headers())
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT DELETE {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT DELETE {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}



# ── JWT Token 管理 ──
_jwt_token: str | None = None
_jwt_expires_at: float = 0


async def _ensure_jwt() -> str:
    """获取有效的 JWT token（自动登录+刷新）"""
    global _jwt_token, _jwt_expires_at
    import time
    if _jwt_token and time.time() < _jwt_expires_at - 60:
        return _jwt_token

    # 用 X-Api-Key 调用 auth 服务获取 JWT
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

    # Fallback: return API key (may not work for AI endpoints)
    return settings.YWT_API_KEY


def _ai_headers() -> dict:
    """构建 AI 端点专用的请求头（含 JWT token）"""
    # This is async-dependent, caller must await ensure_jwt first
    return {}


async def _ai_get(path: str, params: dict | None = None) -> dict:
    token = await _ensure_jwt()
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.get(
                _gateway(path), params=params,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT AI GET {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT AI GET {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}


async def _ai_post(path: str, body: dict) -> dict:
    token = await _ensure_jwt()
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.post(
                _gateway(path), json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT AI POST {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT AI POST {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}


async def _ai_put(path: str, body: dict) -> dict:
    token = await _ensure_jwt()
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.put(
                _gateway(path), json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return result
            logger.warning(f"YWT AI PUT {path} returned: {result}")
            return {"code": result.get("code", 500), "data": None, "msg": result.get("msg", "")}
    except httpx.HTTPError as e:
        logger.error(f"YWT AI PUT {path} failed: {e}")
        return {"code": 500, "data": None, "msg": str(e)}


# ── 原有方法 ──

async def upload_oper_log(log_data: dict) -> bool:
    url = f"{settings.YWT_GATEWAY_URL}/system/log/oper"
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.post(url, json=log_data, headers=_headers())
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 200:
                return True
            logger.warning(f"YWT oper log upload returned: {result}")
            return False
    except httpx.HTTPError as e:
        logger.error(f"YWT oper log upload failed: {e}")
        return False


async def get_user_permissions(sys_code: str, username: str) -> list:
    url = f"{settings.YWT_GATEWAY_URL}/system/user/permissions"
    params = {"sysCode": sys_code, "username": username}
    try:
        async with httpx.AsyncClient(timeout=YWT_TIMEOUT) as client:
            resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {await _ensure_jwt()}", "Content-Type": "application/json"})
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
    """GET /system/dict/data/type/{dictType} → 获取某字典类型的条目列表"""
    result = await _ai_get(f"/system/dict/data/type/{dict_type}")
    return result.get("data", []) or []


# ── 提示词 API ──

async def fetch_prompts(category: str | None = None) -> list[dict]:
    """GET /ai/prompt/list (JWT) + 逐条调detail补全systemPrompt/userPromptTemplate"""
    params = {}
    if category:
        params["category"] = category
    result = await _ai_get("/ai/prompt/list", params=params)
    items = result.get("data", []) or []
    
    # 逐条获取详情以补全 systemPrompt 和 userPromptTemplate
    enriched = []
    for item in items:
        pid = item.get("id")
        if pid:
            detail = await fetch_prompt(pid)
            if detail:
                # 归一化 snake_case → camelCase
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
    """GET /ai/prompt/{id} → 获取单个提示词模板(使用JWT认证) → 获取单个提示词模板"""
    result = await _ai_get(f"/ai/prompt/{prompt_id}")
    return result.get("data")


async def create_prompt(data: dict) -> dict:
    """POST /ai/prompt → 创建提示词模板(使用JWT认证) → 创建提示词模板"""
    return await _ai_post("/ai/prompt", data)


async def update_prompt(data: dict) -> dict:
    """PUT /ai/prompt → 更新提示词模板(使用JWT认证) → 更新提示词模板"""
    return await _ai_put("/ai/prompt", data)


async def test_prompt(prompt_id: int, variables: dict) -> dict:
    """POST /ai/prompt/{id}/test → 测试提示词(使用JWT认证) → 测试提示词"""
    return await _ai_post(f"/ai/prompt/{prompt_id}/test", {"variables": variables})


# ── 菜单 API ──

async def fetch_menu_tree(sys_code: str | None = None, app_id: int | None = None) -> list[dict]:
    """GET /system/menu/list → 获取菜单树"""
    params = {}
    if sys_code:
        params["sysCode"] = sys_code
    if app_id:
        params["appId"] = app_id
    result = await _ai_get("/system/menu/list", params=params)
    return result.get("data", []) or []
