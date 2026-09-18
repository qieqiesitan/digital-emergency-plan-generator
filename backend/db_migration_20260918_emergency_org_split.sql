-- 组织架构与应急组织拆分：应急组织三张表 + 成员任职表。全部幂等，可重复执行。
-- 应急组织 = 应急指挥部/应急小组（units）→ 组内角色（roles）→ 人员指派（assignments）；
-- 成员任职 = 一人多岗（member_positions），enterprise_members.org_node_id 保留为主岗镜像列。

CREATE TABLE IF NOT EXISTS emergency_org_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    parent_id UUID NULL REFERENCES emergency_org_units(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    duties TEXT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_units_ent
    ON emergency_org_units(enterprise_id, parent_id, sort_order);

CREATE TABLE IF NOT EXISTS emergency_org_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    unit_id UUID NOT NULL REFERENCES emergency_org_units(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    duties TEXT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_roles_unit
    ON emergency_org_roles(unit_id, sort_order);

CREATE TABLE IF NOT EXISTS emergency_org_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES emergency_org_roles(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES enterprise_members(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (role_id, member_id)
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_assignments_role
    ON emergency_org_assignments(role_id);
CREATE INDEX IF NOT EXISTS idx_emergency_org_assignments_member
    ON emergency_org_assignments(member_id);

CREATE TABLE IF NOT EXISTS member_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES enterprise_members(id) ON DELETE CASCADE,
    org_node_id VARCHAR(64) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (member_id, org_node_id)
);
-- member_id / org_node_id 的单列索引由 ORM 的 index=True 建（ix_member_positions_member_id、
-- ix_member_positions_org_node_id），此处不再重复建，避免同列双索引。
CREATE UNIQUE INDEX IF NOT EXISTS uq_member_positions_primary
    ON member_positions(member_id) WHERE is_primary;
