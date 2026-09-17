"""DataHub 表结构与迁移 SQL 断言。"""

import re
from pathlib import Path

from app.models.ingest import (
    FieldMapping,
    IngestItem,
    IngestJob,
    IngestReconciliation,
    IngestSource,
)

BACKEND = Path(__file__).resolve().parents[1]
SQL = (BACKEND / "db_migration_20260917_datahub.sql").read_text(encoding="utf-8")


def test_tablenames():
    assert IngestSource.__tablename__ == "ingest_sources"
    assert FieldMapping.__tablename__ == "field_mappings"
    assert IngestJob.__tablename__ == "ingest_jobs"
    assert IngestItem.__tablename__ == "ingest_items"
    assert IngestReconciliation.__tablename__ == "ingest_reconciliations"


def test_item_required_columns():
    cols = IngestItem.__table__.columns
    for name in ("job_id", "idempotency_key", "raw_payload", "status", "confidence"):
        assert name in cols, name
    assert cols["raw_payload"].nullable is False
    assert cols["status"].nullable is False


def test_source_never_stores_plaintext_secret():
    cols = IngestSource.__table__.columns
    assert "secret_ref" in cols
    for banned in ("secret", "password", "api_key", "token"):
        assert banned not in cols, f"数据源表不得直接存明文密钥字段：{banned}"


def test_migration_creates_five_tables():
    for t in (
        "ingest_sources",
        "field_mappings",
        "ingest_jobs",
        "ingest_items",
        "ingest_reconciliations",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{t}\b", SQL), t


def test_migration_has_unique_idempotency_key():
    """幂等键必须是数据库级唯一约束，不能只靠应用层判断。"""
    assert re.search(r"UNIQUE\s*\(\s*idempotency_key\s*\)", SQL, re.I)


def test_migration_has_no_delete_or_update_on_items():
    upper = SQL.upper()
    assert "DELETE FROM INGEST_ITEMS" not in upper
    assert "UPDATE INGEST_ITEMS SET RAW_PAYLOAD" not in upper
