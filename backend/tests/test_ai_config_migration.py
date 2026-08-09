def test_migration_sql_has_system_unique_index():
    from pathlib import Path
    sql = Path(__file__).resolve().parents[1] / "db_migration_ai_config_system.sql"
    text = sql.read_text(encoding="utf-8")
    assert "DROP NOT NULL" in text
    assert "ADD COLUMN IF NOT EXISTS is_system" in text
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_configs_system" in text
    assert "user_id IS NULL" in text


def test_migration_sql_backfills_system_config_from_user_idempotently():
    from pathlib import Path
    sql = Path(__file__).resolve().parents[1] / "db_migration_ai_config_system.sql"
    text = sql.read_text(encoding="utf-8")
    assert "INSERT INTO ai_configs" in text
    assert "gen_random_uuid()" in text
    assert "user_id IS NULL AND is_system = TRUE" in text
    assert "NOT EXISTS" in text
    assert "LIMIT 1" in text
