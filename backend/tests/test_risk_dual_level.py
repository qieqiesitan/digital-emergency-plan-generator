import pytest
from pydantic import ValidationError
from app.services.risk_method_engine import validate_dual_level
from app.schemas.risk_management import RiskEventCreate, RiskEventResponse

def test_validate_dual_level_ok():
    validate_dual_level("一般", "重大")  # 不抛异常

def test_validate_dual_level_raises():
    with pytest.raises(ValueError, match="不应高于"):
        validate_dual_level("重大", "一般")

def test_migration_contains_columns():
    sql = open("db_migration_risk_control_enhancement.sql", encoding="utf-8").read()
    assert "inherent_risk_level" in sql
    assert "inherent_risk_score" in sql
    assert "control_level" in sql
    assert "public_risk_token" in sql

def test_risk_event_schemas_have_inherent_fields():
    fields = set(RiskEventCreate.model_fields) | set(RiskEventResponse.model_fields)
    assert {"inherent_risk_level", "inherent_risk_score", "control_level"} <= fields
