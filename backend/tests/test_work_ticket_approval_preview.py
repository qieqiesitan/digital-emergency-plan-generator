"""开票前审批链预检：能提前发现「本节点无人可审批」。

背景（2026-09-23 用户实测）：特级动火要求「主管领导」审批，
而企业组织架构里没有同名节点 → 票提交后卡在审批中、不在任何人待办里，提交前毫无提示。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import work_ticket_service as wts


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def all(self):
        return self._items


def _node(node_key: str, name: str, role_code: str | None = None, units=None):
    node = MagicMock()
    node.node_key = node_key
    node.name = name
    node.role_code = role_code
    node.countersign_units = units
    node.condition_expr = None
    node.is_statutory = True
    return node


def _flow():
    flow = MagicMock()
    flow.id = "flow-1"
    return flow


@pytest.mark.asyncio
async def test_returns_empty_when_no_flow(monkeypatch):
    async def handler(stmt, *a, **k):
        return _Result([])

    db = MagicMock()
    db.execute = AsyncMock(side_effect=handler)
    assert await wts.preview_approval_chain(db, enterprise_id="e1", template_id="t1") == []


@pytest.mark.asyncio
async def test_marks_node_without_eligible_users(monkeypatch):
    """没有匹配到审批人的节点必须被标出来（eligible_count = 0）。"""
    approve = _node("approve", "主管领导审批", role_code="主管领导")
    calls = {"n": 0}

    async def handler(stmt, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Result([_flow()])   # 流程
        if calls["n"] == 2:
            return _Result([approve])   # 节点
        return _Result([])

    db = MagicMock()
    db.execute = AsyncMock(side_effect=handler)

    async def _no_one(_db, _node, *, enterprise_id=None):
        return []

    monkeypatch.setattr(wts, "eligible_users_for_node", _no_one)
    preview = await wts.preview_approval_chain(db, enterprise_id="e1", template_id="t1")
    assert len(preview) == 1
    assert preview[0]["eligible_count"] == 0
    assert preview[0]["role_code"] == "主管领导"
    assert preview[0]["is_statutory"] is True


@pytest.mark.asyncio
async def test_reports_matched_names(monkeypatch):
    approve = _node("approve", "所在基层单位审批", role_code="所在基层单位")
    calls = {"n": 0}

    async def handler(stmt, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Result([_flow()])
        if calls["n"] == 2:
            return _Result([approve])
        return _Result([("张三",), ("李四",)])  # 匹配到的成员姓名

    db = MagicMock()
    db.execute = AsyncMock(side_effect=handler)

    async def _two(_db, _node, *, enterprise_id=None):
        return ["u1", "u2"]

    monkeypatch.setattr(wts, "eligible_users_for_node", _two)
    preview = await wts.preview_approval_chain(db, enterprise_id="e1", template_id="t1")
    assert preview[0]["eligible_count"] == 2
    assert preview[0]["eligible_names"] == ["张三", "李四"]


@pytest.mark.asyncio
async def test_countersign_node_exposes_units(monkeypatch):
    """会签节点要把会签单位带出来，前端才能说清"缺哪些单位的人"。"""
    countersign = _node("countersign", "涉及单位会签", units=["水", "电", "消防"])
    calls = {"n": 0}

    async def handler(stmt, *a, **k):
        calls["n"] += 1
        return _Result([_flow()]) if calls["n"] == 1 else _Result([countersign])

    db = MagicMock()
    db.execute = AsyncMock(side_effect=handler)

    async def _none(_db, _node, *, enterprise_id=None):
        return []

    monkeypatch.setattr(wts, "eligible_users_for_node", _none)
    preview = await wts.preview_approval_chain(db, enterprise_id="e1", template_id="t1")
    assert preview[0]["countersign_units"] == ["水", "电", "消防"]
    assert preview[0]["eligible_count"] == 0
