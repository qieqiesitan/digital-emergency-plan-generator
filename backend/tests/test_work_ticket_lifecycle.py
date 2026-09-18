"""作业票生命周期推进（开始作业 / 完工 / 归档 / 作废）——2026-09-18 补。

背景：状态机 `TRANSITIONS` 早就定义了 `approved→working→finished→closed`，
但后端没有任何端点驱动这些动作——票批准后永远停在「已批准」，无法完工与归档，
归档留痕（GB 30871 要求至少保存一年）也就无从谈起。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.work_ticket_flow import FlowError, lifecycle_target
from app.services.work_ticket_service import WorkTicketError, transition_ticket


def test_lifecycle_target_mapping_and_unknown_action():
    assert lifecycle_target("start") == "working"
    assert lifecycle_target("finish") == "finished"
    assert lifecycle_target("close") == "closed"
    assert lifecycle_target("cancel") == "cancelled"
    with pytest.raises(FlowError):
        lifecycle_target("approve")  # 审批节点动作不属生命周期


def _db(instance):
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = instance
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _instance(status: str, *, valid_to=None):
    inst = SimpleNamespace(
        id="t1",
        enterprise_id="e1",
        status=status,
        current_node_key="approve",
        current_order=1,
        valid_to=valid_to,
    )
    return inst


@pytest.mark.asyncio
async def test_start_moves_approved_to_working_and_logs():
    inst = _instance("approved")
    db = _db(inst)
    out = await transition_ticket(db, instance_id="t1", action="start", user_id="u1")
    assert out == {"instance_id": "t1", "action": "start", "from_status": "approved",
                   "status": "working"}
    assert inst.status == "working"
    log = db.add.call_args_list[0].args[0]
    assert (log.action, log.from_status, log.to_status) == ("start", "approved", "working")
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_finish_and_close_clear_current_node():
    inst = _instance("working")
    db = _db(inst)
    await transition_ticket(db, instance_id="t1", action="finish", user_id="u1")
    assert inst.status == "finished"
    assert inst.current_node_key is None and inst.current_order == 0

    inst2 = _instance("finished")
    db2 = _db(inst2)
    await transition_ticket(db2, instance_id="t1", action="close", user_id="u1")
    assert inst2.status == "closed"
    assert inst2.current_node_key is None


@pytest.mark.asyncio
async def test_illegal_transition_rejected():
    """草稿不能直接完工；终态不能再作废。"""
    for status, action in (("draft", "finish"), ("closed", "cancel"), ("working", "close")):
        db = _db(_instance(status))
        with pytest.raises(WorkTicketError):
            await transition_ticket(db, instance_id="t1", action=action, user_id="u1")


@pytest.mark.asyncio
async def test_start_after_valid_to_expires_ticket():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    inst = _instance("approved", valid_to=past)
    db = _db(inst)
    with pytest.raises(WorkTicketError) as ei:
        await transition_ticket(db, instance_id="t1", action="start", user_id="u1")
    assert "有效期" in str(ei.value)
    assert inst.status == "expired"
    log = db.add.call_args_list[0].args[0]
    assert (log.action, log.to_status) == ("expire", "expired")


@pytest.mark.asyncio
async def test_missing_ticket_raises():
    db = _db(None)
    with pytest.raises(WorkTicketError):
        await transition_ticket(db, instance_id="nope", action="start", user_id="u1")
