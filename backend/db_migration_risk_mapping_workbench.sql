BEGIN;

CREATE TABLE IF NOT EXISTS enterprise_floors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    floor_plan_url VARCHAR(500),
    description TEXT,
    canvas_width INTEGER,
    canvas_height INTEGER,
    canvas_texts JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_ef_enterprise FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_ef_enterprise ON enterprise_floors(enterprise_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ef_enterprise_name ON enterprise_floors(enterprise_id, name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ef_default_per_enterprise ON enterprise_floors(enterprise_id) WHERE is_default = true;

DO $$
DECLARE fk_name text;
BEGIN
    SELECT conname INTO fk_name
    FROM pg_constraint
    WHERE conrelid = 'enterprise_floors'::regclass
      AND contype = 'f'
      AND confrelid = 'enterprises'::regclass
      AND conname <> 'fk_ef_enterprise';
    IF fk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE enterprise_floors DROP CONSTRAINT %I', fk_name);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_ef_enterprise'
          AND conrelid = 'enterprise_floors'::regclass
    ) THEN
        ALTER TABLE enterprise_floors
            ADD CONSTRAINT fk_ef_enterprise
            FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE RESTRICT;
    END IF;
END $$;

INSERT INTO enterprise_floors (enterprise_id, name, sort_order, floor_plan_url, description, is_default)
SELECT e.id, '默认总图', 0, e.floor_plan_url, '由 enterprises.floor_plan_url 迁移生成', true
FROM enterprises e
WHERE NOT EXISTS (
    SELECT 1 FROM enterprise_floors ef WHERE ef.enterprise_id = e.id AND ef.is_default = true
)
ON CONFLICT (enterprise_id, name) DO UPDATE
SET is_default = true,
    floor_plan_url = EXCLUDED.floor_plan_url,
    description = EXCLUDED.description;

ALTER TABLE risk_zones ADD COLUMN IF NOT EXISTS floor_id UUID;
ALTER TABLE risk_objects ADD COLUMN IF NOT EXISTS floor_id UUID;

UPDATE risk_zones rz
SET floor_id = ef.id
FROM enterprise_floors ef
WHERE ef.enterprise_id = rz.enterprise_id
  AND ef.is_default = true
  AND rz.floor_id IS NULL;

UPDATE risk_objects ro
SET floor_id = COALESCE(rz.floor_id, ef.id)
FROM risk_zones rz, enterprise_floors ef
WHERE rz.id = ro.zone_id
  AND ef.enterprise_id = ro.enterprise_id
  AND ef.is_default = true
  AND ro.floor_id IS NULL;

ALTER TABLE risk_zones ALTER COLUMN floor_id SET NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_risk_zones_floor'
    ) THEN
        ALTER TABLE risk_zones
            ADD CONSTRAINT fk_risk_zones_floor
            FOREIGN KEY (floor_id) REFERENCES enterprise_floors(id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_risk_objects_floor'
    ) THEN
        ALTER TABLE risk_objects
            ADD CONSTRAINT fk_risk_objects_floor
            FOREIGN KEY (floor_id) REFERENCES enterprise_floors(id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
DECLARE fk_name text;
BEGIN
    SELECT conname INTO fk_name
    FROM pg_constraint
    WHERE conrelid = 'risk_objects'::regclass
      AND contype = 'f'
      AND confrelid = 'risk_zones'::regclass
      AND conname <> 'fk_risk_objects_zone';
    IF fk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE risk_objects DROP CONSTRAINT %I', fk_name);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_risk_objects_zone'
          AND conrelid = 'risk_objects'::regclass
    ) THEN
        ALTER TABLE risk_objects
            ADD CONSTRAINT fk_risk_objects_zone
            FOREIGN KEY (zone_id) REFERENCES risk_zones(id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_rz_floor ON risk_zones(floor_id);
CREATE INDEX IF NOT EXISTS idx_ro_floor ON risk_objects(floor_id);

UPDATE risk_zones rz
SET floor_plan_polygon = jsonb_build_object(
    'version', 2,
    'color_source', 'auto',
    'color', NULL::text,
    'polygons', jsonb_build_array(
        jsonb_build_object(
            'id', rz.id::text,
            'label', rz.name,
            'points', rz.floor_plan_polygon->'points'
        )
    )
)
WHERE rz.floor_plan_polygon IS NOT NULL
  AND rz.floor_plan_polygon ? 'points'
  AND NOT (rz.floor_plan_polygon ? 'version');

COMMIT;
