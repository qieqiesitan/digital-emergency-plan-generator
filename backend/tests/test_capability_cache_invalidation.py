"""AI 能力开关：更新后必须清理进程内缓存（2026-09-19 审计修复）。"""

import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services import llm_client
from app.services.llm_client import (
    CAPABILITY_CACHE_TTL_SECONDS,
    invalidate_capability_cache,
)


def test_invalidate_single_and_all():
    now = time.monotonic()
    llm_client._CAPABILITY_CACHE["a"] = (now, object())
    llm_client._CAPABILITY_CACHE["b"] = (now, object())
    invalidate_capability_cache("a")
    assert "a" not in llm_client._CAPABILITY_CACHE and "b" in llm_client._CAPABILITY_CACHE
    invalidate_capability_cache()
    assert llm_client._CAPABILITY_CACHE == {}


def test_ttl_constant_is_bounded():
    """TTL 必须存在且不超过 60s：多 worker 部署下靠它兜底。"""
    assert 0 < CAPABILITY_CACHE_TTL_SECONDS <= 60


@pytest.mark.asyncio
async def test_platform_update_capability_invalidates_cache(monkeypatch):
    """管理端改开关 → 当前 worker 的缓存必须立即失效。"""
    from app.routers import platform as platform_router
    from app.models.ai_capability import AICapability

    # 用真实模型实例：update_capability 末尾会用 CapabilityOut.model_validate 序列化返回
    cap = AICapability(
        id="3f1a1c9e-0000-5000-8000-000000000005",
        code="hazard_grade",
        module="隐患排查治理",
        name="隐患分级建议",
        is_enabled=True,
        allow_manual=True,
        sort_order=50,
    )
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = cap
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    llm_client._CAPABILITY_CACHE["hazard_grade"] = (time.monotonic(), object())
    payload = MagicMock()
    payload.model_dump.return_value = {"is_enabled": False}

    await platform_router.update_capability("hazard_grade", payload, db)

    assert "hazard_grade" not in llm_client._CAPABILITY_CACHE, "更新能力后应清掉对应缓存"
    assert cap.is_enabled is False
