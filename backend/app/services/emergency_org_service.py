"""应急组织读写：整树覆盖保存 + 展开读取 + 消费方分组格式。

入参 id 由前端生成（可能不是 UUID），落库统一换新 UUID 并重挂 parent_id/role_id；
纯函数（flatten_units / build_groups_for_consumers）与 DB 编排分离，便于单测。
"""

from typing import Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.models.emergency_org import (
    EmergencyOrgAssignment,
    EmergencyOrgRole,
    EmergencyOrgUnit,
)
from app.models.enterprise_org import EnterpriseMember
from app.services.org_tree_validate import validate_emergency_units

# 预置名称 → 旧分组 key（与前端 PRESET_EMERGENCY_GROUPS 一致）
GROUP_KEY_BY_NAME = {
    "应急指挥部": "headquarters",
    "抢险救灾组": "rescue",
    "疏散引导组": "evacuation",
    "医疗救护组": "medical",
    "通讯联络组": "communication",
    "后勤保障组": "logistics",
}

# 角色名 → 旧成员 role 码
ROLE_CODE_BY_NAME = {
    "总指挥": "chief",
    "副总指挥": "deputy",
    "组长": "leader",
    "副组长": "deputy_leader",
    "组员": "member",
    "成员": "member",
}


def flatten_units(units: Iterable[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """把带 roles/member_ids 的平铺单元拆成三张表的插入行，id 全部重新生成并重挂关系。"""
    unit_list = [u for u in units if isinstance(u, dict)]
    id_map: dict[str, str] = {}
    for ui, u in enumerate(unit_list):
        raw_id = str(u.get("id") or f"__idx_{ui}")
        id_map[raw_id] = str(uuid4())

    unit_rows: list[dict] = []
    role_rows: list[dict] = []
    assignment_rows: list[dict] = []
    for ui, u in enumerate(unit_list):
        raw_id = str(u.get("id") or f"__idx_{ui}")
        unit_id = id_map[raw_id]
        parent_raw = u.get("parent_id")
        unit_rows.append(
            {
                "id": unit_id,
                "parent_id": id_map.get(str(parent_raw)) if parent_raw else None,
                "name": str(u.get("name") or "").strip(),
                "duties": u.get("duties") or None,
                "sort_order": int(u.get("sort_order") if u.get("sort_order") is not None else ui),
            }
        )
        for ri, r in enumerate(u.get("roles") or []):
            if not isinstance(r, dict):
                continue
            role_id = str(uuid4())
            role_rows.append(
                {
                    "id": role_id,
                    "unit_id": unit_id,
                    "name": str(r.get("name") or "").strip(),
                    "duties": r.get("duties") or None,
                    "sort_order": int(
                        r.get("sort_order") if r.get("sort_order") is not None else ri
                    ),
                    "is_required": bool(r.get("is_required")),
                }
            )
            for mi, mid in enumerate(r.get("member_ids") or []):
                assignment_rows.append(
                    {"role_id": role_id, "member_id": str(mid), "sort_order": mi}
                )
    return unit_rows, role_rows, assignment_rows


def build_groups_for_consumers(units: Iterable[dict]) -> list[dict]:
    """应急组织 → 预案侧通用分组格式。

    返回 [{group_name, responsibilities, members:[{name, role, role_name, position, phone,
    email, responsibilities}]}]，与既有「预案生成 / 章节自动填充 / 导出签署页」的输入结构一致
    （旧分组格式分支可直接消费），额外提供 role_name 供签署页把应急角色作为职务展示。
    """
    unit_list = [u for u in units if isinstance(u, dict)]
    groups: list[dict] = []
    for u in unit_list:
        if not u.get("parent_id"):
            continue
        members: list[dict] = []
        for r in u.get("roles") or []:
            if not isinstance(r, dict):
                continue
            role_name = str(r.get("name") or "").strip()
            for m in r.get("members") or []:
                if not isinstance(m, dict) or not m.get("name"):
                    continue
                members.append(
                    {
                        "name": m.get("name"),
                        "role": ROLE_CODE_BY_NAME.get(role_name, "member"),
                        "role_name": role_name,
                        "position": m.get("position") or "",
                        "phone": m.get("phone") or "",
                        "email": m.get("email"),
                        "responsibilities": r.get("duties") or "",
                    }
                )
        groups.append(
            {
                "group_name": str(u.get("name") or "应急小组"),
                "responsibilities": u.get("duties") or "",
                "members": members,
            }
        )
    return groups


def build_legacy_groups(units: Iterable[dict]) -> list[dict]:
    """应急组织 → 旧分组格式（GET /org-structure 兼容视图），字段收敛为历史结构。"""
    return [
        {
            "group_key": GROUP_KEY_BY_NAME.get(g["group_name"], g["group_name"]),
            "group_name": g["group_name"],
            "responsibilities": g["responsibilities"],
            "members": [
                {
                    "name": m["name"],
                    "role": m["role"],
                    "position": m["position"],
                    "phone": m["phone"],
                    "responsibilities": m["responsibilities"],
                }
                for m in g["members"]
            ],
        }
        for g in build_groups_for_consumers(units)
    ]


async def _known_member_ids(db, enterprise_id: str) -> set[str]:
    rows = (
        await db.execute(
            select(EnterpriseMember.id).where(
                EnterpriseMember.enterprise_id == enterprise_id,
                EnterpriseMember.enabled.is_(True),
            )
        )
    ).scalars().all()
    return {str(r) for r in rows}


async def load_emergency_org(db, enterprise_id: str) -> list[dict]:
    """整树读取：平铺 units（按 sort_order）→ 挂 roles → 挂成员简要信息。"""
    unit_rows = (
        await db.execute(
            select(EmergencyOrgUnit)
            .where(EmergencyOrgUnit.enterprise_id == enterprise_id)
            .order_by(EmergencyOrgUnit.sort_order)
        )
    ).scalars().all()
    role_rows = (
        await db.execute(
            select(EmergencyOrgRole)
            .where(EmergencyOrgRole.enterprise_id == enterprise_id)
            .order_by(EmergencyOrgRole.sort_order)
        )
    ).scalars().all()
    assignment_rows = (
        await db.execute(
            select(EmergencyOrgAssignment, EnterpriseMember)
            .join(EnterpriseMember, EnterpriseMember.id == EmergencyOrgAssignment.member_id)
            .where(EmergencyOrgAssignment.enterprise_id == enterprise_id)
            .order_by(EmergencyOrgAssignment.sort_order)
        )
    ).all()

    roles_by_unit: dict[str, list[dict]] = {}
    role_index: dict[str, dict] = {}
    for r in role_rows:
        item = {
            "id": r.id,
            "name": r.name,
            "duties": r.duties,
            "sort_order": r.sort_order,
            "is_required": r.is_required,
            "member_ids": [],
            "members": [],
        }
        role_index[r.id] = item
        roles_by_unit.setdefault(r.unit_id, []).append(item)
    for a, m in assignment_rows:
        role = role_index.get(a.role_id)
        if role is None:
            continue
        role["member_ids"].append(a.member_id)
        role["members"].append(
            {
                "id": m.id,
                "name": m.name,
                "phone": m.phone,
                "position": m.position,
                "email": m.email,
                "org_node_id": m.org_node_id,
            }
        )
    return [
        {
            "id": u.id,
            "parent_id": u.parent_id,
            "name": u.name,
            "duties": u.duties,
            "sort_order": u.sort_order,
            "roles": roles_by_unit.get(u.id, []),
        }
        for u in unit_rows
    ]


async def load_emergency_groups(db, enterprise_id: str) -> list[dict]:
    """预案侧统一入口：加载应急组织并转成消费方分组格式。"""
    return build_groups_for_consumers(await load_emergency_org(db, enterprise_id))


async def save_emergency_org(db, enterprise_id: str, units: list) -> list[dict]:
    """整树覆盖保存：校验 → 清空重建 → 返回新树。校验失败抛 422。"""
    known = await _known_member_ids(db, enterprise_id)
    errors = validate_emergency_units(units, known_member_ids=known)
    if errors:
        raise HTTPException(422, "；".join(errors))
    unit_rows, role_rows, assignment_rows = flatten_units(units)
    await db.execute(
        delete(EmergencyOrgAssignment).where(EmergencyOrgAssignment.enterprise_id == enterprise_id)
    )
    await db.execute(delete(EmergencyOrgRole).where(EmergencyOrgRole.enterprise_id == enterprise_id))
    await db.execute(delete(EmergencyOrgUnit).where(EmergencyOrgUnit.enterprise_id == enterprise_id))
    if unit_rows:
        await db.execute(
            EmergencyOrgUnit.__table__.insert(),
            [{"enterprise_id": enterprise_id, **row} for row in unit_rows],
        )
    if role_rows:
        await db.execute(
            EmergencyOrgRole.__table__.insert(),
            [{"enterprise_id": enterprise_id, **row} for row in role_rows],
        )
    if assignment_rows:
        await db.execute(
            EmergencyOrgAssignment.__table__.insert(),
            [{"enterprise_id": enterprise_id, **row} for row in assignment_rows],
        )
    await db.commit()
    return await load_emergency_org(db, enterprise_id)
