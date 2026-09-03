# 报告 Word 导出统一复用预案公文版式 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 风险评估报告与应急资源调查报告的 Word 导出改为复用预案 docx 公文样式引擎，视觉与预案导出一致。

**架构：** 新增 `backend/app/services/report_docx.py`，内部复用 `docx_template.py` 的 `register_all_styles` / `add_section` / `add_body_title` / `add_heading` / `_setup_header_footer` / `html_to_docx_content` 等能力，输出公文版式报告；risk/resource 两个 export 端点仅替换“生成 Document”部分。

**技术栈：** python-docx、markdown、BeautifulSoup；测试 pytest；执行环境 docker 容器 `emergency-plan-backend`（代码 bind mount `backend/app`，测试文件需 `docker cp` 到 `/app/tests`）。

规格文档：`docs/superpowers/specs/2026-09-03-report-docx-format-design.md`

---

## 文件结构

- 创建 `backend/app/services/report_docx.py`：报告版式生成器（封面、正文节、页眉页码、章节、内容清洗/转换、可选本地图片嵌入）。
- 创建 `backend/tests/test_report_docx_format.py`：生成器单元测试（封面/样式/分页/表格/清洗/kind 文案）。
- 修改 `backend/app/routers/risk_assessment.py`：export 端点调用生成器（删除手写 Document 与 `_render_content_to_docx` 路径）。
- 修改 `backend/app/routers/resource_investigation.py`：export 端点调用生成器。
- 不动：`docx_template.py`、`_clean_for_docx`（保留原位，生成器函数内延迟 import 复用）、DB、前端。

---

### 任务 1：新增报告 DOCX 生成器 + 格式单元测试

**文件：**
- 创建：`backend/app/services/report_docx.py`
- 测试：`backend/tests/test_report_docx_format.py`

- [ ] **步骤 1：编写失败的测试**

`backend/tests/test_report_docx_format.py`：

```python
"""报告 docx 公文版式生成器单元测试。"""
import io
import re

from docx import Document

from app.services.report_docx import generate_report_docx


def _doc(kind="risk", chapters=None):
    buf = io.BytesIO()
    doc = generate_report_docx(
        company_name="西安宝岳空间科技有限公司",
        report_kind=kind,
        chapters=chapters or [
            {"key": "ch1", "title": "一、危险有害因素辨识分析",
             "content": "正文第一段。\n\n**加粗** 内容。\n\n"
                        "| 序号 | 名称 |\n| --- | --- |\n| 1 | 干粉灭火器 |\n"
                        '\n<table border="1"><tr><th>等级</th><th>描述</th></tr>'
                        '<tr><td>低</td><td>可控</td></tr></table>\n'
                        "```mermaid\nflowchart LR\nA-->B\n```\n"
                        '{"overall_assessment": "尾随JSON"}'),
            {"key": "ch2", "title": "二、危险有害因素辨识汇总", "content": "第二章内容。"},
        ],
    )
    doc.save(buf)
    buf.seek(0)
    return Document(buf)


def test_cover_contains_company_and_kind_title_without_approval_page():
    doc = _doc()
    texts = [p.text for p in doc.paragraphs]
    joined = "\n".join(texts)
    assert "西安宝岳空间科技有限公司" in joined
    assert "生产安全事故风险评估报告" in joined
    assert "批准页" not in joined


def test_resource_kind_uses_resource_title():
    doc = _doc(kind="resource")
    assert any("应急资源调查报告" in p.text for p in doc.paragraphs)


def test_chapter_headings_present():
    doc = _doc()
    heading_texts = [p.text for p in doc.paragraphs if p.style.name == "Heading 1"]
    assert "一、危险有害因素辨识分析" in heading_texts
    assert "二、危险有害因素辨识汇总" in heading_texts


def test_clean_removes_mermaid_and_trailing_json():
    doc = _doc()
    joined = "\n".join(p.text for p in doc.paragraphs)
    assert "flowchart" not in joined
    assert "尾随JSON" not in joined
    assert "overall_assessment" not in joined


def test_markdown_and_html_tables_become_docx_tables():
    doc = _doc()
    assert len(doc.tables) >= 2
    table_text = "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    assert "干粉灭火器" in table_text
    assert "可控" in table_text


def test_first_chapter_heading_has_page_break_before():
    doc = _doc()
    for p in doc.paragraphs:
        if p.style.name == "Heading 1" and "一、" in p.text:
            assert p.paragraph_format.page_break_before is True
            return
    raise AssertionError("未找到分页的一级标题")
```

- [ ] **步骤 2：运行测试确认失败**

```bash
docker cp backend/tests/test_report_docx_format.py emergency-plan-backend:/app/tests/test_report_docx_format.py
docker exec emergency-plan-backend python -m pytest tests/test_report_docx_format.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.report_docx'`。

- [ ] **步骤 3：实现 `backend/app/services/report_docx.py`**

```python
"""报告（风险评估/应急资源调查）DOCX 公文版式生成器。

复用 docx_template 的预案样式引擎，产出与应急预案一致的版式：
封面（企业名+报告名+日期）→ 页眉页码 → 正文大标题 → 黑体一级标题分页 →
仿宋 16pt 正文 + 规范表格。不含预案“批准页/发布页”。
"""

import io
import logging
import re
from datetime import datetime

import markdown
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.services.docx_template import (
    FIRST_INDENT_NORMAL,
    FONT_HEITI,
    FONT_SONGTI,
    MARGIN_COVER_BOTTOM,
    MARGIN_COVER_LEFT,
    MARGIN_COVER_RIGHT,
    MARGIN_COVER_TOP,
    STYLE_COVER_SIGN,
    STYLE_COVER_TITLE,
    add_body_title,
    add_heading,
    add_normal_paragraph,
    add_section,
    html_to_docx_content,
    register_all_styles,
    set_page_margins,
    _set_east_asian_font_in_run,
    _setup_header_footer,
)

logger = logging.getLogger(__name__)

REPORT_KIND_TITLES = {
    "risk": "生产安全事故风险评估报告",
    "resource": "应急资源调查报告",
}


def _build_report_cover(doc, company_name: str, report_label: str):
    """封面：企业名 + 报告名 + 落款日期（不含预案批准页）。"""
    for _ in range(3):
        doc.add_paragraph("")
    p = doc.add_paragraph(company_name, style=STYLE_COVER_TITLE)
    doc.add_paragraph(report_label, style=STYLE_COVER_TITLE)
    for _ in range(2):
        doc.add_paragraph("")
    sig = doc.add_paragraph(company_name, style=STYLE_COVER_SIGN)
    for run in sig.runs:
        run.font.name = FONT_HEITI
        _set_east_asian_font_in_run(run, FONT_HEITI)
    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = date_p.add_run(datetime.now().strftime("%Y年%m月"))
    r.font.name = FONT_HEITI
    r.font.size = Pt(18)
    _set_east_asian_font_in_run(r, FONT_HEITI)
    doc.add_page_break()


def _clean_chapter(content: str) -> str:
    """复用风险路由清洗（去 Markdown 表格残留/mermaid/尾随 JSON 等）。"""
    from app.routers.risk_assessment import _clean_for_docx
    return _clean_for_docx(content or "")


def _split_fallback_chapters(content: str) -> list[dict]:
    """summary 无 chapters 时按 '## 标题' 切分兜底。"""
    lines = (content or "").splitlines()
    chapters = []
    cur_title = None
    cur_body = []

    def flush():
        if cur_title is not None:
            chapters.append({"title": cur_title, "content": "\n".join(cur_body).strip()})

    for line in lines:
        m = re.match(r"^#{1,4}\s+(.+)$", line.strip())
        if m and cur_title is None:
            cur_title = m.group(1).strip()
            continue
        if m and cur_title is not None:
            flush()
            cur_title = m.group(1).strip()
            cur_body = []
            continue
        cur_body.append(line)
    flush()
    return chapters


def _embed_local_image(doc, src: str):
    """把 /uploads/... 本地图嵌入 docx；失败返回 False。"""
    from app.main import UPLOAD_DIR
    path = src
    if src.startswith("/uploads/"):
        path = str(UPLOAD_DIR) + src[len("/uploads"):]
    try:
        with open(path, "rb") as f:
            doc.add_picture(io.BytesIO(f.read()), width=Cm(14.6))
        if doc.paragraphs:
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        return True
    except Exception:
        return False


def generate_report_docx(
    *,
    company_name: str,
    report_kind: str,
    chapters: list[dict],
    report_title: str = "",
) -> Document:
    """生成公文版式报告 DOCX。"""
    report_label = REPORT_KIND_TITLES.get(report_kind, report_title or "调查报告")
    doc = Document()
    register_all_styles(doc)

    first = doc.sections[0]
    set_page_margins(first, MARGIN_COVER_LEFT, MARGIN_COVER_RIGHT,
                     MARGIN_COVER_TOP, MARGIN_COVER_BOTTOM)
    first.page_width = Cm(21)
    first.page_height = Cm(29.7)

    _build_report_cover(doc, company_name, report_label)
    add_section(doc, MARGIN_COVER_LEFT, MARGIN_COVER_RIGHT,
                MARGIN_COVER_TOP, MARGIN_COVER_BOTTOM)
    body_section = doc.sections[-1]
    body_section.header.is_linked_to_previous = True
    body_section.footer.is_linked_to_previous = True
    _setup_header_footer(doc, company_name, report_label)
    add_body_title(doc, report_label)

    for ch in chapters:
        title = (ch.get("title") or "").strip()
        content = (ch.get("content") or "").strip()
        if not title and not content:
            continue
        if title:
            heading = add_heading(doc, title, 1)
            heading.paragraph_format.page_break_before = True
        if not content:
            continue
        cleaned = _clean_chapter(content)
        html = markdown.markdown(cleaned, extensions=["tables", "fenced_code", "md_in_html"])
        # 正文内 <img src="/uploads/..."> 本地嵌入；失败降级为文字占位
        for m in re.finditer(r'<img[^>]*src="(/uploads/[^"]+)"', html):
            if not _embed_local_image(doc, m.group(1)):
                add_normal_paragraph(doc, "【图片：%s 嵌入失败】" % m.group(1))
        html = re.sub(r'<img[^>]*src="/uploads/[^"]+"[^>]*/?>', "", html)
        html_to_docx_content(doc, html, base_level=1)

    return doc
```

> 注：`_set_east_asian_font_in_run` 为 `docx_template.py:373` 模块级函数，可直接 import；上传根目录用 `app.main.UPLOAD_DIR`（对应容器 `/app/uploads`），不以 `settings` 读取。

- [ ] **步骤 4：运行测试确认通过**

```bash
docker exec emergency-plan-backend python -m pytest tests/test_report_docx_format.py -q
```

预期：PASS（若某个断言暴露真实差异，则修实现而非改断言）。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/report_docx.py backend/tests/test_report_docx_format.py
git commit -m "feat(report): add plan-style docx builder for risk/resource reports"
```

---

### 任务 2：risk export 端点接入生成器

**文件：**
- 修改：`backend/app/routers/risk_assessment.py` export 端点（约 420-525 行区域）

- [ ] **步骤 1：先写/更新回归断言**

在 `backend/tests/test_report_docx_format.py` 增加一个纯函数级断言（验证“章节优先取 summary.chapters”）：

```python
def test_builder_uses_chapters_argument():
    doc = _doc(chapters=[{"key": "only", "title": "唯一章节", "content": "只有一章"}])
    assert sum(1 for p in doc.paragraphs if p.style.name == "Heading 1") == 1
```

运行同任务 1 命令确认仍绿。

- [ ] **步骤 2：替换 export 端点正文**

保留企业/报告查询、`os.makedirs(settings.EXPORT_DIR, exist_ok=True)`、`filename`、`FileResponse`；删除手写 `doc = Document()`…`_render_content_to_docx(doc, report.content)` 段，替换为：

```python
    from app.services.report_docx import generate_report_docx

    chapters = (report.summary or {}).get("chapters") or []
    doc = generate_report_docx(
        company_name=ent.name,
        report_kind="risk",
        chapters=chapters,
        report_title=report.title or "生产安全事故风险评估报告",
    )
```

并保留其后 `doc.save(path)` / `FileResponse(...)`。

- [ ] **步骤 3：后端 import 冒烟 + 相关回归**

```bash
docker exec emergency-plan-backend python -c "import app.routers.risk_assessment; print('ok')"
docker exec emergency-plan-backend python -m pytest tests/test_report_docx_format.py tests/test_report_docx_clean.py tests/test_report_versions.py tests/test_report_skip.py -q
```

预期：全绿。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/routers/risk_assessment.py
git commit -m "feat(report): risk assessment export uses plan-style docx"
```

---

### 任务 3：resource export 端点接入生成器

**文件：**
- 修改：`backend/app/routers/resource_investigation.py` export 端点（约 260-285 行区域）

- [ ] **步骤 1：替换 export 端点正文**

保留查询/文件名/FileResponse；删除手写 Document 段，替换为：

```python
    from app.services.report_docx import generate_report_docx

    chapters = (report.summary or {}).get("chapters") or []
    doc = generate_report_docx(
        company_name=ent.name,
        report_kind="resource",
        chapters=chapters,
        report_title=report.title or "应急资源调查报告",
    )
```

- [ ] **步骤 2：import 冒烟 + 相关回归**

```bash
docker exec emergency-plan-backend python -c "import app.routers.resource_investigation; print('ok')"
docker exec emergency-plan-backend python -m pytest tests/test_report_docx_format.py tests/test_report_versions.py tests/test_report_skip.py -q
```

预期：全绿。

- [ ] **步骤 3：Commit**

```bash
git add backend/app/routers/resource_investigation.py
git commit -m "feat(report): resource investigation export uses plan-style docx"
```

---

### 任务 4：真实数据冒烟与收尾

**文件：** 无新代码

- [ ] **步骤 1：对已完成行真实导出**

用本地 JWT（用户 9afddfc7-87a1-4aa1-80c1-22693cbd2144，企业 94804158-cc33-464d-9aef-025ec90226be）调用：

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/enterprises/94804158-cc33-464d-9aef-025ec90226be/risk-assessment/export -o /tmp/ra.docx
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/enterprises/94804158-cc33-464d-9aef-025ec90226be/resource-investigation/export -o /tmp/ri.docx
```

用 python-docx 检查：正文段落数 >0、Heading 1 数量 == 章节数、`批准页` 不存在、含页眉/页脚字段。

- [ ] **步骤 2：重启 backend 并健康检查**

```bash
docker restart emergency-plan-backend
docker exec emergency-plan-backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/health').status)"
```

预期：200。

- [ ] **步骤 3：更新 TASKS.md 快照**（不 commit）

记录：已完成方案 A、生成器文件、测试数量、冒烟结果、遗留（docx 视觉核对需用户在 Word/WPS 打开确认）。

---

## 自检结论

- 规格覆盖：封面/正文大标题/页眉页码/标题分页/仿宋正文/表格/清洗（任务 1）；两端点接入（任务 2/3）；真实冒烟（任务 4）。
- 无占位符；类型/命名跨任务一致（`generate_report_docx`、`chapters`、`report_kind`）。
- 已知未覆盖（规格已声明“增强项”）：`<img>` 嵌入失败不阻塞；docx 模板引擎本身不动。
