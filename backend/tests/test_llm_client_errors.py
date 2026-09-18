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


# --- B2：流式截断 ---------------------------------------------------------


class _FakeResp:
    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    async def aread(self):
        return b""

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *a):
        return False


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, *a, **k):
        return _FakeStreamCtx(self._resp)


def _patch_httpx(monkeypatch, lines):
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")
    monkeypatch.setattr(
        llm_client.httpx, "AsyncClient", lambda *a, **k: _FakeClient(_FakeResp(lines))
    )


@pytest.mark.asyncio
async def test_b2_truncated_stream_raises(monkeypatch):
    """中途断连（没有 [DONE]）必须抛可识别异常，不能静默返回半截文本。

    这是最危险的一类错误：用户拿到半截报告，系统标记成功，没人会去查。
    """
    _patch_httpx(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"content":"前半段"}}]}',
            'data: {"choices":[{"delta":{"content":"后半段"}}]}',
        ],
    )
    chunks = []
    with pytest.raises(llm_client.LLMStreamTruncatedError):
        async for c in llm_client._stream_response("https://x/v1", {}, _Cfg()):
            chunks.append(c)
    assert chunks == ["前半段", "后半段"], "已收到的分片应先正常产出，再由异常收尾"


@pytest.mark.asyncio
async def test_b2_complete_stream_ok(monkeypatch):
    """正常收到 [DONE] 不应抛异常。"""
    _patch_httpx(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"content":"完整"}}]}',
            "data: [DONE]",
        ],
    )
    chunks = [c async for c in llm_client._stream_response("https://x/v1", {}, _Cfg())]
    assert chunks == ["完整"]


@pytest.mark.asyncio
async def test_b2_truncated_reports_received_chars(monkeypatch):
    """异常要带上已收到的字符数，便于排查断在哪儿。"""
    _patch_httpx(
        monkeypatch,
        ['data: {"choices":[{"delta":{"content":"12345"}}]}'],
    )
    with pytest.raises(llm_client.LLMStreamTruncatedError) as ei:
        async for _ in llm_client._stream_response("https://x/v1", {}, _Cfg()):
            pass
    assert ei.value.received_chars == 5


# --- B3：流中途失败不得重试（重试会把已产出的正文再吐一遍）------------------


class _MidStreamTimeoutResp:
    """先吐一个分片，再抛读超时——模拟"供应商传到一半卡住"。"""

    status_code = 200

    def __init__(self, text: str):
        self._text = text

    async def aread(self):
        return b""

    async def aiter_lines(self):
        yield 'data: {"choices":[{"delta":{"content":"' + self._text + '"}}]}'
        raise llm_client.httpx.ReadTimeout("read timeout")


class _CountingClient:
    def __init__(self, text: str):
        self.text = text
        self.opens = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, *a, **k):
        self.opens += 1

        class _Ctx:
            async def __aenter__(_self):
                return _MidStreamTimeoutResp(self_outer.text)

            async def __aexit__(_self, *a):
                return False

        self_outer = self
        return _Ctx()


@pytest.mark.asyncio
async def test_b3_midstream_timeout_does_not_retry(monkeypatch):
    """中途读超时若重试，调用方会收到重复正文（实测出现过 4 个 "分片0"）。

    正确行为：只要已经吐过分片，就不再重试，直接以"流被截断"收尾——
    调用方据此拒绝落库，用户看到一次明确的失败，而不是一段重复的正文。
    """
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")
    client = _CountingClient("分片0")
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", lambda *a, **k: client)
    monkeypatch.setattr(llm_client.asyncio, "sleep", _no_sleep)

    chunks = []
    with pytest.raises((llm_client.LLMStreamTruncatedError, llm_client.LLMTimeoutError)):
        async for c in llm_client._stream_response(
            "https://x/v1", {}, _Cfg(), max_retries=3
        ):
            chunks.append(c)

    assert chunks == ["分片0"], f"分片被重复产出：{chunks}"
    assert client.opens == 1, f"已经吐过内容还重试了 {client.opens} 次请求"


async def _no_sleep(*_a, **_k):
    return None
