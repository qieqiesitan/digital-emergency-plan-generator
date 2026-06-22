import os, re, markdown, io, asyncio, hashlib, logging, traceback
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.enterprise import Enterprise, PlanProject, PlanSection
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user
from app.config import settings
from pydantic import BaseModel
from app.services.mermaid_renderer import (
    _extract_mermaid_code, render_mermaid_png, render_svg_to_png,
    _mermaid_hash, replace_mermaid_with_placeholders
)
from app.services.docx_template import (
    generate_plan_docx, fix_markdown_tables, _wrap_raw_mermaid,
    html_to_docx_content
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Export"])

class ExportPreviewResponse(BaseModel):
    plan_id: str; title: str; html: str

class ExportValidationResponse(BaseModel):
    valid: bool; issues: list[dict]; warnings: list[str]

# Preview CSS matching TipTap editor styling
PREVIEW_CSS = """<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 14px; line-height: 1.6; color: #333; padding: 20px;
  }
  h1 { font-size: 24px; font-weight: 700; margin: 20px 0 12px; }
  h2 { font-size: 20px; font-weight: 600; margin: 18px 0 10px; }
  h3 { font-size: 16px; font-weight: 600; margin: 16px 0 8px; }
  h4 { font-size: 15px; font-weight: 600; margin: 14px 0 6px; }
  h5 { font-size: 14px; font-weight: 600; margin: 12px 0 6px; }
  h6 { font-size: 13px; font-weight: 600; margin: 10px 0 4px; }
  p { margin: 0 0 8px; }
  ul, ol { padding-left: 24px; margin: 0 0 8px; }
  li { margin-bottom: 4px; }
  table {
    border-collapse: collapse; width: 100%%; margin: 12px 0;
    table-layout: auto; word-break: break-all; overflow-wrap: break-word;
  }
  table td, table th {
    border: 1px solid #d9d9d9 !important; padding: 6px 10px !important;
    min-width: 20px; vertical-align: top;
  }
  table th { background: #fafafa; font-weight: 600; text-align: center; white-space: nowrap; }
  table tr:nth-child(even) { background: #fafafa; }
  strong { font-weight: 700; }
  em { font-style: italic; }
  u { text-decoration: underline; }
  s { text-decoration: line-through; }
  blockquote {
    border-left: 3px solid #d9d9d9; padding-left: 12px; margin: 8px 0; color: #666;
  }
  hr.plan-section-separator {
    border: none; border-top: 1px solid #e8e8e8; margin: 24px 0;
  }
</style>"""


def _strip_section_heading(html: str) -> str:
    """Recursively strip all leading heading tags from HTML or Markdown content."""
    if not html or not html.strip():
        return html
    while True:
        m_html = re.match(
            r'\s*<h[1-6][^>]*>\s*(?:[\d.]+\s*)?.*?</h[1-6]>\s*',
            html, re.DOTALL
        )
        if m_html:
            html = html[m_html.end():]
            continue
        m_p = re.match(
            r'\s*<(?:p|div)[^>]*>\s*(?:[\d.]+\s*)?[^<]{1,80}</(?:p|div)>\s*',
            html, re.DOTALL
        )
        if m_p:
            html = html[m_p.end():]
            continue
        m_md = re.match(r'\s*#{1,6}\s+[^\n]+\n\s*', html)
        if m_md:
            html = html[m_md.end():]
            continue
        m_num = re.match(r'\s*\d+\.\s+[^\n]+\n\s*', html)
        if m_num:
            html = html[m_num.end():]
            continue
        m_plain = re.match(r'\s*[^\n<]{1,80}\n\s*\n', html)
        if m_plain:
            html = html[m_plain.end():]
            continue
        break
    return html


# Route: Export Preview (unchanged)

@router.get("/{plan_id}/export/preview")
async def get_export_preview(
    plan_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = (
        await db.execute(
            select(PlanProject).where(
                PlanProject.id == plan_id,
                PlanProject.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")

    sections = (
        await db.execute(
            select(PlanSection)
            .where(PlanSection.plan_project_id == plan_id)
            .order_by(PlanSection.sort_order)
        )
    ).scalars().all()

    if not sections:
        raise HTTPException(404, "Plan has no sections")

    html_parts = []
    for section in sections:
        if not section.content or not section.content.strip():
            continue
        content = section.content
        content = _strip_section_heading(content)
        if not content.strip().startswith("<"):
            content = _wrap_raw_mermaid(content)

        level = min(section.level + 1, 6)
        html_parts.append(f"<h{level}>{section.title}</h{level}>")

        if not content.strip().startswith("<"):
            content = markdown.markdown(content, extensions=["tables", "fenced_code"])

        content = fix_markdown_tables(content)
        html_parts.append(content)
        html_parts.append('<hr class="plan-section-separator">')

    full_html = "\n".join(html_parts)

    wrapped = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{PREVIEW_CSS}</head>
<body>
<h1>{plan.title}</h1>
{full_html}
</body>
</html>"""

    return ApiResponse(data=ExportPreviewResponse(
        plan_id=plan_id,
        title=plan.title,
        html=wrapped,
    ))


# Route: Export DOCX (完全重写，使用模板引擎)

@router.post("/{plan_id}/export/docx")
async def export_plan_docx(
    plan_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = (
        await db.execute(
            select(PlanProject).where(
                PlanProject.id == plan_id,
                PlanProject.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")

    enterprise = (
        await db.execute(
            select(Enterprise).where(Enterprise.id == plan.enterprise_id)
        )
    ).scalar_one_or_none()
    if not enterprise:
        raise HTTPException(404, "Enterprise not found")

    sections = (
        await db.execute(
            select(PlanSection)
            .where(PlanSection.plan_project_id == plan_id)
            .order_by(PlanSection.sort_order)
        )
    ).scalars().all()

    if not sections:
        raise HTTPException(404, "Plan has no sections")

    # 构建章节数据
    sections_data = []
    for s in sections:
        if not s.content or not s.content.strip():
            continue
        content = s.content
        content = _strip_section_heading(content)
        if not content.strip().startswith("<"):
            content = _wrap_raw_mermaid(content)

        if not content.strip().startswith("<"):
            content = markdown.markdown(content, extensions=["tables", "fenced_code"])

        content = fix_markdown_tables(content)

        sections_data.append({
            "title": s.title,
            "level": s.level,
            "content": content,
            "mermaid_svgs": s.mermaid_svgs or {},
        })

    # 生成文档
    now = datetime.now()
    doc = generate_plan_docx(
        company_name=enterprise.name,
        plan_title=plan.title,
        plan_type=plan.plan_type,
        plan_number=getattr(plan, 'plan_number', '') or f"XXZYT-YA-001",
        version_number=getattr(plan, 'version_number', '') or f"A-{now.year}-{now.month:02d}",
        sections=sections_data,
    )

    # 保存
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", plan.title)
    filename = f"{safe_title}.docx"
    path = os.path.join(settings.EXPORT_DIR, filename)
    doc.save(path)

    return FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# Route: Validate Export (unchanged)

@router.post("/{plan_id}/export/validate")
async def validate_plan_export(
    plan_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = (
        await db.execute(
            select(PlanProject).where(
                PlanProject.id == plan_id,
                PlanProject.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")

    sections = (
        await db.execute(
            select(PlanSection)
            .where(PlanSection.plan_project_id == plan_id)
            .order_by(PlanSection.sort_order)
        )
    ).scalars().all()

    issues = []
    warnings = []

    if not sections:
        issues.append({"section_key": "", "section_title": "All", "issue": "Plan has no sections"})
    else:
        for section in sections:
            if not section.content or not section.content.strip():
                issues.append({
                    "section_key": section.section_key,
                    "section_title": section.title,
                    "issue": "Section content is empty",
                })

        for section in sections:
            if section.content:
                codes = _extract_mermaid_code(section.content)
                for code in codes:
                    if not code.strip().startswith(("flowchart", "graph", "sequenceDiagram",
                        "classDiagram", "stateDiagram", "erDiagram", "gantt", "pie",
                        "gitGraph", "mindmap", "timeline", "journey")):
                        warnings.append(f"Mermaid in section '{section.title}' may be missing diagram type declaration")

    return ApiResponse(data={
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    })
