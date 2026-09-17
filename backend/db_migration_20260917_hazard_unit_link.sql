-- 20260917 隐患可关联重大危险源单元。
-- 可空是刻意的：多数隐患与重大危险源单元无关，强制关联会逼用户乱选。
ALTER TABLE hazard_records
    ADD COLUMN IF NOT EXISTS major_hazard_unit_id UUID
    REFERENCES major_hazard_units(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_hazard_records_mh_unit
    ON hazard_records (major_hazard_unit_id);
