# 应急预案 DOCX 导出排版系统性优化 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将应急预案 DOCX 导出（综合/专项/现场处置）从当前"Letter+硬编码+项目符号错乱"的排版，重构为 GB/T 29639-2020 公文体例（A4+公文边距、样式单一事实源、目录/页眉/页码、优化表格与列表、消除空白页）。

**架构：** 全部格式收敛到 `backend/app/services/docx_template.py` 的 `register_all_styles` 样式表；渲染分支只引用样式，不再逐段硬编码。页面设置统一 A4+3.7/3.5/2.8/2.6cm；封面保留当前版式；列表按长度判定（不超过 30 字转项目符号，超过 30 字转正文）；表格按内容分配列宽+表头底纹；主流程补齐目录域、页眉、页脚页码，一级章节改用 `page_break_before`。

**技术栈：** Python 3、python-docx 1.1.2、pytest、Word COM（验证用，仅本机）。

---

## 文件结构

- 修改：`backend/app/services/docx_template.py` — 全部排版改动（样式常量/注册、页面、封面、列表、表格、目录页眉页脚、分页、图题）
- 创建：`backend/tests/test_docx_layout.py` — 新增排版回归测试（页面/样式/列表/表格/域/分页/图题）
- 不修改：`backend/app/routers/export.py` — 调用签名不变（`generate_plan_docx` 参数兼容）

**commit 纪律：** 工作区存在他人未提交改动（generation.py、plan_diagram_service.py 等 8 个文件）。每个任务 commit 只 `git add` 本任务涉及的 `docx_template.py` 与 `test_docx_layout.py`，**严禁 `git add -A` / `git add .`**。

---

## 任务 1：样式常量与样式注册重构

**文件：**
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_docx_layout.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_docx_layout.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_docx_layout.py -v`
预期：FAIL — ImportError/KeyError（`LI_TEXT_THRESHOLD`、`TABLE_BODY_WIDTH_CM`、`Caption`、`TOC Title` 不存在）

- [ ] **步骤 3：编写最少实现代码**

在 `docx_template.py` 顶部常量区追加：

```python
# 表格/图题/页眉页脚（GB/T 29639 与 PRD-07）
SIZE_TABLE = 12            # 表格文字（小四）
SIZE_CAPTION = 14          # 图题
SIZE_HEADER_FOOTER = 10.5  # 页眉页脚（五号）
LINE_SPACING_BODY = 28     # 正文固定行距（磅）
LINE_SPACING_TABLE = 22    # 表格固定行距（磅）
LI_TEXT_THRESHOLD = 30     # 列表项转正文的字符阈值
TABLE_BODY_WIDTH_CM = 15.6 # 正文区宽（21 - 2.8 - 2.6）
TABLE_COL_MIN_CM = 1.5
TABLE_COL_MAX_CM = 6.0
STYLE_TOC_TITLE = "TOC Title"
```

重构 `register_all_styles` 为（替换现有函数体）：

```python
def register_all_styles(doc: Document):
    """注册所有自定义样式。调用一次即可。"""
    # ── Normal 基准 ──
    normal = doc.styles["Normal"]
    normal.font.name = FONT_TNR
    normal.font.size = Pt(SIZE_NORMAL)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    normal.paragraph_format.line_spacing = Pt(LINE_SPACING_BODY)
    _set_full_fonts(normal, ascii_font=FONT_TNR, ea_font=FONT_FANGSONG)

    # ── 封面标题 / 落款 / 正文大标题 ──
    _define_style(doc, STYLE_COVER_TITLE, font_name=FONT_SONGTI,
                  font_size=SIZE_COVER_TITLE, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_before=0, space_after=0)
    _set_east_asian_font(doc.styles[STYLE_COVER_TITLE], FONT_SONGTI)
    _define_style(doc, STYLE_COVER_SIGN, font_name=FONT_FANGSONG,
                  font_size=SIZE_COVER_SIGN, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_before=0, space_after=0)
    _set_east_asian_font(doc.styles[STYLE_COVER_SIGN], FONT_FANGSONG)
    _define_style(doc, STYLE_BODY_TITLE, font_name=FONT_SONGTI,
                  font_size=SIZE_BODY_TITLE, bold=True,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_before=Pt(24), space_after=Pt(12))
    _set_east_asian_font(doc.styles[STYLE_BODY_TITLE], FONT_SONGTI)

    # ── 标题 1-6：黑体/楷体/仿宋 ──
    headings = [
        ("Heading 1", FONT_HEITI, 28),
        ("Heading 2", FONT_KAITI, 6),
        ("Heading 3", FONT_FANGSONG, 6),
        ("Heading 4", FONT_FANGSONG, 6),
        ("Heading 5", FONT_FANGSONG, 6),
        ("Heading 6", FONT_FANGSONG, 6),
    ]
    for name, font_name, before in headings:
        st = _define_style(doc, name, font_name=font_name, font_size=SIZE_HEADING,
                           bold=True, first_line_indent=FIRST_INDENT_HEADING,
                           space_before=Pt(before), space_after=Pt(0))
        _set_east_asian_font(st, font_name)

    # ── 正文 ──
    bt = _define_style(doc, "Body Text", font_name=FONT_FANGSONG_GB,
                       font_size=SIZE_NORMAL, first_line_indent=FIRST_INDENT_NORMAL)
    _set_east_asian_font(bt, FONT_FANGSONG_GB)
    bt.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    bt.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    bt.paragraph_format.line_spacing = Pt(LINE_SPACING_BODY)

    # ── 图题 / 目录标题 ──
    cap = _define_style(doc, "Caption", font_name=FONT_SONGTI,
                        font_size=SIZE_CAPTION, alignment=WD_ALIGN_PARAGRAPH.CENTER)
    _set_east_asian_font(cap, FONT_SONGTI)
    toc = _define_style(doc, STYLE_TOC_TITLE, font_name=FONT_HEITI,
                        font_size=18, alignment=WD_ALIGN_PARAGRAPH.CENTER)
    _set_east_asian_font(toc, FONT_HEITI)

    # ── IDX-B（保留参考文档兼容） ──
    _define_style(doc, STYLE_IDX_B, font_name=FONT_HK_ZHONGKAI,
                  font_size=SIZE_IDX, first_line_indent=0)
    _set_east_asian_font(doc.styles[STYLE_IDX_B], FONT_HK_ZHONGKAI)

    logger.info("All custom styles registered")
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_docx_layout.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/docx_template.py backend/tests/test_docx_layout.py
git commit -m "style(export): centralize docx styles and constants"
```

---

## 任务 2：A4 纸张与统一公文边距

**文件：**
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_docx_layout.py`

- [ ] **步骤 1：编写失败的测试**

追加到 `test_docx_layout.py`：

```python
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
    for sec in doc.sections:
        assert sec.page_width == Cm(21)
        assert sec.page_height == Cm(29.7)
        assert sec.top_margin == Cm(3.7)
        assert sec.bottom_margin == Cm(3.5)
        assert sec.left_margin == Cm(2.8)
        assert sec.right_margin == Cm(2.6)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_page_setup_a4_and_unified_margins -v`
预期：FAIL — 页面为 21.59×27.94cm（Letter），正文节边距 3.18/2.54

- [ ] **步骤 3：编写最少实现代码**

在 `generate_plan_docx` 中，把第一节设置替换为：

```python
    # 2) 页面：A4 + 公文边距，全文统一
    first_section = doc.sections[0]
    set_page_margins(first_section,
                     MARGIN_COVER_LEFT, MARGIN_COVER_RIGHT,
                     MARGIN_COVER_TOP, MARGIN_COVER_BOTTOM)
    first_section.page_width = Cm(21)
    first_section.page_height = Cm(29.7)
```

并把正文节创建从 `add_section(doc, MARGIN_BODY_LEFT, MARGIN_BODY_RIGHT, MARGIN_BODY_TOP, MARGIN_BODY_BOTTOM)` 改为：

```python
    add_section(doc, MARGIN_COVER_LEFT, MARGIN_COVER_RIGHT,
                MARGIN_COVER_TOP, MARGIN_COVER_BOTTOM)
```

`add_section` 内部会把页面尺寸复制到新节，且会调用 `set_page_margins`；确认新节 page_width/page_height 为 A4，若不是则在新节上同样显式设置。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_page_setup_a4_and_unified_margins -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/docx_template.py backend/tests/test_docx_layout.py
git commit -m "fix(export): use A4 and unified GB/T margins for plan docx"
```

---

## 任务 3：封面标题参数化 + 删除调试残留

**文件：**
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_docx_layout.py`

- [ ] **步骤 1：编写失败的测试**

追加到 `test_docx_layout.py`：

```python
def test_cover_doc_title_derived_from_plan_title(no_playwright):
    doc = generate_plan_docx(
        company_name="测试公司", plan_title="测试公司-综合应急预案",
        plan_type="comprehensive", plan_number="ZH-001", version_number="V1",
        sections=_sample_sections(),
    )
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    assert "综合应急预案" in texts
    assert "测试公司-综合应急预案" not in texts


def test_no_debug_print_in_source():
    import inspect
    import app.services.docx_template as m
    src = inspect.getsource(m)
    assert "generate_plan_docx CALLED" not in src
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_cover_doc_title_derived_from_plan_title tests/test_docx_layout.py::test_no_debug_print_in_source -v`
预期：FAIL — 封面 doc_title 仍为固定"生产安全事故应急预案"；源码含调试 print

- [ ] **步骤 3：编写最少实现代码**

在 `generate_plan_docx` 中，把调用 `build_cover` 前增加标题推导：

```python
    # 封面标题：plan_title 去掉企业名前缀，避免重复
    doc_title = plan_title or ""
    if doc_title.startswith(company_name):
        doc_title = doc_title[len(company_name):].lstrip("-— ")
    if not doc_title:
        doc_title = body_title

    build_cover(doc,
                plan_number=plan_number,
                version_number=version_number,
                company_name=company_name,
                doc_title=doc_title,
                signature_company=company_name)
```

删除函数开头两行调试残留（`import builtins` 与 `builtins.print("!!! generate_plan_docx CALLED !!!", flush=True)`）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_docx_layout.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/docx_template.py backend/tests/test_docx_layout.py
git commit -m "fix(export): derive cover title from plan title, drop debug print"
```

---

## 任务 4：列表长短判定（消除长段落变项目符号）

**文件：**
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_docx_layout.py`

- [ ] **步骤 1：编写失败的测试**

追加到 `test_docx_layout.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_long_list_item_becomes_body_paragraph -v`
预期：FAIL — 长条目仍为 `List Bullet` 样式

- [ ] **步骤 3：编写最少实现代码**

替换 `html_to_docx_content` 的 `ul`/`ol` 分支为：

```python
        elif tag in ("ul", "ol"):
            style_name = "List Bullet" if tag == "ul" else "List Number"
            for li in element.find_all("li", recursive=False):
                text = li.get_text().strip()
                if not text:
                    continue
                if len(text) <= LI_TEXT_THRESHOLD:
                    p = doc.add_paragraph(text, style=style_name)
                    p.paragraph_format.left_indent = Cm(1.0)
                    p.paragraph_format.first_line_indent = Cm(-0.5)
                else:
                    p = doc.add_paragraph()
                    p.paragraph_format.first_line_indent = Pt(FIRST_INDENT_NORMAL)
                    _add_inline_runs(p, li)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_long_list_item_becomes_body_paragraph tests/test_docx_layout.py::test_short_list_item_stays_bullet tests/test_docx_layout.py::test_ordered_short_item_stays_numbered -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/docx_template.py backend/tests/test_docx_layout.py
git commit -m "fix(export): route long list items to body paragraphs"
```

---

## 任务 5：表格渲染重构（列宽分配 / 表头底纹 / 12pt / 对齐）

**文件：**
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_docx_layout.py`

- [ ] **步骤 1：编写失败的测试**

追加到 `test_docx_layout.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_docx_layout.py -k table -v`
预期：FAIL — 列宽均分、表头无底纹、字号 10.5pt、全居中

- [ ] **步骤 3：编写最少实现代码**

在 `docx_template.py` 的表格构建区新增辅助函数并重写 `build_table`：

```python
def _char_units(text) -> float:
    """估算文本宽度单位：中文 1 单位，西文/数字 0.5 单位。"""
    return max(sum(1.0 if ord(ch) > 0x2E80 else 0.5 for ch in str(text)), 1.0)


def _compute_col_widths(headers, rows, total_cm=TABLE_BODY_WIDTH_CM):
    units = []
    for j, h in enumerate(headers):
        u = _char_units(h)
        for row in rows:
            if j < len(row):
                u = max(u, _char_units(row[j]))
        units.append(u)
    total = sum(units) or len(units)
    widths = [u / total * total_cm for u in units]
    widths = [max(TABLE_COL_MIN_CM, min(TABLE_COL_MAX_CM, w)) for w in widths]
    s = sum(widths)
    if s:
        widths = [w / s * total_cm for w in widths]
    return widths


def _shade_cell(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{fill}"/>')
        tcPr.append(shd)
    else:
        shd.set(qn("w:fill"), fill)


def build_table(doc: Document, headers: list[str], rows: list[list[str]],
                col_widths: list[float] | None = None):
    """构建标准格式表格：内容分配列宽、表头底纹、12pt、长短列对齐。"""
    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths = col_widths or _compute_col_widths(headers, rows)

    # 表头
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.width = Cm(widths[j])
        cell.text = h
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            p.paragraph_format.line_spacing = Pt(LINE_SPACING_TABLE)
            for r in p.runs:
                r.font.name = FONT_FANGSONG
                r.font.size = Pt(SIZE_TABLE)
                r.bold = True
                _set_east_asian_font_in_run(r, FONT_FANGSONG)
        _shade_cell(cell, "D9D9D9")

    # 数据行
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            if j >= len(headers):
                break
            cell = table.cell(i + 1, j)
            cell.width = Cm(widths[j])
            cell.text = str(val) if val is not None else ""
            col_units = max(_char_units(headers[j]),
                            max((_char_units(r[j]) for r in rows), default=1.0))
            align = (WD_ALIGN_PARAGRAPH.CENTER if col_units <= 6
                     else WD_ALIGN_PARAGRAPH.LEFT)
            for p in cell.paragraphs:
                p.alignment = align
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
                p.paragraph_format.line_spacing = Pt(LINE_SPACING_TABLE)
                for r in p.runs:
                    r.font.name = FONT_FANGSONG
                    r.font.size = Pt(SIZE_TABLE)
                    _set_east_asian_font_in_run(r, FONT_FANGSONG)

    return table
```

并把 `html_to_docx_content` 的 `table` 分支整体替换为调用 `build_table`：

```python
        elif tag == "table":
            rows = element.find_all("tr")
            if not rows:
                continue

            def _cells(row_el):
                return [c.get_text().strip() for c in row_el.find_all(["th", "td"])]

            headers = _cells(rows[0])
            if not headers:
                continue
            data_rows = [_cells(r) for r in rows[1:]]
            build_table(doc, headers, data_rows)
            doc.add_paragraph("")
```

（原分支中表格后的空段落保留在 `build_table` 调用之后。）

同时更新 `build_signature_page`：在其表头循环（`for j, h in enumerate(headers)`）内、设置完字体后追加一行 `_shade_cell(cell, "D9D9D9")`，使签署页表头与正文表格风格一致（12pt、底纹）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_docx_layout.py -k table -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/docx_template.py backend/tests/test_docx_layout.py
git commit -m "feat(export): content-aware table widths, shaded headers, 12pt"
```

---

## 任务 6：目录页 + 页眉页脚

**文件：**
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_docx_layout.py`

- [ ] **步骤 1：编写失败的测试**

追加到 `test_docx_layout.py`：

```python
def test_toc_field_present(no_playwright):
    doc = generate_plan_docx(
        company_name="测试公司", plan_title="测试公司-综合应急预案",
        plan_type="comprehensive", plan_number="ZH-001", version_number="V1",
        sections=_sample_sections(),
    )
    flds = doc.element.body.findall(".//" + qn("w:fldSimple"))
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_toc_field_present tests/test_docx_layout.py::test_header_footer_text_and_first_page -v`
预期：FAIL — 无 TOC 域、无 PAGE/NUMPAGES 域、页眉页脚为空

- [ ] **步骤 3：编写最少实现代码**

在 `docx_template.py` 新增两个函数（放在 `build_cover` 之后）：

```python
def add_toc(doc: Document):
    """插入目录页：黑体 18pt 标题 + TOC 域（Word/WPS 打开后 F9 刷新）。"""
    p = doc.add_paragraph("目　　录", style=STYLE_TOC_TITLE)
    p.paragraph_format.space_after = Pt(24)
    toc_p = doc.add_paragraph()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), r'TOC \o "1-3" \h \z \u')
    run_el = OxmlElement("w:r")
    t_el = OxmlElement("w:t")
    t_el.text = "（打开文档后按 F9 刷新目录）"
    run_el.append(t_el)
    fld.append(run_el)
    toc_p._p.append(fld)
    doc.add_page_break()


def _setup_header_footer(doc: Document, company_name: str, plan_title: str):
    """页眉=企业名+预案标题；页脚=第 X 页 共 Y 页；封面首页不显示。"""
    sec = doc.sections[0]
    sec.different_first_page_header_footer = True

    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = hp.add_run(f"{company_name}　{plan_title}")
    r.font.size = Pt(SIZE_HEADER_FOOTER)
    _set_east_asian_font_in_run(r, FONT_SONGTI)

    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _footer_run(text=""):
        run = fp.add_run(text)
        run.font.size = Pt(SIZE_HEADER_FOOTER)
        _set_east_asian_font_in_run(run, FONT_SONGTI)
        return run

    def _field(instr):
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), instr)
        run_el = OxmlElement("w:r")
        t_el = OxmlElement("w:t")
        t_el.text = "1"
        run_el.append(t_el)
        fld.append(run_el)
        fp._p.append(fld)

    _footer_run("第 ")
    _field("PAGE")
    _footer_run(" 页 共 ")
    _field("NUMPAGES")
    _footer_run(" 页")
```

在 `generate_plan_docx` 中，签署页之后、正文节创建之前插入目录页，并在正文节创建后设置页眉页脚：

```python
    # 3) 签署页（保留）
    if signers:
        build_signature_page(doc, signers)

    # 4) 目录页（批准页/签署页之后、正文节之前）
    add_toc(doc)

    # 5) 正文节（统一边距）
    add_section(doc, MARGIN_COVER_LEFT, MARGIN_COVER_RIGHT,
                MARGIN_COVER_TOP, MARGIN_COVER_BOTTOM)
    body_section = doc.sections[-1]
    body_section.header.is_linked_to_previous = True
    body_section.footer.is_linked_to_previous = True

    # 6) 页眉页脚（封面节，首页不显示）
    _setup_header_footer(doc, company_name, plan_title)
```

注意：`_setup_header_footer` 必须放在所有节创建完成之后执行，确保 `doc.sections[0]` 与正文节都存在。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_toc_field_present tests/test_docx_layout.py::test_header_footer_text_and_first_page -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/docx_template.py backend/tests/test_docx_layout.py
git commit -m "feat(export): add toc field, header and page-number footer"
```

---

## 任务 7：一级章节分页改用 page_break_before

**文件：**
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_docx_layout.py`

- [ ] **步骤 1：编写失败的测试**

追加到 `test_docx_layout.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_first_level_section_uses_page_break_before -v`
预期：FAIL — 一级章节仍用循环末尾手动分页，标题段无 `page_break_before`

- [ ] **步骤 3：编写最少实现代码**

在 `generate_plan_docx` 章节循环中，标题写入处改为：

```python
        # 写标题（含编号）
        section_level = level
        heading_level = min(level + 1, 6)
        num = sec_numbers.get(idx, "")
        numbered_title = f"{num} {title}" if num else title
        heading = add_heading(doc, numbered_title, heading_level)
        if section_level == 1:
            heading.paragraph_format.page_break_before = True
```

并删除循环末尾的两行手动分页（`if section_level == 1: doc.add_page_break()` 及其上方注释），替换为说明注释：一级章节分页由标题段 `page_break_before` 承担，避免满页产生空白页。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_first_level_section_uses_page_break_before -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/docx_template.py backend/tests/test_docx_layout.py
git commit -m "fix(export): page-break-before for level-1 headings to avoid blank pages"
```

---

## 任务 8：图片图题（Mermaid 图与疏散图）

**文件：**
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_docx_layout.py`

- [ ] **步骤 1：编写失败的测试**

追加到 `test_docx_layout.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_figure_caption_added_after_mermaid_png tests/test_docx_layout.py::test_diagram_caption_map -v`
预期：FAIL — 无 Caption 段落、`_diagram_caption` 不存在

- [ ] **步骤 3：编写最少实现代码**

在 `docx_template.py` 常量区追加：

```python
DIAGRAM_CAPTION_MAP = {
    "evacuation": "人员疏散路线示意图",
    "rescue": "应急救援路线示意图",
    "risk_distribution": "风险分布示意图",
    "floor": "楼层平面示意图",
}
```

新增函数（放在 `build_table` 之后）：

```python
def _diagram_caption(key: str, figure_no: int) -> str:
    """根据 diagram_svgs 的 key 生成图题文本。"""
    if key.startswith("evacuation_"):
        floor_no = key.split("_", 1)[1]
        name = f"{floor_no}层人员疏散路线示意图"
    else:
        name = DIAGRAM_CAPTION_MAP.get(key, "示意图")
    return f"图 {figure_no} {name}"
```

在 `generate_plan_docx` 中：

1. 函数开头（`sections_data` 之前）加图号计数器：

```python
    figure_no = 0
```

2. Mermaid PNG 插入处（`if png_bytes:` 块内）加图题：

```python
            if png_bytes:
                img_stream = io.BytesIO(png_bytes)
                doc.add_picture(img_stream, width=Cm(14.6))
                if doc.paragraphs:
                    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                figure_no += 1
                doc.add_paragraph(f"图 {figure_no} 流程图", style="Caption")
```

3. 疏散图 PNG 插入处（`if png_bytes:` 块内）加图题：

```python
            if png_bytes:
                img_stream = io.BytesIO(png_bytes)
                doc.add_picture(img_stream, width=Cm(14.6))
                if doc.paragraphs:
                    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                figure_no += 1
                doc.add_paragraph(_diagram_caption(key, figure_no), style="Caption")
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_docx_layout.py::test_figure_caption_added_after_mermaid_png tests/test_docx_layout.py::test_diagram_caption_map -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/docx_template.py backend/tests/test_docx_layout.py
git commit -m "feat(export): add centered figure captions for diagrams"
```

---

## 任务 9：真实样本集成验证（Word 转 PDF 回归）

**文件：**
- 临时：`backend/exports/_layout_verify.py`（一次性脚本，验证后删除）
- 不修改源码

- [ ] **步骤 1：构造覆盖性样本并生成 DOCX**

创建 `backend/exports/_layout_verify.py`（一次性脚本，项目惯例 `_*.py` 不入 commit）：

```python
"""docx 排版优化集成验证：构造覆盖性样本 → 生成 docx → 输出到 exports/。"""
from app.services.docx_template import generate_plan_docx

sections = [
    {
        "title": "总则", "level": 0, "section_key": "general",
        "content": (
            "<p>本预案依据下列法律法规、标准及文件编制。</p>"
            "<table><tr><th>类别</th><th>法律法规及标准名称</th><th>文号/标准号</th></tr>"
            "<tr><td>法律</td><td>《中华人民共和国安全生产法》</td><td>主席令第八十八号</td></tr>"
            "<tr><td>标准</td><td>《生产经营单位生产安全事故应急预案编制导则》</td><td>GB/T 29639-2020</td></tr></table>"
            "<ul><li>短条目一</li><li>短条目二</li></ul>"
            "<ul><li>这是一个非常长的列表项内容，它超过三十个字符，应当作为正文段落渲染而不是项目符号列表</li></ul>"
        ),
        "mermaid_svgs": {}, "diagram_svgs": {},
    },
    {
        "title": "事故风险", "level": 0, "section_key": "risk",
        "content": "<p>第二章正文：描述主要事故风险类型与等级。</p>",
        "mermaid_svgs": {}, "diagram_svgs": {},
    },
    {
        "title": "组织机构", "level": 0, "section_key": "org",
        "content": "<p>第三章正文：应急组织机构及职责。</p>",
        "mermaid_svgs": {}, "diagram_svgs": {},
    },
]

doc = generate_plan_docx(
    company_name="验证测试企业",
    plan_title="验证测试企业-综合应急预案",
    plan_type="comprehensive",
    plan_number="YZ-001",
    version_number="V1.0",
    sections=sections,
)
doc.save(r"backend/exports/_layout_verify.docx")
print("saved backend/exports/_layout_verify.docx")
```

运行：`cd backend && python exports/_layout_verify.py`
预期：`saved backend/exports/_layout_verify.docx`，无异常

- [ ] **步骤 2：Word COM 转 PDF**

PowerShell 运行：

```powershell
$word = New-Object -ComObject Word.Application
$word.Visible = $false; $word.DisplayAlerts = 0
$doc = $word.Documents.Open("backend/exports/_layout_verify.docx", $false, $true)
$doc.ExportAsFixedFormat("backend/exports/_layout_verify.pdf", 17)
$doc.Close($false); $word.Quit()
```

预期：生成 `_layout_verify.pdf`，无错误

- [ ] **步骤 3：断言空白页与骨架**

运行：

```powershell
python -c "
import pymupdf
doc = pymupdf.open(r'backend/exports/_layout_verify.pdf')
empty = [i for i in range(len(doc)) if not doc[i].get_text().strip()]
print('pages:', len(doc), 'empty:', empty)
assert not empty, f'blank pages found: {empty}'
t_all = ' '.join(doc[i].get_text() for i in range(min(len(doc), 8)))
assert '目' in t_all, 'TOC missing'
assert '第' in t_all, 'footer missing'
print('OK: no blank pages, TOC/footer present')
"
```

预期：`pages: N empty: []` 与 `OK: no blank pages, TOC/footer present`

- [ ] **步骤 4：全量后端测试零回归**

运行：`cd backend && python -m pytest tests/ -q`
预期：全量 PASS（基线 1055 + 新增 test_docx_layout 用例），零回归

- [ ] **步骤 5：人工验收 + 清理临时文件**

用 Word 打开 `backend/exports/_layout_verify.docx`，确认：封面结构照旧、目录 F9 可刷新、页眉页脚显示、表格列宽合理、长列表项为正文、无空白页。验收通过后删除 `_layout_verify.py/_layout_verify.docx/_layout_verify.pdf`。

---
