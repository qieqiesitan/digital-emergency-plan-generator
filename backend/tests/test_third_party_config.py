"""third_party_config 服务测试：DB → env（非空）→ None 优先级、upsert、seed 导入。

参照仓库既有 service 测试的写法（tests/test_batch_context.py），用 monkeypatch
把服务内部的 async_session 替换为共享内存 fake，避免依赖真实数据库。
"""

import pytest

import app.services.third_party_config as tpc


class _FakeSession:
    """极简内存会话：只实现服务用到的主键 get / add / commit。"""

    def __init__(self, store):
        self._store = store

    async def get(self, model, key):
        return self._store.get(key)

    def add(self, obj):
        self._store[obj.config_key] = obj

    async def commit(self):
        pass

    async def rollback(self):
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
    for env_var in tpc.ENV_MAP.values():
        monkeypatch.delenv(env_var, raising=False)


@pytest.fixture
def fake_session(monkeypatch, store):
    monkeypatch.setattr(tpc, "async_session", lambda: _FakeSessionCtx(store))
    return store


@pytest.mark.asyncio
async def test_get_returns_decrypted_db_value_when_db_present(fake_session, monkeypatch):
    await tpc.set_third_party_config("third_party.qcc.api_key", "db-secret")
    monkeypatch.setenv("QCC_API_KEY", "env-secret")
    assert await tpc.get_third_party_config("third_party.qcc.api_key") == "db-secret"


@pytest.mark.asyncio
async def test_get_falls_back_to_env_when_db_missing(fake_session, monkeypatch):
    monkeypatch.setenv("QCC_API_KEY", "env-secret")
    assert await tpc.get_third_party_config("third_party.qcc.api_key") == "env-secret"


@pytest.mark.asyncio
async def test_get_returns_none_when_db_and_env_missing(fake_session, monkeypatch):
    assert await tpc.get_third_party_config("third_party.qcc.api_key") is None


@pytest.mark.asyncio
async def test_empty_env_not_treated_as_value(fake_session, monkeypatch):
    monkeypatch.setenv("QCC_API_KEY", "")
    assert await tpc.get_third_party_config("third_party.qcc.api_key") is None


@pytest.mark.asyncio
async def test_empty_env_does_not_override_db(fake_session, monkeypatch):
    await tpc.set_third_party_config("third_party.qcc.api_key", "db-secret")
    monkeypatch.setenv("QCC_API_KEY", "")
    assert await tpc.get_third_party_config("third_party.qcc.api_key") == "db-secret"


@pytest.mark.asyncio
async def test_set_upsert_then_get_returns_new_value(fake_session):
    await tpc.set_third_party_config("third_party.amap.api_key", "v1", updated_by="admin")
    assert await tpc.get_third_party_config("third_party.amap.api_key") == "v1"
    await tpc.set_third_party_config("third_party.amap.api_key", "v2", updated_by="admin2")
    assert await tpc.get_third_party_config("third_party.amap.api_key") == "v2"
    assert fake_session["third_party.amap.api_key"].updated_by == "admin2"


@pytest.mark.asyncio
async def test_secret_stored_encrypted(fake_session):
    await tpc.set_third_party_config("third_party.qcc.api_key", "plain-secret")
    assert fake_session["third_party.qcc.api_key"].config_value != "plain-secret"


@pytest.mark.asyncio
async def test_import_seed_configs_writes_from_env_when_db_missing(fake_session, monkeypatch):
    monkeypatch.setenv("QCC_ENDPOINT", "https://agent.example.com")
    await tpc.import_seed_configs()
    assert await tpc.get_third_party_config("third_party.qcc.endpoint") == "https://agent.example.com"


@pytest.mark.asyncio
async def test_import_seed_configs_skips_empty_env(fake_session):
    await tpc.import_seed_configs()
    assert await tpc.get_third_party_config("third_party.qcc.api_key") is None
    assert await tpc.get_third_party_config("third_party.amap.api_key") is None


@pytest.mark.asyncio
async def test_import_seed_configs_does_not_overwrite_db(fake_session, monkeypatch):
    await tpc.set_third_party_config("third_party.qcc.api_key", "db-secret")
    monkeypatch.setenv("QCC_API_KEY", "env-secret")
    await tpc.import_seed_configs()
    assert await tpc.get_third_party_config("third_party.qcc.api_key") == "db-secret"
