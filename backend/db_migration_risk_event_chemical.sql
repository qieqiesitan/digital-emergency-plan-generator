-- 风险事件关联危化品（可空，删除化学品时置空）
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS chemical_id UUID REFERENCES hazardous_chemicals(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_risk_events_chemical ON risk_events(chemical_id);
