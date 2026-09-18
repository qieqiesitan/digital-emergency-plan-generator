"""把混在 enterprises.org_structure 里的应急组织搬迁到应急组织表，并从公司树中摘除。

支持两种存量形态（可同时存在）：
- tree：含 preset-org-root（或根节点名为「应急组织机构」）的应急子树
- groups：旧分组格式 [{group_key, group_name, members:[{role,name,...}]}]

幂等：搬迁后公司树里已无应急节点、旧分组已清空，重跑即 skipped。
运行（仓库根目录）：
    backend\\.venv\\Scripts\\python.exe backend/scripts/migrate_emergency_org_split.py --dry-run
    backend\\.venv\\Scripts\\python.exe backend/scripts/migrate_emergency_org_split.py --apply
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models.emergency_org import (  # noqa: E402
    EmergencyOrgAssignment,
    EmergencyOrgRole,
    EmergencyOrgUnit,
)
from app.models.enterprise import Enterprise  # noqa: E402
from app.models.enterprise_org import EnterpriseMember  # noqa: E402
# 必须显式导入 users：enterprise_members.user_id / enterprises.user_id 的外键目标，
# 不导入则 flush 时报 NoReferencedTableError（dry-run 不建 ORM 对象所以看不出来）。
from app.models.user import User  # noqa: E402,F401
from app.services.emergency_org_service import flatten_units  # noqa: E402

EMERGENCY_ROOT_NAME = "应急组织机构"
REQUIRED_ROLE_NAMES = {"总指挥", "副总指挥"}
ROLE_NAME_BY_CODE = {"chief": "总指挥", "deputy": "副总指挥", "leader": "组长", "member": "组员"}


def _items(nodes) -> list[dict]:
    return [n for n in (nodes or []) if isinstance(n, dict)]


def _is_group_item(n: dict) -> bool:
    return bool(n.get("group_key") or n.get("group_name"))


def _emergency_root_ids(items: list[dict]) -> set:
    return {
        n.get("id")
        for n in items
        if n.get("id") == "preset-org-root"
        or (n.get("parent_id") in (None, "") and n.get("name") == EMERGENCY_ROOT_NAME)
    }


def classify_shape(nodes: list) -> str:
    """判定存量形态：tree / groups / both / none（none = 纯公司树或空）。"""
    items = _items(nodes)
    has_groups = any(_is_group_item(n) for n in items)
    has_tree = bool(_emergency_root_ids(items))
    if has_groups and has_tree:
        return "both"
    if has_groups:
        return "groups"
    if has_tree:
        return "tree"
    return "none"


def split_tree(nodes: list) -> tuple[list, list]:
    """按应急根节点把组织树切成（应急节点, 公司节点），公司节点保持原顺序与原 parent。"""
    items = _items(nodes)
    emergency_ids = _emergency_root_ids(items)
    changed = True
    while changed:
        changed = False
        for n in items:
            if n.get("id") in emergency_ids or n.get("parent_id") not in emergency_ids:
                continue
            emergency_ids.add(n.get("id"))
            changed = True
    return (
        [n for n in items if n.get("id") in emergency_ids],
        [n for n in items if n.get("id") not in emergency_ids],
    )


def tree_to_units(emergency_nodes: list) -> list[dict]:
    """树格式 → 应急组织单元。

    根为顶层；根的直接子节点一律建为分组（不按 type 过滤，实测存在 type=dept 的应急小组）；
    分组的叶子节点建为角色。
    """
    items = _items(emergency_nodes)
    root_ids = _emergency_root_ids(items)
    roots = [n for n in items if n.get("id") in root_ids]
    if not roots:
        return []
    root = roots[0]
    root_id = root.get("id")
    units: list[dict] = [
        {
            "id": root_id,
            "parent_id": None,
            "name": root.get("name"),
            "duties": root.get("duties") or "应急组织总览",
            "roles": [],
        }
    ]
    for child in [n for n in items if n.get("parent_id") == root_id]:
        roles = [
            {
                "id": leaf.get("id"),
                "name": str(leaf.get("name") or ""),
                "duties": leaf.get("duties") or "",
                "sort_order": 0,
                "is_required": str(leaf.get("name") or "") in REQUIRED_ROLE_NAMES,
                "members": [],
            }
            for leaf in items
            if leaf.get("parent_id") == child.get("id")
        ]
        units.append(
            {
                "id": child.get("id"),
                "parent_id": root_id,
                "name": child.get("name"),
                "duties": child.get("duties") or "",
                "roles": roles,
            }
        )
    return units


def groups_to_units(groups: list) -> list[dict]:
    """旧分组 → 应急组织单元：按成员 role 码派生角色，同一角色聚合成一个角色。"""
    units: list[dict] = [
        {
            "id": "__root__",
            "parent_id": None,
            "name": EMERGENCY_ROOT_NAME,
            "duties": "应急组织总览",
            "roles": [],
        }
    ]
    for gi, g in enumerate(_items(groups)):
        if not _is_group_item(g):
            continue
        role_map: dict[str, dict] = {}
        for m in g.get("members") or []:
            if not isinstance(m, dict) or not m.get("name"):
                continue
            role_name = ROLE_NAME_BY_CODE.get(str(m.get("role") or "").strip(), "组员")
            role = role_map.setdefault(
                role_name,
                {
                    "id": f"__role_{gi}_{role_name}",
                    "name": role_name,
                    "duties": "",
                    "sort_order": len(role_map),
                    "is_required": role_name in REQUIRED_ROLE_NAMES,
                    "members": [],
                },
            )
            role["members"].append(
                {
                    "name": m.get("name"),
                    "position": m.get("position") or "",
                    "phone": m.get("phone") or "",
                }
            )
        units.append(
            {
                "id": f"__group_{gi}",
                "parent_id": "__root__",
                "name": g.get("group_name") or "应急小组",
                "duties": g.get("responsibilities") or "",
                "roles": list(role_map.values()),
            }
        )
    return units


def combine_units(*unit_lists: list[dict]) -> list[dict]:
    """合并多来源单元（混合形态）：只保留一个顶层单元，其余分组统一重挂到它下面。"""
    roots: list[dict] = []
    children: list[dict] = []
    for units in unit_lists:
        for u in units or []:
            (children if u.get("parent_id") else roots).append(u)
    if not roots:
        return []
    root = roots[0]
    for c in children:
        c["parent_id"] = root["id"]
    return [root] + children


def _sorted_by_depth(unit_rows: list[dict]) -> list[dict]:
    """父先于子：自引用外键逐行校验，父行必须先于子行写入。"""
    by_id = {r["id"]: r for r in unit_rows}
    depth_cache: dict[str, int] = {}

    def depth(uid: str) -> int:
        if uid in depth_cache:
            return depth_cache[uid]
        row = by_id.get(uid)
        parent = row.get("parent_id") if row else None
        d = 0 if not parent or parent not in by_id else depth(parent) + 1
        depth_cache[uid] = d
        return d

    return sorted(unit_rows, key=lambda r: depth(r["id"]))


async def _upsert_units(db, enterprise_id: str, units: list[dict]) -> dict:
    """写入应急组织三表（roles[].member_ids 由调用方先行解析成真实成员 id）。"""
    unit_rows, role_rows, assignment_rows = flatten_units(units)
    if unit_rows:
        await db.execute(
            EmergencyOrgUnit.__table__.insert(),
            [{"enterprise_id": enterprise_id, **r} for r in _sorted_by_depth(unit_rows)],
        )
    if role_rows:
        await db.execute(
            EmergencyOrgRole.__table__.insert(),
            [{"enterprise_id": enterprise_id, **r} for r in role_rows],
        )
    if assignment_rows:
        await db.execute(
            EmergencyOrgAssignment.__table__.insert(),
            [{"enterprise_id": enterprise_id, **r} for r in assignment_rows],
        )
    return {
        "units": len(unit_rows),
        "roles": len(role_rows),
        "assignments": len(assignment_rows),
    }


async def _existing_members(db, enterprise_id: str) -> list:
    return (
        await db.execute(
            select(EnterpriseMember).where(EnterpriseMember.enterprise_id == enterprise_id)
        )
    ).scalars().all()


async def _ensure_group_members(db, enterprise_id: str, units: list[dict], apply: bool) -> int:
    """旧分组形态：内嵌成员按 (姓名|电话) 查重，缺失则新建成员档案，并回填 member_ids。"""
    index: dict[str, str] = {}
    for m in await _existing_members(db, enterprise_id):
        if m.name:
            index[f"{m.name}|{m.phone or ''}"] = m.id
            index.setdefault(f"name:{m.name}", m.id)
    created = 0
    for u in units:
        for r in u.get("roles") or []:
            ids: list[str] = []
            for m in r.get("members") or []:
                key = f"{m['name']}|{m.get('phone') or ''}"
                member_id = index.get(key) or index.get(f"name:{m['name']}")
                if not member_id:
                    created += 1
                    if not apply:
                        continue
                    member = EnterpriseMember(
                        enterprise_id=enterprise_id,
                        name=m["name"],
                        phone=m.get("phone") or None,
                        position=m.get("position") or None,
                        role="member",
                        enabled=True,
                    )
                    db.add(member)
                    await db.flush()
                    member_id = member.id
                    index[key] = member_id
                    index.setdefault(f"name:{m['name']}", member_id)
                ids.append(str(member_id))
            r["member_ids"] = ids
            r.pop("members", None)
    return created


async def migrate_one(db, ent: Enterprise, apply: bool) -> dict:
    """搬迁单个企业并返回统计。apply=False 只统计不写库。"""
    items = _items(ent.org_structure)
    shape = classify_shape(items)
    stats: dict = {"name": ent.name, "shape": shape, "skipped": shape == "none"}
    if shape == "none":
        return stats

    group_items = [n for n in items if _is_group_item(n)]
    rest = [n for n in items if not _is_group_item(n)]
    emergency_nodes, company_nodes = split_tree(rest)
    removed_node_ids = [n.get("id") for n in emergency_nodes if n.get("id")]

    tree_units = tree_to_units(emergency_nodes)
    group_units = groups_to_units(group_items) if group_items else []
    if tree_units and emergency_nodes:
        members_by_node: dict[str, list[str]] = {}
        for m in await _existing_members(db, ent.id):
            if m.org_node_id:
                members_by_node.setdefault(m.org_node_id, []).append(m.id)
        for u in tree_units:
            for r in u["roles"]:
                r["member_ids"] = members_by_node.get(str(r.get("id")), [])
    units = combine_units(tree_units, group_units)
    stats["company_nodes_left"] = len(company_nodes)

    if group_items:
        stats["created_members"] = await _ensure_group_members(db, ent.id, group_units, apply)
    if not apply:
        stats["planned"] = {
            "units": len(units),
            "roles": sum(len(u.get("roles") or []) for u in units),
            "assignments": sum(
                len(r.get("member_ids") or []) for u in units for r in (u.get("roles") or [])
            ),
        }
        return stats

    await _upsert_units(db, ent.id, units)
    if shape in ("tree", "both") and removed_node_ids:
        # 只清掉挂在被摘除应急节点上的挂载，公司岗位挂载原样保留
        await db.execute(
            text(
                "UPDATE enterprise_members SET org_node_id = NULL "
                "WHERE enterprise_id = :ent AND org_node_id = ANY(:ids)"
            ),
            {"ent": ent.id, "ids": removed_node_ids},
        )
    if shape == "groups":
        # 整棵树都是应急组织：成员挂载全部清空
        await db.execute(
            text("UPDATE enterprise_members SET org_node_id = NULL WHERE enterprise_id = :ent"),
            {"ent": ent.id},
        )
    ent.org_structure = company_nodes
    # 按剩余公司树重建主岗任职（幂等：同成员同节点唯一）
    await db.execute(
        text(
            "INSERT INTO member_positions (enterprise_id, member_id, org_node_id, is_primary) "
            "SELECT enterprise_id, id, org_node_id, TRUE FROM enterprise_members "
            "WHERE enterprise_id = :ent AND org_node_id IS NOT NULL "
            "ON CONFLICT DO NOTHING"
        ),
        {"ent": ent.id},
    )
    return stats


async def main(apply: bool) -> None:
    backup_dir = Path("output/migrations")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"org_split_{stamp}.json"
    async with async_session() as db:
        ents = (await db.execute(select(Enterprise))).scalars().all()
        backup = {e.id: (e.org_structure or []) for e in ents}
        backup_path.write_text(
            json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"备份写入 {backup_path}")
        for ent in ents:
            stats = await migrate_one(db, ent, apply=apply)
            print(json.dumps(stats, ensure_ascii=False))
        if apply:
            await db.commit()
            print("已提交")
        else:
            await db.rollback()
            print("dry-run：未写库")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正写库；缺省为 dry-run")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划（默认行为，显式传入亦为 dry-run）")
    args = parser.parse_args()
    asyncio.run(main(apply=bool(args.apply and not args.dry_run)))
