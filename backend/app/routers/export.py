import os, re, markdown, io, asyncio, hashlib, html, logging, traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.enterprise import EmergencyResource, Enterprise, PlanProject, PlanSection, PlanTemplate
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user
from app.config import settings
from pydantic import BaseModel
from app.services.mermaid_renderer import (
    render_mermaid_png, render_svg_to_png,
    _mermaid_hash, replace_mermaid_with_placeholders
)
from app.services.docx_template import (
    generate_plan_docx, fix_markdown_tables, _wrap_raw_mermaid,
    html_to_docx_content
)
from app.services.plan_section_content import strip_section_heading

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Export"])

class ExportPreviewResponse(BaseModel):
    plan_id: str; title: str; html: str

class ExportValidationResponse(BaseModel):
    valid: bool; issues: list[dict]; warnings: list[dict]

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
  .mermaid-diagram { max-width: 100%%; }
  .mermaid-diagram svg { max-width: 100%%; height: auto; }
  .mermaid-rendered { max-width: 100%%; }
  .mermaid-rendered svg { max-width: 100%%; height: auto; }
  .emergency-card-section { margin: 16px 0; display: grid; gap: 14px; }
  .emergency-card {
    border: 1px solid #e8e8e8; border-radius: 10px; padding: 14px 18px;
    background: #fff; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    break-inside: avoid; page-break-inside: avoid;
  }
  .emergency-card h3 {
    margin: 0 0 8px; font-size: 15px; font-weight: 700;
    padding-left: 10px; border-left: 4px solid #d9d9d9;
  }
  .emergency-card ol, .emergency-card ul { margin-bottom: 0; }
  .emergency-card li { margin-bottom: 6px; }
  .emergency-card[data-theme="danger"] { background: #fff7f7; border-color: #ffccc7; }
  .emergency-card[data-theme="danger"] h3 { border-left-color: #ff4d4f; }
  .emergency-card[data-theme="action"] { background: #fffdf6; border-color: #ffe7ba; }
  .emergency-card[data-theme="action"] h3 { border-left-color: #fa8c16; }
  .emergency-card[data-theme="info"] { background: #f6faff; border-color: #bae0ff; }
  .emergency-card[data-theme="info"] h3 { border-left-color: #1677ff; }
  .emergency-card[data-theme="contact"] { background: #f9fff6; border-color: #d9f7be; }
  .emergency-card[data-theme="contact"] h3 { border-left-color: #52c41a; }
  .emergency-card[data-theme="default"] h3 { border-left-color: #8c8c8c; }
</style>"""


def _strip_section_heading(html: str, section_title: str | None = None) -> str:
    """兼容别名：导出预览与历史调用继续使用（实现已抽到 plan_section_content）。"""
    return strip_section_heading(html, section_title)


def _build_section_numbers(sections: list) -> dict:
    """为章节生成编号。level 0 → 1,2,3; level 1 → 1.1,1.2; level 2 → 1.1.1"""
    counters = [0] * 6
    numbers = {}
    for sec in sections:
        level = sec.level
        counters[level] += 1
        for i in range(level + 1, len(counters)):
            counters[i] = 0
        parts = [str(counters[i]) for i in range(level + 1) if counters[i] > 0]
        numbers[id(sec)] = ".".join(parts) if len(parts) > 1 else parts[0]
    return numbers


_CARD_THEME_KEYWORDS = [
    ("danger", ("危险", "警示", "禁忌", "特别警示")),
    ("action", ("处置", "响应", "报警", "步骤", "初起", "报告", "发现")),
    ("info", ("疏散", "集合", "清点", "搜救", "路线")),
    ("contact", ("电话", "联系", "通讯")),
]


def _card_theme_for_title(title: str) -> str:
    """根据卡片分区标题推断主题色（danger/action/info/contact/default）。"""
    for theme, keywords in _CARD_THEME_KEYWORDS:
        if any(kw in title for kw in keywords):
            return theme
    return "default"


def _wrap_emergency_cards(content: str) -> str:
    """按 h3 分区把章节正文切成「应急处置卡」卡片；无 h3 时整段单卡。"""
    pattern = re.compile(r"(<h3[^>]*>.*?</h3>)", re.DOTALL | re.IGNORECASE)
    parts = pattern.split(content)
    preamble = parts[0].strip()
    cards = []
    if preamble:
        cards.append(f'<div class="emergency-card" data-theme="default">{preamble}</div>')
    for i in range(1, len(parts), 2):
        heading = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        title = re.sub(r"<[^>]+>", "", heading).strip()
        theme = _card_theme_for_title(title)
        cards.append(f'<div class="emergency-card" data-theme="{theme}">{heading}{body}</div>')
    if not cards:
        cards.append(f'<div class="emergency-card" data-theme="default">{content}</div>')
    return f'<div class="emergency-card-section">{"".join(cards)}</div>'


def _build_preview_section_html(section, sec_numbers: dict, plan_type: str = "") -> str:
    """构建单个章节的导出预览 HTML（标题 + 正文 + 附图）。

    section: PlanSection ORM 对象（或等效 mock），需要 title/level/content/
             mermaid_svgs/diagram_svgs 属性。
    sec_numbers: {id(section): "1.2"} 章节编号映射。
    plan_type: 预案类型，onsite 时 sec_3* 章节卡片化渲染。
    """
    content = section.content or ""
    content = _strip_section_heading(content, getattr(section, "title", None))
    # 仅当内容不含已被包裹的 Mermaid 时才包装原始代码
    if '<code class="language-mermaid"' not in content and '```mermaid' not in content:
        content = _wrap_raw_mermaid(content)

    level = min(section.level + 1, 6)
    num = sec_numbers.get(id(section), "")
    parts = [f"<h{level}>{num} {section.title}</h{level}>"]

    # 仅在内容不是 HTML 时才做 Markdown 转换（DB 中已存 HTML）
    if not content.strip().startswith('<'):
        content = markdown.markdown(content, extensions=["tables", "fenced_code", "md_in_html"])

    content = fix_markdown_tables(content)

    # 现场处置方案「应急处置卡」系列章节：按 h3 分区渲染成卡片
    is_card_section = (
        plan_type == "onsite"
        and str(getattr(section, "section_key", "")).startswith("sec_3")
    )
    if is_card_section:
        content = _wrap_emergency_cards(content)

    # 服务端嵌入 Mermaid SVG（预览直接显示，不依赖前端 MermaidRenderer）
    mermaid_svgs = section.mermaid_svgs or {}
    if mermaid_svgs:
        import hashlib as _hl

        def _embed_preview_svgs(m):
            code = html.unescape(m.group(1).strip())
            h = _hl.sha256(code.encode('utf-8')).hexdigest()[:16]
            svg = mermaid_svgs.get(h)
            if svg:
                _m = re.search(r'<svg[^>]*>.*?</svg>', svg, re.DOTALL)
                svg_clean = _m.group(0) if _m else svg
                return '<div class="mermaid-diagram" style="margin:16px 0;padding:16px;background:#fafafa;border:1px solid #e8e8e8;border-radius:6px;overflow-x:auto;"><div style="font-size:12px;color:#999;margin-bottom:8px;font-weight:500;">流程图</div><div style="text-align:center;">' + svg_clean + '</div></div>'
            return m.group(0)
        content = re.sub(
            r'<code class="language-mermaid"[^>]*>(.*?)</code>',
            _embed_preview_svgs, content, flags=re.DOTALL
        )

    parts.append(content)

    # 附图：非占位 SVG 内嵌，占位转文字
    for key, meta in (section.diagram_svgs or {}).items():
        if isinstance(meta, dict) and meta.get("placeholder"):
            parts.append(
                f'<p class="diagram-placeholder">【{html.escape(str(key))}】待补充数据后生成'
                f"（{html.escape(str(meta.get('reason','')))}）</p>"
            )
        elif isinstance(meta, dict) and meta.get("svg"):
            svg = meta["svg"]
            m = re.search(r"<svg[^>]*>.*?</svg>", svg, re.DOTALL)
            if m:
                parts.append(
                    '<div class="mermaid-diagram" style="margin:16px 0;padding:16px;'
                    'background:#fafafa;border:1px solid #e8e8e8;border-radius:6px;'
                    'text-align:center;">' + m.group(0) + "</div>"
                )

    return "\n".join(parts)


# Route: Export Preview

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
    sec_numbers = _build_section_numbers(sections)

    for section in sections:
        if not section.content or not section.content.strip():
            continue
        html_parts.append(_build_preview_section_html(section, sec_numbers, plan.plan_type))
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

def _build_signers_from_org(org_structure: list | None) -> list[dict]:
    """组织架构 → 签署人列表（跳过无姓名成员）。"""
    signers = []
    for g in org_structure or []:
        for m in g.get("members", []):
            if m.get("name"):
                signers.append({"seq": len(signers) + 1, "name": m["name"], "title": m.get("position", "")})
    return signers


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
        content = _strip_section_heading(content, s.title)

        _ms = s.mermaid_svgs or {}
        sections_data.append({
            "section_key": s.section_key,
            "title": s.title,
            "level": s.level,
            "content": content,
            "mermaid_svgs": _ms,
            "diagram_svgs": s.diagram_svgs or {},
        })

    # 质量校验 → 正文证据片段（预览与 docx 高亮共用）
    from app.services.plan_quality_service import check_plan
    required = []
    tpl = (await db.execute(
        select(PlanTemplate).where(
            PlanTemplate.plan_type == plan.plan_type, PlanTemplate.is_active == True
        ).order_by(PlanTemplate.version.desc()).limit(1)
    )).scalar_one_or_none()
    if tpl and tpl.structure:
        required = [item.get("key") for item in tpl.structure if item.get("required")]
    resources = (await db.execute(
        select(EmergencyResource).where(EmergencyResource.enterprise_id == plan.enterprise_id)
    )).scalars().all()
    quality_result = check_plan(
        plan, enterprise, sections,
        required_sections=required or None,
        resources=resources,
        has_risk=bool(enterprise.risk_sources) if enterprise else False,
    )
    quality_evidence: dict[str, list[str]] = {}
    for w in quality_result["warnings"]:
        if w.get("evidence"):
            quality_evidence.setdefault(w.get("section_key", ""), []).append(w["evidence"])

    # 生成文档
    if not plan.plan_number or not plan.version_number:
        raise HTTPException(400, "请先设置预案编号与版本号")
    signers = _build_signers_from_org(enterprise.org_structure or [])
    try:
        import asyncio as _asyncio_dbg
        # ponytail: 在线程中运行 generate_plan_docx，避免 Playwright sync API 与 asyncio 冲突
        doc = await _asyncio_dbg.to_thread(
            generate_plan_docx,
            company_name=enterprise.name,
            plan_title=plan.title,
            plan_type=plan.plan_type,
            plan_number=plan.plan_number,
            version_number=plan.version_number,
            sections=sections_data,
            signers=signers or None,
            quality_evidence=quality_evidence or None,
        )

        # 保存
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        safe_title = re.sub(r'[\/*?:"<>|]', "_", plan.title)
        filename = f"{safe_title}.docx"
        filepath = os.path.join(settings.EXPORT_DIR, filename)
        doc.save(filepath)

        return FileResponse(
            filepath,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        logger.error(f"DOCX generation failed for plan {plan_id}: {traceback.format_exc()}")
        raise HTTPException(500, f"DOCX 生成失败: {str(e)}")


# Route: Validate Export

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

    enterprise = (
        await db.execute(
            select(Enterprise).where(Enterprise.id == plan.enterprise_id)
        )
    ).scalar_one_or_none()

    sections = (
        await db.execute(
            select(PlanSection)
            .where(PlanSection.plan_project_id == plan_id)
            .order_by(PlanSection.sort_order)
        )
    ).scalars().all()

    if not sections:
        return ApiResponse(data={
            "valid": False,
            "issues": [{"section_key": "", "section_title": "All", "issue": "预案没有章节"}],
            "warnings": [],
        })

    from app.services.plan_quality_service import check_plan
    required = []
    tpl = (await db.execute(
        select(PlanTemplate).where(
            PlanTemplate.plan_type == plan.plan_type, PlanTemplate.is_active == True
        ).order_by(PlanTemplate.version.desc()).limit(1)
    )).scalar_one_or_none()
    if tpl and tpl.structure:
        required = [item.get("key") for item in tpl.structure if item.get("required")]
    resources = (await db.execute(
        select(EmergencyResource).where(EmergencyResource.enterprise_id == plan.enterprise_id)
    )).scalars().all()
    result = check_plan(
        plan, enterprise, sections,
        required_sections=required or None,
        resources=resources,
        # 风险点来源：企业档案风险源（selectin 已预加载），用于 E3「资源数量为 0」告警前提
        has_risk=bool(enterprise.risk_sources) if enterprise else False,
    )
    # 结构化为 {section_key, section_title, warning, evidence}，前端可定位正文并高亮
    warnings = [
        {
            "section_key": w.get("section_key", ""),
            "section_title": w.get("section_title", ""),
            "warning": w["warning"],
            "evidence": w.get("evidence", ""),
        }
        for w in result["warnings"]
    ]
    return ApiResponse(data={
        "valid": result["valid"],
        "issues": result["issues"],
        "warnings": warnings,
    })

