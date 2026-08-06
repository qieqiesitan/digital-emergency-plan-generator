import os

from app.models.risk_management import RiskObject

SQL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "db_migration_risk_source_consolidation.sql",
)


def test_risk_object_has_legacy_source_id():
    cols = {c.name for c in RiskObject.__table__.columns}
    assert "legacy_source_id" in cols
    legacy_idx = next(
        (i for i in RiskObject.__table__.indexes if i.name == "idx_ro_legacy_source"),
        None,
    )
    assert legacy_idx is not None
    assert [c.name for c in legacy_idx.columns] == ["enterprise_id", "legacy_source_id"]


def test_migration_sql_adds_legacy_source_id():
    with open(SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    assert "ADD COLUMN IF NOT EXISTS legacy_source_id" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_ro_legacy_source" in sql
    assert "ON risk_objects(enterprise_id, legacy_source_id)" in sql
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql
    assert "VARCHAR(64)" in sql
