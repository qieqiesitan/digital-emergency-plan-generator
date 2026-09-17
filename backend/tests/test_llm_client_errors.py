"""llm_client 异常语义测试：B1 超时映射、B2 流截断。

来源：docs/系统诊断报告-2026-09-17.md §九（mock 供应商实测）——
超时经 llm_text_completion 变成 500 + "AI调用失败: 0"（except httpx.TimeoutException 是死代码）；
流中途断连静默返回半截文本且标记 success。
"""

import pytest
from fastapi import HTTPException

from app.services import llm_client
from app.services.llm_client import LLMError, llm_text_completion


class _Cfg:
    api_key_encrypted = "00" * 16
    provider = "deepseek"
    base_url = "https://example.invalid/v1"
    model = "test-model"


@pytest.mark.asyncio
async def test_b1_timeout_maps_to_504(monkeypatch):
    """超时必须映射为 504，而不是 500 + "AI调用失败: 0"。"""
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")

    async def _boom(*a, **k):
        raise LLMError(0, "timed out")

    monkeypatch.setattr(llm_client, "llm_chat_completion", _boom)

    with pytest.raises(HTTPException) as ei:
        await llm_text_completion([{"role": "user", "content": "hi"}], _Cfg(), timeout=1)
    assert ei.value.status_code == 504
    assert "超时" in ei.value.detail


@pytest.mark.asyncio
async def test_b1_non_timeout_status_zero_still_502(monkeypatch):
    """status_code=0 但不是超时（如连接被拒）应映射 502，不能一律 504。"""
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")

    async def _boom(*a, **k):
        raise LLMError(0, "connection refused")

    monkeypatch.setattr(llm_client, "llm_chat_completion", _boom)
    with pytest.raises(HTTPException) as ei:
        await llm_text_completion([{"role": "user", "content": "hi"}], _Cfg(), timeout=1)
    assert ei.value.status_code == 502


@pytest.mark.asyncio
async def test_b1_401_still_500_with_hint(monkeypatch):
    """401 语义不变：500 + 重新配置提示。"""
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")

    async def _boom(*a, **k):
        raise LLMError(401, "unauthorized")

    monkeypatch.setattr(llm_client, "llm_chat_completion", _boom)
    with pytest.raises(HTTPException) as ei:
        await llm_text_completion([{"role": "user", "content": "hi"}], _Cfg(), timeout=1)
    assert ei.value.status_code == 500
    assert "API Key" in ei.value.detail
