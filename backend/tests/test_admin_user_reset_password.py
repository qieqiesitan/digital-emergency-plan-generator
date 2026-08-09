import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.routers.admin_users import reset_user_password
from app.schemas.role import AdminResetPassword


def test_reset_password_schema_rejects_short_password():
    with pytest.raises(Exception):
        AdminResetPassword(new_password="123")


def test_reset_password_accepts_valid_password():
    data = AdminResetPassword(new_password="newpass123")
    assert data.new_password == "newpass123"


def test_reset_password_raises_404_when_user_missing():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    with pytest.raises(Exception) as exc:
        asyncio.run(reset_user_password("u1", AdminResetPassword(new_password="newpass123"), _=None, db=db))
    assert exc.value.status_code == 404


def test_reset_password_updates_hash():
    from app.services.auth_service import verify_password

    db = AsyncMock()
    user = MagicMock(id="u1", email="admin@example.com", role="admin", created_at=None)
    user.name = "管理员"
    user.password_hash = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result
    asyncio.run(reset_user_password("u1", AdminResetPassword(new_password="newpass123"), _=None, db=db))
    assert verify_password("newpass123", user.password_hash)
    db.commit.assert_awaited_once()
