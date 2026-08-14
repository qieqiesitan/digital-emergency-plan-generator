"""隐患排查治理状态机测试（任务 2，TDD）。

覆盖 can_transition 状态流转/权限矩阵（非法动作 409 语义、角色不符、
复查人=整改人 422、严格+重大 close 前必须 second_review），
以及 apply_transition 各动作字段更新（grade 重大→pending_approval、
approve→rectifying、reject→grading、rectify→reviewing、
review pass/fail 分支、close 写 closed_at + audit log）。
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.models.enterprise import Enterprise
from app.models.hazard_management import (
    HazardApproval,
    HazardAuditLog,
    HazardRecord,
    HazardRectification,
    HazardReview,
)
from app.services.hazard_state_machine import (
    ROLE_GATE,
    TRANSITIONS,
    apply_transition,
    can_transition,
)


def _record(status="registered", level=None, reviewer=None, rectifier=None, **kw):
    return HazardRecord(
        id="r1",
        enterprise_id="e1",
        code="H-2026-001",
        source_type="inspection",
        title="配电箱门缺失",
        description="配电箱门破损",
        status=status,
        level=level,
        reviewer_user_id=reviewer,
        rectification_user_id=rectifier,
        **kw,
    )


def _user(uid="u1"):
    return MagicMock(id=uid)


def _enterprise(mode="standard"):
    return Enterprise(id="e1", user_id="u1", name="甲公司", hazard_closure_mode=mode)


def _db():
    return MagicMock()


_PLAN = {
    "goal": "消除隐患",
    "measures": "更换箱门并加锁",
    "budget": "2000元",
    "emergency_measures": "临时隔离警示",
    "acceptance_criteria": "门体完好、锁具正常",
}

_DEADLINE_RULES = {"major": {"days": 15}, "general": {"days": 7}}


# ── Enterprise 企业隐患配置列（迁移已含，ORM 补充） ──

def test_enterprise_hazard_config_columns():
    cols = {c.name for c in Enterprise.__table__.columns}
    assert {"hazard_closure_mode", "hazard_public_token", "hazard_report_token", "hazard_config"} <= cols
    # 列默认与迁移一致：closure_mode 默认 standard、config 默认空 dict
    assert Enterprise.__table__.c.hazard_closure_mode.default.arg == "standard"


def test_enterprise_hazard_config_construct():
    e = Enterprise(id="e1", user_id="u1", name="甲公司", hazard_closure_mode="strict", hazard_config={"x": 1})
    assert e.hazard_closure_mode == "strict"
    assert e.hazard_public_token is None
    assert e.hazard_report_token is None
    assert e.hazard_config == {"x": 1}


# ── 状态流转矩阵（can_transition） ──

def test_transitions_constant_shape():
    """业务矩阵（契约字面 rectify/review 与目标状态名同形错位，已按行为描述修正）。"""
    assert TRANSITIONS == {
        "registered": {"grade"},
        "grading": {"rectify", "pending_approval"},
        "pending_approval": {"rectify"},
        "rectifying": {"rectify"},
        "reviewing": {"close", "review"},
        "second_review": {"close", "review"},
    }
    assert ROLE_GATE == {
        "grade": {"enterprise_admin"},
        "pending_approval": {"enterprise_admin"},
        "rectify": {"rectifier", "enterprise_admin"},
        "review": {"reviewer", "enterprise_admin"},
        "close": {"enterprise_admin"},
    }


def test_each_status_allows_declared_actions():
    """标准模式下每个状态声明的动作均可达（close 不设严格+重大限制）。"""
    for status, actions in TRANSITIONS.items():
        record = _record(
            status=status,
            level="major" if status in ("pending_approval", "second_review") else "general",
            reviewer="u2",
            rectifier="u1",
        )
        for action in actions:
            role = next(iter(ROLE_GATE[action]))
            ok, reason = can_transition(record, action, role, strict_mode=False)
            assert ok, f"{status} -> {action}: {reason}"


def test_illegal_action_rejected():
    """非法动作 409 语义：返回 (False, 非空 reason)。"""
    r = _record(status="registered")
    ok, reason = can_transition(r, "review", "enterprise_admin", strict_mode=False)
    assert ok is False
    assert reason
    assert "registered" in reason


def test_unknown_status_rejected():
    r = _record(status="deleted")
    ok, reason = can_transition(r, "close", "enterprise_admin", strict_mode=False)
    assert ok is False
    assert reason


# ── 权限矩阵（can_transition） ──

def test_role_gate_rejects_wrong_role():
    r = _record(status="registered")
    ok, reason = can_transition(r, "grade", "rectifier", strict_mode=False)
    assert ok is False
    assert "无权" in reason


def test_role_gate_allows_admin_on_review():
    r = _record(status="reviewing", level="general", reviewer="u2", rectifier="u1")
    ok, reason = can_transition(r, "review", "enterprise_admin", strict_mode=False)
    assert ok is True, reason


def test_review_rejects_reviewer_equals_rectifier():
    """复查人=整改人 422 语义。"""
    r = _record(status="reviewing", level="general", reviewer="u1", rectifier="u1")
    ok, reason = can_transition(r, "review", "reviewer", strict_mode=False)
    assert ok is False
    assert "复查人" in reason and "整改人" in reason


def test_review_requires_assigned_reviewer():
    r = _record(status="reviewing", level="general", reviewer=None, rectifier="u1")
    ok, reason = can_transition(r, "review", "reviewer", strict_mode=False)
    assert ok is False
    assert reason


def test_close_strict_major_requires_second_review():
    r = _record(status="reviewing", level="major", reviewer="u2", rectifier="u1")
    ok, reason = can_transition(r, "close", "enterprise_admin", strict_mode=True)
    assert ok is False
    assert "二次复核" in reason


def test_close_strict_major_allowed_after_second_review():
    r = _record(status="second_review", level="major", reviewer="u2", rectifier="u1")
    ok, reason = can_transition(r, "close", "enterprise_admin", strict_mode=True)
    assert ok is True, reason


def test_close_standard_allowed_in_reviewing():
    r = _record(status="reviewing", level="major", reviewer="u2", rectifier="u1")
    ok, reason = can_transition(r, "close", "enterprise_admin", strict_mode=False)
    assert ok is True, reason


def test_close_strict_general_ignores_major_rule():
    r = _record(status="reviewing", level="general", reviewer="u2", rectifier="u1")
    ok, reason = can_transition(r, "close", "enterprise_admin", strict_mode=True)
    assert ok is True, reason


# ── apply_transition：grade ──

@pytest.mark.asyncio
async def test_apply_grade_major_goes_pending_approval():
    r = _record()
    payload = {
        "level": "major",
        "hazard_type": "fire",
        "grading_basis": "依据 A",
        "deadline_rules": _DEADLINE_RULES,
        "rectification_plan": _PLAN,
    }
    out = await apply_transition(_db(), r, "grade", _user(), "enterprise_admin", payload, _enterprise())
    assert out.status == "pending_approval"
    assert out.level == "major"
    assert out.hazard_type == "fire"
    assert out.grading_basis == "依据 A"
    assert out.deadline == date.today() + timedelta(days=15)


@pytest.mark.asyncio
async def test_apply_grade_general_goes_rectifying():
    r = _record()
    payload = {
        "level": "general",
        "hazard_type": "equipment",
        "grading_basis": None,
        "deadline_rules": _DEADLINE_RULES,
    }
    out = await apply_transition(_db(), r, "grade", _user(), "enterprise_admin", payload, _enterprise())
    assert out.status == "rectifying"
    assert out.level == "general"
    assert out.deadline == date.today() + timedelta(days=7)


@pytest.mark.asyncio
async def test_apply_grade_major_requires_plan_and_basis():
    r = _record()
    with pytest.raises(HTTPException) as exc:
        await apply_transition(
            _db(), r, "grade", _user(), "enterprise_admin",
            {"level": "major", "deadline_rules": _DEADLINE_RULES},
            _enterprise(),
        )
    assert exc.value.status_code == 422
    assert exc.value.detail


@pytest.mark.asyncio
async def test_apply_grade_major_requires_grading_basis():
    r = _record()
    with pytest.raises(HTTPException) as exc:
        await apply_transition(
            _db(), r, "grade", _user(), "enterprise_admin",
            {"level": "major", "deadline_rules": _DEADLINE_RULES, "rectification_plan": _PLAN},
            _enterprise(),
        )
    assert exc.value.status_code == 422
    assert "判定依据" in exc.value.detail


@pytest.mark.asyncio
async def test_apply_grade_major_requires_full_plan_keys():
    r = _record()
    payload = {
        "level": "major",
        "grading_basis": "依据 A",
        "deadline_rules": _DEADLINE_RULES,
        "rectification_plan": {"goal": "g"},
    }
    with pytest.raises(HTTPException) as exc:
        await apply_transition(_db(), r, "grade", _user(), "enterprise_admin", payload, _enterprise())
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_apply_pending_approval_action():
    r = _record(status="grading", level="major")
    out = await apply_transition(
        _db(), r, "pending_approval", _user(), "enterprise_admin", {"comment": "挂牌督办"}, _enterprise()
    )
    assert out.status == "pending_approval"


# ── apply_transition：approve / reject ──

@pytest.mark.asyncio
async def test_apply_approve_goes_rectifying_and_writes_approval():
    r = _record(status="pending_approval", level="major")
    db = _db()
    out = await apply_transition(db, r, "approve", _user(), "enterprise_admin", {"comment": "同意挂牌"}, _enterprise())
    assert out.status == "rectifying"
    added = [a.args[0] for a in db.add.call_args_list]
    assert any(isinstance(x, HazardApproval) and x.action == "approve" for x in added)


@pytest.mark.asyncio
async def test_apply_reject_goes_grading():
    r = _record(status="pending_approval", level="major")
    out = await apply_transition(_db(), r, "reject", _user(), "enterprise_admin", {"comment": "材料不足"}, _enterprise())
    assert out.status == "grading"


@pytest.mark.asyncio
async def test_apply_approve_reject_require_pending_approval():
    r = _record(status="grading", level="major")
    with pytest.raises(HTTPException) as exc:
        await apply_transition(_db(), r, "approve", _user(), "enterprise_admin", {}, _enterprise())
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_apply_approve_requires_admin_role():
    r = _record(status="pending_approval", level="major")
    with pytest.raises(HTTPException) as exc:
        await apply_transition(_db(), r, "approve", _user(), "rectifier", {}, _enterprise())
    assert exc.value.status_code == 403


# ── apply_transition：rectify ──

@pytest.mark.asyncio
async def test_apply_rectify_goes_reviewing_and_writes_rectification():
    r = _record(status="rectifying", reviewer="u2")
    db = _db()
    out = await apply_transition(
        db, r, "rectify", _user("u1"), "rectifier",
        {"content": "已更换箱门", "evidence": ["e1.png"]},
        _enterprise(),
    )
    assert out.status == "reviewing"
    assert out.rectification_user_id == "u1"
    added = [a.args[0] for a in db.add.call_args_list]
    rect = next(x for x in added if isinstance(x, HazardRectification))
    assert rect.record_id == "r1"
    assert rect.content == "已更换箱门"
    assert rect.evidence == ["e1.png"]
    assert rect.submitted_at is not None


@pytest.mark.asyncio
async def test_apply_rectify_reviewer_assignable_in_payload():
    r = _record(status="rectifying")
    out = await apply_transition(
        _db(), r, "rectify", _user("u1"), "rectifier",
        {"content": "已更换", "reviewer_user_id": "u2"},
        _enterprise(),
    )
    assert out.status == "reviewing"
    assert out.reviewer_user_id == "u2"


# ── apply_transition：review pass/fail 分支 ──

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("level", "mode", "status", "expected"),
    [
        ("general", "standard", "reviewing", "closed"),
        ("general", "strict", "reviewing", "closed"),
        ("major", "standard", "reviewing", "closed"),
        ("major", "strict", "reviewing", "second_review"),
        ("major", "strict", "second_review", "closed"),
    ],
)
async def test_apply_review_pass_target_matrix(level, mode, status, expected):
    r = _record(status=status, level=level, reviewer="u2", rectifier="u1")
    out = await apply_transition(
        _db(), r, "review", _user("u2"), "reviewer", {"result": "pass", "comment": "合格"},
        _enterprise(mode),
    )
    assert out.status == expected
    if expected == "closed":
        assert out.closed_at is not None
    else:
        assert out.closed_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["reviewing", "second_review"])
async def test_apply_review_fail_returns_rectifying(status):
    r = _record(status=status, level="major", reviewer="u2", rectifier="u1")
    out = await apply_transition(
        _db(), r, "review", _user("u2"), "reviewer",
        {"result": "fail", "comment": "未整改到位"},
        _enterprise("strict"),
    )
    assert out.status == "rectifying"
    assert out.closed_at is None


@pytest.mark.asyncio
async def test_apply_review_writes_review_record():
    r = _record(status="reviewing", level="general", reviewer="u2", rectifier="u1")
    db = _db()
    await apply_transition(
        db, r, "review", _user("u2"), "reviewer",
        {"result": "fail", "comment": "未整改到位", "evidence": ["e2.png"]},
        _enterprise(),
    )
    added = [a.args[0] for a in db.add.call_args_list]
    review = next(x for x in added if isinstance(x, HazardReview))
    assert review.record_id == "r1"
    assert review.user_id == "u2"
    assert review.result == "fail"
    assert review.comment == "未整改到位"
    assert review.evidence == ["e2.png"]


@pytest.mark.asyncio
async def test_apply_review_non_assigned_reviewer_422():
    r = _record(status="reviewing", level="general", reviewer="u2", rectifier="u1")
    with pytest.raises(HTTPException) as exc:
        await apply_transition(
            _db(), r, "review", _user("u9"), "reviewer", {"result": "pass"}, _enterprise()
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_apply_review_admin_can_review_without_reviewer_role():
    r = _record(status="reviewing", level="general", reviewer="u2", rectifier="u1")
    out = await apply_transition(
        _db(), r, "review", _user("u1"), "enterprise_admin", {"result": "pass"}, _enterprise()
    )
    assert out.status == "closed"


@pytest.mark.asyncio
async def test_apply_review_invalid_result_rejected():
    r = _record(status="reviewing", level="general", reviewer="u2", rectifier="u1")
    with pytest.raises(HTTPException) as exc:
        await apply_transition(
            _db(), r, "review", _user("u2"), "reviewer", {"result": "maybe"}, _enterprise()
        )
    assert exc.value.status_code == 422


# ── apply_transition：close ──

@pytest.mark.asyncio
async def test_apply_close_writes_closed_at_and_audit():
    r = _record(status="second_review", level="major", reviewer="u2", rectifier="u1")
    db = _db()
    out = await apply_transition(db, r, "close", _user(), "enterprise_admin", {"comment": "销号"}, _enterprise("strict"))
    assert out.status == "closed"
    assert out.closed_at is not None
    added = [a.args[0] for a in db.add.call_args_list]
    assert any(isinstance(x, HazardReview) and x.review_type == "close" for x in added)
    audit = [x for x in added if isinstance(x, HazardAuditLog)]
    assert audit and audit[-1].action == "close"


@pytest.mark.asyncio
async def test_apply_close_strict_major_before_second_review_409():
    r = _record(status="reviewing", level="major", reviewer="u2", rectifier="u1")
    with pytest.raises(HTTPException) as exc:
        await apply_transition(_db(), r, "close", _user(), "enterprise_admin", {}, _enterprise("strict"))
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_apply_close_illegal_action_409():
    r = _record(status="registered")
    with pytest.raises(HTTPException) as exc:
        await apply_transition(_db(), r, "close", _user(), "enterprise_admin", {}, _enterprise())
    assert exc.value.status_code == 409


# ── audit log ──

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "payload", "from_status"),
    [
        ("grade", {"level": "general", "deadline_rules": _DEADLINE_RULES}, "registered"),
        ("rectify", {"content": "已更换"}, "rectifying"),
        ("review", {"result": "pass"}, "reviewing"),
        ("close", {}, "second_review"),
    ],
)
async def test_every_action_writes_audit_log(action, payload, from_status):
    kwargs = {}
    if from_status == "rectifying":
        kwargs["reviewer"] = "u2"
    if from_status == "reviewing":
        kwargs.update(level="general", reviewer="u2", rectifier="u1")
    if from_status == "second_review":
        kwargs.update(level="major", reviewer="u2", rectifier="u1")
    r = _record(status=from_status, **kwargs)
    db = _db()
    role = "enterprise_admin" if action in ("grade", "close") else ("rectifier" if action == "rectify" else "reviewer")
    await apply_transition(db, r, action, _user("u2" if action == "review" else "u1"), role, payload, _enterprise())
    added = [a.args[0] for a in db.add.call_args_list]
    audit = [x for x in added if isinstance(x, HazardAuditLog)]
    assert audit, f"{action} 未写 audit log"
    assert audit[-1].action == action
    assert audit[-1].enterprise_id == "e1"
    assert audit[-1].record_id == "r1"
    assert audit[-1].detail
