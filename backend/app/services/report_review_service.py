"""报告草稿章节的确定性规则审查（供前端展示并人工确认修订）。"""

import re


def review_report_chapters(chapters: list[dict]) -> list[dict]:
    """返回 issues：{severity, section_key, kind, issue, suggestion}。"""
    issues: list[dict] = []
    for ch in chapters:
        key = ch.get("key", "")
        title = ch.get("title", "")
        content = ch.get("content", "") or ""
        text = content.strip()
        if not text:
            issues.append(_issue(key, "error", "empty", "章节内容为空", "请生成或补充该章节内容"))
            continue
        if len(text) < 80:
            issues.append(_issue(key, "error", "too_short", f"章节内容过短（{len(text)} 字）", "请重新生成或补充内容"))
        if re.search(r"XXX|x{3,}", text, re.IGNORECASE):
            issues.append(_issue(key, "warning", "placeholder", "正文残留占位符 XXX/xxx", "请用实际内容替换占位符"))
        if re.search(r"^\s*\|[\s:\-|]+\|\s*$", text, re.MULTILINE):
            issues.append(_issue(key, "warning", "markdown_table", "正文含 Markdown 表格分隔线", "请改用 HTML 表格"))
        if "```mermaid" in text or re.search(r"\nmermaid\n(flowchart|graph|sequenceDiagram)", text):
            issues.append(_issue(key, "warning", "mermaid_block", "正文含 Mermaid 代码块", "请删除代码块，仅保留正文"))
        if content.count("<p>") != content.count("</p>"):
            issues.append(_issue(key, "error", "html_unbalanced", "HTML 段落标签未闭合", "请修复标签配对"))
        first_line = text.splitlines()[0].strip() if text.splitlines() else ""
        if title and first_line == title:
            issues.append(_issue(key, "info", "title_duplicate", "章节首行重复了章节标题", "删除首行标题"))
    return issues


def _issue(section_key: str, severity: str, kind: str, issue: str, suggestion: str) -> dict:
    return {
        "severity": severity,
        "section_key": section_key,
        "kind": kind,
        "issue": issue,
        "suggestion": suggestion,
    }
