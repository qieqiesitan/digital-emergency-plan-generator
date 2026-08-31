"""预案 AI 审查服务：规则审查（占位符/空章节/法规引用真实性/档案一致性/章节完整性）。"""
import re
from app.services.plan_quality_service import check_plan
from app.regulations import get_graph


def _extract_regulation_names(text: str) -> list[str]:
    return re.findall(r"《([^》]{2,60})》", text or "")


def _regulation_exists(name: str) -> bool:
    """法规名是否存在于知识图谱（模糊匹配全称/简称）。"""
    graph = get_graph()
    name_l = (name or "").strip().lower()
    if not name_l:
        return False
    for nid, data in graph._g.nodes(data=True):
        full = (data.get("full_name") or "").lower()
        label = (data.get("label") or "").lower()
        if (full and (name_l in full or full in name_l)) or (label and name_l in label):
            return True
    return False


def review_plan(plan, enterprise, sections) -> dict:
    """返回 {"issues": [...], "warnings": [...]}。
    issue 字段：section_key/section_title/issue；warning 字段：section_key/section_title/warning/evidence。
    """
    rules = check_plan(plan, enterprise, sections)
    issues = list(rules.get("issues", []))
    warnings = list(rules.get("warnings", []))

    # 法规引用真实性：正文引用的法规名必须在图谱中存在（防编造）
    for s in sections:
        text = re.sub(r"<[^>]+>", "", s.content or "")
        for name in _extract_regulation_names(text):
            if not _regulation_exists(name):
                issues.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "issue": f"疑似编造法规引用：{name}（法规库中未找到）",
                })
    return {"issues": issues, "warnings": warnings}
