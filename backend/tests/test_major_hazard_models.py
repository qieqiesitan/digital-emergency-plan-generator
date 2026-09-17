"""常量表 ORM 结构断言。"""

from app.models.standard_constants import (
    CriticalQuantity,
    ExposureAlphaFactor,
    HazardBetaFactor,
    MajorHazardLevel,
)


def test_critical_quantity_table_shape():
    assert CriticalQuantity.__tablename__ == "critical_quantities"
    cols = CriticalQuantity.__table__.columns
    for name in ("id", "standard", "table_no", "chemical_name", "critical_t"):
        assert name in cols, name
    assert cols["standard"].nullable is False
    assert cols["chemical_name"].nullable is False
    assert cols["critical_t"].nullable is True  # 表2 的 J/W 分组行为 NULL


def test_beta_factor_table_shape():
    assert HazardBetaFactor.__tablename__ == "hazard_beta_factors"
    cols = HazardBetaFactor.__table__.columns
    assert cols["beta"].nullable is False


def test_alpha_factor_table_shape():
    assert ExposureAlphaFactor.__tablename__ == "exposure_alpha_factors"
    cols = ExposureAlphaFactor.__table__.columns
    assert cols["label"].nullable is False
    assert cols["population_min"].nullable is False
    assert cols["population_max"].nullable is True  # "100人以上" 无上界


def test_level_table_shape():
    assert MajorHazardLevel.__tablename__ == "major_hazard_levels"
    cols = MajorHazardLevel.__table__.columns
    assert cols["level_name"].nullable is False
    assert cols["r_expression"].nullable is False


# --- 任务 4：业务模型 ---

import re as _re
from pathlib import Path as _Path

from app.models.major_hazard import (
    MajorHazardCalculation,
    MajorHazardRecord,
    MajorHazardUnit,
    MajorHazardUnitChemical,
)


def _migration_sql() -> str:
    return (
        _Path(__file__).resolve().parents[1] / "db_migration_20260917_major_hazard.sql"
    ).read_text(encoding="utf-8")


def test_unit_table_shape():
    assert MajorHazardUnit.__tablename__ == "major_hazard_units"
    cols = MajorHazardUnit.__table__.columns
    assert cols["enterprise_id"].nullable is False
    assert cols["name"].nullable is False
    assert cols["unit_type"].nullable is False
    for name in ("floor_id", "polygon", "risk_object_id", "responsible_person"):
        assert name in cols, name


def test_unit_chemical_table_shape():
    assert MajorHazardUnitChemical.__tablename__ == "major_hazard_unit_chemicals"
    cols = MajorHazardUnitChemical.__table__.columns
    assert cols["unit_id"].nullable is False
    assert cols["q_design_max"].nullable is False
    assert cols["critical_quantity_t"].nullable is False
    assert cols["beta"].nullable is False
    assert cols["beta_source"].nullable is False


def test_calculation_snapshot_table_shape():
    assert MajorHazardCalculation.__tablename__ == "major_hazard_calculations"
    cols = MajorHazardCalculation.__table__.columns
    for name in (
        "unit_id",
        "seq",
        "s_value",
        "r_value",
        "alpha",
        "exposed_population",
        "is_major_hazard",
        "level",
        "formula_version",
        "inputs_snapshot",
    ):
        assert name in cols, name
    assert cols["inputs_snapshot"].nullable is False
    assert cols["level"].nullable is True  # 不构成重大危险源时无级别


def test_record_table_shape():
    assert MajorHazardRecord.__tablename__ == "major_hazard_records"
    cols = MajorHazardRecord.__table__.columns
    for name in ("unit_id", "hazard_code", "filing_status"):
        assert name in cols, name
    for prefix in ("chief", "tech", "oper"):
        for suffix in ("name", "post", "phone"):
            assert f"{prefix}_{suffix}" in cols, f"{prefix}_{suffix}"


def test_migration_sql_declares_all_tables():
    sql = _migration_sql()
    for table in (
        "major_hazard_units",
        "major_hazard_unit_chemicals",
        "major_hazard_calculations",
        "major_hazard_records",
    ):
        assert _re.search(rf"CREATE TABLE IF NOT EXISTS\s+{table}\b", sql), table


def test_migration_has_no_update_or_delete_on_snapshots():
    """快照表只允许 INSERT/SELECT——迁移脚本不得出现对它的 UPDATE/DELETE。"""
    upper = _migration_sql().upper()
    assert "UPDATE MAJOR_HAZARD_CALCULATIONS" not in upper
    assert "DELETE FROM MAJOR_HAZARD_CALCULATIONS" not in upper
