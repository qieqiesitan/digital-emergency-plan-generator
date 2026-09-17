-- 20260917 危化品存量结构化：新增数值列并尽力回填，无法解析的留 NULL 人工确认。
-- 旧字段 max_storage 保留不动。

ALTER TABLE hazardous_chemicals
    ADD COLUMN IF NOT EXISTS storage_amount NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS storage_unit VARCHAR(20);

-- 回填：仅处理"数字 + 单位"能明确识别的文本；其余留空等待人工确认。
-- 注意：只回填 storage_amount IS NULL 的行，重复执行不会覆盖人工修正过的值。
DO $$
DECLARE
    rec RECORD;
    m TEXT[];
    val NUMERIC;
    un TEXT;
BEGIN
    FOR rec IN
        SELECT id, max_storage FROM hazardous_chemicals
         WHERE max_storage IS NOT NULL
           AND storage_amount IS NULL
    LOOP
        m := regexp_match(rec.max_storage, '([0-9]+(?:\.[0-9]+)?)\s*(吨|t|千克|公斤|kg)', 'i');
        IF m IS NOT NULL THEN
            val := m[1]::NUMERIC;
            un := lower(m[2]);
            IF un IN ('千克', '公斤', 'kg') THEN
                val := val / 1000;
            END IF;
            UPDATE hazardous_chemicals
               SET storage_amount = val, storage_unit = 't'
             WHERE id = rec.id;
        END IF;
    END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS ix_hc_storage_amount ON hazardous_chemicals (storage_amount);
