"""常量迁移 SQL 的结构断言（不连数据库，只校验生成物内容）。"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SQL_PATH = BACKEND / "db_migration_20260917_standard_constants.sql"


def _sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8")


def test_sql_file_exists():
    assert SQL_PATH.exists(), "常量迁移脚本缺失"


def test_creates_four_constant_tables():
    sql = _sql()
    for table in (
        "critical_quantities",
        "hazard_beta_factors",
        "exposure_alpha_factors",
        "major_hazard_levels",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{table}\b", sql), table


def test_table1_has_85_rows():
    sql = _sql()
    rows = re.findall(r"INSERT INTO critical_quantities", sql)
    # 表1 85 条 + 表2 24 条（另有 2 行分组表头不灌）
    assert len(rows) == 109, f"预期 109 行常量，实际 {len(rows)}"


def test_all_inserts_are_idempotent():
    sql = _sql()
    inserts = re.findall(r"INSERT INTO [a-z_]+\s*\([^)]*\)\s*VALUES", sql)
    on_conflicts = re.findall(r"ON CONFLICT \(id\) DO NOTHING", sql)
    assert len(inserts) == len(on_conflicts) > 0


def test_seed_uses_deterministic_uuid5_namespace():
    """种子 id 必须来自固定命名空间，重复生成结果一致。"""
    gen = (BACKEND.parent / "scripts" / "gen_major_hazard_seed_sql.py").read_text(encoding="utf-8")
    assert "NAMESPACE_URL" in gen
    assert "major-hazard/GB18218-2018/" in gen


def test_chemical_names_are_not_corrupted():
    """防回归：序号 13 的煤气含下标 ₂/₄，序号 6 碳酰氯临界量 0.3。"""
    sql = _sql()
    assert "H₂" in sql and "CH₄" in sql
    assert "'碳酰氯'" in sql and "0.3" in sql
