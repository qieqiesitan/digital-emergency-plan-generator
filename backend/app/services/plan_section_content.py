"""预案章节正文处理公共工具（预览与 docx 导出共用）。"""
import re


def strip_section_heading(html: str) -> str:
    """递归剥离正文开头的章节标题（HTML 标题 / 编号行 / 纯文本标题），
    避免与导出时按 section.title 生成的编号标题重复。"""
    if not html or not html.strip():
        return html
    while True:
        m_html = re.match(
            r'\s*<h[1-6][^>]*>\s*(?:[\d.]+\s*)?.*?</h[1-6]>\s*',
            html, re.DOTALL
        )
        if m_html:
            html = html[m_html.end():]
            continue
        m_p = re.match(
            r'\s*<(?:p|div)[^>]*>\s*(?:[\d.]+\s*)?[^<]{1,80}</(?:p|div)>\s*',
            html, re.DOTALL
        )
        if m_p:
            html = html[m_p.end():]
            continue
        m_md = re.match(r'\s*#{1,6}\s+[^\n]+\n\s*', html)
        if m_md:
            html = html[m_md.end():]
            continue
        m_num = re.match(r'\s*\d+\.\s+[^\n]+\n\s*', html)
        if m_num:
            html = html[m_num.end():]
            continue
        m_plain = re.match(r'\s*[^\n<]{1,80}\n\s*\n', html)
        if m_plain:
            html = html[m_plain.end():]
            continue
        break
    return html
