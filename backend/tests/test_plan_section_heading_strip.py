"""章节标题剥离：只剥"与章节名等价的标题行"，绝不误删正文（2026-09-18 修）。

背景（本轮实测）：导出预览与 DOCX 共用的 `strip_section_heading` 原先用**子串包含**
判定标题，导致正文里只要出现章节名就被整段删除——
`<p>正文包含总则二字</p>`、`<p>探针正文：总则。</p>` 都被删成空，
导出的"完整预案"只剩目录与标题、没有正文。改成归一化等值判定，并钉住这些用例。
"""

import pytest

from app.services.plan_section_content import strip_section_heading


@pytest.mark.parametrize(
    ("content", "title", "expected"),
    [
        # —— 该剥的：等价标题行（含编号/序号/中文"第X章"前缀/句末标点）
        ("<h3>1.2 编制依据</h3><p>正文</p>", "编制依据", "<p>正文</p>"),
        ("<h3>编制依据</h3><p>正文</p>", "编制依据", "<p>正文</p>"),
        ("<h2>第三章 应急组织机构及职责</h2><p>正文</p>", "应急组织机构及职责", "<p>正文</p>"),
        ("<p>总则</p><p>正文</p>", "总则", "<p>正文</p>"),
        ("<p>总则。</p><p>正文</p>", "总则", "<p>正文</p>"),
        ("<p>一、总则</p><p>正文</p>", "总则", "<p>正文</p>"),
        # —— 不该剥的：正文里出现章节名（本 bug 的核心回归）
        ("<p>正文包含总则二字</p>", "总则", "<p>正文包含总则二字</p>"),
        ("<p>探针正文：总则。</p>", "总则", "<p>探针正文：总则。</p>"),
        ("<p>总则概述</p>", "总则", "<p>总则概述</p>"),
        ("<p>本章依据《安全生产法》编写</p>", "编制依据", "<p>本章依据《安全生产法》编写</p>"),
        # —— 不该剥的：不匹配的分区标题要保留（卡片化章节依赖它）
        ("<h3>处置步骤</h3><p>第一步</p>", "紧急处置步骤", "<h3>处置步骤</h3><p>第一步</p>"),
        ("<h3>注意事项</h3><ol><li>注意</li></ol>", "紧急处置步骤", "<h3>注意事项</h3><ol><li>注意</li></ol>"),
    ],
)
def test_strip_only_equivalent_heading(content, title, expected):
    assert strip_section_heading(content, title) == expected


def test_heading_strip_keeps_following_paragraphs_and_diagram():
    """剥标题不能连带删正文段落或图代码。"""
    content = (
        "<h3>1 总则</h3>"
        "<p>为规范应急管理，制定本预案。</p>"
        '<pre><code class="language-mermaid">graph TD; A-->B;</code></pre>'
    )
    out = strip_section_heading(content, "总则")
    assert "制定本预案" in out
    assert "language-mermaid" in out
    assert "<h3>1 总则</h3>" not in out


def test_legacy_behavior_without_title():
    """不传章节名时保持旧行为：剥离开头的裸标题行（既有调用方契约）。"""
    assert strip_section_heading("第一章 总则\n\n正文内容") == "正文内容"
    assert strip_section_heading("<h1>第一章 总则</h1>\n\n正文内容") == "正文内容"


def test_empty_input_passthrough():
    assert strip_section_heading("", "总则") == ""
    assert strip_section_heading("   ", "总则") == "   "
