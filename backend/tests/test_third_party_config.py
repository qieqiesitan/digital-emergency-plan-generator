"""third_party_config 服务测试：DB → env（非空）→ None 优先级、原子 upsert、seed 导入。

参照仓库既有 service 测试的写法（tests/test_batch_context.py），用 monkeypatch
把服务内部的 async_session 替换为共享内存 fake，避免依赖真实数据库。
并发用例通过「闸门 + 陈旧空读 + commit 冲突」三层模拟还原 check-then-insert
的真实竞态：两个事务先汇合（都读到"行不存在"），随后都写入同一主键，旧实现
下后提交方会抛 IntegrityError。
"""

import asyncio

import pytest
from sqlalchemy.dialects.postgresql.dml import Insert as PgInsert
from sqlalchemy.exc import IntegrityError

import app.services.third_party_config as tpc
from app.database import Base
from app.models.third_party_config import ThirdPartyConfig
from app.services.llm_client import decrypt_api_key
from app.services.secret_utils import decrypt_secret


class _RaceGate:
    """两方并发闸门：n 个协程全部到达后才放行，模拟真实并发交错。

    最后到达者先让出一次事件循环（sleep(0)），保证先到达者按注册顺序先恢复，
    从而调用顺序 = 写入顺序（后调用者最后写入，最终值为后写值）。
    """

    def __init__(self, n):
        self._remaining = n
        self._event = asyncio.Event()

    async def wait(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self._event.set()
            await asyncio.sleep(0)
        await self._event.wait()


class _FakeSession:
    """极简内存会话：模拟服务用到的 get / execute / add / commit / rollback。

    race_stale_read=True 时 get 恒返回 None（模拟另一事务尚未提交时的空读）；
    raise_on_conflict=True 时 commit 对已存在主键抛 IntegrityError（模拟唯一键冲突）。
    """

    def __init__(self, store, gate=None, race_stale_read=False, raise_on_conflict=False):
        self._store = store
        self._gate = gate
        self._race_stale_read = race_stale_read
        self._raise_on_conflict = raise_on_conflict
        self._pending = {}

    async def _sync_point(self):
        if self._gate is not None:
            await self._gate.wait()

    async def get(self, model, key):
        await self._sync_point()
        if self._race_stale_read:
            return None
        return self._store.get(key)

    async def execute(self, stmt):
        # 服务只发送 PostgreSQL INSERT ... ON CONFLICT DO UPDATE（原子 upsert）；
        # 内存模拟 = 直接按新值覆盖主键行。
        await self._sync_point()
        if not isinstance(stmt, PgInsert):
            raise AssertionError(f"unexpected statement type: {type(stmt)!r}")
        values = {col.key: bp.effective_value for col, bp in stmt._values.items()}
        self._store[values["config_key"]] = ThirdPartyConfig(**values)

    def add(self, obj):
        self._pending[obj.config_key] = obj

    async def commit(self):
        await self._sync_point()
        if self._raise_on_conflict:
            for key in self._pending:
                if key in self._store:
                    raise IntegrityError("stmt", {}, Exception("UNIQUE constraint failed"))
        for key, obj in self._pending.items():
            self._store[key] = obj
        self._pending.clear()

    async def rollback(self):
        self._pending.clear()


class _FakeSessionCtx:
    def __init__(self, store, gate=None, race_stale_read=False, raise_on_conflict=False):
        self._store = store
        self._gate = gate
        self._race_stale_read = race_stale_read
        self._raise_on_conflict = raise_on_conflict

    async def __aenter__(self):
        return _FakeSession(
            self._store,
            gate=self._gate,
            race_stale_read=self._race_stale_read,
            raise_on_conflict=self._raise_on_conflict,
        )

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
async def test_whitespace_env_treated_as_empty(fake_session, monkeypatch):
    monkeypatch.setenv("QCC_API_KEY", "   ")
    assert await tpc.get_third_party_config("third_party.qcc.api_key") is None


@pytest.mark.asyncio
async def test_env_value_is_stripped(fake_session, monkeypatch):
    monkeypatch.setenv("QCC_API_KEY", "  env-secret  ")
    assert await tpc.get_third_party_config("third_party.qcc.api_key") == "env-secret"


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
async def test_secret_set_then_decrypts_to_plaintext(fake_session):
    await tpc.set_third_party_config("third_party.qcc.api_key", "plain-secret")
    stored = fake_session["third_party.qcc.api_key"].config_value
    assert decrypt_secret(stored) == "plain-secret"


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
async def test_import_seed_configs_skips_whitespace_env(fake_session, monkeypatch):
    monkeypatch.setenv("QCC_API_KEY", "   ")
    await tpc.import_seed_configs()
    assert await tpc.get_third_party_config("third_party.qcc.api_key") is None


@pytest.mark.asyncio
async def test_import_seed_configs_does_not_overwrite_db(fake_session, monkeypatch):
    await tpc.set_third_party_config("third_party.qcc.api_key", "db-secret")
    monkeypatch.setenv("QCC_API_KEY", "env-secret")
    await tpc.import_seed_configs()
    assert await tpc.get_third_party_config("third_party.qcc.api_key") == "db-secret"


@pytest.mark.asyncio
async def test_import_seed_configs_falls_back_to_settings_when_env_missing(fake_session, monkeypatch):
    """进程环境缺 QCC_API_KEY 但 settings（.env 加载）有值 → seed 落库（任务 7 并入项）。"""
    monkeypatch.setattr(tpc.settings, "QCC_API_KEY", "settings-secret")
    await tpc.import_seed_configs()
    # 直接断言 seed 真实落库（get 本身带 settings 兜底，无法区分来源）。
    assert "third_party.qcc.api_key" in fake_session
    stored = fake_session["third_party.qcc.api_key"]
    assert decrypt_secret(stored.config_value) == "settings-secret"


@pytest.mark.asyncio
async def test_import_seed_configs_skips_settings_class_default(fake_session, monkeypatch):
    """无任何 env/.env：settings 字段命中声明默认值（QCC_ENDPOINT 内置 URL）→ 不写入 DB。"""
    default = tpc.settings.model_fields["QCC_ENDPOINT"].default
    monkeypatch.setattr(tpc.settings, "QCC_ENDPOINT", default)
    await tpc.import_seed_configs()
    assert "third_party.qcc.endpoint" not in fake_session


@pytest.mark.asyncio
async def test_get_ignores_settings_class_default(fake_session, monkeypatch):
    """无 env/.env 且 settings 字段 = 声明默认值 → get 不返回类默认值。"""
    default = tpc.settings.model_fields["QCC_ENDPOINT"].default
    monkeypatch.setattr(tpc.settings, "QCC_ENDPOINT", default)
    assert await tpc.get_third_party_config("third_party.qcc.endpoint") is None


@pytest.mark.asyncio
async def test_import_seed_configs_writes_settings_non_default(fake_session, monkeypatch):
    """.env 显式配置（非类默认值）经 settings 兜底仍写入 DB。"""
    monkeypatch.setattr(tpc.settings, "QCC_ENDPOINT", "https://custom.example.com/stream")
    await tpc.import_seed_configs()
    assert "third_party.qcc.endpoint" in fake_session


@pytest.mark.asyncio
async def test_concurrent_set_same_key_no_integrity_error(monkeypatch, store):
    # 还原真实竞态：两事务先汇合（都读到"行不存在"），再各自写入同一主键；
    # 旧 check-then-insert 实现会因后提交方唯一键冲突抛 IntegrityError。
    gate = _RaceGate(2)
    race_ctx = _FakeSessionCtx(store, gate=gate, race_stale_read=True, raise_on_conflict=True)
    monkeypatch.setattr(tpc, "async_session", lambda: race_ctx)

    results = await asyncio.gather(
        tpc.set_third_party_config("third_party.qcc.endpoint", "v1"),
        tpc.set_third_party_config("third_party.qcc.endpoint", "v2"),
        return_exceptions=True,
    )
    assert not any(isinstance(r, Exception) for r in results), results

    # 用普通读取会话确认最终值 = 后写值
    normal_ctx = _FakeSessionCtx(store)
    monkeypatch.setattr(tpc, "async_session", lambda: normal_ctx)
    assert await tpc.get_third_party_config("third_party.qcc.endpoint") == "v2"


def test_decrypt_failure_uses_generic_message():
    with pytest.raises(Exception) as exc:
        decrypt_secret("not-hex")
    assert "配置解密失败" in str(exc.value)


def test_llm_decrypt_api_key_keeps_ai_message():
    with pytest.raises(Exception) as exc:
        decrypt_api_key("not-hex")
    assert "AI Key解密失败" in str(exc.value)


def test_startup_models_registered_in_metadata():
    """启动接线守护：create_all 必须建 third_party_config 与 schema_migrations 表。"""
    assert 'third_party_config' in Base.metadata.tables
    assert 'schema_migrations' in Base.metadata.tables
