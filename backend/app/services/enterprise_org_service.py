ORG_TYPES = {"dept", "team", "position"}


def validate_org_tree(nodes: list) -> list[str]:
    """校验组织树：id 唯一、parent 存在（根为 None）、type 合法、members 为列表且 name 非空。返回错误列表。"""
    errors: list[str] = []
    ids = [n.get("id") for n in nodes]
    seen: set[str] = set()
    for i, n in enumerate(nodes):
        nid = n.get("id")
        if not nid:
            errors.append(f"节点 {i + 1} 缺少 id")
            continue
        if nid in seen:
            errors.append(f"节点 id 重复: {nid}")
        seen.add(nid)
        if n.get("type") not in ORG_TYPES:
            errors.append(f"节点 {nid} type 非法: {n.get('type')}")
        parent = n.get("parent_id")
        if parent is not None and parent not in ids:
            errors.append(f"节点 {nid} parent 不存在: {parent}")
        members = n.get("members")
        if not isinstance(members, list):
            errors.append(f"节点 {nid} members 必须为数组")
        else:
            for m in members:
                if not (m or {}).get("name"):
                    errors.append(f"节点 {nid} 存在无姓名成员")
    return errors


def sync_org_structure(enterprise, nodes: list) -> None:
    """规范化后写回 org_structure（向后兼容：保留 name/members[].name 结构）。"""
    enterprise.org_structure = normalize_org_nodes(nodes)


def normalize_org_nodes(nodes: list) -> list:
    """为缺 id 的节点生成短 id，统一结构。"""
    out = []
    for i, n in enumerate(nodes):
        item = dict(n)
        if not item.get("id"):
            item["id"] = f"node-{i + 1}"
        item.setdefault("members", [])
        out.append(item)
    return out
