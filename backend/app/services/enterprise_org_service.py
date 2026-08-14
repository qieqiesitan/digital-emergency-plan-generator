import re

from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation


ORG_TYPES = {"dept", "team", "position"}

ROLE_LABEL_MAP = {"企业管理员": "enterprise_admin", "班组长": "team_leader", "员工": "member"}

IMPORT_HEADERS = ["姓名", "邮箱", "部门", "班组", "岗位", "角色"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_org_tree(nodes: list) -> list[str]:
    """校验组织树：id 唯一、parent 存在（根为 None）、type 合法、members 为列表且 name 非空。返回错误列表。"""
    errors: list[str] = []
    ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    seen: set[str] = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"节点 {i + 1} 必须是对象")
            continue
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
                if not isinstance(m, dict):
                    errors.append(f"节点 {nid} 存在非法成员")
                elif not m.get("name"):
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


def build_member_import_template() -> Workbook:
    """openpyxl 模板：表头 姓名/邮箱/部门/班组/岗位/角色；角色列数据校验下拉。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "成员导入"
    ws.append(IMPORT_HEADERS)
    dv = DataValidation(type="list", formula1='"企业管理员,班组长,员工"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("F2:F1000")
    return wb


def parse_member_rows(rows: list[dict]) -> list[dict]:
    """rows 为 {列名: 值}；邮箱必填且格式校验；角色映射 ROLE_LABEL_MAP（缺省 member）。

    返回 [{name, email, department, team, position, role, error?}]。
    """
    out = []
    for row in rows:
        email = str(row.get("邮箱") or "").strip()
        role = ROLE_LABEL_MAP.get(str(row.get("角色") or "").strip(), "member")
        item = {
            "name": str(row.get("姓名") or "").strip(),
            "email": email,
            "department": str(row.get("部门") or "").strip(),
            "team": str(row.get("班组") or "").strip(),
            "position": str(row.get("岗位") or "").strip(),
            "role": role,
        }
        if not email:
            item["error"] = "邮箱必填"
        elif not _EMAIL_RE.match(email):
            item["error"] = "邮箱格式不正确"
        out.append(item)
    return out
