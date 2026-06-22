# PRD-07：文档导出模块

> **版本**：1.0 | **创建日期**：2026-06-05 | **依赖**：PRD-00, PRD-01, PRD-05

---

## 1. 模块概述

将已完成的预案项目按 **GB/T 29639-2020 公文格式**导出为 `.docx` 文件，同时提供 HTML 在线预览。这是用户交付最终成果的出口。

**核心能力**：
- Word (.docx) 导出，严格遵循公文排版规范
- HTML 在线预览（模拟 Word 排版效果）
- 封面、批准页、目录、正文、附件完整结构
- Markdown 章节内容 → Word 段落转换
- 企业数据表格自动生成（风险源清单、资源清单、组织架构表）
- 导出前合规校验（必填章节检查）
- 异步导出支持（大文档通过 Celery 后台生成）

---

## 2. 导出格式规范（GB/T 29639-2020）

### 2.1 页面设置

| 属性 | 值 |
|------|-----|
| 纸张 | A4 (210mm × 297mm) |
| 上边距 | 3.7 cm |
| 下边距 | 3.5 cm |
| 左边距 | 2.8 cm |
| 右边距 | 2.6 cm |

### 2.2 字体与段落

| 元素 | 字体 | 字号 | 加粗 | 对齐 | 行距 |
|------|------|------|------|------|------|
| 封面预案标题 | 黑体 | 二号 (22pt) | 是 | 居中 | 单倍 |
| 封面副标题 | 仿宋 | 三号 (16pt) | 否 | 居中 | 单倍 |
| 一级标题 | 黑体 | 三号 (16pt) | 是 | 两端对齐 | 固定 28 磅 |
| 二级标题 | 楷体 | 三号 (16pt) | 是 | 两端对齐 | 固定 28 磅 |
| 三级标题 | 仿宋 | 三号 (16pt) | 是 | 两端对齐 | 固定 28 磅 |
| 正文 | 仿宋 | 三号 (16pt) | 否 | 两端对齐 | 固定 28 磅 |
| 表格内文字 | 仿宋 | 小四 (12pt) | 否 | — | 固定 22 磅 |
| 表头文字 | 仿宋 | 小四 (12pt) | 是 | 居中 | 固定 22 磅 |
| 页眉 | 宋体 | 五号 (10.5pt) | 否 | 居中 | — |
| 页脚（页码） | 宋体 | 五号 (10.5pt) | 否 | 居中 | — |

### 2.3 标题编号

- 一级标题：`1.` `2.` `3.` …（数字后跟点，非顿号）
- 二级标题：`1.1` `1.2` …
- 三级标题：`1.1.1` `1.1.2` …

---

## 3. 导出文档结构

```
┌─────────────────┐
│  1. 封面页       │  预案名称、企业名称、版本号、编制日期
├─────────────────┤
│  2. 批准页       │  批准人/审核人/编制人签字位、实施日期
├─────────────────┤
│  3. 目录         │  自动生成（含页码，在 Word 中刷新）
├─────────────────┤
│  4. 正文         │  按章节结构依次输出
│    4.1 总则      │
│    4.2 事故风险  │
│    4.3 组织机构  │  ← 含自动生成的表格
│    ...           │
├─────────────────┤
│  5. 附件         │
│    5.1 应急资源  │  ← 企业应急资源表格
│      清单        │
│    5.2 规范化    │
│      格式文本    │
│    5.3 图纸(占位)│
└─────────────────┘
```

---

## 4. 数据模型

### 4.1 export_tasks 表（异步导出）

```sql
CREATE TABLE export_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    plan_id UUID NOT NULL REFERENCES plan_projects(id) ON DELETE CASCADE,
    format VARCHAR(10) NOT NULL DEFAULT ''docx'' CHECK (format IN (''docx'', ''pdf'')),
    status VARCHAR(20) NOT NULL DEFAULT ''pending''
        CHECK (status IN (''pending'', ''processing'', ''completed'', ''failed'')),
    progress INTEGER NOT NULL DEFAULT 0,
    file_path VARCHAR(500),
    file_size_bytes BIGINT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_export_tasks_user ON export_tasks(user_id);
CREATE INDEX idx_export_tasks_status ON export_tasks(status);
```

### 4.2 Pydantic Schema

```python
class ExportPreviewResponse(BaseModel):
    plan_id: UUID
    title: str
    html: str    # 完整 HTML 预览内容

class ExportDocxResponse(BaseModel):
    """同步导出直接返回文件流，此 schema 用于异步"""
    task_id: UUID

class ExportTaskStatus(BaseModel):
    task_id: UUID
    status: str
    progress: int           # 0-100
    download_url: str | None
    error_message: str | None
```

---

## 5. API 接口

### 5.1 导出预览

```
GET /api/v1/plans/{plan_id}/export/preview
Authorization: Bearer <access_token>
```

**响应**：
```json
{
  "code": 0,
  "data": {
    "plan_id": "uuid",
    "title": "XX化工-综合应急预案",
    "html": "<!DOCTYPE html>..."
  }
}
```

**处理逻辑**：
1. 获取预案所有章节（按 sort_order 排序）
2. 调用 `PreviewRenderer` 渲染为完整 HTML
3. HTML 使用内联样式模拟 Word 公文排版
4. 嵌入封面、批准页信息

### 5.2 导出 .docx

```
POST /api/v1/plans/{plan_id}/export/docx
Authorization: Bearer <access_token>
```

**处理流程**：

```
步骤 1：导出前合规校验
  → 检查所有必填章节是否已填写
  → 检查企业基本信息是否完整
  → 返回校验结果

步骤 2：用户确认
  前端弹出校验结果：
  - 全部通过 → 直接开始导出
  - 有缺失项 → 列出缺失清单，让用户选择"继续导出"或"返回编辑"

步骤 3：生成文档
  1. 创建空白 python-docx Document
  2. 设置页面参数
  3. 生成封面页
  4. 生成批准页
  5. 添加分页符
  6. 添加目录域
  7. 添加分页符
  8. 遍历章节 → Markdown 转 Word 段落
     - 自动填充的表格特殊处理（组织架构表、风险源表、资源表）
  9. 添加附件（资源清单表）
  10. 设置页眉页脚
  11. 保存到 BytesIO → 返回字节流
```

**同步响应（文档较小）**：
```
HTTP 200
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="XX化工有限公司-生产安全事故综合应急预案-V1.docx"
Content-Length: 85600
```

**异步响应（文档较大，> 50 章节 或 触发异步条件）**：
```json
{
  "code": 0,
  "data": { "task_id": "uuid-xxxx" }
}
```

### 5.3 异步任务状态查询

```
GET /api/v1/export/tasks/{task_id}
Authorization: Bearer <access_token>
```

**响应**：
```json
// 处理中
{ "code": 0, "data": { "status": "processing", "progress": 60 } }

// 已完成
{
  "code": 0,
  "data": {
    "status": "completed",
    "progress": 100,
    "download_url": "/api/v1/export/download/uuid-file-key",
    "file_size_bytes": 85600
  }
}

// 失败
{ "code": 0, "data": { "status": "failed", "error_message": "生成封面时出错..." } }
```

### 5.4 下载导出文件

```
GET /api/v1/export/download/{file_key}
Authorization: Bearer <access_token>
```

临时下载链接，有效期 30 分钟。

### 5.5 导出前校验（独立接口）

```
POST /api/v1/plans/{plan_id}/export/validate
Authorization: Bearer <access_token>
```

**响应**：
```json
{
  "code": 0,
  "data": {
    "valid": false,
    "issues": [
      {
        "section_key": "purpose",
        "section_title": "1.1 编制目的",
        "issue": "必填章节内容为空"
      },
      {
        "section_key": "response_measures",
        "section_title": "5.3 处置措施",
        "issue": "必填章节内容为空"
      },
      {
        "issue": "企业「应急指挥部」未设置总指挥"
      }
    ],
    "warnings": [
      "外部救援力量信息未填写",
      "周边环境信息未填写"
    ]
  }
}
```

---

## 6. 核心实现

### 6.1 DocxExporter 类

```python
# services/export_service.py
import io
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

class DocxExporter:
    """GB/T 29639-2020 格式 .docx 导出器"""

    FONTS = {
        ''cover_title'': (''黑体'', Pt(22), True),
        ''cover_subtitle'': (''仿宋'', Pt(16), False),
        ''h1'': (''黑体'', Pt(16), True),
        ''h2'': (''楷体'', Pt(16), True),
        ''h3'': (''仿宋'', Pt(16), True),
        ''body'': (''仿宋'', Pt(16), False),
        ''table_cell'': (''仿宋'', Pt(12), False),
        ''table_header'': (''仿宋'', Pt(12), True),
        ''header_footer'': (''宋体'', Pt(10.5), False),
    }
    LINE_SPACING = Pt(28)
    TABLE_LINE_SPACING = Pt(22)

    def __init__(self, plan_service, enterprise_service):
        self.plan_service = plan_service
        self.enterprise_service = enterprise_service

    async def export(self, plan_id: UUID) -> bytes:
        plan = await self.plan_service.get_detail(plan_id)
        enterprise = await self.enterprise_service.get(plan.enterprise_id)

        doc = Document()
        self._setup_page(doc)
        self._setup_styles(doc)

        # 1. 封面
        self._add_cover_page(doc, plan, enterprise)

        # 2. 批准页
        self._add_approval_page(doc, plan, enterprise)
        doc.add_page_break()

        # 3. 目录
        self._add_toc(doc)
        doc.add_page_break()

        # 4. 正文（遍历所有章节）
        await self._add_body(doc, plan, enterprise)

        # 5. 附件
        self._add_attachments(doc, plan, enterprise)

        # 6. 页眉页脚
        self._add_header_footer(doc, plan, enterprise)

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def _setup_page(self, doc: Document):
        for section in doc.sections:
            section.page_width = Cm(21)
            section.page_height = Cm(29.7)
            section.top_margin = Cm(3.7)
            section.bottom_margin = Cm(3.5)
            section.left_margin = Cm(2.8)
            section.right_margin = Cm(2.6)

    def _set_font(self, run, font_name: str, size, bold: bool = False):
        """设置中文字体（处理东亚字体回退）"""
        run.font.name = font_name
        r = run._element
        rPr = r.get_or_add_rPr()
        rFonts = OxmlElement(''w:rFonts'')
        rFonts.set(qn(''w:eastAsia''), font_name)
        rPr.insert(0, rFonts)
        run.font.size = size
        run.bold = bold

    def _add_styled_paragraph(self, doc, text: str, style_key: str,
                               alignment=None, spacing=None):
        """添加带统一风格的段落"""
        font_name, size, bold = self.FONTS[style_key]
        p = doc.add_paragraph()
        if alignment:
            p.alignment = alignment
        if spacing:
            p.paragraph_format.line_spacing = spacing
        else:
            p.paragraph_format.line_spacing = self.LINE_SPACING
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)

        run = p.add_run(text)
        self._set_font(run, font_name, size, bold)
        return p
```

### 6.2 封面页生成

```python
def _add_cover_page(self, doc, plan, enterprise):
    """生成 GB/T 标准封面"""
    # 顶部留白
    for _ in range(6):
        doc.add_paragraph()

    # 预案名称（二号黑体加粗居中）
    self._add_styled_paragraph(
        doc, plan.title, ''cover_title'', WD_ALIGN_PARAGRAPH.CENTER
    )

    # 空行
    for _ in range(3):
        doc.add_paragraph()

    # 企业信息（三号仿宋居中）
    date_str = datetime.now().strftime(''%Y年%m月%d日'')
    info_lines = [
        f"企业名称：{enterprise.name}",
        f"版本号：V{plan.current_version}.0",
        f"编制日期：{date_str}",
    ]
    for line in info_lines:
        self._add_styled_paragraph(
            doc, line, ''cover_subtitle'', WD_ALIGN_PARAGRAPH.CENTER
        )

    doc.add_page_break()
```

### 6.3 批准页生成

```python
def _add_approval_page(self, doc, plan, enterprise):
    """生成批准页"""
    self._add_styled_paragraph(
        doc, ''批准页'', ''h1'', WD_ALIGN_PARAGRAPH.CENTER
    )
    doc.add_paragraph()

    # 批准信息表格（无边框）
    table = doc.add_table(rows=3, cols=2)

    sign_items = [
        (''批准人：'', ''____________（签字）        年  月  日''),
        (''审核人：'', ''____________（签字）        年  月  日''),
        (''编制人：'', ''____________（签字）        年  月  日''),
    ]
    for i, (label, value) in enumerate(sign_items):
        label_cell = table.rows[i].cells[0]
        value_cell = table.rows[i].cells[1]
        label_cell.width = Cm(3)
        value_cell.width = Cm(12)

        lp = label_cell.paragraphs[0]
        lp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        self._set_font(lp.add_run(label), ''仿宋'', Pt(16))

        vp = value_cell.paragraphs[0]
        self._set_font(vp.add_run(value), ''仿宋'', Pt(16))

    doc.add_paragraph()
    self._add_styled_paragraph(
        doc, f"实施日期：{datetime.now().strftime(''%Y年%m月%d日'')}",
        ''body'', WD_ALIGN_PARAGRAPH.LEFT
    )
```

### 6.4 Markdown 转 Word 段落

```python
import markdown
from bs4 import BeautifulSoup, NavigableString

def _render_markdown_to_docx(self, doc: Document, md_content: str):
    """将 Markdown 内容渲染为 Word 段落"""
    if not md_content.strip():
        return

    html = markdown.markdown(md_content, extensions=[''tables'', ''fenced_code''])
    soup = BeautifulSoup(html, ''html.parser'')

    for element in soup.children:
        if isinstance(element, NavigableString):
            continue

        tag = element.name

        if tag in (''h1'', ''h2'', ''h3''):
            level = int(tag[1])
            style_key = f''h{level}''
            self._add_styled_paragraph(doc, element.get_text(), style_key)

        elif tag == ''p'':
            text = element.get_text()
            if text.strip():
                self._add_styled_paragraph(doc, text, ''body'')

        elif tag == ''ul'':
            for li in element.find_all(''li'', recursive=False):
                p = doc.add_paragraph(style=''List Bullet'')
                p.paragraph_format.line_spacing = self.LINE_SPACING
                self._set_font(p.add_run(li.get_text()), ''仿宋'', Pt(16))

        elif tag == ''ol'':
            for li in element.find_all(''li'', recursive=False):
                p = doc.add_paragraph(style=''List Number'')
                p.paragraph_format.line_spacing = self.LINE_SPACING
                self._set_font(p.add_run(li.get_text()), ''仿宋'', Pt(16))

        elif tag == ''table'':
            self._render_html_table_as_word_table(doc, element)

        elif tag == ''blockquote'':
            text = element.get_text()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1)
            p.paragraph_format.line_spacing = self.LINE_SPACING
            self._set_font(p.add_run(text), ''仿宋'', Pt(16))
```

---

## 7. 预览渲染器（PreviewRenderer）

```python
class PreviewRenderer:
    """将预案渲染为 HTML 预览，样式模拟 Word 公文排版"""

    CSS = """
    <style>
      @page { size: A4; margin: 3.7cm 2.6cm 3.5cm 2.8cm; }
      body {
        font-family: ''FangSong'', ''仿宋'', serif;
        font-size: 16pt;
        line-height: 28pt;
        color: #000;
        max-width: 210mm;
        margin: 0 auto;
        padding: 2cm;
      }
      .cover { text-align: center; padding-top: 6cm; page-break-after: always; }
      .cover h1 { font-family: ''SimHei'', ''黑体'', sans-serif; font-size: 22pt; }
      .cover p { font-size: 16pt; margin: 0.5cm 0; }
      .approval { page-break-after: always; }
      .approval h2 { text-align: center; }
      .toc { page-break-after: always; }
      h1 { font-family: ''SimHei'', ''黑体'', sans-serif; font-size: 16pt; }
      h2 { font-family: ''KaiTi'', ''楷体'', serif; font-size: 16pt; }
      h3 { font-family: ''FangSong'', ''仿宋'', serif; font-size: 16pt; font-weight: bold; }
      table { border-collapse: collapse; width: 100%; margin: 0.5cm 0; }
      table th, table td { border: 1px solid #000; padding: 4px 8px; font-size: 12pt; }
      table th { font-weight: bold; text-align: center; }
      @media print { body { margin: 0; padding: 0; } }
    </style>
    """

    async def render(self, plan_id: UUID) -> str:
        plan = await self.plan_service.get_detail(plan_id)
        sections = plan.sections

        html_parts = [''<!DOCTYPE html><html><head><meta charset="utf-8">'', self.CSS]
        html_parts.append(f''<title>{plan.title}</title></head><body>'')

        # 封面
        html_parts.append(self._render_cover(plan))
        # 批准页
        html_parts.append(self._render_approval(plan))
        # 目录占位
        html_parts.append(''<div class="toc"><h2>目  录</h2><p>（导出为 Word 后请右键更新目录）</p></div>'')
        # 正文
        for section in sections:
            html_parts.append(self._render_section(section))

        html_parts.append(''</body></html>'')
        return ''''.join(html_parts)

    def _render_section(self, section) -> str:
        html = markdown.markdown(section.content or '''')
        heading_tag = f''h{min(section.level + 1, 3)}''
        return f''<{heading_tag}>{section.title}</{heading_tag}>\n{html}''
```

---

## 8. 自动填充表格

### 8.1 组织架构表

对于 key 为 `org_structure` 的章节，导出时从企业数据自动生成表格：

```python
def _add_org_structure_table(self, doc, enterprise):
    """生成组织架构表"""
    self._add_styled_paragraph(doc, ''应急组织机构表'', ''h2'')

    org = enterprise.org_structure or []
    table = doc.add_table(rows=1, cols=4, style=''Table Grid'')
    headers = [''应急小组'', ''职务'', ''姓名'', ''联系电话'']

    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._set_font(p.add_run(h), ''仿宋'', Pt(12), bold=True)

    for group in org:
        for i, member in enumerate(group.get(''members'', [])):
            row = table.add_row()
            values = [
                group[''group_name''] if i == 0 else '''',
                member.get(''role'', ''''),
                member.get(''name'', ''''),
                member.get(''phone'', ''''),
            ]
            for j, val in enumerate(values):
                cell = row.cells[j]
                p = cell.paragraphs[0]
                self._set_font(p.add_run(val), ''仿宋'', Pt(12))
```

### 8.2 风险源清单表

```python
def _add_risk_sources_table(self, doc, risk_sources):
    """生成风险源清单表"""
    if not risk_sources:
        return

    self._add_styled_paragraph(doc, ''表：风险源清单'', ''h2'')

    table = doc.add_table(rows=1, cols=6, style=''Table Grid'')
    headers = [''序号'', ''风险类别'', ''风险名称'', ''位置'', ''风险等级'', ''管控措施摘要'']

    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._set_font(p.add_run(h), ''仿宋'', Pt(12), bold=True)

    for idx, rs in enumerate(risk_sources, 1):
        row = table.add_row()
        control_summary = (rs.control_measures[:50] + ''...'') if len(rs.control_measures) > 50 else rs.control_measures
        values = [str(idx), rs.category, rs.name, rs.location, rs.risk_level, control_summary]
        for j, val in enumerate(values):
            cell = row.cells[j]
            p = cell.paragraphs[0]
            self._set_font(p.add_run(val), ''仿宋'', Pt(12))

    # 设置列宽
    widths = [Cm(1), Cm(2), Cm(3), Cm(3), Cm(2), Cm(4.5)]
    for row in table.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = w
```

---

## 9. 前端页面

### 9.1 导出预览页

- 路由：`/plans/:id/preview`
- 全页 iframe 或直接渲染 HTML
- 显示白底 A4 宽度容器，模拟纸张外观
- 顶部工具栏：
  - 左侧：`← 返回编辑器`
  - 右侧：`下载 .docx`（主按钮）、`打印`
- 预览样式与最终 docx 尽可能一致

### 9.2 导出流程

```
用户点击"导出"
      │
      ▼
┌─────────────────┐
│ 后端合规校验      │ ← POST /export/validate
│ 返回 issues/warnings │
└────────┬────────┘
         │
    ┌────┴────┐
    │ 有缺失？  │
    ├─ 是 ──→ 弹窗列出缺失项
    │         ├─ [继续导出] → 继续
    │         └─ [返回编辑] → 关闭
    │
    └─ 否 ──→ 直接导出
              │
              ▼
    ┌─────────────────┐
    │ POST /export/docx│
    │ 同步/异步返回     │
    └────────┬────────┘
             │
        ┌────┴────┐
        │ 异步？    │
        ├─ 否 ──→ 浏览器自动下载
        │
        └─ 是 ──→ 显示进度弹窗
                  │ (轮询 GET /export/tasks/{id})
                  │ progress: 0 → 50 → 100
                  └─→ 自动下载
```

### 9.3 导出进度弹窗

```
┌──────────────────────────┐
│  正在生成文档...           │
│                          │
│  ████████████░░░░  60%   │
│                          │
│  正在生成「5.3 处置措施」   │
├──────────────────────────┤
│         [取消]            │
└──────────────────────────┘
```

---

## 10. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC59 | 封面页正确生成 | 人工：打开 docx，封面含预案名、企业名、版本号、日期 |
| AC60 | 批准页正确生成 | 人工：打开 docx，批准页含签字位 |
| AC61 | 目录域可刷新 | 人工：Word 中右键目录 → 更新域 |
| AC62 | 标题格式正确 | 人工：一级标题黑体 16pt 加粗，二级楷体 16pt 加粗 |
| AC63 | 正文格式正确 | 人工：仿宋 16pt，固定行距 28 磅 |
| AC64 | 表格正确渲染 | 人工：打开 docx，组织架构表/风险源表数据正确 |
| AC65 | Markdown 列表正确 | 人工：编辑器中的 ul/ol 在 docx 中为项目符号/编号列表 |
| AC66 | 预览 HTML 可正常访问 | 自动化：GET /preview → 200 + HTML 含 title 标签 |
| AC67 | 导出前校验拦截缺失 | 自动化：清空必填章 → POST /validate → valid=false |
| AC68 | 异步导出状态轮询 | 自动化：POST /export/docx → 返回 task_id → 轮询 → completed |
| AC69 | 导出文件可下载 | 自动化：completed 后 GET download_url → 200 + Content-Type |
| AC70 | 页眉页脚正确 | 人工：页眉含企业名-预案名，页脚含页码 |
| AC71 | 文件中文字体不乱码 | 人工：用 Word 打开，所有中文正确显示 |
