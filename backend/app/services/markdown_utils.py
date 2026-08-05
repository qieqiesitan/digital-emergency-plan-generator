"""Markdown → HTML 共享工具（预案生成 / 报告 / 聊天通用）。"""

import re

import markdown


def _split_merged_content(text: str) -> str:
    """拆分 AI 输出中标题与表格/列表黏在同一行的情况。"""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue

        # Case A: 标题 + 表格头黏在同一行 (e.g. "7.1 内部应急联系方式 | 序号 | ...")
        if not stripped.startswith("|") and "|" in stripped:
            pipe_idx = stripped.find("|")
            heading = stripped[:pipe_idx].strip()
            table_part = stripped[pipe_idx:].strip()
            if heading and table_part.startswith("|"):
                if result and result[-1].strip():
                    result.append("")
                result.append(heading)
                result.append("")
                result.append(table_part)
                continue

        # Case B: 标题 + 列表项黏在同一行 (e.g. "7.3 注意事项 - 内容")
        m = re.match(r"^(\d+(?:\.\d+)*\s+\S.*?)\s+(-\s+.+)$", stripped)
        if m:
            heading = m.group(1).strip()
            list_item = m.group(2).strip()
            if result and result[-1].strip():
                result.append("")
            result.append(heading)
            result.append("")
            result.append(list_item)
            continue

        # Case C: 标题 + 正文段落黏在同一行 (e.g. "7. 紧急联系电话 为确保应急响应时...")
        m = re.match(r"^(\d+\.(?:\d+)?\s+[\u4e00-\u9fff]+)\s+([\u4e00-\u9fff].{10,})$", stripped)
        if m:
            heading = m.group(1).strip()
            content = m.group(2).strip()
            if result and result[-1].strip():
                result.append("")
            result.append(heading)
            result.append("")
            result.append(content)
            continue
        result.append(line)
    return "\n".join(result)


def _normalize_linebreaks(text: str) -> str:
    """防御性预处理：先拆分黏连内容，再给编号子节行前后插入空行。"""
    text = _split_merged_content(text)
    lines = text.split("\n")
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue
        is_numbered = bool(re.match(r"^\d+(?:\.\d+)+\s+\S", stripped))
        is_top = bool(re.match(r"^\d+\.\s+\S", stripped)) and not re.match(r"^\d+\.\d", stripped)
        if is_numbered or is_top:
            if result and result[-1].strip():
                result.append("")
            result.append(line)
            if i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^\d+(?:\.\d+)*\s+\S", lines[i + 1].strip()):
                result.append("")
        else:
            result.append(line)
    return "\n".join(result)


def _fix_markdown_tables(md_text: str) -> str:
    """Preprocess Markdown to fix malformed tables before HTML conversion.

    Handles cases where AI-generated content has:
    - Heading text merged with table header on same line
    - Tables without blank lines before them
    - Non-table text immediately after table rows
    """
    lines = md_text.split("\n")
    result = []
    in_table = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            result.append("")
            in_table = False
            i += 1
            continue

        is_pipe_start = stripped.startswith("|")
        is_sep_line = bool(re.match(r"^\|[\s\-:|]+\|$", stripped))

        # Case 1: Heading text merged with table header on same line
        if not is_pipe_start and "|" in stripped:
            pipe_idx = stripped.find("|")
            if pipe_idx > 0:
                heading = stripped[:pipe_idx].strip()
                table_part = stripped[pipe_idx:].strip()
                if result and result[-1].strip():
                    result.append("")
                result.append(heading)
                result.append("")
                result.append(table_part)
                in_table = True
                i += 1
                continue

        # Case 2: Non-table line after table rows - insert blank line separator
        if not is_pipe_start and not is_sep_line and in_table:
            result.append("")
            in_table = False

        if is_sep_line:
            if not in_table and result and result[-1].strip():
                result.append("")
            result.append(lines[i])
            in_table = True
        elif is_pipe_start:
            if not in_table and result and result[-1].strip():
                result.append("")
            result.append(lines[i])
            in_table = True
        else:
            result.append(lines[i])

        i += 1

    return "\n".join(result)


def md_to_html(text: str, normalize: bool = False, output_format: str | None = None) -> str:
    """Convert AI-generated Markdown to HTML for the TipTap editor.

    Args:
        text: Markdown 或已是 HTML 的内容。
        normalize: 是否先做黏连内容拆分 / 空行归一化 / 表格修复。
        output_format: 传给 python-markdown 的输出格式（默认 xhtml，与 markdown 库一致）。
    """
    if not text or text.strip().startswith("<"):
        return text
    if normalize:
        text = _normalize_linebreaks(text)
        text = _fix_markdown_tables(text)
    kwargs = {"extensions": ["tables", "fenced_code"]}
    if output_format:
        kwargs["output_format"] = output_format
    return markdown.markdown(text, **kwargs)
