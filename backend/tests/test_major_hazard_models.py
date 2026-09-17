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
