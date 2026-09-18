"""成员任职服务：一人多岗的唯一写入口。

约定：`enterprise_members.org_node_id` 始终等于 `member_positions` 中 `is_primary` 的那条，
由本模块在每次写入后同步，供只认主岗的既有消费方（隐患报表部门列等）继续工作。
"""

from typing import Iterable, Optional

from sqlalchemy import text


async def sync_member_positions(
    db,
    member,
    primary_node_id: Optional[str],
    extra_node_ids: Optional[Iterable[str]] = None,
) -> None:
    """整体替换某成员的任职：primary 为主岗，extra 为兼岗（自动去重、去主岗重复）。"""
    await db.execute(
        text("DELETE FROM member_positions WHERE member_id = :member_id"),
        {"member_id": member.id},
    )
    ordered: list[tuple[str, bool]] = []
    if primary_node_id:
        ordered.append((primary_node_id, True))
    seen = {primary_node_id} if primary_node_id else set()
    for node_id in extra_node_ids or []:
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        ordered.append((node_id, False))
    for node_id, is_primary in ordered:
        await db.execute(
            text(
                "INSERT INTO member_positions (enterprise_id, member_id, org_node_id, is_primary) "
                "VALUES (:ent, :member_id, :node, :primary)"
            ),
            {
                "member_id": member.id,
                "ent": member.enterprise_id,
                "node": node_id,
                "primary": is_primary,
            },
        )
    member.org_node_id = primary_node_id


async def sync_member_primary_node(db, member, node_id: Optional[str]) -> None:
    """仅设置主岗（清空兼岗）：用于只改主岗、不涉及兼岗列表的场景。"""
    await sync_member_positions(db, member, node_id)


async def positions_by_member(
    db, enterprise_id: str, member_ids: list[str]
) -> dict[str, list[dict]]:
    """批量取任职并按 member_id 分组，供列表接口一次查询避免 N+1。"""
    if not member_ids:
        return {}
    rows = (
        await db.execute(
            text(
                "SELECT member_id, org_node_id, is_primary FROM member_positions "
                "WHERE enterprise_id = :ent AND member_id = ANY(:ids) "
                "ORDER BY is_primary DESC, created_at"
            ),
            {"ent": enterprise_id, "ids": [str(m) for m in member_ids]},
        )
    ).all()
    out: dict[str, list[dict]] = {}
    for member_id, org_node_id, is_primary in rows:
        out.setdefault(str(member_id), []).append(
            {"org_node_id": org_node_id, "is_primary": bool(is_primary)}
        )
    return out
