import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.ai_config_service import get_system_ai_config


def test_get_system_ai_config_returns_none_when_missing():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    result = asyncio.run(get_system_ai_config(db))
    assert result is None


def test_get_system_ai_config_filters_user_id_is_null():
    db = AsyncMock()
    cfg = MagicMock()
    db.execute.return_value = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = cfg
    result = asyncio.run(get_system_ai_config(db))
    assert result is cfg
    call_kwargs = db.execute.call_args
    sql = str(call_kwargs.args[0])
    assert "user_id IS NULL" in sql or "user_id IS" in sql


def test_risk_ai_get_config_raises_when_system_missing():
    from app.services.risk_ai_service import _get_ai_config
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(Exception) as exc:
        asyncio.run(_get_ai_config("any-user", db))
    assert exc.value.status_code == 400
