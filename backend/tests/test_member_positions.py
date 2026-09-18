"""成员任职（一人多岗）服务：写入、主岗镜像同步、批量读取（任务 3）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.member_position_service import (
    positions_by_member,
    sync_member_primary_node,
    sync_member_positions,
)


def _member(mid: str, node_id: str | None = None):
    return SimpleNamespace(id=mid, org_node_id=node_id, enterprise_id="e1")


@pytest.mark.asyncio
async def test_sync_member_positions_writes_all_and_mirrors_primary():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    member = _member("m1")
    await sync_member_positions(
        db, member, primary_node_id="n1", extra_node_ids=["n2", "n2", "n1"]
    )
    sql_texts = [str(c.args[0]) for c in db.execute.await_args_list]
    assert any("DELETE FROM member_positions" in s for s in sql_texts)
    insert_calls = [
        c for c in db.execute.await_args_list if "INSERT INTO member_positions" in str(c.args[0])
    ]
    # 兼岗去重后只剩 n2（n2 重复一次、n1 与主岗重复）
    assert len(insert_calls) == 2
    assert insert_calls[0].args[1] == {"member_id": "m1", "ent": "e1", "node": "n1", "primary": True}
    assert insert_calls[1].args[1] == {"member_id": "m1", "ent": "e1", "node": "n2", "primary": False}
    assert member.org_node_id == "n1"


@pytest.mark.asyncio
async def test_sync_member_primary_node_clears_when_none():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    member = _member("m1", node_id="n1")
    await sync_member_primary_node(db, member, None)
    assert member.org_node_id is None
    assert not any(
        "INSERT INTO member_positions" in str(c.args[0]) for c in db.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_positions_for_members_groups_by_member_id():
    db = AsyncMock()
    rows = [("m1", "n1", True), ("m1", "n2", False), ("m2", "n3", True)]
    db.execute.return_value = MagicMock(all=lambda: rows)
    out = await positions_by_member(db, "e1", ["m1", "m2"])
    assert out["m1"] == [
        {"org_node_id": "n1", "is_primary": True},
        {"org_node_id": "n2", "is_primary": False},
    ]
    assert out["m2"] == [{"org_node_id": "n3", "is_primary": True}]


@pytest.mark.asyncio
async def test_positions_for_members_empty_input_skips_query():
    db = AsyncMock()
    assert await positions_by_member(db, "e1", []) == {}
    db.execute.assert_not_called()
