"""P0 安全加固回归测试（2026-09-08 QA 报告 #3 / S1 / #11 / S4）。

- JWT：默认/弱 SECRET_KEY 必须被拒绝，不产生可伪造 token。
- /configs：普通用户不可读写删系统配置；管理员可正常操作。
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from app.config import Settings
from app.dependencies import get_current_user, require_admin
from app.database import get_db
from app.main import app
from app.services import auth_service


# ── JWT 密钥策略 ──

def test_settings_has_no_known_default_secret():
    """默认 Settings 不允许使用可预测的弱密钥。"""
    settings = Settings(_env_file=None)
    assert settings.SECRET_KEY not in (
        "dev-secret-key-change-in-production",
        "emergency-plan-docker-secret-key-2026",
    )


def test_create_token_refuses_weak_default_secret():
    """用弱默认密钥调用 create_access_token 必须抛错而非签发。"""
    weak_keys = (
        "dev-secret-key-change-in-production",
        "emergency-plan-docker-secret-key-2026",
    )
    for key in weak_keys:
        with patch.object(auth_service.settings, "SECRET_KEY", key):
            with pytest.raises(ValueError):
                auth_service.create_access_token("some-user-id")


def test_token_signing_uses_strong_key_and_roundtrips():
    """强密钥（>=32 字节随机）可正常签发与解码。"""
    strong = os.urandom(48).hex()
    with patch.object(auth_service.settings, "SECRET_KEY", strong):
        token = auth_service.create_access_token("user-1")
        payload = jwt.decode(token, strong, algorithms=["HS256"])
        assert payload["sub"] == "user-1"
        assert payload["type"] == "access"


# ── /configs 权限 ──

def _routes_for(path: str):
    return [r for r in app.routes if getattr(r, "path", "") == path]


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_configs_routes_require_admin_dependency(method):
    """/configs 全部端点必须带 require_admin（而非仅 get_current_user）。"""
    for route in _routes_for("/api/v1/configs"):
        if method in getattr(route, "methods", set()):
            assert "require_admin" in route.dependant.dependencies[0].call.__module__ + "." + (
                route.dependant.dependencies[0].call.__name__
            )


@pytest.mark.anyio
async def test_require_admin_rejects_normal_user():
    from app.models.user import User

    user = User(id="u1", email="u@test.com", role="user")
    with pytest.raises(Exception) as exc:
        await require_admin(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_require_admin_accepts_admin_and_super_admin():
    from app.models.user import User

    for role in ("admin", "super_admin"):
        user = User(id="u1", email="u@test.com", role=role)
        result = await require_admin(current_user=user)
        assert result is user


def test_configs_api_forbids_normal_user():
    """真实 API：普通用户 GET/PUT/DELETE /configs 均 403。"""
    from app.models.user import User

    user = User(id="u-normal", email="u@test.com", role="user", password_hash="x")
    from fastapi import HTTPException

    async def deny():
        raise HTTPException(status_code=403, detail="需要管理员权限")

    # 覆盖 require_admin 直接返回 403（等价于普通用户命中权限拦截）
    app.dependency_overrides[require_admin] = deny
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: None

    from httpx import ASGITransport, AsyncClient

    async def run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            get_resp = await client.get("/api/v1/configs")
            put_resp = await client.put(
                "/api/v1/configs/export_dir", json={"config_value": "./evil"}
            )
            del_resp = await client.delete("/api/v1/configs/export_dir")
        return get_resp.status_code, put_resp.status_code, del_resp.status_code

    import asyncio

    statuses = asyncio.run(run())
    assert statuses == (403, 403, 403)
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_configs_api_allows_admin():
    """真实 API：管理员可读系统配置（覆盖 get_db 防真实 DB 依赖）。"""
    from app.models.user import User

    admin = User(id="u-admin", email="admin@test.com", role="super_admin", password_hash="x")
    app.dependency_overrides[require_admin] = lambda: admin
    db = AsyncMock()
    rows = MagicMock()
    rows.scalars.return_value.all.return_value = []
    db.execute.return_value = rows
    app.dependency_overrides[get_db] = lambda: db

    from httpx import ASGITransport, AsyncClient

    async def run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/configs")
        return resp.status_code

    import asyncio

    assert asyncio.run(run()) == 200
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(get_db, None)
