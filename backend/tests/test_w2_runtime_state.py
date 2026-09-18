"""W2：跨 worker 共享运行时状态基座（SQL/参数级回归）。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import runtime_state

pytestmark = pytest.mark.real_runtime_state


def _session(row=None, rows=None):
    session = MagicMock()
    result = MagicMock()
    result.fetchone.return_value = row
    result.fetchall.return_value = rows or []
    session.execute = AsyncMock(return_value=result)
    return session, result


@pytest.mark.asyncio
async def test_set_state_uses_upsert_with_ttl():
    session, _ = _session()
    await runtime_state.set_state("k", {"a": 1}, ttl_seconds=60, session=session)
    sql = str(session.execute.await_args.args[0]).lower()
    params = session.execute.await_args.args[1]
    assert "insert into app_runtime_state" in sql and "on conflict (key) do update" in sql
    assert params["key"] == "k" and params["ttl"] == 60
    assert '"a": 1' in params["value"]


@pytest.mark.asyncio
async def test_get_state_filters_expired_and_parses_json():
    session, _ = _session(row=('{"active": true}',))
    assert await runtime_state.get_state("k", session=session) == {"active": True}
    sql = str(session.execute.await_args.args[0]).lower()
    assert "expires_at" in sql and "now()" in sql

    empty, _ = _session(row=None)
    assert await runtime_state.get_state("k", session=empty) is None


@pytest.mark.asyncio
async def test_try_acquire_lease_returns_whether_row_returned():
    ok, _ = _session(row=("k",))
    assert await runtime_state.try_acquire_lease("lease", 120, owner="w1", session=ok) is True
    sql = str(ok.execute.await_args.args[0]).lower()
    assert "where app_runtime_state.expires_at is null" in sql, "过期/不存在才可抢占"

    busy, _ = _session(row=None)
    assert await runtime_state.try_acquire_lease("lease", 120, owner="w2", session=busy) is False


@pytest.mark.asyncio
async def test_release_lease_requires_owner():
    session, _ = _session()
    await runtime_state.release_lease("lease", "w1", session=session)
    sql = str(session.execute.await_args.args[0]).lower()
    params = session.execute.await_args.args[1]
    assert "value->>'owner' = :owner" in sql
    assert params == {"key": "lease", "owner": "w1"}


@pytest.mark.asyncio
async def test_incr_counter_returns_count():
    session, _ = _session(row=(3,))
    assert await runtime_state.incr_counter("rl", 900, session=session) == 3
    sql = str(session.execute.await_args.args[0]).lower()
    assert "count" in sql and "returning" in sql


@pytest.mark.asyncio
async def test_consume_once_first_use_only():
    first, _ = _session(row=("n1",))
    assert await runtime_state.consume_once("nonce:n1", 300, session=first) is True
    second, _ = _session(row=None)
    assert await runtime_state.consume_once("nonce:n1", 300, session=second) is False
