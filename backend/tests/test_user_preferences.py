"""test_user_preferences.py — 偏好读写与缓存失效。"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.user_preference_service import get_preferences, set_preferences


@pytest.mark.asyncio
async def test_get_preferences_defaults():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    prefs = await get_preferences(db, "u1")
    assert prefs["style_preference"] is None
    assert prefs["detail_level"] is None


@pytest.mark.asyncio
async def test_set_preferences_updates():
    db = AsyncMock()
    db.get.return_value = None
    db.add = MagicMock()
    out = await set_preferences(db, "u1", {"style_preference": "practical"})
    assert out["style_preference"] == "practical"
