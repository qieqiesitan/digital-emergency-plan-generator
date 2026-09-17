"""危化品存量结构化字段测试：新字段存在、旧字段保留、解析函数行为。"""

from app.models.hazardous_chemicals import HazardousChemical
from app.services.chemical_storage_parser import parse_storage_text


def test_new_columns_exist_and_old_is_kept():
    cols = HazardousChemical.__table__.columns
    assert "storage_amount" in cols
    assert "storage_unit" in cols
    assert "max_storage" in cols, "旧字段必须保留，避免破坏既有数据与接口"


def test_parse_common_text_forms():
    assert parse_storage_text("50t") == (50.0, "t")
    assert parse_storage_text("50 吨") == (50.0, "t")
    assert parse_storage_text("最大储存量 12.5吨") == (12.5, "t")
    assert parse_storage_text("3000kg") == (3.0, "t")
    assert parse_storage_text("2.5m³") == (2.5, "m³")


def test_parse_unknown_returns_none_instead_of_guessing():
    """解析不出来就返回 None，交人工确认——绝不猜测数值。"""
    assert parse_storage_text("见台账") == (None, None)
    assert parse_storage_text("") == (None, None)
    assert parse_storage_text(None) == (None, None)


def test_migration_sql_keeps_old_column():
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1] / "db_migration_20260917_chemical_storage_numeric.sql"
    ).read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS storage_amount" in sql
    assert "ADD COLUMN IF NOT EXISTS storage_unit" in sql
    assert "DROP COLUMN" not in sql.upper(), "不得删除旧字段 max_storage"
