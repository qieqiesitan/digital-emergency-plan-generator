"""llm_client 扩展与各调用方迁移回归测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException

from app.services.llm_client import LLMError, llm_chat_completion, llm_stream_all, llm_text_completion


class FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self._text = text
        self._json_data = json_data if json_data is not None else {
            "choices": [{"message": {"content": "ok"}}],
        }

    @property
    def text(self):
        return self._text

    async def aread(self):
        return self._text.encode("utf-8")

    def json(self):
        return self._json_data


class FakeStream:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeAsyncClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None, **kw):
        self.calls.append(("post", url, json, headers))
        return self._response

    async def stream(self, method, url, json=None, headers=None, **kw):
        self.calls.append(("stream", url, json, headers))
        return FakeStream(self._response)


def _cfg(**kw):
    c = MagicMock(
        provider=kw.get("provider", "deepseek"),
        base_url=kw.get("base_url"),
        model_name=kw.get("model_name", "deepseek-chat"),
        temperature=kw.get("temperature", 0.7),
        max_tokens=kw.get("max_tokens", 2000),
        top_p=kw.get("top_p", 1.0),
        api_key_encrypted="00" * 16,
    )
    return c


@pytest.mark.asyncio
async def test_llm_chat_completion_passes_tools_and_overrides(monkeypatch):
    import app.services.llm_client as lc
    fake = FakeAsyncClient(FakeResponse())
    monkeypatch.setattr(lc.httpx, "AsyncClient", lambda *a, **k: fake)
    monkeypatch.setattr(lc, "decrypt_api_key", lambda *a: "sk-test")

    await lc.llm_chat_completion(
        [{"role": "user", "content": "hi"}], _cfg(), stream=False, timeout=60,
        tools=[{"type": "function", "function": {"name": "x"}}],
        payload_overrides={"temperature": 0.1},
        include_top_p=False,
    )
    kind, url, payload, headers = fake.calls[0]
    assert kind == "post"
    assert url == "https://api.deepseek.com/v1/chat/completions"
    assert payload["tools"] == [{"type": "function", "function": {"name": "x"}}]
    assert payload["temperature"] == 0.1
    assert "top_p" not in payload
    assert payload["stream"] is False
    assert headers["Authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_llm_chat_completion_raises_llm_error(monkeypatch):
    import app.services.llm_client as lc
    fake = FakeAsyncClient(FakeResponse(status_code=500, text="boom"))
    monkeypatch.setattr(lc.httpx, "AsyncClient", lambda *a, **k: fake)
    monkeypatch.setattr(lc, "decrypt_api_key", lambda *a: "sk-test")

    with pytest.raises(LLMError) as exc_info:
        await lc.llm_chat_completion([{"role": "user", "content": "hi"}], _cfg(), stream=False)
    assert exc_info.value.status_code == 500
    assert str(exc_info.value) == "AI调用失败: 500 boom"


@pytest.mark.asyncio
async def test_llm_stream_all_collects_chunks(monkeypatch):
    import app.services.llm_client as lc

    async def fake_gen(messages, cfg, stream=False, timeout=120, **kw):
        assert stream is True

        async def _inner():
            for c in ["你", "好"]:
                yield c

        return _inner()

    monkeypatch.setattr(lc, "llm_chat_completion", fake_gen)
    assert await lc.llm_stream_all([{"role": "user", "content": "hi"}], _cfg(), timeout=120) == "你好"


@pytest.mark.asyncio
async def test_llm_text_completion_maps_401_to_500(monkeypatch):
    import app.services.llm_client as lc
    monkeypatch.setattr(lc, "decrypt_api_key", lambda *a: "sk-test")

    async def fake_call(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(401, "bad key")

    monkeypatch.setattr(lc, "llm_chat_completion", fake_call)
    with pytest.raises(HTTPException) as exc_info:
        await lc.llm_text_completion([{"role": "user", "content": "hi"}], _cfg())
    assert exc_info.value.status_code == 500
    assert "AI API Key 无效" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_chat_call_llm_uses_llm_client_with_tools(monkeypatch):
    from app.routers import chat
    calls = {}

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        calls.update({"stream": stream, "timeout": timeout, "tools": kw.get("tools")})
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(chat, "llm_chat_completion", fake_chat)
    cfg = _cfg()
    result = await chat._call_llm([{"role": "user", "content": "hi"}], cfg)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert calls == {"stream": False, "timeout": 60, "tools": chat.CHAT_TOOLS}


@pytest.mark.asyncio
async def test_chat_call_llm_stream_preserves_error_message(monkeypatch):
    from app.routers import chat

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(500, "boom")

    monkeypatch.setattr(chat, "llm_chat_completion", fake_chat)
    gen = chat._call_llm_stream([{"role": "user", "content": "hi"}], _cfg())
    with pytest.raises(Exception) as exc_info:
        async for _ in gen:
            pass
    assert str(exc_info.value) == "AI调用失败: 500 boom"


@pytest.mark.asyncio
async def test_chat_collect_llm_uses_llm_collect_all(monkeypatch):
    from app.routers import chat
    calls = {}

    async def fake_collect(messages, cfg, timeout=120):
        calls["timeout"] = timeout
        return "collected"

    monkeypatch.setattr(chat, "llm_collect_all", fake_collect)
    assert await chat._collect_llm([{"role": "user", "content": "hi"}], _cfg()) == "collected"
    assert calls["timeout"] == 180


@pytest.mark.asyncio
async def test_risk_assessment_stream_uses_llm_client_and_preserves_errors(monkeypatch):
    from app.routers import risk_assessment as ra
    calls = {}

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        calls.update({"stream": stream, "timeout": timeout})

        async def gen():
            yield "a"
            yield "b"

        return gen()

    monkeypatch.setattr(ra, "llm_chat_completion", fake_chat)
    # llm_stream_all 内部调用的是 llm_client 模块级函数，需同时 patch
    import app.services.llm_client as lc
    monkeypatch.setattr(lc, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(ra, "decrypt_api_key", lambda *a: "sk-test")

    chunks = [c async for c in ra._stream_llm_with_messages_chunked(
        [{"role": "user", "content": "hi"}], _cfg())]
    assert chunks == ["a", "b"]
    assert calls == {"stream": True, "timeout": 120}

    full = await ra._stream_llm_with_messages([{"role": "user", "content": "hi"}], _cfg())
    assert full == "ab"


@pytest.mark.asyncio
async def test_risk_assessment_stream_llm_error_message(monkeypatch):
    from app.routers import risk_assessment as ra

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(500, "boom")

    monkeypatch.setattr(ra, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(ra, "decrypt_api_key", lambda *a: "sk-test")
    with pytest.raises(Exception) as exc_info:
        async for _ in ra._stream_llm_with_messages_chunked(
            [{"role": "user", "content": "hi"}], _cfg()):
            pass
    assert str(exc_info.value) == "LLM call failed: 500 boom"


@pytest.mark.asyncio
async def test_risk_assessment_decrypt_failure_maps_to_500(monkeypatch):
    from app.routers import risk_assessment as ra

    def bad_decrypt(*a):
        raise Exception("bad")

    monkeypatch.setattr(ra, "decrypt_api_key", bad_decrypt)
    with pytest.raises(HTTPException) as exc_info:
        async for _ in ra._stream_llm_with_messages_chunked(
            [{"role": "user", "content": "hi"}], _cfg()):
            pass
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "AI config key decryption failed"
