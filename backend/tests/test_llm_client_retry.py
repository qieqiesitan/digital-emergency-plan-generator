"""test_llm_client_retry.py — LLM 重试行为。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_client import llm_chat_completion, LLMError


def _cfg():
    c = MagicMock(provider="deepseek", model_name="deepseek-chat", base_url=None,
                  temperature=0.7, max_tokens=4096, top_p=1.0)
    return c


def _resp(status_code, text="", json_data=None):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    r.json.return_value = json_data or {"choices": [{"message": {"content": "ok"}}]}
    return r


@pytest.mark.asyncio
async def test_retry_429_then_success():
    calls = []

    async def fake_post(url, **kwargs):
        calls.append(url)
        return _resp(429, "rate limited") if len(calls) == 1 else _resp(200)

    client = AsyncMock()
    client.post.side_effect = fake_post
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"), \
         patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
        out = await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg())
    assert len(calls) == 2
    assert out["choices"][0]["message"]["content"] == "ok"


@pytest.mark.asyncio
async def test_retry_5xx_exhausted():
    client = AsyncMock()
    client.post.side_effect = lambda url, **kw: _resp(500, "boom")
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"), \
         patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(LLMError) as ei:
            await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg())
    assert ei.value.status_code == 500


@pytest.mark.asyncio
async def test_no_retry_on_401():
    client = AsyncMock()
    client.post.side_effect = lambda url, **kw: _resp(401, "bad key")
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"):
        with pytest.raises(LLMError) as ei:
            await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg())
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_retry_network_error():
    import httpx
    calls = []

    async def fake_post(url, **kw):
        calls.append(url)
        if len(calls) == 1:
            raise httpx.ConnectError("conn refused")
        return _resp(200)

    client = AsyncMock()
    client.post.side_effect = fake_post
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"), \
         patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
        out = await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg())
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_max_retries_override_not_sent_in_payload():
    """B19：payload_overrides 的 max_retries 只控制重试次数，不得混入请求体（严格 API 400）。"""
    calls = []

    async def fake_post(url, **kwargs):
        calls.append(kwargs.get("json") or {})
        return _resp(429, "rate limited") if len(calls) == 1 else _resp(200)

    client = AsyncMock()
    client.post.side_effect = fake_post
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"), \
         patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
        out = await llm_chat_completion(
            [{"role": "user", "content": "hi"}], _cfg(),
            payload_overrides={"max_retries": 1, "temperature": 0.3})
    assert len(calls) == 2                    # max_retries=1 → 共 2 次尝试
    for body in calls:
        assert "max_retries" not in body      # 请求体不得含该键
        assert body["temperature"] == 0.3     # 其余 override 仍生效
    assert out["choices"][0]["message"]["content"] == "ok"
