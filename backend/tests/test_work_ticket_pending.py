"""作业票「我的待办」筛选：按当前节点可签人 + 是否已签收窄（2026-09-18 补）。

背景：前端审批工作台原先只能按"本企业 + 审批中"列出全部票据，法定审批人（非企业主）
既进不来（企业归属校验 404），也不存在"轮到我签"的口径。这两个函数是那条链路的
核心判定，用假 session 钉住语义。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import work_ticket_service as wts


def _inst(instance_id: str, *, node: str = "approve") -> SimpleNamespace:
    return SimpleNamespace(
        id=instance_id,
        status="approving",
        current_node_key=node,
        flow_template_id="flow-1",
        enterprise_id="ent-1",
    )


def _scalars_result(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _rows_result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_pending_filters_by_eligibility_and_signed(monkeypatch):
    node = SimpleNamespace(flow_template_id="flow-1", node_key="approve", sign_policy="all")
    mine = _inst("t-mine")
    signed_already = _inst("t-signed")
    # 该票当前节点是另一个节点（不在节点查询结果里）→ 不轮到任何人签，必须被过滤
    other_node = _inst("t-other", node="approve2")
    draft = SimpleNamespace(
        id="t-draft",
        status="draft",
        current_node_key=None,
        flow_template_id="flow-1",
        enterprise_id="ent-1",
    )

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalars_result([node]),  # 节点查询
            _rows_result([("t-signed", "approve", "u-1")]),  # 当前节点已签记录
        ]
    )

    async def _eligible(_db, _node, *, enterprise_id=None):
        return ["u-1", "u-2"]

    monkeypatch.setattr(wts, "eligible_users_for_node", _eligible)

    pending = await wts.tickets_pending_for_user(
        db,
        [mine, signed_already, other_node, draft],
        user_id="u-1",
        enterprise_id="ent-1",
    )
    assert [t.id for t in pending] == ["t-mine"]

    # u-2 也在这个节点里，但没人签过 → 两人都应看到
    db.execute = AsyncMock(
        side_effect=[_scalars_result([node]), _rows_result([])]
    )
    pending_u2 = await wts.tickets_pending_for_user(
        db, [mine, signed_already], user_id="u-2", enterprise_id="ent-1"
    )
    assert [t.id for t in pending_u2] == ["t-mine", "t-signed"]


@pytest.mark.asyncio
async def test_pending_empty_without_user_id(monkeypatch):
    node = SimpleNamespace(flow_template_id="flow-1", node_key="approve", sign_policy="any")
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalars_result([node])])

    async def _eligible(_db, _node, *, enterprise_id=None):
        return ["u-1"]

    monkeypatch.setattr(wts, "eligible_users_for_node", _eligible)
    assert await wts.tickets_pending_for_user(
        db, [_inst("t-1")], user_id=None, enterprise_id="ent-1"
    ) == []


@pytest.mark.asyncio
async def test_member_can_view_when_signed_before(monkeypatch):
    """已签过但当前节点不轮到自己时，仍可回看/打印自己签过的票。"""
    node = SimpleNamespace(flow_template_id="flow-1", node_key="approve", sign_policy="all")
    instance = _inst("t-1")

    async def _eligible(_db, _node, *, enterprise_id=None):
        return ["u-9"]  # 当前节点轮到别人

    monkeypatch.setattr(wts, "eligible_users_for_node", _eligible)

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalars_result([node]),  # 节点查询（pending 判定）
            _rows_result([]),  # 当前节点已签记录（不含 u-1）
            _scalar_result("rec-1"),  # 历史签署记录命中
        ]
    )
    assert await wts.member_can_view_ticket(
        db, instance, user_id="u-1", enterprise_id="ent-1"
    ) is True

    db.execute = AsyncMock(
        side_effect=[
            _scalars_result([node]),
            _rows_result([]),
            _scalar_result(None),  # 既不是可签人，也没签过
        ]
    )
    assert await wts.member_can_view_ticket(
        db, instance, user_id="u-3", enterprise_id="ent-1"
    ) is False
