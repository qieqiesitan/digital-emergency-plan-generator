BEGIN;

ALTER TABLE risk_objects
    ADD COLUMN IF NOT EXISTS legacy_source_id VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_ro_legacy_source
    ON risk_objects(enterprise_id, legacy_source_id);

COMMIT;
