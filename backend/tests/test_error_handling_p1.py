"""P1 输入容错加固回归测试（2026-09-08 QA 报告 #4 / #5 / S5 / S6）。

- 非法 UUID 路径参数 → 422（非 500，无 traceback 泄露）。
- 超长字段 → 422（非 500）。
- 正常业务 404（资源不存在）语义保持不变。
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient
import asyncpg
from sqlalchemy.exc import StatementError

from app.main import app
from app.dependencies import get_current_user
from app.database import get_db
from app.models.user import User


async def _request(method: str, url: str, **kwargs):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, url, **kwargs)


def _setup_user(role: str = "user"):
    user = User(id="u-err", email="err@test.com", role=role, password_hash="x")
    app.dependency_overrides[get_current_user] = lambda: user


def _fake_db_with_uuid_error():
    """DB mock：对 UUID 过滤查询抛出包装 asyncpg DataError 的 StatementError，
    复现真实 PostgreSQL invalid input syntax for type uuid 行为。"""
    db = AsyncMock()

    def fake_execute(stmt, *params, **kwargs):
        text = str(stmt)
        if "FROM plan_projects" in text or "FROM enterprises" in text:
            orig = asyncpg.exceptions.DataError(
                'invalid input syntax for type uuid: "not-a-uuid"'
            )
            raise StatementError(
                "invalid input syntax for type uuid", str(stmt), {}, orig
            )
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    db.execute.side_effect = fake_execute
    return db


def _setup_db_for_invalid_uuid():
    app.dependency_overrides[get_db] = _fake_db_with_uuid_error


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_invalid_uuid_returns_422_for_enterprises():
    _setup_user()
    _setup_db_for_invalid_uuid()
    try:
        resp = asyncio.run(_request("GET", "/api/v1/enterprises/not-a-uuid"))
        assert resp.status_code == 422
        body = resp.text.lower()
        assert "traceback" not in body
        assert "asyncpg" not in body
        assert "internal server error" not in body
    finally:
        _teardown()


def test_invalid_uuid_returns_422_for_plans():
    _setup_user()
    _setup_db_for_invalid_uuid()
    try:
        resp = asyncio.run(_request("GET", "/api/v1/plans/not-a-uuid"))
        assert resp.status_code == 422
    finally:
        _teardown()


def test_oversized_field_returns_422_not_500():
    _setup_user()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    try:
        resp = asyncio.run(
            _request(
                "POST",
                "/api/v1/enterprises",
                json={"name": "X" * 200_000},
            )
        )
        assert resp.status_code in (400, 422)
        assert "internal server error" not in resp.text.lower()
    finally:
        _teardown()


def test_normal_404_preserved():
    _setup_user()
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = asyncio.run(_request("GET", f"/api/v1/enterprises/{uuid.uuid4()}"))
        assert resp.status_code == 404
    finally:
        _teardown()
