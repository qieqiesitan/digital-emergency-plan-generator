"""预案章节正文处理公共工具（预览与 docx 导出共用）。"""
import re


def strip_section_heading(html: str, section_title: str | None = None) -> str:
    """递归剥离正文开头的章节标题（HTML 标题 / 编号行 / 纯文本标题），
    避免与导出时按 section.title 生成的编号标题重复。

    section_title: 传入章节标题时，只剥离与该标题匹配的标题行；
    不匹配的 h3 分区标题（如「处置步骤」）保留，避免误剥卡片分区。
    不传时保持旧行为（剥离任意开头标题）。"""
    if not html or not html.strip():
        return html

    def _heading_text(fragment: str) -> str:
        """提取标题文本并去掉编号前缀（如「3.2 」「第一章 」）。"""
        text = re.sub(r"<[^>]+>", "", fragment).strip()
        text = re.sub(r"^\s*(?:[\d.]+\s*|[一二三四五六七八九十]+[章节条篇]?\s*)+", "", text)
        return text.strip()

    def _matches_title(text: str) -> bool:
        if not section_title:
            return True
        return section_title in text

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
