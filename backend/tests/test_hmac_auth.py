"""hmac_auth 中间件测试：配置读取异常回退 env、DB 值优先于 env。"""

import time

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.middleware.hmac_auth import HmacAuthMiddleware, _build_signature


async def _empty_body_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def _make_request(method: str, path: str, sig: str, ts: str) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (b"x-signature", sig.encode()),
            (b"x-timestamp", ts.encode()),
            (b"content-type", b"application/json"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
        "http_version": "1.1",
    }
    return Request(scope, receive=_empty_body_receive)


@pytest.mark.asyncio
async def test_db_exception_falls_back_to_env_secret(monkeypatch):
    async def boom(_config_key):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.middleware.hmac_auth.get_third_party_config", boom)
    monkeypatch.setattr(settings, "EXTERNAL_API_HMAC_SECRET", "env-secret")

    ts = str(int(time.time()))
    sig = _build_signature("POST", "/api/external/plan/123", ts, "", "env-secret")
    request = _make_request("POST", "/api/external/plan/123", sig, ts)

    passed = []

    async def call_next(req):
        passed.append(req)
        return JSONResponse({"ok": True})

    middleware = HmacAuthMiddleware(lambda scope, receive, send: None)
    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert len(passed) == 1


@pytest.mark.asyncio
async def test_db_secret_takes_precedence_over_env(monkeypatch):
    async def fake_config(_config_key):
        return "db-secret"

    monkeypatch.setattr("app.middleware.hmac_auth.get_third_party_config", fake_config)
    monkeypatch.setattr(settings, "EXTERNAL_API_HMAC_SECRET", "env-secret")

    middleware = HmacAuthMiddleware(lambda scope, receive, send: None)
    ts = str(int(time.time()))
    passed = []

    async def call_next(req):
        passed.append(req)
        return JSONResponse({"ok": True})

    # DB secret 签名 → 通过
    db_sig = _build_signature("POST", "/api/external/plan/123", ts, "", "db-secret")
    ok_resp = await middleware.dispatch(
        _make_request("POST", "/api/external/plan/123", db_sig, ts), call_next
    )
    assert ok_resp.status_code == 200
    assert len(passed) == 1

    # env secret 签名（与 DB 不一致）→ 401，证明 DB 值优先
    env_sig = _build_signature("POST", "/api/external/plan/123", ts, "", "env-secret")
    bad_resp = await middleware.dispatch(
        _make_request("POST", "/api/external/plan/123", env_sig, ts), call_next
    )
    assert bad_resp.status_code == 401


@pytest.mark.asyncio
async def test_no_secret_rejects_with_503(monkeypatch):
    async def no_config(_config_key):
        return None

    monkeypatch.setattr("app.middleware.hmac_auth.get_third_party_config", no_config)
    monkeypatch.setattr(settings, "EXTERNAL_API_HMAC_SECRET", "")

    middleware = HmacAuthMiddleware(lambda scope, receive, send: None)

    async def call_next(req):
        return JSONResponse({"ok": True})

    response = await middleware.dispatch(
        _make_request("POST", "/api/external/plan/123", "sig", str(int(time.time()))),
        call_next,
    )
    assert response.status_code == 503
