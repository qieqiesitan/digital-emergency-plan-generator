"""test_workflow_tables.py — workflow 模型映射。"""
from app.services.workflow.models import WorkflowRun, WorkflowRunStep


def test_workflow_run_columns():
    cols = {c.name for c in WorkflowRun.__table__.columns}
    assert {"id", "user_id", "workflow_name", "params", "status",
            "current_step", "created_at", "updated_at"} <= cols


def test_workflow_step_columns():
    cols = {c.name for c in WorkflowRunStep.__table__.columns}
    assert {"run_id", "step_name", "status", "result", "retry_count", "error"} <= cols
