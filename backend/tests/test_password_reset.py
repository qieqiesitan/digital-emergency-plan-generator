import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.password_reset import PasswordResetToken
from app.routers.auth import forgot_password, reset_password
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest


def _user(email="user@example.com", user_id="u1"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    return user


def _valid_reset(user_id="u1"):
    reset = MagicMock()
    reset.user_id = user_id
    reset.used_at = None
    reset.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    return reset


def test_forgot_password_creates_token_and_returns_success():
    db = AsyncMock()
    db.add = MagicMock()  # db.add 是同步方法，避免 AsyncMock 产生未 await 协程
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: _user())
    resp = asyncio.run(forgot_password(ForgotPasswordRequest(email="user@example.com"), db))
    assert resp.message == "如果该邮箱已注册，我们将发送密码重置邮件"
    added = db.add.call_args[0][0]
    assert isinstance(added, PasswordResetToken)
    assert added.user_id == "u1"
    assert added.token
    db.commit.assert_awaited_once()


def test_forgot_password_unknown_email_does_not_leak():
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    resp = asyncio.run(forgot_password(ForgotPasswordRequest(email="nobody@example.com"), db))
    assert resp.message == "如果该邮箱已注册，我们将发送密码重置邮件"
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


def test_reset_password_success_updates_password_and_marks_used():
    user = _user()
    user.password_hash = "old-hash"
    reset = _valid_reset()
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: reset),
        MagicMock(scalar_one_or_none=lambda: user),
    ]
    resp = asyncio.run(reset_password(ResetPasswordRequest(token="tk", new_password="newpass123"), db))
    assert resp.message == "密码已重置，请使用新密码登录"
    assert user.password_hash != "old"
    assert reset.used_at is not None
    db.commit.assert_awaited_once()


def test_reset_password_invalid_token_fails():
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: None),
    ]
    with pytest.raises(Exception) as exc:
        asyncio.run(reset_password(ResetPasswordRequest(token="bad", new_password="newpass123"), db))
    assert exc.value.status_code == 400


def test_reset_password_expired_token_fails():
    reset = _valid_reset()
    reset.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db = AsyncMock()
    db.execute.side_effect = [MagicMock(scalar_one_or_none=lambda: reset)]
    with pytest.raises(Exception) as exc:
        asyncio.run(reset_password(ResetPasswordRequest(token="tk", new_password="newpass123"), db))
    assert exc.value.status_code == 400


def test_reset_password_used_token_fails():
    reset = _valid_reset()
    reset.used_at = datetime.now(timezone.utc)
    db = AsyncMock()
    db.execute.side_effect = [MagicMock(scalar_one_or_none=lambda: reset)]
    with pytest.raises(Exception) as exc:
        asyncio.run(reset_password(ResetPasswordRequest(token="tk", new_password="newpass123"), db))
    assert exc.value.status_code == 400
