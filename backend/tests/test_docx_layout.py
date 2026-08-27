"""docx_template 排版规格测试：样式表、页面、列表、表格、域、分页、图题。"""
import pytest
from docx import Document
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, Cm

from app.services.docx_template import (
    register_all_styles, build_table, html_to_docx_content,
    generate_plan_docx, LI_TEXT_THRESHOLD, TABLE_BODY_WIDTH_CM,
    FONT_FANGSONG, FONT_FANGSONG_GB, FONT_KAITI, FONT_SONGTI, FONT_HEITI,
)


def _ea_font(style) -> str:
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    return rf.get(qn("w:eastAsia")) if rf is not None else None


def test_styles_registered():
    doc = Document()
    register_all_styles(doc)

    normal = doc.styles["Normal"]
    assert normal.font.name == "Times New Roman"
    assert normal.font.size == Pt(16)
    assert _ea_font(normal) == FONT_FANGSONG
    assert normal.paragraph_format.line_spacing_rule == WD_LINE_SPACING.EXACTLY
    assert normal.paragraph_format.line_spacing == Pt(28)
    assert normal.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY

    h1 = doc.styles["Heading 1"]
    assert _ea_font(h1) == FONT_HEITI and h1.font.size == Pt(16) and h1.font.bold

    h2 = doc.styles["Heading 2"]
    assert _ea_font(h2) == FONT_KAITI and h2.font.bold

    h3 = doc.styles["Heading 3"]
    assert _ea_font(h3) == FONT_FANGSONG and h3.font.bold

    body = doc.styles["Body Text"]
    assert _ea_font(body) == FONT_FANGSONG_GB
    assert body.font.size == Pt(16)
    assert body.paragraph_format.first_line_indent == Pt(32)
    assert body.paragraph_format.line_spacing_rule == WD_LINE_SPACING.EXACTLY

    caption = doc.styles["Caption"]
    assert _ea_font(caption) == FONT_SONGTI
    assert caption.font.size == Pt(14)
    assert caption.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.CENTER

    toc_title = doc.styles["TOC Title"]
    assert _ea_font(toc_title) == FONT_HEITI
    assert toc_title.font.size == Pt(18)


def test_style_constants():
    assert LI_TEXT_THRESHOLD == 30
    assert TABLE_BODY_WIDTH_CM == 15.6
