"""体检修复 S5/S9 回归测试：CORS 收敛、密码最小长度。

- S5：CORS 默认仅本地开发源，且不允许 `*` 与 allow_credentials=True 组合。
- S9：register / reset-password 密码统一 min_length=6 校验。
"""

import pytest
from fastapi.middleware.cors import CORSMiddleware

from app.main import app, _resolve_cors_origins
from app.schemas.auth import RegisterRequest, ResetPasswordRequest


# ── S9 密码策略 ──

def test_register_rejects_short_password():
    with pytest.raises(Exception):
        RegisterRequest(email="a@example.com", password="12345", password_confirm="12345", name="测试用户")


def test_register_accepts_minimum_length_password():
    data = RegisterRequest(email="a@example.com", password="123456", password_confirm="123456", name="测试用户")
    assert data.password == "123456"


def test_register_rejects_mismatched_confirm():
    with pytest.raises(Exception):
        RegisterRequest(email="a@example.com", password="123456", password_confirm="654321", name="测试用户")


def test_reset_password_rejects_short_password():
    with pytest.raises(Exception):
        ResetPasswordRequest(token="tk", new_password="12345")


def test_reset_password_accepts_minimum_length():
    data = ResetPasswordRequest(token="tk", new_password="123456")
    assert data.new_password == "123456"


# ── S5 CORS 收敛 ──

def test_cors_resolver_defaults_to_local_dev_origins():
    assert _resolve_cors_origins() == ["http://localhost:5173", "http://localhost:8082"]


def test_cors_resolver_parses_comma_separated_env():
    assert _resolve_cors_origins(" https://a.example.com , https://b.example.com ") == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_cors_middleware_no_wildcard_with_credentials():
    opts = None
    for m in app.user_middleware:
        if m.cls is CORSMiddleware:
            opts = m.kwargs
    assert opts is not None
    assert "*" not in opts["allow_origins"]
    assert opts["allow_credentials"] is True
    assert opts["allow_origins"] == ["http://localhost:5173", "http://localhost:8082"]
