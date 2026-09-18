"""多单位会签：按部门/单位取会签资格人。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.work_ticket_flow import sign_requirement_met
from app.services.work_ticket_service import eligible_users_for_node


def _node(policy="all", role=None, units=None):
    n = MagicMock()
    n.sign_policy = policy
    n.role_code = role
    n.node_key = "countersign"
    n.name = "会签"
    n.countersign_units = units
    return n


def test_node_can_declare_units_instead_of_role():
    """单位会签节点不需要 role_code。"""
    n = _node(units=["水", "电", "汽"])
    assert n.role_code is None
    assert n.countersign_units == ["水", "电", "汽"]


def test_sign_requirement_all_with_units():
    """七个单位都要签，只签三个不能流转。"""
    n = _node(policy="all", units=["水", "电", "汽", "工艺", "设备", "消防", "安全管理"])
    assert sign_requirement_met(
        n,
        signed_users=["u1", "u2", "u3"],
        eligible_users=["u1", "u2", "u3", "u4", "u5", "u6", "u7"],
    ) is False
    assert sign_requirement_met(
        n,
        signed_users=["u1", "u2", "u3", "u4", "u5", "u6", "u7"],
        eligible_users=["u1", "u2", "u3", "u4", "u5", "u6", "u7"],
    ) is True


@pytest.mark.asyncio
async def test_eligible_users_by_units_queries_departments():
    """按单位取人：走组织成员关系，不走 Role。"""
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.all.return_value = [("u1",), ("u2",)]
        return res

    db.execute = execute
    node = _node(units=["水", "电"])
    users = await eligible_users_for_node(db, node)
    assert set(users) == {"u1", "u2"}


@pytest.mark.asyncio
async def test_eligible_users_empty_when_node_has_neither_role_nor_units():
    db = MagicMock()
    db.execute = AsyncMock()
    node = _node(role=None, units=None)
    assert await eligible_users_for_node(db, node) == []
