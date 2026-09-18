"""组织树通用校验：公司组织架构（dept/team/position）与应急组织（unit/role）共用。

从 enterprise_org_service.validate_org_tree 抽出，避免应急组织再抄一份规则。
"""

from typing import Iterable


def validate_tree(
    nodes: list,
    allow_types: set[str] | None,
    id_field: str = "id",
    parent_field: str = "parent_id",
    name_field: str = "name",
    require_members: bool = True,
) -> list[str]:
    """校验扁平树：id 唯一、name 非空、parent 存在、无自环与环、type 合法、members 为数组且成员有姓名。

    allow_types 为 None 时跳过 type 校验（应急组织不区分类型）。
    require_members 为 False 时跳过 members 校验（应急单元用 roles 承载成员）。
    """
    errors: list[str] = []
    ids = [n.get(id_field) for n in nodes if isinstance(n, dict)]
    by_id = {n.get(id_field): n for n in nodes if isinstance(n, dict) and n.get(id_field)}
    seen: set[str] = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"节点 {i + 1} 必须是对象")
            continue
        nid = n.get(id_field)
        if not nid:
            errors.append(f"节点 {i + 1} 缺少 {id_field}")
            continue
        if nid in seen:
            errors.append(f"节点 id 重复: {nid}")
        seen.add(nid)
        if allow_types is not None and n.get("type") not in allow_types:
            errors.append(f"节点 {nid} type 非法: {n.get('type')}")
        if not isinstance(n.get(name_field), str) or not str(n.get(name_field)).strip():
            errors.append(f"节点 {nid} 名称不能为空")
        parent = n.get(parent_field)
        if parent is not None and parent not in ids:
            errors.append(f"节点 {nid} parent 不存在: {parent}")
        elif parent == nid:
            errors.append(f"节点 {nid} 不能以自身为父节点")
        elif parent is not None:
            # 沿 parent 链检测环：从父节点一路向上，回到自身即循环引用
            cur = parent
            walked: set[str] = set()
            while cur in by_id and cur not in walked:
                if cur == nid:
                    errors.append(f"节点 {nid} 存在循环引用")
                    break
                walked.add(cur)
                cur = by_id[cur].get(parent_field)
        if not require_members:
            continue
        members = n.get("members")
        if not isinstance(members, list):
            errors.append(f"节点 {nid} members 必须为数组")
        else:
            for m in members:
                if not isinstance(m, dict):
                    errors.append(f"节点 {nid} 存在非法成员")
                elif not isinstance(m.get("name"), str) or not m.get("name").strip():
                    errors.append(f"节点 {nid} 存在无姓名成员")
    return errors


def validate_emergency_units(units: Iterable[dict], known_member_ids: set[str]) -> list[str]:
    """校验应急组织：单元树规则 + 同单元角色名唯一 + 角色内成员不重复且属于本企业。"""
    unit_list = list(units)
    errors = validate_tree(
        unit_list, allow_types=None, id_field="id", parent_field="parent_id", require_members=False
    )
    for u in unit_list:
        if not isinstance(u, dict):
            continue
        uid = u.get("id")
        roles = u.get("roles")
        if not isinstance(roles, list):
            errors.append(f"单元 {uid} roles 必须为数组")
            continue
        seen_role_names: set[str] = set()
        for r in roles:
            if not isinstance(r, dict):
                errors.append(f"单元 {uid} 存在非法角色")
                continue
            rid = r.get("id")
            name = str(r.get("name") or "").strip()
            if not name:
                errors.append(f"角色 {rid} 名称不能为空")
            elif name in seen_role_names:
                errors.append(f"单元 {uid} 角色名重复: {name}")
            seen_role_names.add(name)
            member_ids = r.get("member_ids")
            if not isinstance(member_ids, list):
                errors.append(f"角色 {rid} member_ids 必须为数组")
                continue
            if len(set(member_ids)) != len(member_ids):
                errors.append(f"角色 {rid} 存在重复指派")
            for mid in member_ids:
                if mid not in known_member_ids:
                    errors.append(f"角色 {rid} 成员不属于本企业或已停用: {mid}")
    return errors
