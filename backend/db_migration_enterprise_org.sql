CREATE TABLE IF NOT EXISTS enterprise_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_node_id VARCHAR(64) NULL,
    position VARCHAR(100) NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'member',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (enterprise_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_enterprise_members_org_node ON enterprise_members(org_node_id);
