"""作业票审批引擎：状态机、会签、条件分支、法定环节保护。"""

from unittest.mock import MagicMock

import pytest

from app.services.work_ticket_flow import (
    FlowError,
    TRANSITIONS,
    can_transition,
    evaluate_condition,
    is_node_active,
    next_node,
    sign_requirement_met,
    validate_node_deletion,
)


def _node(key, order, policy="any", cond=None, statutory=False, role="mgr"):
    n = MagicMock()
    n.node_key = key
    n.sort_order = order
    n.sign_policy = policy
    n.condition_expr = cond
    n.is_statutory = statutory
    n.role_code = role
    n.name = key
    return n


def test_transitions_table_shape():
    assert set(TRANSITIONS) >= {
        "draft", "submitted", "approving", "approved",
        "rejected", "cancelled", "working", "finished", "closed", "expired",
    }
    assert "approve" in TRANSITIONS["approving"]
    assert "reject" in TRANSITIONS["approving"]


def test_can_transition_allows_legal_action():
    assert can_transition("approving", "approve") is True


def test_can_transition_rejects_illegal_action():
    """已归档的票不能再审批。"""
    assert can_transition("closed", "approve") is False


def test_can_transition_rejects_expired_resume():
    """已过期的票不能直接进入作业中，必须重新开票。"""
    assert can_transition("expired", "start") is False


def test_evaluate_condition_simple_equality():
    assert evaluate_condition("level == 特级", {"level": "特级"}) is True
    assert evaluate_condition("level == 特级", {"level": "一级"}) is False


def test_evaluate_condition_in_operator():
    assert evaluate_condition("level in [特级, 一级]", {"level": "一级"}) is True
    assert evaluate_condition("level in [特级, 一级]", {"level": "二级"}) is False


def test_evaluate_condition_boolean_field():
    assert evaluate_condition("is_cross_dept == true", {"is_cross_dept": True}) is True
    assert evaluate_condition("is_cross_dept == true", {"is_cross_dept": False}) is False


def test_evaluate_condition_empty_means_always_active():
    assert evaluate_condition(None, {}) is True
    assert evaluate_condition("", {}) is True


def test_evaluate_condition_unknown_field_is_false_not_crash():
    """字段不存在时返回 False，不抛异常——流程不能因为少一个字段就崩。"""
    assert evaluate_condition("level == 特级", {}) is False


def test_evaluate_condition_rejects_unsupported_syntax():
    """不支持的语法必须报错，不能静默放行——静默放行等于绕过审批。"""
    with pytest.raises(FlowError):
        evaluate_condition("__import__('os').system('ls')", {"level": "一级"})


def test_is_node_active_uses_condition():
    assert is_node_active(_node("a", 1, cond="level == 一级"), {"level": "一级"}) is True
    assert is_node_active(_node("a", 1, cond="level == 一级"), {"level": "二级"}) is False


def test_sign_requirement_met_any():
    node = _node("a", 1, policy="any")
    assert sign_requirement_met(node, signed_users=["u1"], eligible_users=[]) is True


def test_sign_requirement_met_all_needs_everyone():
    node = _node("a", 1, policy="all")
    assert sign_requirement_met(node, signed_users=["u1"], eligible_users=["u1", "u2"]) is False
    assert sign_requirement_met(node, signed_users=["u1", "u2"], eligible_users=["u1", "u2"]) is True


def test_sign_requirement_met_all_with_no_eligible_users():
    """节点没配人时不能判定为已签，否则审批会被空跳过。"""
    node = _node("a", 1, policy="all")
    assert sign_requirement_met(node, signed_users=[], eligible_users=[]) is False


def test_next_node_skips_inactive_branches():
    nodes = [
        _node("approve_special", 1, cond="level == 特级"),
        _node("approve_first", 2, cond="level == 一级"),
        _node("approve_second", 3, cond="level == 二级"),
    ]
    nxt = next_node(nodes, current_order=0, ctx={"level": "一级"})
    assert nxt.node_key == "approve_first"


def test_next_node_returns_none_when_finished():
    nodes = [_node("approve", 1)]
    assert next_node(nodes, current_order=1, ctx={}) is None


def test_validate_node_deletion_blocks_statutory():
    """法定环节不可删——这是"平台不提供绕过合规的开关"的代码落点。"""
    with pytest.raises(FlowError) as ei:
        validate_node_deletion(_node("approve", 1, statutory=True))
    assert "法定" in str(ei.value)


def test_validate_node_deletion_allows_custom():
    validate_node_deletion(_node("custom", 2, statutory=False))
