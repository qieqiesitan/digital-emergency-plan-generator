"""W1：AI 能力开关接线 / 调用留痕埋点 / 超时错误码（先失败后修复）。"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from app.services import llm_client
from app.services.llm_client import (
    CapabilityDisabledError,
    LLMError,
    LLMStreamTruncatedError,
    LLMTimeoutError,
    llm_chat_completion,
    llm_text_completion,
)
from app.services.secret_utils import encrypt_secret


def _cfg(**kw):
    base = dict(
        provider="mock", base_url="http://127.0.0.1:1/mock",
        api_key_encrypted=encrypt_secret("mock-key"), model_name="m-default",
        temperature=0.1, max_tokens=16, top_p=1.0,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _cap(**kw):
    base = dict(code="cap-x", name="测试能力", module="test", is_enabled=True,
                model_override=None, prompt_ref=None)
    base.update(kw)
    return SimpleNamespace(**base)


# ── 1. 能力开关 ──

@pytest.mark.asyncio
async def test_disabled_capability_blocks_call(monkeypatch):
    """能力被停用后必须直接拒绝，且不再发起供应商请求。"""
    monkeypatch.setattr(llm_client, "_load_capability", AsyncMock(return_value=_cap(is_enabled=False)))
    called = False

    async def _should_not_run(*a, **k):
        nonlocal called
        called = True
        raise AssertionError("停用的能力不应发起 LLM 调用")

    monkeypatch.setattr(llm_client, "_post_with_retry", _should_not_run)
    with pytest.raises(CapabilityDisabledError):
        await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg(),
                                  stream=False, capability="cap-x", module="test")
    assert called is False


@pytest.mark.asyncio
async def test_capability_model_override_applied(monkeypatch):
    monkeypatch.setattr(llm_client, "_load_capability",
                        AsyncMock(return_value=_cap(model_override="m-override")))
    seen = {}

    async def _fake_post(base, payload, headers, timeout, max_retries=3, metrics=None):
        seen["payload"] = payload
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(llm_client, "_post_with_retry", _fake_post)
    monkeypatch.setattr(llm_client, "_emit_telemetry", AsyncMock())
    await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg(),
                              stream=False, capability="cap-x")
    assert seen["payload"]["model"] == "m-override"


@pytest.mark.asyncio
async def test_unregistered_capability_still_runs(monkeypatch):
    """未注册能力默认启用（不因忘注册而静默失效）。"""
    monkeypatch.setattr(llm_client, "_load_capability", AsyncMock(return_value=None))
    monkeypatch.setattr(llm_client, "_post_with_retry",
                        AsyncMock(return_value={"choices": [{"message": {"content": "ok"}}]}))
    monkeypatch.setattr(llm_client, "_emit_telemetry", AsyncMock())
    data = await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg(),
                                     stream=False, capability="not-registered")
    assert data["choices"][0]["message"]["content"] == "ok"


# ── 2. 调用留痕 ──

@pytest.mark.asyncio
async def test_nonstream_success_emits_telemetry(monkeypatch):
    monkeypatch.setattr(llm_client, "_load_capability", AsyncMock(return_value=_cap()))
    monkeypatch.setattr(llm_client, "_post_with_retry", AsyncMock(return_value={
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }))
    emitted = []

    async def _emit(record):
        emitted.append(record)

    monkeypatch.setattr(llm_client, "_emit_telemetry", _emit)
    await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg(),
                              stream=False, capability="cap-x", module="test",
                              user_id="u1", enterprise_id="e1")
    assert len(emitted) == 1
    rec = emitted[0]
    assert rec.success is True and rec.module == "test" and rec.capability == "cap-x"
    assert rec.total_tokens == 18 and rec.duration_ms is not None
    assert rec.user_id == "u1" and rec.enterprise_id == "e1"


@pytest.mark.asyncio
async def test_nonstream_failure_emits_telemetry(monkeypatch):
    monkeypatch.setattr(llm_client, "_load_capability", AsyncMock(return_value=_cap()))
    monkeypatch.setattr(llm_client, "_post_with_retry",
                        AsyncMock(side_effect=LLMError(429, "rate limited")))
    emitted = []

    async def _emit(record):
        emitted.append(record)

    monkeypatch.setattr(llm_client, "_emit_telemetry", _emit)
    with pytest.raises(LLMError):
        await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg(),
                                  stream=False, capability="cap-x", module="test")
    assert len(emitted) == 1
    assert emitted[0].success is False and emitted[0].error_code == 429


@pytest.mark.asyncio
async def test_stream_truncation_emits_telemetry_and_raises(monkeypatch):
    monkeypatch.setattr(llm_client, "_load_capability", AsyncMock(return_value=_cap()))

    async def _cut_stream(*a, **k):
        yield "A"
        raise LLMStreamTruncatedError(1)

    monkeypatch.setattr(llm_client, "_stream_response", _cut_stream)
    emitted = []

    async def _emit(record):
        emitted.append(record)

    monkeypatch.setattr(llm_client, "_emit_telemetry", _emit)
    gen = await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg(),
                                    stream=True, capability="cap-x", module="test")
    pieces = []
    with pytest.raises(LLMStreamTruncatedError):
        async for piece in gen:
            pieces.append(piece)
    assert pieces == ["A"]
    assert len(emitted) == 1 and emitted[0].truncated is True and emitted[0].success is False


# ── 3. 超时错误码 ──

@pytest.mark.asyncio
async def test_transport_timeout_is_classified(monkeypatch):
    """httpx 超时消息为空也要被识别为超时（原实现按文本特征判断会漏）。"""
    class _Boom:
        def __init__(self, *a, **k):
            pass

        async def post(self, *a, **k):
            raise httpx.ReadTimeout("")

        async def aclose(self):
            return None

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", _Boom)
    with pytest.raises(LLMTimeoutError):
        await llm_client._post_with_retry(
            "http://127.0.0.1:1", {"model": "m"}, {"Authorization": "Bearer x"}, 1, max_retries=0)


@pytest.mark.asyncio
async def test_timeout_maps_to_504(monkeypatch):
    monkeypatch.setattr(llm_client, "llm_chat_completion",
                        AsyncMock(side_effect=LLMTimeoutError(0)))
    with pytest.raises(HTTPException) as exc:
        await llm_text_completion([{"role": "user", "content": "hi"}], _cfg(), timeout=1)
    assert exc.value.status_code == 504
    assert "超时" in str(exc.value.detail)


# ── 4. 能力码接到真实调用点（防"接线回退"） ──

def test_capability_codes_wired_to_feature_services():
    backend = Path(__file__).resolve().parents[1]
    expectations = {
        "app/services/risk_ai_service.py": (
            "risk_suggest_objects", "risk_suggest_events", "risk_suggest_measures",
        ),
        "app/services/hazard_ai_service.py": ("hazard_record_assist", "hazard_grade"),
        "app/services/extraction_service.py": ("major_hazard_extract",),
    }
    for rel, codes in expectations.items():
        src = (backend / rel).read_text(encoding="utf-8")
        for code in codes:
            assert f'capability="{code}"' in src, f"{rel} 未接线 {code}"
        assert "module=" in src, f"{rel} 未标注 module"


def test_pending_capabilities_are_marked():
    """未接入实现的 2 个能力必须在注册表里标注为规划中，避免管理页误导。"""
    backend = Path(__file__).resolve().parents[1]
    sql = (backend / "db_migration_20260918_capability_pending.sql").read_text(encoding="utf-8")
    assert "work_ticket_jsa" in sql and "work_ticket_precheck" in sql
    assert "规划中" in sql
