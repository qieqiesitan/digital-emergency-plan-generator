import json, os, re, logging
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse
from app.database import get_db, async_session
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise, AIConfig
from app.models.risk_assessment import RiskAssessmentReport
from app.schemas.risk_assessment import (
    RiskAssessmentGenerateRequest,
    RiskAssessmentReportResponse,
    RiskAssessmentPreviewResponse,
)
from app.schemas.common import ApiResponse
from app.services.ai_config_service import get_system_ai_config
from app.services.llm_client import decrypt_api_key, llm_chat_completion, llm_stream_all, LLMError
from app.services.markdown_utils import md_to_html
from app.services.report_chapter_utils import (
    chapters_to_summary,
    get_chapters,
    upsert_chapter,
)
from app.services.report_review_service import review_report_chapters
from app.services.sse_utils import sse_event
from app.services.risk_assessment_service import (
    CHAPTER_DEFINITIONS as RA_CHAPTER_DEFINITIONS,
)
from app.services.risk_context_builder import build_risk_management_context
from app.services.risk_assessment_service import (
    build_chapter_prompt,
    get_chapter_keys,
    get_chapter_title,
    _get_ra_system_prompt,
)
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enterprises", tags=["Risk Assessment"])


def _schedule_enterprise_index_rebuild(enterprise_id: str) -> None:
    """评估报告写库后异步重建企业画像索引（不阻塞主流程，复用 chat_dispatch 挂点）。"""
    try:
        from app.services.chat_dispatch import _schedule_enterprise_index_rebuild as _schedule
        _schedule(enterprise_id)
    except Exception:
        pass


@router.post("/{enterprise_id}/risk-assessment/skip")
async def skip_risk_assessment(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """标记风险评估报告跳过（规格 6.6：跳过时完成度权重归入风险与危化品）。"""
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    generating = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status == "generating",
        )
    )).scalar_one_or_none()
    if generating:
        raise HTTPException(400, "报告正在生成中，无法跳过")
    existing_completed = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status == "completed",
        )
    )).scalar_one_or_none()
    if existing_completed:
        raise HTTPException(400, "报告已生成，无需跳过")
    # upsert：已有记录（含 draft）改写为 skipped，避免「生成→未合并→跳过」产生重复行
    existing = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status != "skipped",
        ).order_by(RiskAssessmentReport.id)
    )).scalars().first()
    if existing:
        existing.status = "skipped"
        await db.commit()
        return ApiResponse(data={}, message="已跳过风险评估报告")
    existing_skipped = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status == "skipped",
        )
    )).scalars().first()
    if not existing_skipped:
        db.add(RiskAssessmentReport(enterprise_id=enterprise_id, title="", status="skipped"))
        await db.commit()
    return ApiResponse(data={}, message="已跳过风险评估报告")


def _html_table_to_docx(doc, html_table: str):
    """将 HTML <table> 渲染为 python-docx 表格"""
    from docx.shared import Pt, Inches, RGBColor
    from docx.oxml.ns import qn
    soup = BeautifulSoup(html_table, "html.parser")
    table_el = soup.find("table")
    if not table_el:
        return
    rows = table_el.find_all("tr")
    if not rows:
        return
    # Determine column count from first row
    first_cells = rows[0].find_all(["th", "td"])
    col_count = len(first_cells)
    if col_count == 0:
        return
    docx_table = doc.add_table(rows=len(rows), cols=col_count)
    docx_table.style = "Table Grid"
    for ri, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        for ci, cell in enumerate(cells):
            if ci >= col_count:
                break
            docx_cell = docx_table.cell(ri, ci)
            text = cell.get_text(strip=True)
            docx_cell.text = text
            # Bold for header cells
            if cell.name == "th":
                for p in docx_cell.paragraphs:
                    for run in p.runs:
                        run.bold = True
                        run.font.size = Pt(9)
            else:
                for p in docx_cell.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(9)
    doc.add_paragraph("")  # spacing after table


def _clean_for_docx(content: str) -> str:
    """Strip markdown artifacts that _render_content_to_docx doesn't handle."""
    import re as _re
    # 1. Remove fenced code blocks
    content = _re.sub(r'```[\w]*\n[\s\S]*?```', '', content)
    # 2. Remove bare mermaid blocks (no code fences: "mermaid\nflowchart...")
    content = _re.sub(r'\nmermaid\n(?:flowchart|graph|sequenceDiagram|pie|mindmap|classDiagram|stateDiagram|erDiagram|gantt|journey|gitgraph)[\s\S]*?(?=\n\n[^A-Za-z\-\[]>]|\n(?:json|```)\n|\Z)', '', content)
    # 3. Remove bare "json\n{...}\n```" blocks (opening ``` missing, closing present)
    content = _re.sub(r'\njson\n\{[\s\S]*?\n```', '', content)
    # 4. Strip trailing ``` backticks before JSON detection
    content = _re.sub(r'\n```\s*$', '', content)
    # 5. Remove trailing JSON summary block (handles nested braces)
    def _strip_trailing_json(s: str) -> str:
        """Find and remove a trailing JSON object with balanced braces."""
        stripped = s.rstrip()
        if not stripped.endswith('}'):
            return s
        # Count braces backwards
        depth = 0
        for i in range(len(stripped) - 1, -1, -1):
            ch = stripped[i]
            if ch == '}':
                depth += 1
            elif ch == '{':
                depth -= 1
                if depth == 0:
                    prefix = stripped[:i].rstrip()
                    if prefix:
                        return prefix + '\n'
                    return prefix
        return s
    content = _strip_trailing_json(content)
    # 3. Strip **bold** markers
    content = content.replace('**', '')
    # 4. Convert * list markers to - (already handled)
    content = _re.sub(r'^(\s*)\* ', r'\1- ', content, flags=_re.MULTILINE)
    # 5. Fix #text -> # text (missing space after #)
    content = _re.sub(r'^(#{1,6})([^\s#])', r'\1 \2', content, flags=_re.MULTILINE)
    # 6. Remove duplicate lines immediately following a heading
    lines_out = []
    prev_line = None
    for line in content.split('\n'):
        stripped = line.strip()
        # If current line is a duplicate of the previous line's content (after heading prefix)
        if prev_line and stripped and stripped == prev_line:
            continue
        lines_out.append(line)
        # Extract plain text from heading for next-line dedup
        m = _re.match(r'^#{1,6}\s+(.+)', stripped)
        if m:
            prev_line = m.group(1).strip()
        elif stripped:
            prev_line = stripped
        else:
            prev_line = None
    content = '\n'.join(lines_out)
    return content

def _render_content_to_docx(doc, content: str):
    """Render content that may contain interleaved text and HTML tables into docx."""
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    content = _clean_for_docx(content)
    # Split content by HTML table blocks
    parts = re.split(r"(<table[\s\S]*?</table>)", content)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("<table"):
            _html_table_to_docx(doc, part)
        else:
            # Render text lines
            for line in part.split("\n"):
                line = line.strip()
                if not line:
                    doc.add_paragraph("")
                elif line.startswith("# "):
                    h = doc.add_heading(level=1)
                    h.add_run(line[2:])
                elif line.startswith("## "):
                    h = doc.add_heading(level=2)
                    h.add_run(line[3:])
                elif line.startswith("### "):
                    h = doc.add_heading(level=3)
                    h.add_run(line[4:])
                elif line.startswith("- "):
                    doc.add_paragraph(line[2:], style="List Bullet")
                elif re.match(r"^\d+[.)] ", line):
                    doc.add_paragraph(re.sub(r"^\d+[.)]\s*", "", line), style="List Number")
                elif re.match(r"^\d+）", line):
                    doc.add_paragraph(re.sub(r"^\d+）\s*", "", line), style="List Number")
                else:
                    doc.add_paragraph(line)

# ---- LLM streaming utilities (used by both risk_assessment and resource_investigation) ----

def _guard_decrypt(ai_config) -> None:
    """保持原 decrypt 失败 → HTTPException(500) 的语义。"""
    try:
        decrypt_api_key(ai_config.api_key_encrypted)
    except Exception:
        raise HTTPException(500, "AI config key decryption failed")


async def _stream_llm_with_messages(messages: list[dict], ai_config: AIConfig) -> str:
    _guard_decrypt(ai_config)
    try:
        return await llm_stream_all(messages, ai_config, timeout=120)
    except LLMError as e:
        # 保持原 risk_assessment 文案
        raise Exception(f"LLM call failed: {e.status_code} {e.text[:300]}")


async def _stream_llm_with_messages_chunked(messages: list[dict], ai_config: AIConfig):
    _guard_decrypt(ai_config)
    try:
        gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=120)
        async for chunk in gen:
            yield chunk
    except LLMError as e:
        raise Exception(f"LLM call failed: {e.status_code} {e.text[:300]}")


async def _stream_llm_with_system(prompt: str, ai_config: AIConfig) -> str:
    messages = [
        {"role": "system", "content": _get_ra_system_prompt()},
        {"role": "user", "content": prompt},
    ]
    return await _stream_llm_with_messages(messages, ai_config)


# ---- API Endpoints ----

@router.get("/{enterprise_id}/risk-assessment")
async def get_risk_assessment(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")

    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["completed", "draft"]),
        )
    )).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "未找到已完成的风险评估报告")

    return ApiResponse(data=RiskAssessmentReportResponse.model_validate(report))


@router.get("/{enterprise_id}/risk-assessment/summary")
async def get_risk_assessment_summary(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")

    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["completed", "draft"]),
        )
    )).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "未找到已完成的风险评估报告")

    return ApiResponse(data=report.summary or {})


@router.get("/{enterprise_id}/risk-assessment/preview")
async def preview_risk_assessment(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")

    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["completed", "draft"]),
        )
    )).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "未找到已完成的风险评估报告")

    html = md_to_html(_clean_for_docx(report.content), output_format="html5")
    return ApiResponse(data=RiskAssessmentPreviewResponse(
        report_id=report.id, title=report.title, html=html
    ))


@router.get("/{enterprise_id}/risk-assessment/export")
async def export_risk_assessment(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")

    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["completed", "draft"]),
        )
    )).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "未找到已完成的风险评估报告")

    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
    except ImportError:
        raise HTTPException(500, "python-docx 未安装")

    doc = Document()
    style = doc.styles["Normal"]
    style.font.size = Pt(12)

    # ---- Professional Cover Page ----
    # Add empty paragraphs for spacing (top margin)
    for _ in range(6):
        doc.add_paragraph("")

    # Main title
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run(ent.name)
    run.font.size = Pt(28)
    run.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)

    # Report type subtitle
    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub_p.add_run("生产安全事故风险评估报告")
    run.font.size = Pt(22)
    run.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)

    # Spacer
    for _ in range(4):
        doc.add_paragraph("")

    # Cover footer
    for line in [
        f"编制单位：{ent.name}",
        f"编制日期：{datetime.now().strftime('%Y年%m月%d日')}",
    ]:
        if line:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(line)
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(0, 0, 0)

    doc.add_page_break()

    # ---- Report Body ----
    _render_content_to_docx(doc, report.content)

    # ---- Export ----
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    safe_name = ent.name.replace(" ", "_") if ent else "企业"
    filename = f"{safe_name}_事故风险评估报告.docx"
    path = os.path.join(settings.EXPORT_DIR, filename)
    doc.save(path)
    return FileResponse(
        path, filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )



@router.post("/{enterprise_id}/risk-assessment/generate")
async def generate_risk_assessment(
    enterprise_id: str,
    request: RiskAssessmentGenerateRequest = RiskAssessmentGenerateRequest(),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")

    context = await build_risk_management_context(enterprise_id, db)
    if context["total_events"] == 0:
        raise HTTPException(400, "请先录入风险分级管控数据")

    from app.services.ai_config_service import get_system_ai_config

    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    existing = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status == "generating",
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "已有正在生成的报告，请等待完成")

    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["generating", "draft", "completed"]),
        ).order_by(RiskAssessmentReport.id)
    )).scalars().first()

    title = f"{ent.name} 事故风险评估报告"
    if report:
        report.title = title
        report.content = ""
        report.summary = {}
        report.status = "generating"
    else:
        report = RiskAssessmentReport(
            enterprise_id=enterprise_id, title=title, status="generating",
        )
        db.add(report)
    await db.commit()
    _schedule_enterprise_index_rebuild(enterprise_id)

    async def event_generator():
        full_content = ""
        chapter_contents: list[dict] = []
        try:
            chapter_keys = get_chapter_keys()
            total = len(chapter_keys)
            yield sse_event("progress", message=f"开始逐章生成风险评估报告（共{total}章）...",
                       current=0, total=total)

            for i, ck in enumerate(chapter_keys):
                ctitle = get_chapter_title(ck)
                yield sse_event("progress",
                           message=f"正在生成「{ctitle}」（{i+1}/{total}）",
                           current=i+1, total=total, section_key=ck)

                ch_prompt = build_chapter_prompt(
                    ck, context,
                    previous_chapters=chapter_contents if chapter_contents else None,
                    custom_instruction=request.custom_instruction,
                )
                messages = [
                    {"role": "system", "content": _get_ra_system_prompt()},
                    {"role": "user", "content": ch_prompt},
                ]
                ch_content = ""
                async for chunk_content in _stream_llm_with_messages_chunked(messages, ai_config):
                    ch_content += chunk_content
                    yield sse_event("chunk", content=chunk_content, section_key=ck)

                chapter_contents.append({
                    "key": ck, "title": ctitle, "content": ch_content,
                })
                full_content += f"\n\n{ctitle}\n\n{ch_content}"
                yield sse_event("section_done", section_key=ck,
                           message=f"「{ctitle}」生成完成",
                           completed=i+1, total=total)

            # Save chapter contents to summary, set status to draft (user will merge manually)
            chapters_json = [
                {"key": c["key"], "title": c["title"], "content": c["content"]}
                for c in chapter_contents
            ]

            async with async_session() as bg_db:
                bg_report = (await bg_db.execute(
                    select(RiskAssessmentReport).where(RiskAssessmentReport.id == report.id)
                )).scalar_one_or_none()
                if bg_report:
                    bg_report.status = "draft"
                    bg_report.content = full_content.strip()
                    bg_report.summary = {"chapters": chapters_json}
                    try:
                        import json as _json2, re as _re2
                        last_ch = chapter_contents[-1] if chapter_contents else None
                        if last_ch:
                            m = _re2.search(r"\{[^}]+\}\s*$", last_ch.get("content", ""))
                            if m:
                                struct = _json2.loads(m.group())
                                bg_report.summary.update(struct)
                    except Exception:
                        pass
                    await bg_db.commit()

            import json as _json
            yield sse_event("batch_done", report_id=report.id,
                       message=f"报告生成完成，共{total}章",
                       completed=total, total=total,
                       chapters=_json.dumps(chapters_json, ensure_ascii=False))
        except Exception as e:
            import traceback
            logger.error(f"Risk assessment generation failed: {e}\n{traceback.format_exc()}")
            async with async_session() as bg_db:
                bg_report = (await bg_db.execute(
                    select(RiskAssessmentReport).where(RiskAssessmentReport.id == report.id)
                )).scalar_one_or_none()
                if bg_report:
                    bg_report.status = "draft"
                    bg_report.content = full_content
                    await bg_db.commit()
            yield sse_event("error", message=str(e))
    return EventSourceResponse(event_generator())


@router.get("/{enterprise_id}/risk-assessment/chapters")
async def get_risk_assessment_chapters():
    """Return chapter definitions for risk assessment report (used by frontend)."""
    return ApiResponse(data=[
        {"key": c["key"], "title": c["title"]}
        for c in RA_CHAPTER_DEFINITIONS
    ])


# ============================================================
# 章节级端点：单章生成/重生成（SSE）、章节保存、规则审查、
# LLM 应用修订、创作风格偏好（risk-assessment）
# ============================================================

class SectionGenerateRequest(BaseModel):
    chapter_key: str
    custom_instruction: str | None = None


class SectionRegenerateRequest(BaseModel):
    custom_instruction: str | None = None


class SectionContentUpdate(BaseModel):
    content: str


class ReportReviewRequest(BaseModel):
    section_keys: list[str] | None = None


class StyleUpdate(BaseModel):
    style_preference: dict


async def _prepare_risk_section_generation(
    enterprise_id: str,
    chapter_key: str,
    current_user,
    db,
):
    """单章生成前置校验，返回 (context, ai_config, cdef, report, style_pref)。"""
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    context = await build_risk_management_context(enterprise_id, db)
    if context["total_events"] == 0:
        raise HTTPException(400, "请先录入风险分级管控数据")
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")
    cdef = next((c for c in RA_CHAPTER_DEFINITIONS if c["key"] == chapter_key), None)
    if not cdef:
        raise HTTPException(400, "未知章节")
    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["draft", "generating", "completed"]),
        ).order_by(RiskAssessmentReport.id)
    )).scalars().first()
    if not report:
        report = RiskAssessmentReport(enterprise_id=enterprise_id, title="", status="draft")
        db.add(report)
    report.status = "draft"
    style_pref = report.style_preference or None
    await db.commit()
    return context, ai_config, cdef, report, style_pref


def _risk_section_event_generator(
    context, ai_config, cdef, report, style_pref, custom_instruction,
):
    """单章生成/重生成共用 SSE 生成器（事件协议与全量 generate 一致）。"""
    async def event_generator():
        try:
            yield sse_event("progress", message=f"正在生成「{cdef['title']}」...",
                            current=1, total=1, section_key=cdef["key"])
            ch_prompt = build_chapter_prompt(
                cdef["key"], context,
                custom_instruction=custom_instruction,
                style_preference=style_pref,
            )
            messages = [
                {"role": "system", "content": _get_ra_system_prompt()},
                {"role": "user", "content": ch_prompt},
            ]
            ch_content = ""
            async for chunk_content in _stream_llm_with_messages_chunked(messages, ai_config):
                ch_content += chunk_content
                yield sse_event("chunk", content=chunk_content, section_key=cdef["key"])
            if not ch_content.strip():
                raise Exception("AI 未返回内容，请重试")
            async with async_session() as bg_db:
                bg_report = (await bg_db.execute(
                    select(RiskAssessmentReport).where(
                        RiskAssessmentReport.id == report.id
                    )
                )).scalar_one_or_none()
                if bg_report:
                    # 拷贝章节后再 upsert：JSONB 内层 dict 原地修改不会被
                    # SQLAlchemy 判定为变更，必须生成新对象才会发 UPDATE
                    chapters = [dict(c) for c in get_chapters(bg_report.summary)]
                    chapters = upsert_chapter(chapters, cdef["key"], cdef["title"], ch_content)
                    bg_report.summary = chapters_to_summary(chapters)
                    await bg_db.commit()
            yield sse_event("section_done", section_key=cdef["key"],
                            message=f"「{cdef['title']}」生成完成",
                            completed=1, total=1)
        except Exception as e:
            import traceback
            logger.error(f"Risk assessment section generation failed: {e}\n{traceback.format_exc()}")
            yield sse_event("error", message=str(e))
    return event_generator


@router.post("/{enterprise_id}/risk-assessment/generate/section")
async def generate_risk_assessment_section(
    enterprise_id: str,
    body: SectionGenerateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """单章生成（SSE），完成后写入草稿 summary.chapters 并落库。"""
    context, ai_config, cdef, report, style_pref = await _prepare_risk_section_generation(
        enterprise_id, body.chapter_key, current_user, db,
    )
    gen = _risk_section_event_generator(
        context, ai_config, cdef, report, style_pref, body.custom_instruction,
    )
    return EventSourceResponse(gen())


@router.post("/{enterprise_id}/risk-assessment/sections/{chapter_key}/regenerate")
async def regenerate_risk_assessment_section(
    enterprise_id: str,
    chapter_key: str,
    body: SectionRegenerateRequest | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """单章重新生成（SSE），复用单章生成逻辑。"""
    context, ai_config, cdef, report, style_pref = await _prepare_risk_section_generation(
        enterprise_id, chapter_key, current_user, db,
    )
    gen = _risk_section_event_generator(
        context, ai_config, cdef, report, style_pref,
        body.custom_instruction if body else None,
    )
    return EventSourceResponse(gen())


@router.put("/{enterprise_id}/risk-assessment/sections/{chapter_key}")
async def save_risk_assessment_section(
    enterprise_id: str,
    chapter_key: str,
    body: SectionContentUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """保存单章内容到草稿 summary.chapters（title 从章节定义取）。"""
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["draft", "generating"]),
        )
    )).scalars().first()
    if not report:
        raise HTTPException(404, "请先生成报告")
    title = next(
        (c["title"] for c in RA_CHAPTER_DEFINITIONS if c["key"] == chapter_key),
        chapter_key,
    )
    # 拷贝章节后再 upsert，避免 JSONB 原地修改不被识别
    chapters = [dict(c) for c in get_chapters(report.summary)]
    chapters = upsert_chapter(chapters, chapter_key, title, body.content)
    report.summary = chapters_to_summary(chapters)
    await db.commit()
    return ApiResponse(data={"content_length": len(body.content)})


@router.post("/{enterprise_id}/risk-assessment/review")
async def review_risk_assessment(
    enterprise_id: str,
    body: ReportReviewRequest | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """按确定性规则审查草稿章节，返回 issues（不调用 LLM）。"""
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["draft", "generating", "completed"]),
        )
    )).scalars().first()
    if not report:
        raise HTTPException(404, "请先生成报告")
    chapters = get_chapters(report.summary)
    keys = set(body.section_keys) if body and body.section_keys else None
    targets = [c for c in chapters if keys is None or c.get("key") in keys]
    issues = review_report_chapters(targets)
    return ApiResponse(data={"report_id": report.id, "issues": issues})


@router.post("/{enterprise_id}/risk-assessment/review/apply")
async def apply_risk_assessment_review(
    enterprise_id: str,
    body: ReportReviewRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """对指定章节用 LLM 重写，返回 {applied:[...]}，不落库。"""
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status.in_(["draft", "generating", "completed"]),
        )
    )).scalars().first()
    if not report:
        raise HTTPException(404, "请先生成报告")
    chapters = get_chapters(report.summary)
    keys = set(body.section_keys or [])
    issues = review_report_chapters([c for c in chapters if c.get("key") in keys])
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")
    applied = []
    for c in chapters:
        if c.get("key") not in keys:
            continue
        ch_issues = [i for i in issues if i["section_key"] == c.get("key")]
        if not ch_issues:
            continue
        issue_text = "；".join(
            f"{i['issue']}（建议：{i['suggestion']}）" for i in ch_issues
        )
        prompt = (
            "你是注册安全工程师。以下报告章节存在质量问题，请仅重写该章节正文，"
            "保留原章节标题语义，修正问题，不得编造企业数据；表格用 HTML 表格。\n"
            f"【问题】{issue_text}\n"
            f"【原内容】{c.get('content', '')}\n"
            "直接输出修订后的章节正文："
        )
        messages = [
            {"role": "system", "content": _get_ra_system_prompt()},
            {"role": "user", "content": prompt},
        ]
        revised = ""
        try:
            async for chunk_content in _stream_llm_with_messages_chunked(messages, ai_config):
                revised += chunk_content
        except Exception as e:
            raise HTTPException(500, f"AI 修订失败：{e}")
        if not revised.strip() or len(revised.strip()) < 30:
            continue
        applied.append({
            "section_key": c["key"],
            "title": c.get("title", ""),
            "original": c.get("content", ""),
            "revised": revised,
        })
    return ApiResponse(data={"applied": applied})


@router.get("/{enterprise_id}/risk-assessment/style")
async def get_risk_assessment_style(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """读取报告级创作风格偏好。"""
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id
        )
    )).scalars().first()
    return ApiResponse(data={
        "style_preference": (report.style_preference if report else {}) or {},
    })


@router.put("/{enterprise_id}/risk-assessment/style")
async def save_risk_assessment_style(
    enterprise_id: str,
    body: StyleUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """保存报告级创作风格偏好（强制 diagram_preference=none）。"""
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id
        )
    )).scalars().first()
    if not report:
        report = RiskAssessmentReport(enterprise_id=enterprise_id, title="", status="draft")
        db.add(report)
    style = dict(body.style_preference)
    style["diagram_preference"] = "none"
    report.style_preference = style
    await db.commit()
    return ApiResponse(data={"style_preference": style})


@router.post("/{enterprise_id}/risk-assessment/merge")
async def merge_risk_assessment(
    enterprise_id: str,
    request: RiskAssessmentGenerateRequest = RiskAssessmentGenerateRequest(),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Merge edited chapters into final risk assessment report."""
    ent = (
        await db.execute(
            select(Enterprise).where(
                Enterprise.id == enterprise_id,
                Enterprise.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "ERROR")

    import json as _json
    chapters_data = request.custom_instruction

    report = (
        (await db.execute(
            select(RiskAssessmentReport).where(
                RiskAssessmentReport.enterprise_id == enterprise_id,
                RiskAssessmentReport.status.in_(["generating", "draft", "completed"]),
            )
        )).scalars().first()
    )

    if not report:
        report = RiskAssessmentReport(
            enterprise_id=enterprise_id,
            title="",
            status="draft",
        )
        db.add(report)
        await db.commit()

    chapters = []
    try:
        if chapters_data:
            chapters = _json.loads(chapters_data)
    except Exception:
        raise HTTPException(400, "ERROR")

    if not chapters:
        raise HTTPException(400, "ERROR")

    report_title = f"#{ent.name} 生产安全事故风险评估报告"
    merged_parts = []
    for ch in chapters:
        merged_parts.append(f"## {ch.get('title', '')}\n\n{ch.get('content', '')}")
    merged = report_title + "\n\n" + "\n\n".join(merged_parts)

    report.title = report_title
    merged = _clean_for_docx(merged)
    report.content = merged
    report.status = "completed"
    report.summary = {"chapters": chapters}
    try:
        import json as _json2, re as _re2
        last_ch = chapters[-1] if chapters else None
        if last_ch:
            m = _re2.search(r"\{[^}]+\}\s*$", last_ch.get("content", ""))
            if m:
                struct = _json2.loads(m.group())
                report.summary.update(struct)
    except Exception:
        pass
    report.generated_at = datetime.now(timezone.utc)
    await db.commit()
    _schedule_enterprise_index_rebuild(enterprise_id)

    return ApiResponse(data={"report_id": report.id, "title": report_title, "status": "completed"})
