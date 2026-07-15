"""Prompt 注入器 ― 编制依据（plan_type检索）+ 其他章节（topic检索）双路径。"""

import logging

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = ["sec_1_2", "sec_1", "编制依据", "1.2", "1.1"]


def inject_regulations(plan_type: str, section_key: str,
                       section_title: str, prompt: str,
                       enterprise_data: dict = None) -> str:
    """章节法规注入。编制依据用 plan_type 精确检索，其余用 topic 检索。"""

    try:
        from app.regulations import get_retriever
        retriever = get_retriever()
    except Exception as e:
        logger.warning("法规检索器不可用: %s", e)
        return prompt

    # 编制依据 → 原逻辑：plan_type 精确匹配
    if _should_inject_basis(section_key, section_title):
        try:
            result = retriever.retrieve(plan_type, section_key, enterprise_data)
        except Exception as e:
            logger.warning("法规检索失败: %s", e)
            return prompt
        if result and result.get("effective"):
            return prompt + "\n\n---\n\n" + _format(result, label="编制依据参考")
        return prompt

    # 其他章节 → topic 检索
    try:
        result = retriever.retrieve_by_topics(
            section_key, section_title, plan_type, max_articles=15
        )
    except Exception as e:
        logger.warning("Topic检索失败: %s", e)
        return prompt

    if result and result.get("effective"):
        topics = result.get("matched_topics", [])
        label = f"章节参考（主题: {', '.join(topics)}）" if topics else "章节参考"
        return prompt + "\n\n---\n\n" + _format(result, label=label, compact=True)

    return prompt


def _should_inject_basis(section_key: str, section_title: str) -> bool:
    if not section_key and not section_title:
        return False
    combined = f"{section_key or ''} {section_title or ''}"
    for pat in INJECTION_PATTERNS:
        if pat in combined:
            return True
    return False


def _format(result: dict, label: str = "编制依据参考",
            compact: bool = False) -> str:
    lines = [
        f"【系统确认的现行有效法律法规参考 ― {label} ― 请严格依据以下条文撰写】",
        "",
    ]

    effective = result.get("effective", [])
    if effective:
        if not compact:
            lines.append("以下为当前系统确认有效的法律法规条文原文。")
            lines.append("请据此撰写，在正文中准确引用法规名称和具体条款号。")
            lines.append("不得引用已废止的法规，不得编造不存在的条文。")
            lines.append("")

        for reg in effective:
            full_name = reg.get("full_name", reg.get("label", ""))
            version = reg.get("version", "")
            effective_date = reg.get("effective_date", "")

            lines.append(f"### {full_name}")
            if version or effective_date:
                lines.append(f"施行日期：{effective_date} | 状态：现行有效")
            lines.append("")
            articles = reg.get("articles", [])
            if compact and len(articles) > 5:
                articles = articles[:5]
                lines.append(f"（共{len(reg.get('articles',[]))}条，以下摘录前5条）")
            for art in articles:
                num = art.get("number", "")
                text = art.get("text", "")
                lines.append(f"**{num}** {text}")
                lines.append("")
            lines.append("")
    else:
        lines.append("（本章节无匹配法规条文）")
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
                if isinstance(replaced_node, dict):
                    replaced_label = replaced_node.get("label", replaced)
                else:
                    replaced_label = replaced
                lines.append(f"- **{label}**，已被 {replaced_label} 替代")
            else:
                lines.append(f"- **{label}**")

    return "\n".join(lines)