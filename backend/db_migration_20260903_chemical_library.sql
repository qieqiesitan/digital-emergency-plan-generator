-- 2026-09-03 危化品公共库：chemical_library 表 + 企业台账来源列 + 菜单权限补种
-- 幂等：IF NOT EXISTS / ON CONFLICT，可重复执行。

CREATE TABLE IF NOT EXISTS chemical_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    cas_no VARCHAR(50),
    un_no VARCHAR(20),
    physical_state VARCHAR(200),
    flash_point VARCHAR(50),
    explosion_limit VARCHAR(50),
    ignition_temp VARCHAR(50),
    density VARCHAR(50),
    boiling_point VARCHAR(50),
    health_hazard TEXT,
    fire_hazard TEXT,
    leak_response TEXT,
    storage_transport TEXT,
    first_aid TEXT,
    protective_measures TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_chemical_library_cas
    ON chemical_library(cas_no) WHERE cas_no IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chemical_library_name ON chemical_library(name);

ALTER TABLE hazardous_chemicals
    ADD COLUMN IF NOT EXISTS library_id UUID REFERENCES chemical_library(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_hazardous_chemicals_library
    ON hazardous_chemicals(library_id);

INSERT INTO permissions (id, code, name, resource, action, category) VALUES
  (gen_random_uuid(), 'menu:chemical_library', '化学品库管理', 'menu', 'chemical_library', 'menu')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code = 'menu:chemical_library'
WHERE r.code IN ('super_admin', 'admin')
ON CONFLICT DO NOTHING;
