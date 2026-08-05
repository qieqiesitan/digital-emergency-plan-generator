from app.models.enterprise import EnterpriseFloor
from app.models.risk_management import RiskZone, RiskObject


def test_enterprise_floor_columns():
    cols = {c.name for c in EnterpriseFloor.__table__.columns}
    assert {"enterprise_id", "name", "sort_order", "floor_plan_url", "canvas_width", "canvas_height", "canvas_texts", "is_default"} <= cols


def test_risk_floor_columns():
    zone_cols = {c.name for c in RiskZone.__table__.columns}
    object_cols = {c.name for c in RiskObject.__table__.columns}
    assert "floor_id" in zone_cols
    assert "floor_id" in object_cols


def test_zone_object_fk_restrict():
    fk = next(f for f in RiskObject.__table__.foreign_keys if f.parent.name == "zone_id")
    assert fk.ondelete == "RESTRICT"
