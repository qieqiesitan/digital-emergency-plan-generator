"""隐患排查治理模型测试（任务 1：迁移 + 模型，TDD）。

覆盖 10 张 hazard_* 表的表名/关键列子集与构造默认值
（status/result/level、photo_urls/rectification_plan、enabled/is_system/items 等）。
"""

from datetime import datetime

from app.models.hazard_management import (
    HazardApproval,
    HazardAuditLog,
    HazardChecklistTemplate,
    HazardInspectionItem,
    HazardInspectionPlan,
    HazardInspectionTask,
    HazardNotification,
    HazardRecord,
    HazardRectification,
    HazardReview,
)


def _col_names(model):
    return {c.name for c in model.__table__.columns}


# ── hazard_inspection_plans ──

def test_hazard_inspection_plan_metadata():
    assert HazardInspectionPlan.__tablename__ == "hazard_inspection_plans"
    assert {
        "id", "enterprise_id", "name", "category", "frequency", "weekdays",
        "zone_ids", "template_id", "responsible_user_id", "ai_suggestion",
        "enabled", "created_at", "updated_at",
    } <= _col_names(HazardInspectionPlan)


def test_hazard_inspection_plan_construct():
    p = HazardInspectionPlan(enterprise_id="e1", name="日常检查", category="daily", frequency="daily")
    assert p.enabled is True
    assert p.zone_ids == []
    assert p.weekdays is None
    assert p.ai_suggestion is None
    assert p.template_id is None
    assert p.responsible_user_id is None


# ── hazard_inspection_tasks ──

def test_hazard_inspection_task_metadata():
    assert HazardInspectionTask.__tablename__ == "hazard_inspection_tasks"
    assert {
        "id", "plan_id", "enterprise_id", "title", "status", "responsible_user_id",
        "due_at", "completed_at", "overdue_notified_at",
    } <= _col_names(HazardInspectionTask)


def test_hazard_inspection_task_construct():
    t = HazardInspectionTask(plan_id="p1", enterprise_id="e1", due_at=datetime(2026, 8, 20))
    assert t.status == "pending"
    assert t.completed_at is None
    assert t.overdue_notified_at is None
    assert t.title is None


# ── hazard_inspection_items ──

def test_hazard_inspection_item_metadata():
    assert HazardInspectionItem.__tablename__ == "hazard_inspection_items"
    assert {
        "id", "task_id", "object_id", "measure_id", "content", "expected_note",
        "result", "remark", "photo_urls",
    } <= _col_names(HazardInspectionItem)


def test_hazard_inspection_item_construct():
    it = HazardInspectionItem(task_id="t1", content="检查灭火器")
    assert it.result == "pending"
    assert it.photo_urls == []
    assert it.remark is None
    assert it.expected_note is None


# ── hazard_records ──

def test_hazard_record_metadata():
    assert HazardRecord.__tablename__ == "hazard_records"
    assert {
        "id", "enterprise_id", "code", "source_type", "source_task_id",
        "source_item_id", "object_id", "measure_id", "title", "description",
        "photo_urls", "location", "hazard_type", "cause_analysis", "level",
        "level_source", "grading_basis", "status", "rectification_plan",
        "deadline", "rectification_user_id", "reviewer_user_id", "created_by",
        "closed_at",
    } <= _col_names(HazardRecord)


def test_hazard_record_construct():
    r = HazardRecord(enterprise_id="e1", code="H-2026-001", source_type="inspection",
                     title="配电箱门缺失", description="配电箱门破损")
    assert r.status == "registered"
    assert r.level is None
    assert r.level_source is None
    assert r.photo_urls == []
    assert r.rectification_plan == {}
    assert r.deadline is None
    assert r.closed_at is None


def test_hazard_record_code_unique_constraint():
    names = {c.name for c in HazardRecord.__table__.constraints}
    assert "uq_hazard_records_ent_code" in names
    constraint = next(c for c in HazardRecord.__table__.constraints if c.name == "uq_hazard_records_ent_code")
    assert [c.name for c in constraint.columns] == ["enterprise_id", "code"]


# ── hazard_rectifications ──

def test_hazard_rectification_metadata():
    assert HazardRectification.__tablename__ == "hazard_rectifications"
    assert {"id", "record_id", "user_id", "content", "evidence", "submitted_at"} <= _col_names(HazardRectification)


def test_hazard_rectification_construct():
    r = HazardRectification(record_id="r1", user_id="u1", content="更换配电箱门")
    assert r.evidence == []
    assert r.submitted_at is None


# ── hazard_reviews ──

def test_hazard_review_metadata():
    assert HazardReview.__tablename__ == "hazard_reviews"
    assert {"id", "record_id", "review_type", "user_id", "result", "comment", "evidence"} <= _col_names(HazardReview)


def test_hazard_review_construct():
    r = HazardReview(record_id="r1", review_type="first_review", user_id="u1", result="pass")
    assert r.comment is None
    assert r.evidence == []


# ── hazard_approvals ──

def test_hazard_approval_metadata():
    assert HazardApproval.__tablename__ == "hazard_approvals"
    assert {"id", "record_id", "user_id", "action", "comment"} <= _col_names(HazardApproval)


def test_hazard_approval_construct():
    a = HazardApproval(record_id="r1", user_id="u1", action="approve")
    assert a.comment is None


# ── hazard_audit_logs ──

def test_hazard_audit_log_metadata():
    assert HazardAuditLog.__tablename__ == "hazard_audit_logs"
    assert {"id", "enterprise_id", "record_id", "user_id", "action", "detail"} <= _col_names(HazardAuditLog)


def test_hazard_audit_log_construct():
    log = HazardAuditLog(enterprise_id="e1", action="create")
    assert log.detail == {}
    assert log.record_id is None


# ── hazard_notifications ──

def test_hazard_notification_metadata():
    assert HazardNotification.__tablename__ == "hazard_notifications"
    assert {"id", "enterprise_id", "user_id", "record_id", "type", "message", "read_at"} <= _col_names(HazardNotification)


def test_hazard_notification_construct():
    n = HazardNotification(enterprise_id="e1", user_id="u1", type="deadline")
    assert n.message is None
    assert n.read_at is None


# ── hazard_checklist_templates ──

def test_hazard_checklist_template_metadata():
    assert HazardChecklistTemplate.__tablename__ == "hazard_checklist_templates"
    assert {"id", "enterprise_id", "name", "category", "items", "is_system", "created_at", "updated_at"} <= _col_names(HazardChecklistTemplate)


def test_hazard_checklist_template_construct():
    tpl = HazardChecklistTemplate(name="日常检查表", category="daily")
    assert tpl.is_system is False
    assert tpl.items == []
    assert tpl.enterprise_id is None
