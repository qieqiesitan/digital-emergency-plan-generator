"""P1-7 登录/注册/忘记密码限流回归测试（2026-09-08 QA 报告 #6 / S3）。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_db
from app.models.user import User
from app.services.auth_service import hash_password


def _install_db_mock():
    """覆盖 get_db，避免限流探针触碰真实数据库。"""
    db = AsyncMock()

    # 按 SQL 内容区分返回：auth 端点查询 user 用真实 User 对象
    def fake_execute(stmt, *params, **kwargs):
        text = str(stmt)
        if "FROM users" in text:
            user = User(
                id="rate-probe-id",
                email="rate_probe@test.com",
                name="限流探针",
                role="user",
                password_hash=hash_password("real-hash-123"),
            )
            r = MagicMock()
            r.scalar_one_or_none.return_value = user
            return r
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        r.scalar.return_value = None
        return r

    db.execute.side_effect = fake_execute
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db


def _uninstall_db_mock():
    app.dependency_overrides.pop(get_db, None)


async def _post(client: AsyncClient, path: str, body: dict):
    return await client.post(path, json=body)


async def _get(client: AsyncClient, path: str):
    return await client.get(path)


def _run_sequence(path: str, body: dict, times: int):
    async def run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            statuses = []
            for _ in range(times):
                if body:
                    resp = await _post(client, path, body)
                else:
                    resp = await _get(client, path)
                statuses.append(resp.status_code)
            return statuses

    return asyncio.run(run())


def test_login_rate_limited_after_30_attempts():
    """同一来源连续 30+ 次登录尝试后必须出现 429。"""
    _install_db_mock()
    try:
        body = {"email": "rate_probe@test.com", "password": "wrong-password"}
        statuses = _run_sequence("/api/v1/auth/login", body, 33)
        assert 429 in statuses
        # 一旦触发限流，后续请求都应被 429 拒绝
        first_429 = statuses.index(429)
        assert all(s == 429 for s in statuses[first_429:])
    finally:
        _uninstall_db_mock()


def test_register_rate_limited():
    _install_db_mock()
    try:
        body = {
            "email": "reg_probe@test.com",
            "password": "Abcdef12",
            "password_confirm": "Abcdef12",
            "name": "限流探针",
        }
        statuses = _run_sequence("/api/v1/auth/register", body, 12)
        assert 429 in statuses
    finally:
        _uninstall_db_mock()


def test_forgot_password_rate_limited():
    _install_db_mock()
    try:
        body = {"email": "nobody@test.com"}
        statuses = _run_sequence("/api/v1/auth/forgot-password", body, 12)
        assert 429 in statuses
    finally:
        _uninstall_db_mock()


def test_health_not_rate_limited():
    """健康检查等非 auth 端点不受影响。"""
    statuses = _run_sequence("/api/health", None, 3)
    assert statuses == [200, 200, 200]
