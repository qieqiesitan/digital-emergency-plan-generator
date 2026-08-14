import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.data_dict import DataDict

_CACHE_TTL = 60
_cache: dict[tuple[str, str], tuple[float, dict[str, dict]]] = {}


async def get_dict_map(db: AsyncSession, enterprise_id: str | None, dict_type: str) -> dict[str, dict]:
    """合并读取：企业条目 > 系统默认；60s 进程内缓存。返回 {code: {label, value, description}}。"""
    key = (enterprise_id or "system", dict_type)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]
    rows = (await db.execute(
        select(DataDict).where(
            DataDict.dict_type == dict_type,
            DataDict.enabled.is_(True),
            (DataDict.enterprise_id == enterprise_id) | (DataDict.enterprise_id.is_(None)),
        ).order_by(DataDict.scope, DataDict.sort_order)
    )).scalars().all()
    merged: dict[str, dict] = {}
    for r in rows:
        merged[r.code] = {"label": r.label, "value": r.value, "description": r.description}
    _cache[key] = (now, merged)
    return merged


def invalidate_dict_cache(enterprise_id: str | None = None, dict_type: str | None = None) -> None:
    for k in list(_cache):
        if (enterprise_id is None or k[0] == (enterprise_id or "system")) and (dict_type is None or k[1] == dict_type):
            _cache.pop(k, None)
