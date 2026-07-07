"""Prompt 注入器 — 对编制依据章节注入法规条文。"""

import logging

logger = logging.getLogger(__name__)

# 需要注入法规的章节匹配模式
INJECTION_PATTERNS = ["sec_1_2", "sec_1", "编制依据", "1.2", "1.1"]


def inject_regulations(plan_type: str, section_key: str,
                       section_title: str, prompt: str,
                       enterprise_data: dict = None) -> str:
    """编制依据章节注入法规条文，非目标章节原样返回。静默降级。"""
    if not _should_inject(section_key, section_title):
        return prompt

    try:
        from app.regulations import get_retriever
        retriever = get_retriever()
        result = retriever.retrieve(plan_type, section_key, enterprise_data)
    except Exception as e:
        logger.warning("法规检索失败，降级: %s", e)
        return prompt

    if not result or not result.get("effective"):
        return prompt

    block = _format(result)
    return prompt + "\n\n---\n\n" + block


def _should_inject(section_key: str, section_title: str) -> bool:
    if not section_key and not section_title:
        return False
    combined = f"{section_key or ''} {section_title or ''}"
    for pat in INJECTION_PATTERNS:
        if pat in combined:
            return True
    return False


def _format(result: dict) -> str:
    lines = [
        "【系统确认的现行有效法律法规参考——请严格依据以下条文撰写】",
        "",
        "以下为当前系统确认有效的法律法规条文原文。",
        "请据此撰写编制依据，在正文中准确引用法规名称和具体条款号。",
        "不得引用已废止的法规，不得编造不存在的条文。",
        "",
    ]

    for reg in result.get("effective", []):
        label = reg.get("label", "")
        full_name = reg.get("full_name", "")
        version = reg.get("version", "")
        effective_date = reg.get("effective_date", "")

        lines.append(f"### {label} {full_name}")
        lines.append(f"版本：{version} | 施行日期：{effective_date} | 状态：现行有效")
        lines.append("")
        for art in reg.get("articles", []):
            num = art.get("number", "")
            text = art.get("text", "")
            lines.append(f"**{num}** {text}")
            lines.append("")
        lines.append("")

    abolished = result.get("abolished", [])
    if abolished:
        lines.append("---")
        lines.append("### ⚠ 以下法规已废止/被替代，请勿引用：")
        lines.append("")
        for reg in abolished:
            label = reg.get("label", "")
            replaced = reg.get("abolished_by", "")
            if replaced:
                replaced_node = reg.get("abolished_by_node", {})
                replaced_label = replaced_node.get("label", replaced) if isinstance(replaced_node, dict) else replaced
                lines.append(f"- **{label}**，已被 {replaced_label} 替代")
            else:
                lines.append(f"- **{label}**")

    return "\n".join(lines)
