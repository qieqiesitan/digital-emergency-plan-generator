"""按能力选模型：命中覆盖用覆盖，未命中回落系统级。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai_config_service import apply_capability_override, get_ai_config_for

BACKEND = Path(__file__).resolve().parents[1]
SQL = (BACKEND / "db_migration_20260917_ai_config_capability.sql").read_text(encoding="utf-8")


def _cfg(model="big-model", overrides=None):
    c = MagicMock()
    c.model_name = model
    c.capability_overrides = overrides or {}
    return c


def test_apply_capability_override_replaces_model():
    cfg = _cfg(model="big-model", overrides={"extract": {"model": "small-model"}})
    out = apply_capability_override(cfg, "extract")
    assert out["model"] == "small-model"
    assert out["base_config"] is cfg


def test_apply_capability_override_falls_back():
    """未配置的能力回落系统级模型，不报错。"""
    cfg = _cfg(model="big-model", overrides={})
    out = apply_capability_override(cfg, "report")
    assert out["model"] == "big-model"


def test_apply_capability_override_ignores_unknown_keys():
    """覆盖里只认白名单键。

    历史教训 B19：客户端参数混入请求体会被严格 API 返回 400。
    配置里塞进来的任意键更不能透传。
    """
    cfg = _cfg(overrides={"extract": {"model": "s", "max_retries": 9, "evil": 1}})
    out = apply_capability_override(cfg, "extract")
    assert out["model"] == "s"
    assert "evil" not in out
    assert "max_retries" not in out


def test_apply_capability_override_ignores_none_values():
    """覆盖里显式为 None 的值不应覆盖系统级配置。"""
    cfg = _cfg(model="big", overrides={"extract": {"model": None}})
    out = apply_capability_override(cfg, "extract")
    assert out["model"] == "big"


def test_apply_capability_override_handles_missing_attr():
    """老数据没有该字段时不能炸。"""
    cfg = MagicMock(spec=["model_name"])
    cfg.model_name = "only-model"
    out = apply_capability_override(cfg, "extract")
    assert out["model"] == "only-model"


@pytest.mark.asyncio
async def test_get_ai_config_for_returns_none_when_missing():
    db = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    assert await get_ai_config_for(db, "extract") is None


def test_migration_adds_column():
    assert "capability_overrides" in SQL
    assert "ADD COLUMN IF NOT EXISTS" in SQL
    assert "ai_configs" in SQL
