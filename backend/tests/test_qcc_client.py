"""QCC client tests: keys come from unified third-party config, never hardcoded."""

import pytest

import app.services.qcc_client as qcc_client


class _FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response
        self.request_kwargs = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        self.request_kwargs = {"url": url, "json": json, "headers": headers}
        return self._response


@pytest.mark.asyncio
async def test_get_company_info_not_configured_when_no_key(monkeypatch):
    async def no_config(_config_key):
        return None

    monkeypatch.setattr(qcc_client, "get_third_party_config", no_config)

    result = await qcc_client.get_company_info("ACME")

    assert result == {"ok": False, "reason": "not_configured"}


@pytest.mark.asyncio
async def test_get_company_info_uses_configured_key(monkeypatch):
    async def fake_config(config_key):
        if config_key == "third_party.qcc.api_key":
            return "qcc-primary-key"
        return None

    captured = {}

    async def fake_do_query(search_key, api_key):
        captured["search_key"] = search_key
        captured["api_key"] = api_key
        return {"ok": True, "data": {"companyName": "ACME"}}

    monkeypatch.setattr(qcc_client, "get_third_party_config", fake_config)
    monkeypatch.setattr(qcc_client, "_do_query", fake_do_query)

    result = await qcc_client.get_company_info("ACME")

    assert result["ok"] is True
    assert captured["api_key"] == "qcc-primary-key"
    assert captured["search_key"] == "ACME"


@pytest.mark.asyncio
async def test_do_query_sends_authorization_header_with_key(monkeypatch):
    sse_body = 'data: {"result": {"content": [{"text": "{\\"name\\": \\"ACME\\"}"}]}}\n\n'
    fake = _FakeAsyncClient(_FakeResponse(text=sse_body))
    monkeypatch.setattr(qcc_client.httpx, "AsyncClient", lambda *a, **k: fake)

    result = await qcc_client._do_query("ACME", "qcc-key-abc")

    assert result["ok"] is True
    assert fake.request_kwargs["headers"]["Authorization"] == "qcc-key-abc"


def _rotation_config(primary, fallback):
    async def fake_config(config_key):
        if config_key == "third_party.qcc.api_key":
            return primary
        if config_key == "third_party.qcc.api_key_fallback":
            return fallback
        return None

    return fake_config


@pytest.mark.asyncio
async def test_rotation_primary_exhausted_then_fallback_succeeds(monkeypatch):
    used_keys = []

    async def fake_do_query(search_key, api_key):
        used_keys.append(api_key)
        if api_key == "qcc-primary-key":
            return {"ok": False, "reason": "credits_exhausted"}
        return {"ok": True, "data": {"companyName": "ACME"}}

    monkeypatch.setattr(qcc_client, "get_third_party_config", _rotation_config("qcc-primary-key", "qcc-fallback-key"))
    monkeypatch.setattr(qcc_client, "_do_query", fake_do_query)

    result = await qcc_client.get_company_info("ACME")

    assert result["ok"] is True
    assert used_keys == ["qcc-primary-key", "qcc-fallback-key"]


@pytest.mark.asyncio
async def test_non_credits_error_short_circuits_without_retry(monkeypatch):
    used_keys = []

    async def fake_do_query(search_key, api_key):
        used_keys.append(api_key)
        return {"ok": False, "reason": "not_found"}

    monkeypatch.setattr(qcc_client, "get_third_party_config", _rotation_config("qcc-primary-key", "qcc-fallback-key"))
    monkeypatch.setattr(qcc_client, "_do_query", fake_do_query)

    result = await qcc_client.get_company_info("ACME")

    assert result == {"ok": False, "reason": "not_found"}
    assert used_keys == ["qcc-primary-key"]


@pytest.mark.asyncio
async def test_fallback_only_is_usable(monkeypatch):
    used_keys = []

    async def fake_do_query(search_key, api_key):
        used_keys.append(api_key)
        return {"ok": True, "data": {"companyName": "ACME"}}

    monkeypatch.setattr(qcc_client, "get_third_party_config", _rotation_config(None, "qcc-fallback-key"))
    monkeypatch.setattr(qcc_client, "_do_query", fake_do_query)

    result = await qcc_client.get_company_info("ACME")

    assert result["ok"] is True
    assert used_keys == ["qcc-fallback-key"]
