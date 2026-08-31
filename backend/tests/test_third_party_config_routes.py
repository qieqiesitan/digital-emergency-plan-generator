"""管理员第三方配置 API 路由测试（GET/PUT /api/v1/system/third-party-config）。

参照仓库既有路由测试模式（TestClient + dependency_overrides，见
test_enterprise_org.py / test_risk_control_list.py）：用最小 FastAPI app 只挂载
本路由，覆盖 get_current_user；服务层用内存 fake 会话（沿用 test_third_party_config.py
的 _FakeSession 模式，monkeypatch app.services.third_party_config.async_session），
使 get/set_third_party_config 的加密读写完整走真实实现。
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql.dml import Insert as PgInsert

import app.services.third_party_config as tpc
from app.dependencies import get_current_user
from app.models.third_party_config import ThirdPartyConfig
from app.models.user import User
from app.routers import third_party_config
from app.services.secret_utils import mask_secret


class _FakeSession:
    """极简内存会话：覆盖服务用到的 get / execute / commit。"""

    def __init__(self, store):
        self._store = store

    async def get(self, model, key):
        return self._store.get(key)

    async def execute(self, stmt):
        if not isinstance(stmt, PgInsert):
            raise AssertionError(f"unexpected statement type: {type(stmt)!r}")
        values = {col.key: bp.effective_value for col, bp in stmt._values.items()}
        self._store[values["config_key"]] = ThirdPartyConfig(**values)

    async def commit(self):
        pass


class _FakeSessionCtx:
    def __init__(self, store):
        self._store = store

    async def __aenter__(self):
        return _FakeSession(self._store)

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def store():
    return {}


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """清空所有相关 env，保证每个用例从无 env 基线开始。"""
    for env_var, _ in tpc.KEY_SPEC.values():
        monkeypatch.delenv(env_var, raising=False)


def _make_client(app, role):
    def _override_user():
        return User(id="u1", email="admin@example.com", name="管理员A", role=role)

    app.dependency_overrides[get_current_user] = _override_user
    return app


@pytest.fixture
def client(monkeypatch, store):
    monkeypatch.setattr(tpc, "async_session", lambda: _FakeSessionCtx(store))
    app = FastAPI()
    app.include_router(third_party_config.router)
    _make_client(app, role="admin")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user_client(monkeypatch, store):
    """普通用户客户端：验证 require_admin 403 门禁。"""
    monkeypatch.setattr(tpc, "async_session", lambda: _FakeSessionCtx(store))
    app = FastAPI()
    app.include_router(third_party_config.router)
    _make_client(app, role="user")
    with TestClient(app) as test_client:
        yield test_client


def test_get_requires_admin(user_client):
    resp = user_client.get("/system/third-party-config")
    assert resp.status_code == 403


def test_put_requires_admin(user_client):
    resp = user_client.put(
        "/system/third-party-config",
        json=[{"key": "third_party.qcc.api_key", "value": "secret-1"}],
    )
    assert resp.status_code == 403


def test_admin_get_lists_all_keys_with_labels_and_masks(client):
    resp = client.get("/system/third-party-config")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert [item["key"] for item in items] == list(tpc.KEY_SPEC.keys())
    for item in items:
        # configured/masked_value 必须与服务层实际读取结果一致
        # （服务层 DB → env → pydantic settings 兜底，config.py 对
        # QCC_ENDPOINT 有代码默认值，因此该 key 天然 configured=True）
        expected = asyncio.run(tpc.get_third_party_config(item["key"]))
        assert item["label"]
        assert item["configured"] is (expected is not None)
        assert item["type"] in ("secret", "string")
        if item["type"] == "secret":
            assert item["masked_value"] == (mask_secret(expected) if expected else "****")
        else:
            assert item["masked_value"] == (expected or "")
        assert "description" in item


def test_admin_get_masks_configured_secret_without_leaking(client, store):
    plaintext = "SUPER-SECRET-VALUE-123456789"
    asyncio.run(tpc.set_third_party_config("third_party.qcc.api_key", plaintext))
    resp = client.get("/system/third-party-config")
    assert resp.status_code == 200
    items = resp.json()["data"]
    qcc = next(item for item in items if item["key"] == "third_party.qcc.api_key")
    assert qcc["configured"] is True
    assert qcc["masked_value"] == mask_secret(plaintext)
    assert plaintext not in resp.text


def test_admin_put_updates_config_then_get_shows_new_mask(client, store):
    first = "first-secret"
    second = "second-secret"
    asyncio.run(tpc.set_third_party_config("third_party.qcc.api_key", first))
    resp_put = client.put(
        "/system/third-party-config",
        json=[{"key": "third_party.qcc.api_key", "value": second}],
    )
    assert resp_put.status_code == 200
    assert second not in resp_put.text

    stored = asyncio.run(tpc.get_third_party_config("third_party.qcc.api_key"))
    assert stored == second
    assert store["third_party.qcc.api_key"].updated_by == "管理员A"

    resp_get = client.get("/system/third-party-config")
    qcc = next(item for item in resp_get.json()["data"] if item["key"] == "third_party.qcc.api_key")
    assert qcc["configured"] is True
    assert qcc["masked_value"] == mask_secret(second)
    assert first not in resp_get.text
    assert second not in resp_get.text


def test_admin_put_string_type_stored_and_displayed(client, store):
    endpoint = "https://agent.example.com/api"
    resp = client.put(
        "/system/third-party-config",
        json=[{"key": "third_party.qcc.endpoint", "value": endpoint}],
    )
    assert resp.status_code == 200
    assert asyncio.run(tpc.get_third_party_config("third_party.qcc.endpoint")) == endpoint
    resp_get = client.get("/system/third-party-config")
    item = next(i for i in resp_get.json()["data"] if i["key"] == "third_party.qcc.endpoint")
    assert item["configured"] is True
    assert item["masked_value"] == endpoint


def test_put_empty_value_rejected(client):
    resp = client.put(
        "/system/third-party-config",
        json=[{"key": "third_party.qcc.api_key", "value": ""}],
    )
    assert resp.status_code == 422


def test_put_whitespace_value_rejected(client):
    resp = client.put(
        "/system/third-party-config",
        json=[{"key": "third_party.qcc.api_key", "value": "   "}],
    )
    assert resp.status_code == 422


def test_put_unknown_key_rejected(client):
    resp = client.put(
        "/system/third-party-config",
        json=[{"key": "third_party.unknown.key", "value": "x"}],
    )
    assert resp.status_code == 422


def test_put_logs_do_not_contain_value(client, caplog):
    secret = "log-secret-value-987654321"
    with caplog.at_level("INFO"):
        client.put(
            "/system/third-party-config",
            json=[{"key": "third_party.amap.api_key", "value": secret}],
        )
    assert secret not in caplog.text
