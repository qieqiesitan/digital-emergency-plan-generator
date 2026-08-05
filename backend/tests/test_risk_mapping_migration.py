import os
import re

from app.models.enterprise import EnterpriseFloor
from app.models.risk_management import RiskZone, RiskObject

SQL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "db_migration_risk_mapping_workbench.sql",
)


def _normalized_sql() -> str:
    """Read the workbench migration SQL with whitespace collapsed for robust assertions."""
    with open(SQL_PATH, encoding="utf-8") as f:
        return re.sub(r"\s+", " ", f.read())


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


def test_floor_id_nullability():
    zone_floor_id = RiskZone.__table__.c.floor_id
    object_floor_id = RiskObject.__table__.c.floor_id
    assert zone_floor_id.nullable is False
    assert object_floor_id.nullable is True


def test_migration_creates_enterprise_floors():
    sql = _normalized_sql()
    assert "CREATE TABLE IF NOT EXISTS enterprise_floors" in sql


def test_migration_backfills_default_floors():
    sql = _normalized_sql()
    assert "INSERT INTO enterprise_floors" in sql
    assert "'默认总图'" in sql
    assert "is_default" in sql


def test_migration_backfills_floor_id():
    sql = _normalized_sql()
    assert "UPDATE risk_zones" in sql and "SET floor_id" in sql
    assert "UPDATE risk_objects" in sql and "SET floor_id" in sql


def test_risk_objects_backfill_guards_enterprise():
    sql = _normalized_sql()
    match = re.search(r"UPDATE risk_objects ro.*?;", sql)
    assert match
    stmt = match.group(0)
    assert "rz.enterprise_id = ro.enterprise_id" in stmt
    assert "enterprise_floors" not in stmt


def test_migration_sets_zone_floor_not_null():
    sql = _normalized_sql()
    assert "ALTER TABLE risk_zones ALTER COLUMN floor_id SET NOT NULL" in sql


def test_migration_uses_restrict_foreign_keys():
    sql = _normalized_sql()
    assert "REFERENCES enterprise_floors(id) ON DELETE RESTRICT" in sql
    assert "REFERENCES risk_zones(id) ON DELETE RESTRICT" in sql


def test_zone_fk_replacement_drops_existing_constraint():
    sql = _normalized_sql()
    assert "DROP CONSTRAINT IF EXISTS fk_risk_objects_zone" in sql
    assert "fk_risk_objects_zone" in sql
    assert "ON DELETE RESTRICT" in sql


def test_migration_converts_v2_polygons():
    sql = _normalized_sql()
    assert "'version', 2" in sql
    assert "floor_plan_polygon" in sql
    assert "jsonb_build_object" in sql
