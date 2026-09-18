"""作业票模板层表结构断言。"""

import re
from pathlib import Path

from app.models.work_ticket import (
    WorkTicketFlowNode,
    WorkTicketFlowTemplate,
    WorkTicketTemplate,
    WorkTicketTemplateField,
    WorkTicketTemplateMeasure,
)

BACKEND = Path(__file__).resolve().parents[1]
SQL = (BACKEND / "db_migration_20260917_work_ticket.sql").read_text(encoding="utf-8")


def test_tablenames():
    assert WorkTicketTemplate.__tablename__ == "work_ticket_templates"
    assert WorkTicketTemplateField.__tablename__ == "work_ticket_template_fields"
    assert WorkTicketTemplateMeasure.__tablename__ == "work_ticket_template_measures"
    assert WorkTicketFlowTemplate.__tablename__ == "work_ticket_flow_templates"
    assert WorkTicketFlowNode.__tablename__ == "work_ticket_flow_nodes"


def test_flow_node_has_statutory_flag():
    """法定环节标记是"可加不可删"约束的落点，不能省。"""
    cols = WorkTicketFlowNode.__table__.columns
    assert "is_statutory" in cols
    assert cols["is_statutory"].nullable is False
    assert cols["sign_policy"].nullable is False


def test_measure_has_article_anchor():
    """每条安全措施必须能追溯到标准条款——这是本平台的差异化能力。"""
    cols = WorkTicketTemplateMeasure.__table__.columns
    assert "article_anchor" in cols
    assert cols["article_anchor"].nullable is False
    assert cols["measure_text"].nullable is False


def test_migration_creates_five_tables():
    for t in (
        "work_ticket_templates",
        "work_ticket_template_fields",
        "work_ticket_template_measures",
        "work_ticket_flow_templates",
        "work_ticket_flow_nodes",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{t}\b", SQL), t


def test_migration_has_node_order_unique():
    """同一流程内节点顺序必须唯一，否则审批链会出现并列。"""
    assert re.search(r"UNIQUE\s*\(flow_template_id,\s*sort_order\s*\)", SQL, re.I)


from app.models.work_ticket import (
    WorkTicketAuditLog,
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketNodeRecord,
    WorkTicketPrintSnapshot,
)


def test_instance_tablenames():
    assert WorkTicketInstance.__tablename__ == "work_ticket_instances"
    assert WorkTicketNodeRecord.__tablename__ == "work_ticket_node_records"
    assert WorkTicketGasTest.__tablename__ == "work_ticket_gas_tests"
    assert WorkTicketAuditLog.__tablename__ == "work_ticket_audit_logs"
    assert WorkTicketPrintSnapshot.__tablename__ == "work_ticket_print_snapshots"


def test_instance_has_level_for_condition_branching():
    """level 必须是独立列——审批条件分支依赖它，藏在 JSONB 里搜不动。"""
    cols = WorkTicketInstance.__table__.columns
    assert "level" in cols
    assert "current_order" in cols
    assert "valid_to" in cols
    assert cols["status"].nullable is False


def test_instance_enterprise_code_unique():
    names = {c.name for c in WorkTicketInstance.__table__.constraints if hasattr(c, "name")}
    assert "uq_wti_ent_code" in names


def test_gas_test_requires_sampled_at():
    cols = WorkTicketGasTest.__table__.columns
    assert cols["sampled_at"].nullable is False


def test_print_snapshot_has_hash_and_version():
    cols = WorkTicketPrintSnapshot.__table__.columns
    assert cols["content_hash"].nullable is False
    assert cols["snapshot"].nullable is False


def test_migration_creates_instance_tables():
    for t in (
        "work_ticket_instances",
        "work_ticket_node_records",
        "work_ticket_gas_tests",
        "work_ticket_audit_logs",
        "work_ticket_print_snapshots",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{t}\b", SQL), t


def test_migration_indexes_valid_to():
    """有效期到期扫描要走索引，否则票据一多调度器就慢。"""
    assert re.search(r"INDEX[^\n]*work_ticket_instances\s*\(valid_to\)", SQL, re.I)
