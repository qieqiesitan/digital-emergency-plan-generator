 -- 风险管理功能全面重构 DDL
 BEGIN;
 CREATE TABLE IF NOT EXISTS risk_assessment_methods (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(), enterprise_id UUID REFERENCES enterprises(id) ON DELETE CASCADE,
     method_type VARCHAR(20) NOT NULL CHECK (method_type IN ('LS','LEC','COAL_LS','DIRECT')),
     name VARCHAR(100) NOT NULL, description TEXT DEFAULT '', config JSONB NOT NULL DEFAULT '{}'::jsonb,
     is_active BOOLEAN NOT NULL DEFAULT true, is_system BOOLEAN NOT NULL DEFAULT false,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ram_enterprise ON risk_assessment_methods(enterprise_id);
 CREATE INDEX idx_ram_type_active ON risk_assessment_methods(method_type, is_active) WHERE is_active = true;
 
 CREATE TABLE IF NOT EXISTS risk_zones (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(), enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
     name VARCHAR(255) NOT NULL, description TEXT DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0,
     floor_plan_polygon JSONB DEFAULT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_rz_enterprise ON risk_zones(enterprise_id);
 
 CREATE TABLE IF NOT EXISTS risk_objects (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(), enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
     zone_id UUID REFERENCES risk_zones(id) ON DELETE SET NULL, name VARCHAR(255) NOT NULL,
     category VARCHAR(100) DEFAULT NULL, location VARCHAR(500) DEFAULT NULL,
     location_x FLOAT DEFAULT NULL, location_y FLOAT DEFAULT NULL, description TEXT DEFAULT '',
     image_url VARCHAR(500) DEFAULT NULL, is_risk_point BOOLEAN NOT NULL DEFAULT false,
     sort_order INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ro_enterprise ON risk_objects(enterprise_id);
 CREATE INDEX idx_ro_zone ON risk_objects(zone_id);
 
 CREATE TABLE IF NOT EXISTS risk_units (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(), object_id UUID NOT NULL REFERENCES risk_objects(id) ON DELETE CASCADE,
     name VARCHAR(255) NOT NULL, unit_type VARCHAR(50) DEFAULT NULL, description TEXT DEFAULT '',
     location VARCHAR(500) DEFAULT NULL, sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ru_object ON risk_units(object_id);
 
 CREATE TABLE IF NOT EXISTS risk_events (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(), unit_id UUID REFERENCES risk_units(id) ON DELETE CASCADE,
     object_id UUID REFERENCES risk_objects(id) ON DELETE CASCADE, accident_type VARCHAR(100) NOT NULL,
     description TEXT DEFAULT '', trigger_conditions TEXT DEFAULT '', consequences TEXT DEFAULT '',
     method_type VARCHAR(20) NOT NULL DEFAULT 'LS' CHECK (method_type IN ('LS','LEC','COAL_LS','DIRECT')),
     method_params JSONB NOT NULL DEFAULT '{}'::jsonb, risk_level VARCHAR(20) DEFAULT NULL,
     risk_score VARCHAR(50) DEFAULT NULL, sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     CONSTRAINT ck_event_parent CHECK ((unit_id IS NOT NULL AND object_id IS NULL) OR (unit_id IS NULL AND object_id IS NOT NULL))
 );
 CREATE INDEX idx_re_unit ON risk_events(unit_id);
 CREATE INDEX idx_re_object ON risk_events(object_id);
 CREATE INDEX idx_re_risk_level ON risk_events(risk_level);
 
 CREATE TABLE IF NOT EXISTS risk_measures (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(), event_id UUID NOT NULL REFERENCES risk_events(id) ON DELETE CASCADE,
     measure_category VARCHAR(50) NOT NULL CHECK (measure_category IN ('engineering','management','ppe','emergency')),
     measure_type VARCHAR(100) DEFAULT NULL, description TEXT NOT NULL,
     responsible_person VARCHAR(100) DEFAULT NULL, deadline DATE DEFAULT NULL,
     check_items JSONB DEFAULT '[]'::jsonb, status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','implemented','expired')),
     sort_order INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_rm_event ON risk_measures(event_id);
 
 ALTER TABLE risk_sources ADD COLUMN IF NOT EXISTS migrated BOOLEAN NOT NULL DEFAULT false;
 ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS risk_method_config JSONB DEFAULT '{}'::jsonb;
 COMMIT;
