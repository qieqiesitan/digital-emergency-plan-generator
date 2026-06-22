# PRD-06：版本管理与文档导出

> **版本**：1.0 | **创建日期**：2026-06-05 | **依赖**：PRD-00, PRD-01, PRD-05

---

## 1. 模块概述

包含两个独立但关联的子模块：
- **版本管理**：预案章节内容的自动/手动快照、历史查看、版本对比、回滚
- **文档导出**：将预案按 GB/T 29639-2020 公文格式导出为 .docx 文件

---

##   2. 版本管理

### 2.1 数据模型

#### plan_versions 表

```sql
CREATE TABLE plan_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_project_id UUID NOT NULL REFERENCES plan_projects(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    created_by VARCHAR(20) NOT NULL DEFAULT ''auto'' CHECK (created_by IN (''auto'', ''manual'')),
    description VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_versions_plan ON plan_versions(plan_project_id, version_number DESC);
CREATE UNIQUE INDEX idx_versions_plan_number ON plan_versions(plan_project_id, version_number);
```

#### snapshot JSONB 结构

```json
{
  "plan_id": "uuid",
  "plan_title": "XX化工-综合应急预案",
  "enterprise_id": "uuid",
  "enterprise_name": "XX化工有限公司",
  "created_at": "2026-06-05T10:00:00Z",
  "sections": [
    {
      "section_key": "purpose",
      "title": "1.1 编制目的",
      "content": "为建立健全..."
    },
    {
      "section_key": "basis",
      "title": "1.2 编制依据",
      "content": "依据《安全生产法》..."
    }
  ]
}
```

#### Pydantic Schema

```python
class VersionResponse(BaseModel):
    id: UUID
    version_number: int
    created_by: str       # "auto" | "manual"
    description: str | None
    created_at: datetime

class VersionDetailResponse(VersionResponse):
    snapshot: dict

class VersionCompareResponse(BaseModel):
    version_a: int
    version_b: int
    diffs: list[SectionDiff]

class SectionDiff(BaseModel):
    section_key: str
    title: str
    change_type: str     # "added" | "removed" | "modified" | "unchanged"
    old_content: str | None
    new_content: str | None
```

### 2.2 创建快照时机

| 时机 | created_by |
|------|-----------|
| AI 生成章节前 | `"auto"` |
| 用户手动点击"保存为新版本" | `"manual"` |
| 从旧版本回滚前 | `"auto"` |

**数量控制**：每个预案最多保留 20 个版本。超出时自动删除最旧的 `version_number` 最小的记录。

### 2.3 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/plans/{id}/versions` | 版本列表 |
| GET | `/api/v1/plans/{id}/versions/{vid}` | 版本详情（含完整 snapshot） |
| POST | `/api/v1/plans/{id}/versions` | 手动创建新版本 |
| GET | `/api/v1/plans/{id}/versions/compare` | 两个版本对比 |
| POST | `/api/v1/plans/{id}/versions/{vid}/rollback` | 回滚到指定版本 |

**手动创建版本**：
```
POST /api/v1/plans/{id}/versions
Body: { "description": "完成总则和风险描述初稿" }
```

**版本对比**：
```
GET /api/v1/plans/{id}/versions/compare?a=1&b=3
Response: { "diffs": [ { section_key, title, change_type, old_content, new_content }, ... ] }
```

**版本回滚**：
```
POST /api/v1/plans/{id}/versions/{vid}/rollback
处理逻辑：
1. 创建当前版本的快照（auto）
2. 将 plan_sections 的所有 content 替换为快照中的 content
3. 更新 plan_projects.current_version
4. 重新计算 status
```

### 2.4 前端页面

#### 版本列表页

- 路由：`/plans/:id/versions`
- 表格列：版本号、创建方式（自动/手动 Tag）、说明、创建时间、操作
- 操作：查看详情、对比、回滚
- 顶部："新建版本"按钮 → 弹窗输入说明 → 保存
- 对比：勾选两个版本的 Checkbox（最多 2 个）→ 点击"对比"按钮

#### 版本对比弹窗

- 并排两栏：左栏为旧版本、右栏为新版本
- 按章节展示，修改过的章节黄色高亮标记
- 新增的章节绿色标记
- 删除的章节红色标记
- 支持"回滚到此版本"按钮（仅对较旧版本显示）

---

## 3. 文档导出

### 3.1 导出格式规范（GB/T 29639-2020 公文格式）

| 元素 | 格式 |
|------|------|
| 页面 | A4 (210mm × 297mm)，上 3.7cm 下 3.5cm 左 2.8cm 右 2.6cm |
| 封面标题 | 黑体，二号（22pt），居中，加粗 |
| 封面副标题 | 仿宋，三号（16pt），居中 |
| 一级标题 | 黑体，三号（16pt），加粗，段前段后 0.5 行 |
| 二级标题 | 楷体，三号（16pt），加粗 |
| 正文 | 仿宋，三号（16pt），行距 28 磅（固定值） |
| 表格内文字 | 仿宋，小四（12pt） |
| 页眉 | 「企业名称-预案名称」，宋体五号，居中 |
| 页脚 | 页码，宋体五号，居中 |

### 3.2 导出内容结构

```
1. 封面页
   - 预案名称（居中大字）
   - 企业名称
   - 版本号
   - 编制日期

2. 批准页
   - 批准人、审核人、编制人（签字位）
   - 实施日期
   - 批准日期

3. 目录
   - 自动从标题生成，含页码

4. 正文
   - 各章节内容按模板结构顺序排列
   - 包含从企业数据自动填充的表格
     - 组织架构表
     - 风险源清单表
     - 应急资源清单表

5. 附件
   - 应急资源清单
   - 规范化格式文本
   - 相关图纸（占位）
```

### 3.3 导出实现（python-docx）

```python
# services/export_service.py
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

class DocxExporter:
    """将预案项目导出为符合 GB/T 29639-2020 格式的 .docx"""

    FONT_TITLE = ''黑体''
    FONT_HEADING = ''黑体''
    FONT_HEADING2 = ''楷体''
    FONT_BODY = ''仿宋''
    FONT_TABLE = ''仿宋''
    SIZE_TITLE = Pt(22)
    SIZE_HEADING = Pt(16)
    SIZE_BODY = Pt(16)
    SIZE_TABLE = Pt(12)
    LINE_SPACING = Pt(28)

    async def export(self, plan_id: UUID) -> bytes:
        plan = await self.plan_service.get_detail(plan_id)
        enterprise = await self.enterprise_service.get(plan.enterprise_id)

        doc = Document()
        self._setup_page(doc)
        self._add_cover_page(doc, plan, enterprise)
        self._add_approval_page(doc, plan)
        self._add_toc(doc)
        self._add_body(doc, plan)
        self._add_attachments(doc, plan, enterprise)

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def _setup_page(self, doc: Document):
        section = doc.sections[0]
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(3.7)
        section.bottom_margin = Cm(3.5)
        section.left_margin = Cm(2.8)
        section.right_margin = Cm(2.6)

    def _add_cover_page(self, doc, plan, enterprise):
        # 空行增加间距
        for _ in range(6):
            doc.add_paragraph()

        # 预案名称
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(plan.title)
        run.font.name = self.FONT_TITLE
        run.font.size = self.SIZE_TITLE
        run.bold = True

        # 空行
        for _ in range(3):
            doc.add_paragraph()

        # 企业信息
        info_items = [
            f"企业名称：{enterprise.name}",
            f"版本号：V{plan.current_version}.0",
            f"编制日期：{datetime.now().strftime(''%Y年%m月%d日'')}",
        ]
        for item in info_items:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(item)
            run.font.name = self.FONT_BODY
            run.font.size = Pt(16)

        doc.add_page_break()

    def _set_run_font(self, run, font_name, size, bold=False):
        run.font.name = font_name
        run._element.rPr.rFonts.set(qn(''w:eastAsia''), font_name)
        run.font.size = size
        run.bold = bold

    def _add_paragraph(self, doc, text, font_name, size, bold=False, alignment=None):
        p = doc.add_paragraph()
        if alignment:
            p.alignment = alignment
        p.paragraph_format.line_spacing = self.LINE_SPACING
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)

        run = p.add_run(text)
        self._set_run_font(run, font_name, size, bold)
        return p
```

### 3.4 表格生成

```python
def _add_risk_source_table(self, doc, risk_sources):
    """生成风险源清单表"""
    doc.add_heading(''风险源清单'', level=2)
    table = doc.add_table(rows=1, cols=6, style=''Table Grid'')
    headers = [''序号'', ''风险类别'', ''风险名称'', ''位置'', ''风险等级'', ''管控措施'']

    # 表头
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        p = cell.paragraphs[0]
        run = p.add_run(header)
        self._set_run_font(run, self.FONT_BODY, self.SIZE_TABLE, bold=True)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 数据行
    for idx, rs in enumerate(risk_sources, 1):
        row = table.add_row()
        values = [str(idx), rs.category, rs.name, rs.location, rs.risk_level, rs.control_measures]
        for i, val in enumerate(values):
            cell = row.cells[i]
            p = cell.paragraphs[0]
            run = p.add_run(val)
            self._set_run_font(run, self.FONT_TABLE, self.SIZE_TABLE)
```

### 3.5 Markdown 转 docx 段落

章节内容以 Markdown 格式存储，导出时需转换为 Word 段落：

```python
import markdown
from bs4 import BeautifulSoup

def _markdown_to_docx(self, doc: Document, md_content: str):
    """将 Markdown 内容转换为 Word 段落序列"""
    html = markdown.markdown(md_content)
    soup = BeautifulSoup(html, ''html.parser'')

    for element in soup.children:
        if element.name in (''h1'', ''h2'', ''h3''):
            level = int(element.name[1])
            doc.add_heading(element.get_text(), level=level)
        elif element.name == ''p'':
            self._add_paragraph(doc, element.get_text(), self.FONT_BODY, self.SIZE_BODY)
        elif element.name == ''ul'':
            for li in element.find_all(''li''):
                p = doc.add_paragraph(style=''List Bullet'')
                run = p.add_run(li.get_text())
                self._set_run_font(run, self.FONT_BODY, self.SIZE_BODY)
        elif element.name == ''ol'':
            for li in element.find_all(''li''):
                p = doc.add_paragraph(style=''List Number'')
                run = p.add_run(li.get_text())
                self._set_run_font(run, self.FONT_BODY, self.SIZE_BODY)
```

### 3.6 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/plans/{id}/export/preview` | 导出预览（HTML 格式） |
| POST | `/api/v1/plans/{id}/export/docx` | 导出 .docx 文件 |

**导出预览**：返回 HTML 页面，后端渲染章节内容为 HTML，前端 iframe 或新窗口展示。

**导出 .docx**：
- 小文档（<50KB）：同步返回文件流
- 大文档：通过 Celery 异步任务生成，返回任务 ID

```
POST /api/v1/plans/{id}/export/docx
Response (同步): Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
                 Content-Disposition: attachment; filename="XX化工-综合应急预案-V1.docx"

Response (异步): { "code": 0, "data": { "task_id": "uuid" } }
```

**异步任务轮询**：
```
GET /api/v1/export/tasks/{task_id}
Response: { "status": "processing", "progress": 60 }
Response: { "status": "completed", "download_url": "/api/v1/export/download/{file_key}" }
```

### 3.7 导出前校验

```python
async def validate_before_export(self, plan_id: UUID) -> list[str]:
    """导出前合规检查，返回问题列表"""
    issues = []
    plan = await self.get(plan_id)

    # 获取模板中所有 required=true 的章节
    template = await self.template_service.get(plan.template_id)
    required_keys = self._get_required_keys(template.structure)

    # 检查必填章节
    for key in required_keys:
        section = await self.section_service.get(plan_id, key)
        if not section or not section.content.strip():
            issues.append(f"必填章节「{section.title if section else key}」尚未填写")

    return issues
```

如果 issues 非空，前端弹出确认对话框列出缺失项，用户可选择"继续导出"（缺失章节以「待补充」占位）或"返回编辑"。

---

## 4. 前端页面

### 4.1 导出预览页

- 路由：`/plans/:id/preview`
- 全屏展示已渲染的预案 HTML（模拟 Word 文档外观）
- 顶部工具栏：返回编辑、下载 .docx、打印
- 页面样式：白色 A4 容器，公文字体，打印友好

### 4.2 导出下载流程

1. 用户在编辑器中点击"导出"→ 弹出确认对话框
2. 选择"先去预览"→ 跳转预览页 → 确认后点击"下载 .docx"
3. 或直接"下载 .docx"→ 触发 POST /export/docx
4. 显示下载进度（异步任务时）
5. 完成后浏览器自动下载文件

---

## 5. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC48 | AI 生成前自动创建版本快照 | 自动化：生成章节 → 查询 versions 表 → 存在 auto 记录 |
| AC49 | 手动创建版本 | 自动化：POST /versions → 201 → 版本号递增 |
| AC50 | 版本列表按时间倒序 | 自动化：GET /versions → items 按 version_number DESC |
| AC51 | 版本对比正确识别修改 | 自动化：修改 1 节 → 创建版本 → 对比 v1 v2 → diffs 含该节 modified |
| AC52 | 版本回滚生效 | 自动化：修改 → 回滚 v1 → 内容恢复至 v1 状态 |
| AC53 | 最多保留 20 个版本 | 自动化：创建 25 个版本 → 列表仅返回 20 条 |
| AC54 | 导出 .docx 格式正确 | 人工：打开 docx，检查封面、目录、标题、正文、表格格式 |
| AC55 | 导出预览 HTML 可访问 | E2E：点击"预览"→ 新窗口显示完整预案 |
| AC56 | 必填章节未填写时导出拦截 | 自动化：清空必填章 → POST export → 返回 issues 列表 |
| AC57 | 导出后恢复编辑不影响 docx | 自动化：导出 → 修改内容 → 之前下载的 docx 内容不变 |
| AC58 | Markdown 转 docx 段落正确 | 单元测试：传入 Markdown → 检查生成的 docx 段落数和格式 |
