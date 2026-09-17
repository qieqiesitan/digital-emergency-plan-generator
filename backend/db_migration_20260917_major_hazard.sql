-- 20260917 重大危险源业务表（单元 / 单元品种 / 计算快照 / 档案）
-- 说明：计算快照表只追加不修改；应用层不提供 UPDATE/DELETE 接口。

CREATE TABLE IF NOT EXISTS major_hazard_units (
    id UUID PRIMARY KEY,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    unit_type VARCHAR(20) NOT NULL,
    boundary_desc TEXT,
    floor_id UUID REFERENCES enterprise_floors(id) ON DELETE SET NULL,
    polygon JSONB,
    address VARCHAR(500),
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    department VARCHAR(255),
    responsible_person VARCHAR(100),
    responsible_phone VARCHAR(50),
    risk_object_id UUID REFERENCES risk_objects(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    established_at DATE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_mhu_enterprise_id ON major_hazard_units (enterprise_id);
CREATE INDEX IF NOT EXISTS idx_mhu_enterprise ON major_hazard_units (enterprise_id, is_active);

CREATE TABLE IF NOT EXISTS major_hazard_unit_chemicals (
    id UUID PRIMARY KEY,
    unit_id UUID NOT NULL REFERENCES major_hazard_units(id) ON DELETE CASCADE,
    chemical_id UUID REFERENCES hazardous_chemicals(id) ON DELETE SET NULL,
    chemical_name VARCHAR(500) NOT NULL,
    physical_state VARCHAR(200),
    storage_location VARCHAR(300),
    q_design_max NUMERIC(18, 6) NOT NULL,
    q_actual NUMERIC(18, 6),
    critical_quantity_id UUID REFERENCES critical_quantities(id) ON DELETE SET NULL,
    critical_quantity_t NUMERIC(18, 6) NOT NULL,
    beta NUMERIC(6, 3) NOT NULL,
    beta_source VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_mhuc_unit_id ON major_hazard_unit_chemicals (unit_id);

CREATE TABLE IF NOT EXISTS major_hazard_calculations (
    id UUID PRIMARY KEY,
    unit_id UUID NOT NULL REFERENCES major_hazard_units(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    s_value NUMERIC(18, 6) NOT NULL,
    r_value NUMERIC(18, 6) NOT NULL,
    alpha NUMERIC(4, 2) NOT NULL,
    exposed_population INTEGER NOT NULL,
    is_major_hazard BOOLEAN NOT NULL,
    level VARCHAR(20),
    formula_version VARCHAR(40) NOT NULL,
    inputs_snapshot JSONB NOT NULL,
    calculated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_mhc_unit_seq UNIQUE (unit_id, seq)
);
CREATE INDEX IF NOT EXISTS ix_mhc_unit_id ON major_hazard_calculations (unit_id);

CREATE TABLE IF NOT EXISTS major_hazard_records (
    id UUID PRIMARY KEY,
    unit_id UUID NOT NULL UNIQUE REFERENCES major_hazard_units(id) ON DELETE CASCADE,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    hazard_code VARCHAR(64),
    filing_status VARCHAR(20) NOT NULL DEFAULT '未备案',
    filing_no VARCHAR(100),
    filing_date DATE,
    chief_name VARCHAR(100),
    chief_post VARCHAR(100),
    chief_phone VARCHAR(50),
    tech_name VARCHAR(100),
    tech_post VARCHAR(100),
    tech_phone VARCHAR(50),
    oper_name VARCHAR(100),
    oper_post VARCHAR(100),
    oper_phone VARCHAR(50),
    attachments JSONB NOT NULL DEFAULT '{}'::jsonb,
    completeness JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_mhr_ent_code UNIQUE (enterprise_id, hazard_code)
);
CREATE INDEX IF NOT EXISTS ix_mhr_enterprise_id ON major_hazard_records (enterprise_id);

-- 依据层：任意业务数据挂到法规条文（多态引用，不给每个业务表加外键）
-- 条文原文不冗余存储，实时按 article_anchor 从法规体系取，避免法规修订后引用过期。
CREATE TABLE IF NOT EXISTS evidence_refs (
    id UUID PRIMARY KEY,
    owner_type VARCHAR(40) NOT NULL,
    owner_id UUID NOT NULL,
    regulation_id VARCHAR(64),
    article_anchor VARCHAR(200) NOT NULL,
    relation VARCHAR(20) NOT NULL DEFAULT '依据',
    note TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_evidence_owner_anchor UNIQUE (owner_type, owner_id, article_anchor, relation)
);
CREATE INDEX IF NOT EXISTS idx_evidence_owner ON evidence_refs (owner_type, owner_id);
