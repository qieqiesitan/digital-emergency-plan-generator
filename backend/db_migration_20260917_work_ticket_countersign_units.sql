-- 作业票会签节点增加“会签单位清单”列。
-- 已部署过 v1 模板层的数据库，仅改旧迁移文件不会重跑，故用本增量脚本补齐。

ALTER TABLE work_ticket_flow_nodes
    ADD COLUMN IF NOT EXISTS countersign_units JSONB;
