"""docx 导出前清洗：Markdown 表格须转为 HTML 表格，正文符号清理。

根因：报告导出/合并只按 markdown 行解析，模型违规输出的 | 分隔 Markdown
表格会在 Word 里原样泄漏分隔符；HTML <table> 则原样保留供表格渲染器转换。
"""

from app.routers.risk_assessment import _clean_for_docx


def test_markdown_table_converted_to_html():
    content = (
        "物资清单如下：\n"
        "| 序号 | 名称 |\n"
        "| --- | --- |\n"
        "| 1 | 干粉灭火器 |\n"
        "| 2 | 急救包 |\n"
        "结论。"
    )
    cleaned = _clean_for_docx(content)
    assert "<table" in cleaned
    assert "<td>干粉灭火器</td>" in cleaned
    assert "| --- |" not in cleaned
    assert "结论。" in cleaned


def test_html_table_preserved():
    content = '<table border="1"><tr><td>风险等级</td></tr></table>'
    assert "<table" in _clean_for_docx(content)
    assert "|" not in _clean_for_docx(content)


def test_mermaid_code_block_removed():
    content = "正文。\n```mermaid\nflowchart TD\nA-->B\n```\n后续。"
    cleaned = _clean_for_docx(content)
    assert "```" not in cleaned
    assert "flowchart" not in cleaned
    assert "正文。" in cleaned


def test_plain_text_unchanged():
    content = "一、危险有害因素辨识\n1）某风险；2）某后果。"
    assert _clean_for_docx(content) == content
