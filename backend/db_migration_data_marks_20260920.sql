-- D-3：章节「数据依赖已变更」提示所需的变更标记表 + 应急资源更新时间列。
-- 背景：plan_sections.data_dependencies 早已落库（如 ["risk_sources","emergency_resources"]），
-- 但没有任何消费方，用户改完风险/资源后得不到「章节该重新生成」的提示。
-- 检测口径 = max(依赖域数据变更时间, 章节正文更新时间)：表时间戳覆盖增改，本表覆盖删除。
-- 幂等：可重复执行。
CREATE TABLE IF NOT EXISTS enterprise_data_marks (
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (enterprise_id, domain)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_data_marks_ent
    ON enterprise_data_marks (enterprise_id);

-- 应急资源原表只有 created_at：改了数量/名称无法被「依赖变更」检测到
ALTER TABLE emergency_resources
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
