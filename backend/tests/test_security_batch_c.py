"""P2/P3 安全与输入校验加固回归测试（QA 报告 #7/#9/#16、N2、S16 等）。

- 登出撤销：logout 后 access/refresh 立即失效（jti 黑名单）。
- /prompts 读端点收紧为管理员。
- 注册邮箱格式 EmailStr；密码 >72 字节拒绝（bcrypt 截断面）。
- 负员工数拒绝；未知 /api/* 路径返回 JSON 404 而非 SPA HTML。
- 安全响应头存在。
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import JWTError

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas.auth import RegisterRequest, ResetPasswordRequest
from app.schemas.enterprise import EnterpriseCreate
from app.services import auth_service
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_token,
    hash_password,
)


# ── 登出撤销（服务层） ──

def test_revoke_refresh_token_blocks_decode():
    with patch.object(auth_service.settings, "SECRET_KEY", "s" * 64):
        access = create_access_token("u1")
        refresh = create_refresh_token("u1")
        assert decode_token(refresh)["type"] == "refresh"
        revoke_token(refresh)
        with pytest.raises(JWTError):
            decode_token(refresh)
        # access 未撤销仍可用
        assert decode_token(access)["type"] == "access"


def test_revoke_access_token_blocks_decode():
    with patch.object(auth_service.settings, "SECRET_KEY", "s" * 64):
        access = create_access_token("u1")
        revoke_token(access)
        with pytest.raises(JWTError):
            decode_token(access)


def test_register_rejects_invalid_email_format():
    with pytest.raises(Exception):
        RegisterRequest(
            email="not-an-email",
            password="Abcdef12",
            password_confirm="Abcdef12",
            name="测试",
        )


def test_password_over_72_bytes_rejected():
    long_pwd = "A" * 71 + "b1"  # 73 字节 > 72
    with pytest.raises(Exception):
        RegisterRequest(
            email="a@b.com", password=long_pwd, password_confirm=long_pwd, name="测试"
        )
    with pytest.raises(Exception):
        ResetPasswordRequest(token="t", new_password=long_pwd)


def test_enterprise_negative_employee_rejected():
    with pytest.raises(Exception):
        EnterpriseCreate(name="测试", employee_count=-1)


# ── API 集成 ──

async def _request(method: str, url: str, **kwargs):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, url, **kwargs)


def _user_db_mock(email: str = "u@test.com"):
    db = AsyncMock()
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        name="测试",
        role="user",
        password_hash=hash_password("RealPass123"),
    )

    def fake_execute(stmt, *params, **kwargs):
        text = str(stmt)
        if "FROM users" in text:
            r = MagicMock()
            r.scalar_one_or_none.return_value = user
            return r
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        r.scalar.return_value = None
        return r

    db.execute.side_effect = fake_execute
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def test_unknown_api_path_returns_json_404():
    """/api/v1/nonexistent 返回 JSON 404 而非 SPA HTML。"""
    resp = asyncio.run(_request("GET", "/api/v1/nonexistent"))
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert "接口不存在" in resp.text


def test_health_has_security_headers():
    resp = asyncio.run(_request("GET", "/api/health"))
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "SAMEORIGIN"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_prompts_list_forbidden_for_normal_user():
    from fastapi import HTTPException

    async def deny():
        raise HTTPException(status_code=403, detail="需要管理员权限")

    app.dependency_overrides[require_admin] = deny
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    try:
        resp = asyncio.run(_request("GET", "/api/v1/prompts"))
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_admin, None)
        app.dependency_overrides.pop(get_db, None)


def test_logout_revokes_access_and_refresh_api():
    """登录 → logout（带 refresh + bearer access）→ 两者立即 401。"""
    db = _user_db_mock()
    app.dependency_overrides[get_db] = lambda: db

    async def run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "u@test.com", "password": "RealPass123"},
            )
            assert login_resp.status_code == 200
            data = login_resp.json()["data"]
            access = data["access_token"]
            refresh = data["refresh_token"]

            logout_resp = await client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": refresh},
                headers={"Authorization": f"Bearer {access}"},
            )
            assert logout_resp.status_code == 200

            me_resp = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {access}"},
            )
            refresh_resp = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": refresh}
            )
            return me_resp.status_code, refresh_resp.status_code

    try:
        me_status, refresh_status = asyncio.run(run())
        assert me_status == 401
        assert refresh_status == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
