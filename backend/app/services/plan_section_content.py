"""预案章节正文处理公共工具（预览与 docx 导出共用）。"""
import re

# 标题前的编号/序号前缀：`1.2`、`1、`、`一、`、`第3章`、`（1）` 等
_NUMBER_PREFIX = re.compile(
    r"^\s*(?:"
    r"第\s*[0-9一二三四五六七八九十]+\s*[章节条款篇]"
    r"|(?:[0-9]+\.)*[0-9]+"
    r"|[一二三四五六七八九十]+"
    r"|[（(][0-9一二三四五六七八九十]+[)）]"
    r")\s*[、.．)）:：]?\s*"
)
_TRAILING_PUNCT = re.compile(r"[\s。．.、，,；;：:！!？?]+$")


def _normalize_heading(text: str) -> str:
    """标题归一：去标签 → 去编号前缀 → 去首尾标点。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = _NUMBER_PREFIX.sub("", text.strip())
    return _TRAILING_PUNCT.sub("", text.strip())


def strip_section_heading(html: str, section_title: str | None = None) -> str:
    """递归剥离正文开头的章节标题（HTML 标题 / 编号行 / 纯文本标题），
    避免与导出时按 section.title 生成的编号标题重复。

    section_title: 传入章节标题时，只剥离**与标题等价**的那一行
    （归一化后完全相等，如 `<h3>1.2 编制依据</h3>` / `<p>总则</p>`）；
    不匹配的 h3 分区标题（如「处置步骤」）保留，避免误剥卡片分区。
    不传时保持旧行为（剥离任意开头标题行）。

    ⚠ 2026-09-18 修复：原实现用「子串包含」判定（`section_title in text`），
    导致**正文里只要提到章节名就被整段删掉**（实测 `<p>正文包含总则二字</p>`、
    `<p>探针正文：总则。</p>` 都被删除，导出文档只剩标题没有正文）。改成等值判定。
    """
    if not html or not html.strip():
        return html

    def _heading_text(fragment: str) -> str:
        """提取标题文本并去掉编号前缀（如「3.2 」「第一章 」）。"""
        return _normalize_heading(fragment)

    def _matches_title(text: str) -> bool:
        """是否为可剥离的标题行：未传标题时兼容旧行为（任意标题行都剥）；
        传了标题时要求**归一化后完全相等**，不再用子串包含。"""
        if not section_title:
            return True
        normalized = _normalize_heading(text)
        return bool(normalized) and normalized == _normalize_heading(section_title)

    while True:
        m_html = re.match(
            r'\s*<h[1-6][^>]*>\s*(?:[\d.]+\s*)?.*?</h[1-6]>\s*',
            html, re.DOTALL
        )
        if m_html:
            if _matches_title(_heading_text(m_html.group(0))):
                html = html[m_html.end():]
                continue
            break
        m_p = re.match(
            r'\s*<(?:p|div)[^>]*>\s*(?:[\d.]+\s*)?[^<]{1,80}</(?:p|div)>\s*',
            html, re.DOTALL
        )
        if m_p:
            if _matches_title(_heading_text(m_p.group(0))):
                html = html[m_p.end():]
                continue
            break
        m_md = re.match(r'\s*#{1,6}\s+[^\n]+\n\s*', html)
        if m_md:
            text = m_md.group(0).strip().lstrip("#").strip()
            if _matches_title(_heading_text(text)):
                html = html[m_md.end():]
                continue
            break
        m_num = re.match(r'\s*\d+\.\s+[^\n]+\n\s*', html)
        if m_num:
            if _matches_title(_heading_text(m_num.group(0))):
                html = html[m_num.end():]
                continue
            break
        m_plain = re.match(r'\s*[^\n<]{1,80}\n\s*\n', html)
        if m_plain:
            if _matches_title(_heading_text(m_plain.group(0))):
                html = html[m_plain.end():]
                continue
            break
        break
    return html
