"""Enterprise autofill — QCC lookup with rate limiting and field mapping."""
import logging, re, time
from typing import Any

from app.services.qcc_client import get_company_info
from app.services.runtime_state import get_state, incr_counter, set_state

logger = logging.getLogger("enterprise_autofill")

# ── rate limiting (W2：跨 worker 共享，per-user) ──
MAX_CALLS_PER_MINUTE = 5
MIN_INTERVAL = 3.0  # seconds

# ── field mapping: QCC returned field name → Enterprise model field ──
_FIELD_MAP: dict[str, str] = {
    "企业名称": "name",
    "统一社会信用代码": "credit_code",
    "法定代表人": "legal_representative",
    "成立日期": "established_date",
    "企业类型": "economic_type",
    "国标行业": "industry",
    "注册地址": "address",
    "经营范围": "business_scope",
    "人员规模": "employee_count",
    "注册资本": "registered_capital",
}


async def autofill(user_id: str, company_name: str) -> dict:
    """Look up company info from QCC and map to Enterprise fields.

    Returns:
        {"ok": true, "fields": {...}}
        {"ok": false, "reason": "rate_limited" | "credits_exhausted" | "not_found" | "network_error"}
    """
    # ── rate check ──
    if not await _check_rate(user_id):
        return {"ok": False, "reason": "rate_limited"}

    # ── call QCC ──
    result = await get_company_info(company_name)
    if not result["ok"]:
        return {"ok": False, "reason": result["reason"]}

    raw = result["data"]
    fields = _map_fields(raw)
    return {"ok": True, "name": raw.get("企业名称", company_name), "fields": fields}


async def _check_rate(user_id: str) -> bool:
    """QCC 调用节流：同一用户 3s 最小间隔 + 每分钟最多 5 次（跨 worker）。"""
    now = time.time()
    last = await get_state(f"qcc_last:{user_id}")
    if last and now - float(last.get("ts", 0)) < MIN_INTERVAL:
        return False
    count = await incr_counter(
        f"qcc_rl:{user_id}:{int(now // 60)}", ttl_seconds=61,
    )
    if count > MAX_CALLS_PER_MINUTE:
        return False
    await set_state(f"qcc_last:{user_id}", {"ts": now}, ttl_seconds=60)
    return True


def _map_fields(raw: dict) -> dict:
    """Map QCC response fields to Enterprise model fields."""
    fields: dict[str, Any] = {}
    for qcc_key, ent_key in _FIELD_MAP.items():
        val = raw.get(qcc_key)
        if val is None or val == "":
            continue

        if ent_key == "registered_capital":
            val = _parse_capital(val)
        elif ent_key == "employee_count":
            val = _parse_employee_count(val)
        elif ent_key == "established_date":
            val = str(val)[:10]  # ensure YYYY-MM-DD

        fields[ent_key] = val
    return fields


def _parse_capital(val: str) -> float | None:
    """'4114113.182万元' → 4114113.182"""
    m = re.search(r"([\d,.]+)\s*万?", str(val))
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _parse_employee_count(val: str) -> int | None:
    """'10000人以上' → 10000, '500-999人' → 750"""
    val = str(val)
    m = re.search(r"(\d[\d,]*)", val)
    if m:
        return int(m.group(1).replace(",", ""))
    return None
