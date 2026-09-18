"""开票时绑定审批流程（计划缺口补齐）。

计划原文的 `open_ticket` 只写 ticket_type/template_id，从不写 `flow_template_id`，
于是任何票提交时都会在 `_advance_to_first_active_node` 抛"作业票未绑定审批流程"。
这里是该缺口的回归测试：开票必须绑定模板对应的启用流程。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.work_ticket_service import WorkTicketError, open_ticket


def _db_with(codes, flow):
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    code_result = MagicMock()
    code_result.all.return_value = [(c,) for c in codes]

    flow_result = MagicMock()
    flow_result.scalar_one_or_none.return_value = flow

    db.execute = AsyncMock(side_effect=[code_result, flow_result])
    return db


@pytest.mark.asyncio
async def test_open_ticket_binds_active_flow_template():
    flow = MagicMock()
    flow.id = "flow-1"
    db = _db_with(["DHZY-A-20260918-0001"], flow)

    instance = await open_ticket(
        db,
        enterprise_id="ent-1",
        enterprise_code="A",
        ticket_type="DHZY",
        template_id="tpl-1",
    )

    assert instance.flow_template_id == "flow-1"
    assert instance.code.endswith("-0002")


@pytest.mark.asyncio
async def test_open_ticket_rejects_template_without_flow():
    """模板没配流程时趁早报错，不要留下一张永远提交不了的草稿。"""
    db = _db_with([], None)

    with pytest.raises(WorkTicketError) as ei:
        await open_ticket(
            db,
            enterprise_id="ent-1",
            enterprise_code="A",
            ticket_type="DHZY",
            template_id="tpl-1",
        )
    assert "审批流程" in str(ei.value)
