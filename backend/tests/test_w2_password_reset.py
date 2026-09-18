"""W2：忘记密码闭环（管理员重置口径 + 令牌哈希存储）。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.auth_service import hash_reset_token

BACKEND = Path(__file__).resolve().parents[1]


def test_reset_token_hash_is_deterministic_and_not_plaintext():
    token = "abc123-token"
    digest = hash_reset_token(token)
    assert digest != token
    assert len(digest) == 64
    assert hash_reset_token(token) == digest
    assert hash_reset_token("other") != digest


def test_forgot_password_does_not_claim_email_and_creates_no_dead_token():
    """未接 SMTP 前必须给管理员重置口径，且不再签发无人能收到的死令牌。"""
    src = (BACKEND / "app" / "routers" / "auth.py").read_text(encoding="utf-8")
    forgot_block = src.split("async def forgot_password", 1)[1].split("@router.post(\"/reset-password\")", 1)[0]
    assert "用户管理" in forgot_block, "必须给管理员重置指引"
    assert "发送密码重置邮件" not in forgot_block, "不得再声称已发送邮件"
    assert "PasswordResetToken(" not in forgot_block, "未接 SMTP 时不应签发死令牌"


def test_reset_password_looks_up_by_hash():
    src = (BACKEND / "app" / "routers" / "auth.py").read_text(encoding="utf-8")
    reset_block = src.split("async def reset_password", 1)[1]
    assert "hash_reset_token(data.token)" in reset_block, "重置必须按哈希查令牌"


def test_migration_invalidates_legacy_plaintext_tokens():
    sql = (BACKEND / "db_migration_20260918_reset_token_hash.sql").read_text(encoding="utf-8")
    assert "UPDATE password_reset_tokens" in sql
    assert "used_at = now()" in sql
