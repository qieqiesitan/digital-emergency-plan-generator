"""Pytest bootstrap: make the backend package importable from any invocation directory.

Mirrors the sys.path handling in tests/test_web_search.py (inserting the backend
directory at sys.path[0]) without the hardcoded absolute path or os.chdir, so both
`cd backend && pytest tests/...` and root-level `pytest backend/tests/...` work.
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# ── 跨 worker 运行时状态的单测替身 ──
# 生产实现落 Postgres；单测不应依赖数据库，因此默认替换为进程内字典。
# 需要校验 SQL/参数的用例（如 tests/test_w2_runtime_state.py）用
# @pytest.mark.real_runtime_state 声明，走真实实现。

def pytest_configure(config):
    config.addinivalue_line("markers", "real_runtime_state: 使用真实的 runtime_state 实现")


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _in_memory_runtime_state(monkeypatch, request):
    if request.node.get_closest_marker("real_runtime_state"):
        yield
        return

    from app.services import auth_service, enterprise_autofill, generation_progress, runtime_state
    from app.middleware import rate_limit
    from app.routers import external, public_hazard, resource_investigation, risk_assessment

    store: dict[str, dict] = {}

    async def set_state(key, value, ttl_seconds=None, session=None):
        store[key] = dict(value)

    async def get_state(key, session=None):
        value = store.get(key)
        return dict(value) if value is not None else None

    async def delete_state(key, session=None):
        store.pop(key, None)

    async def try_acquire_lease(key, ttl_seconds, owner, session=None):
        current = store.get(key)
        if current and current.get("_lease_owner"):
            return False
        store[key] = {"_lease_owner": owner}
        return True

    async def release_lease(key, owner, session=None):
        current = store.get(key)
        if current and current.get("_lease_owner") == owner:
            store.pop(key, None)

    async def incr_counter(key, ttl_seconds, session=None):
        current = store.get(key) or {"count": 0}
        current["count"] = int(current.get("count", 0)) + 1
        store[key] = current
        return current["count"]

    async def consume_once(key, ttl_seconds, session=None):
        if key in store:
            return False
        store[key] = {"used": True}
        return True

    for module in (runtime_state, generation_progress, auth_service, enterprise_autofill, rate_limit,
                   public_hazard, external, risk_assessment, resource_investigation):
        for name, fn in (
            ("set_state", set_state), ("get_state", get_state),
            ("delete_state", delete_state),
            ("try_acquire_lease", try_acquire_lease),
            ("release_lease", release_lease),
            ("incr_counter", incr_counter), ("consume_once", consume_once),
        ):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, fn)
    yield
