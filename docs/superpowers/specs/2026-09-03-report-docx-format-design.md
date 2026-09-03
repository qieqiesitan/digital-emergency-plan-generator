# 报告 Word 导出统一复用预案公文版式（risk/resource）

日期：2026-09-03

## 背景与目标

用户反馈“风险评估报告导出格式很丑、很乱”，要求参考应急预案导出的格式调整。

- 现状：风险/资源调查报告的 Word 导出在各自路由里手拼：封面用默认页边距与 28/22pt 大字号，正文无统一样式（标题、列表、表格按行手解析，表格 9pt），无页眉页码、无公文页边距，视觉与预案导出差异很大。
- 预案导出：走 `backend/app/services/docx_template.py` 公文样式引擎（宋体/黑体/仿宋体系、公文页边距、封面/页眉页码/目录、标题分页、表格自适应列宽），视觉规范统一。
- 目标：两份报告导出采用与预案同源的公文版式，风格一致、整洁；不改报告生成/预览/数据。

## 方案（已获用户确认：方案 A）

复用 `docx_template` 的样式注册与 HTML→DOCX 转换能力，新增统一“报告 DOCX 生成器”，risk/resource 两个 export 端点改用它；旧的手写封面与行解析渲染器不再用于导出。

### 范围

- `backend/app/routers/risk_assessment.py` 的 export 端点
- `backend/app/routers/resource_investigation.py` 的 export 端点
- 新增 `backend/app/services/report_docx.py`（报告版式生成器）
- 既有 `_clean_for_docx` 等清洗逻辑保留原位，生成器通过函数内延迟 import 复用，避免模块环依赖；不在本任务内做大规模搬迁
- 不修改：报告生成、合并、预览页、DB、前端

## 生成器设计 `generate_report_docx(...)`

签名：

```python
def generate_report_docx(
    *,
    company_name: str,
    report_kind: str,          # "risk" | "resource"
    chapters: list[dict],      # [{"key","title","content"}]，content 为 markdown/HTML 混合
    report_title: str = "",    # 兜底页眉标题
) -> Document
```

版式（与预案 `generate_plan_docx` 对齐）：

1. `Document()` + `register_all_styles(doc)`。
2. A4；封面与正文节边距同预案（左 2.8cm、右 2.6cm、上 3.7cm、下 3.5cm）。
3. 封面页（不生成预案“批准页/发布页”）：空行撑开 → 企业名（Cover Title 宋体 26pt 居中）→ 报告名（同样式，risk=“生产安全事故风险评估报告”，resource=“应急资源调查报告”）→ 落款：企业名 + 年月（Cover Sign，仿宋 18pt 居中）→ 分页。
4. 正文节：`different_first_page_header_footer` + 页眉“企业名　报告名”（宋体 10.5pt），页脚“第 X 页 共 Y 页”（复用 `_setup_header_footer`）。
5. 正文大标题 `add_body_title`（宋体 22pt 居中加粗）。
6. 逐章：每章标题 `add_heading(level=1)`（黑体 16pt 加粗，首行缩进，`page_break_before` 分页）；正文先做清洗与转换：
   - 逐章 `_clean_for_docx`（Markdown 管道表→HTML、去 ```/mermaid/尾随 JSON 摘要等残留）；
   - `markdown.markdown(..., extensions=["tables","fenced_code","md_in_html"])`；
   - `html_to_docx_content(doc, html, base_level=1)`：正文段首行缩进 2 字符、仿宋 16pt 固定行距，表格由 `build_table` 生成边框/列宽，标题 h2-h6 依序映射。
7. 章节来源：优先 `report.summary.chapters`；若为空/旧数据，按“## ”标题切分 `report.content` 兜底。
8. 图片（增强项，不阻塞本任务）：正文 `<img src="/uploads/...">` 若本地文件存在则解析为 `/backend/uploads` 相对路径并 `add_picture(width=Cm(14.6))` 居中，否则保留原样跳过（与现状一致，不引入新能力）。

## 端点改动

两 export 端点保持：权限校验、`report.status in completed/draft/generating` 查询、中文文件名（risk=`{企业}_事故风险评估报告.docx`、resource=`{企业}_应急资源调查报告.docx`）、`FileResponse` 下载。仅把“手写 Document + 旧渲染器”整段替换为调用 `generate_report_docx`。

## 测试

- 新增 `backend/tests/test_report_docx_format.py`：
  - 封面含企业名与报告名、不含“批准页”；
  - Normal 样式字体为仿宋 16pt（验证 `register_all_styles` 已生效）；
  - 每章标题以黑体 Heading 1 写入且带分页；
  - HTML 表格与 Markdown 表格均生成 docx 表格；
  - 尾随 JSON 摘要与 ```mermaid 残留被剔除；
  - risk/resource 两种 kind 的正文大标题/页眉文案正确。
- 回归：`test_report_docx_clean.py`、`test_report_versions.py`、`test_report_skip.py` 等报告相关套件全绿。
- 冒烟：对已完成的风险评估报告行（d1487dc3）与应急资源调查报告行（1bfa9f67）真实调用 export，检查 docx 可打开、页数与正文段落非空。

## 验收标准

- 导出的两份 Word：封面（企业名+报告名+日期）→ 页眉页码 → 正文大标题 → 各章黑体标题分页、仿宋正文、表格带边框，视觉与预案一致。
- 原功能不回归：文件名、下载、合并后的 content、预览均不受影响。
