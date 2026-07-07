"""QCC MCP client — call Qichacha Agent Platform for company registration data."""
import json, logging

import httpx

from app.config import settings

logger = logging.getLogger("qcc_client")

TIMEOUT = 30  # seconds


async def get_company_info(search_key: str) -> dict:
    """Query QCC for company registration info.

    Tries keys in rotation: primary → fallback → primary → fallback.
    Stops on first success, or returns credits_exhausted after all attempts.
    """
    if not settings.QCC_API_KEY:
        return {"ok": False, "reason": "not_configured"}

    keys = []

    # ponytail: round-robin key rotation, each key tried at most twice
    if settings.QCC_API_KEY:
        keys.append(settings.QCC_API_KEY)
    if settings.QCC_API_KEY_FALLBACK:
        keys.append(settings.QCC_API_KEY_FALLBACK)
    if settings.QCC_API_KEY:
        keys.append(settings.QCC_API_KEY)  # retry primary
    if settings.QCC_API_KEY_FALLBACK:
        keys.append(settings.QCC_API_KEY_FALLBACK)  # retry fallback

    last_reason = "not_configured"
    for i, key in enumerate(keys):
        if i > 0:
            logger.info("QCC: switching to key #%d", i + 1)
        result = await _do_query(search_key, key)
        if result["ok"]:
            return result
        last_reason = result.get("reason", "network_error")
        if last_reason != "credits_exhausted":
            return result  # real error, don't retry

    return {"ok": False, "reason": last_reason}


async def _do_query(search_key: str, api_key: str) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_company_registration_info",
            "arguments": {"searchKey": search_key},
        },
        "id": 1,
    }
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(settings.QCC_ENDPOINT, json=payload, headers=headers)
    except httpx.TimeoutException:
        logger.warning("QCC timeout for searchKey=%r", search_key)
        return {"ok": False, "reason": "network_error"}
    except Exception:
        logger.exception("QCC request failed for searchKey=%r", search_key)
        return {"ok": False, "reason": "network_error"}

    if resp.status_code != 200:
        return {"ok": False, "reason": "network_error"}

    data = _parse_sse(resp.text)
    if data is None:
        return {"ok": False, "reason": "network_error"}

    if "error" in data:
        err = data["error"]
        msg = str(err.get("message", "")).lower()
        if any(kw in msg for kw in ("积分", "quota", "limit", "exceed", "额度", "insufficient")):
            return {"ok": False, "reason": "credits_exhausted"}
        return {"ok": False, "reason": "not_found"}

    result = data.get("result")
    if not result or "content" not in result:
        return {"ok": False, "reason": "not_found"}

    try:
        inner = json.loads(result["content"][0]["text"])
    except (json.JSONDecodeError, KeyError, IndexError):
        return {"ok": False, "reason": "network_error"}

    return {"ok": True, "data": inner}


def _parse_sse(text: str) -> dict | None:
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
    return None
