import json
import logging
import re

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

from app.services.llm_client import llm_text_completion
from app.services.risk_ai_service import _parse_ai_json


logger = logging.getLogger(__name__)


ORG_TYPES = {"dept", "team", "position"}

ROLE_LABEL_MAP = {"企业管理员": "enterprise_admin", "班组长": "team_leader", "员工": "member"}

IMPORT_HEADERS = ["姓名", "邮箱", "部门", "班组", "岗位", "角色"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_org_tree(nodes: list) -> list[str]:
    """校验组织树：id 唯一、parent 存在（根为 None）、无自环/环、type 合法、members 为列表且 name 非空。返回错误列表。"""
    errors: list[str] = []
    ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict) and n.get("id")}
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
                cur = by_id[cur].get("parent_id")
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
    """rows 为 {列名: 值}；姓名必填；邮箱可选（为空则导入为未绑定账号成员），
    有邮箱时格式校验；角色映射 ROLE_LABEL_MAP（缺省 member）。

    返回 [{name, email, department, team, position, role, error?}]。
    """
    out = []
    for row in rows:
        email = str(row.get("邮箱") or "").strip()
        name = str(row.get("姓名") or "").strip()
        role = ROLE_LABEL_MAP.get(str(row.get("角色") or "").strip(), "member")
        item = {
            "name": name,
            "email": email,
            "department": str(row.get("部门") or "").strip(),
            "team": str(row.get("班组") or "").strip(),
            "position": str(row.get("岗位") or "").strip(),
            "role": role,
        }
        if not name:
            item["error"] = "姓名必填"
        elif email and not _EMAIL_RE.match(email):
            item["error"] = "邮箱格式不正确"
        out.append(item)
    return out


def _summarize_org_structure(nodes: list) -> str:
    """把现有组织树压成提示词摘要：沿 parent_id 拼 部门/班组 路径。"""
    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict) and n.get("id")}
    parts = []
    for n in nodes:
        if not isinstance(n, dict) or not n.get("name"):
            continue
        path = []
        cur = n.get("id")
        seen = set()
        while cur and cur in by_id and cur not in seen:
            seen.add(cur)
            path.append(by_id[cur].get("name", ""))
            cur = by_id[cur].get("parent_id")
        parts.append("/".join(reversed([p for p in path if p])))
    return "；".join(parts) if parts else "（暂无）"


async def suggest_org_tree(enterprise_info: dict, ai_config, extra_requirements: str = "") -> dict:
    """AI 建议组织树（文本通道，不依赖图像识别）。

    Args:
        enterprise_info: 企业基础信息（industry / employee_count / 可选的
            org_structure 现有节点列表）
        ai_config: AI 配置（未配置时由调用方传 None，服务兜底降级）

    Returns:
        available=True 时含 nodes 列表；否则
        {"available": False, "note": 可读失败原因（超时/未配置等）}
    """
    existing = enterprise_info.get("org_structure")
    org_summary = (
        _summarize_org_structure(existing)
        if isinstance(existing, list)
        else str(existing or "（暂无）")
    )
    info_for_prompt = {
        k: v for k, v in enterprise_info.items() if k != "org_structure"
    }
    prompt = (
        "你是企业组织架构专家。根据企业基础信息，建议合理的组织架构树。\n\n"
        f"企业信息：\n{json.dumps(info_for_prompt, ensure_ascii=False, indent=2)}\n"
        f"现有组织架构：{org_summary}\n\n"
    )
    if extra_requirements and extra_requirements.strip():
        prompt += f"用户补充要求：{extra_requirements.strip()}\n\n"
    prompt += (
        '输出 JSON：{"nodes": [{"id": "唯一短 id", "type": "dept|team|position", '
        '"name": "部门/班组/岗位名称", "parent_id": "父节点 id 或 null", '
        '"members": [{"name": "姓名", "position": "岗位"}]}]}\n'
        "要求：type 仅限 dept（部门）/team（班组）/position（岗位）；"
        "根节点 parent_id 为 null；members 只含姓名和岗位，不要编造邮箱；"
        "中文输出；只输出 JSON，不要任何解释。"
    )
    messages = [
        {"role": "system", "content": "你是企业组织架构专家，输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm_text_completion(messages, ai_config, timeout=120)
        data = _parse_ai_json(raw)
        nodes = data.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("AI 返回缺少 nodes")
        return {"available": True, "nodes": nodes}
    except HTTPException as e:
        note = e.detail if isinstance(e.detail, str) else "AI 服务异常，请稍后重试"
        logger.warning("AI org tree suggestion failed: %s", note)
        return {"available": False, "note": note}
    except Exception:
        logger.exception("AI org tree suggestion failed: industry=%s", enterprise_info.get("industry"))
        return {"available": False, "note": "AI 服务异常，请稍后重试或手动维护组织架构"}
