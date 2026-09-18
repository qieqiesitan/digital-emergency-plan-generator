"""AI 能力注册表：结构、启停、与调用日志的关联。"""

import re
from pathlib import Path

from app.models.ai_capability import AICapability
from app.services.ai_capability_service import (
    CapabilityError,
    is_capability_enabled,
)

BACKEND = Path(__file__).resolve().parents[1]
SQL = (BACKEND / "db_migration_20260917_ai_capability.sql").read_text(encoding="utf-8")


def test_tablename_and_columns():
    assert AICapability.__tablename__ == "ai_capabilities"
    cols = AICapability.__table__.columns
    for name in (
        "code", "module", "name", "prompt_ref", "model_override",
        "is_enabled", "allow_manual", "description",
    ):
        assert name in cols, name
    assert cols["code"].nullable is False
    assert cols["is_enabled"].nullable is False


def test_migration_creates_table_and_unique_code():
    assert re.search(r"CREATE TABLE IF NOT EXISTS\s+ai_capabilities\b", SQL)
    assert re.search(r"UNIQUE\s*\(\s*code\s*\)", SQL, re.I)


def test_is_capability_enabled_returns_true_when_not_registered():
    """未注册的能力默认启用——注册表是"可管理"，不是"必须注册才能用"，
    否则新加一个 AI 能力忘了注册就会静默失效。"""
    assert is_capability_enabled(None) is True


def test_is_capability_enabled_respects_flag():
    cap = AICapability(code="x", module="m", name="n", is_enabled=False)
    assert is_capability_enabled(cap) is False
    cap.is_enabled = True
    assert is_capability_enabled(cap) is True


def test_capability_error_is_value_error():
    assert issubclass(CapabilityError, ValueError)
