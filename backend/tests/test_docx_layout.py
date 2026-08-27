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


def test_style_spacing_uses_bare_pt_values():
    """回归：space_before/space_after 传裸数值，避免 Pt() 双重包裹
    （Pt(Pt(28)) 会写出 ~7,112,000 twips 的天文间距，导致 Word 丢弃标题段）。"""
    doc = Document()
    register_all_styles(doc)

    assert doc.styles["Heading 1"].paragraph_format.space_before == \
        pytest.approx(Pt(28), abs=Pt(0.1))
    assert doc.styles["Body Title"].paragraph_format.space_before == \
        pytest.approx(Pt(24), abs=Pt(0.1))
    assert doc.styles["Heading 2"].paragraph_format.space_before == \
        pytest.approx(Pt(6), abs=Pt(0.1))


@pytest.fixture
def no_playwright(monkeypatch):
    """generate_plan_docx 内部会用 Playwright 渲染图；测试环境不启动浏览器。"""
    import playwright.sync_api as psa

    def _boom():
        raise RuntimeError("browser unavailable in unit tests")
    monkeypatch.setattr(psa, "sync_playwright", _boom)


def _sample_sections():
    return [
        {
            "title": "总则", "level": 0, "section_key": "general",
            "content": "<p>正文段落。</p>", "mermaid_svgs": {}, "diagram_svgs": {},
        },
        {
            "title": "组织机构", "level": 0, "section_key": "org",
            "content": "<p>第二章节正文。</p>", "mermaid_svgs": {}, "diagram_svgs": {},
        },
    ]


def test_page_setup_a4_and_unified_margins(no_playwright):
    doc = generate_plan_docx(
        company_name="测试公司", plan_title="测试公司-综合应急预案",
        plan_type="comprehensive", plan_number="ZH-001", version_number="V1",
        sections=_sample_sections(),
    )
    # python-docx 把页面尺寸/边距存成 twips，读回有 ≤1 twip（≈0.0018cm）量化误差，
    # 故用 0.01cm 容差比较（Word 中 A4 即为 11906×16838 twips）。
    for sec in doc.sections:
        assert sec.page_width == pytest.approx(Cm(21), abs=Cm(0.01))
        assert sec.page_height == pytest.approx(Cm(29.7), abs=Cm(0.01))
        assert sec.top_margin == pytest.approx(Cm(3.7), abs=Cm(0.01))
        assert sec.bottom_margin == pytest.approx(Cm(3.5), abs=Cm(0.01))
        assert sec.left_margin == pytest.approx(Cm(2.8), abs=Cm(0.01))
        assert sec.right_margin == pytest.approx(Cm(2.6), abs=Cm(0.01))


def test_cover_doc_title_derived_from_plan_title(no_playwright):
    doc = generate_plan_docx(
        company_name="测试公司", plan_title="测试公司-综合应急预案",
        plan_type="comprehensive", plan_number="ZH-001", version_number="V1",
        sections=_sample_sections(),
    )
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    assert "综合应急预案" in texts
    assert "测试公司-综合应急预案" not in texts
    # 计划原断言无法区分封面标题与正文大标题（正文恒为"综合应急预案"），
    # 补一条断言确保封面不再使用硬编码的"生产安全事故应急预案"。
    assert "生产安全事故应急预案" not in texts


def test_no_debug_print_in_source():
    import inspect
    import app.services.docx_template as m
    src = inspect.getsource(m)
    assert "generate_plan_docx CALLED" not in src


def test_long_list_item_becomes_body_paragraph():
    doc = Document()
    long_text = "这是一个非常长的列表项内容，它超过三十个字符，应当作为正文段落渲染而不是项目符号列表"
    html_to_docx_content(doc, f"<ul><li>{long_text}</li></ul>")
    assert len(doc.paragraphs) == 1
    p = doc.paragraphs[0]
    assert p.style.name != "List Bullet"
    assert p.paragraph_format.first_line_indent == Pt(32)
    assert long_text in p.text


def test_short_list_item_stays_bullet():
    doc = Document()
    html_to_docx_content(doc, "<ul><li>短条目</li></ul>")
    assert doc.paragraphs[0].style.name == "List Bullet"


def test_ordered_short_item_stays_numbered():
    doc = Document()
    html_to_docx_content(doc, "<ol><li>第一步</li></ol>")
    assert doc.paragraphs[0].style.name == "List Number"


def test_build_table_column_widths_not_even():
    doc = Document()
    tbl = build_table(
        doc,
        ["序号", "法律法规及标准名称", "文号/标准号"],
        [["1", "《中华人民共和国安全生产法》及其配套法规标准的完整名称", "主席令第八十八号"]],
    )
    widths = [tbl.cell(0, j).width for j in range(3)]
    assert len(set(widths)) > 1


def test_build_table_header_shading_and_size():
    doc = Document()
    tbl = build_table(doc, ["类别", "名称"], [["法律", "《安全生产法》"]])
    shd = tbl.cell(0, 0)._tc.get_or_add_tcPr().find(qn("w:shd"))
    assert shd is not None and shd.get(qn("w:fill")) == "D9D9D9"
    run = tbl.cell(0, 0).paragraphs[0].runs[0]
    assert run.font.size == Pt(12) and run.bold
    data_run = tbl.cell(1, 1).paragraphs[0].runs[0]
    assert data_run.font.size == Pt(12)
    assert data_run.font.bold is not True


def test_build_table_long_column_left_aligned():
    doc = Document()
    tbl = build_table(
        doc,
        ["类别", "非常长的法规名称列标题用于测试对齐"],
        [["法律", "这是一段很长的标准名称内容，超过六个字，应当左对齐阅读"]],
    )
    from docx.enum.text import WD_ALIGN_PARAGRAPH as WA
    assert tbl.cell(1, 1).paragraphs[0].alignment == WA.LEFT
    assert tbl.cell(1, 0).paragraphs[0].alignment == WA.CENTER


def test_html_table_uses_build_table():
    doc = Document()
    html_to_docx_content(
        doc,
        "<table><tr><th>类别</th><th>名称</th></tr>"
        "<tr><td>法律</td><td>《中华人民共和国安全生产法》</td></tr></table>",
    )
    assert len(doc.tables) == 1
    tbl = doc.tables[0]
    assert tbl.cell(0, 0).paragraphs[0].runs[0].font.size == Pt(12)


def test_toc_field_present(no_playwright):
    doc = generate_plan_docx(
        company_name="测试公司", plan_title="测试公司-综合应急预案",
        plan_type="comprehensive", plan_number="ZH-001", version_number="V1",
        sections=_sample_sections(),
    )
    # 计划原测试只查 body：TOC 域在正文 body 可命中，但 PAGE/NUMPAGES 域位于
    # 页脚部件（w:ftr）而非 body，故合并 body + 各节页脚部件一起收集域。
    flds = list(doc.element.body.findall(".//" + qn("w:fldSimple")))
    for sec in doc.sections:
        flds.extend(sec.footer._element.findall(".//" + qn("w:fldSimple")))
    instrs = [f.get(qn("w:instr")) for f in flds]
    assert any("TOC" in (i or "") for i in instrs)
    assert any((i or "").strip() == "PAGE" for i in instrs)
    assert any((i or "").strip() == "NUMPAGES" for i in instrs)


def test_header_footer_text_and_first_page(no_playwright):
    doc = generate_plan_docx(
        company_name="测试公司", plan_title="测试公司-综合应急预案",
        plan_type="comprehensive", plan_number="ZH-001", version_number="V1",
        sections=_sample_sections(),
    )
    sec = doc.sections[0]
    assert sec.different_first_page_header_footer is True
    assert "测试公司" in sec.header.paragraphs[0].text
    assert "综合应急预案" in sec.header.paragraphs[0].text
    assert "第" in sec.footer.paragraphs[0].text
    assert "共" in sec.footer.paragraphs[0].text


def test_first_level_section_uses_page_break_before(no_playwright):
    doc = generate_plan_docx(
        company_name="测试公司", plan_title="测试公司-综合应急预案",
        plan_type="comprehensive", plan_number="ZH-001", version_number="V1",
        sections=_sample_sections(),
    )
    headings = [p for p in doc.paragraphs if p.text.strip().startswith("1 ") or
                p.text.strip().startswith("2 ")]
    assert headings
    for h in headings:
        assert h.paragraph_format.page_break_before is True


def _placeholder_png() -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buf, format="PNG")
    return buf.getvalue()


class _FakeEl:
    def __init__(self, png):
        self._png = png

    def screenshot(self, type="png"):
        return self._png


class _FakePage:
    def __init__(self, png):
        self._png = png
        self._el = _FakeEl(png)

    def set_content(self, *a, **k):
        pass

    def wait_for_selector(self, *a, **k):
        return True

    def wait_for_timeout(self, *a, **k):
        pass

    def query_selector(self, *a, **k):
        return self._el

    def close(self):
        pass


class _FakeBrowser:
    def __init__(self, png):
        self._png = png

    def new_page(self, **k):
        return _FakePage(self._png)

    def close(self):
        pass


class _FakeChromium:
    def __init__(self, png):
        self._png = png

    def launch(self, *a, **k):
        return _FakeBrowser(self._png)


class _FakePW:
    def __init__(self, png):
        self._png = png
        self.chromium = _FakeChromium(png)

    def start(self):
        return self

    def stop(self):
        pass


@pytest.fixture
def fake_playwright(monkeypatch):
    png = _placeholder_png()
    import playwright.sync_api as psa
    monkeypatch.setattr(psa, "sync_playwright", lambda: _FakePW(png))
    return png


def test_figure_caption_added_after_mermaid_png(fake_playwright):
    sections = [
        {
            "title": "处置措施", "level": 0, "section_key": "measures",
            "content": (
                '<div class="mermaid-rendered" data-mermaid-hash="abc">'
                '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
                '<rect width="100" height="50" fill="#fff"/></svg></div>'
            ),
            "mermaid_svgs": {}, "diagram_svgs": {},
        },
    ]
    doc = generate_plan_docx(
        company_name="测试公司", plan_title="测试公司-综合应急预案",
        plan_type="comprehensive", plan_number="ZH-001", version_number="V1",
        sections=sections,
    )
    captions = [p.text for p in doc.paragraphs if p.style.name == "Caption"]
    assert any("图 1" in t for t in captions)
    assert any("流程图" in t for t in captions)


def test_diagram_caption_map():
    from app.services.docx_template import _diagram_caption
    assert _diagram_caption("evacuation", 1) == "图 1 人员疏散路线示意图"
    assert _diagram_caption("evacuation_3", 2) == "图 2 3层人员疏散路线示意图"
    assert _diagram_caption("unknown", 3) == "图 3 示意图"
