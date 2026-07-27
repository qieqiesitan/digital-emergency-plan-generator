from pydantic import BaseModel
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from sse_starlette.sse import EventSourceResponse

from app.database import get_db, async_session

from app.models.user import User

from app.models.enterprise import Enterprise, PlanProject, PlanSection, PlanTemplate, AIConfig, RiskSource, EmergencyResource, PlanVersion

from app.models.risk_assessment import RiskAssessmentReport

from app.models.resource_investigation import ResourceInvestigationReport

from app.models.risk_assessment import RiskAssessmentReport

from app.models.resource_investigation import ResourceInvestigationReport

from app.dependencies import get_current_user

from app.config import settings

from Crypto.Cipher import AES

from Crypto.Util.Padding import unpad

import httpx

import asyncio

import logging

import markdown

import re

from app.services.llm_client import decrypt_api_key, llm_chat_completion, llm_collect_all
from app.services.mermaid_renderer import extract_mermaid_from_markdown, render_mermaid_svg, _mermaid_hash
from app.services.sse_utils import sse_event
from app.services.prompt_cache import ensure_loaded, get_system_prompt, build_system_prompt_with_style, REGULATION_WRITING_RULE, get_section_prompt, get_mermaid_prompt, get_diagram_prompt, render_template
from app.regulations.context_builder import RegulationContextBuilder

from app.schemas.plan import RegenerateRequest

logger = logging.getLogger(__name__)



router = APIRouter(prefix="/plans", tags=["Generation"])



_active_generations: dict[str, bool] = {}

_background_tasks: dict[str, asyncio.Task] = {}



# Mermaid flowchart section mapping by section_key

FLOWCHART_SECTION_MAP: dict[str, str] = {

    # Comprehensive

    "sec_4":   "预警信息报告流程",

    "sec_5":   "应急响应流程",

    "sec_5_2": "应急响应程序流程",

    "sec_5_3": "应急处置措施流程",

    # Special

    "sec_3":   "处置程序流程",

    "sec_3_1": "应急响应启动流程",

    "sec_3_2": "现场应急处置流程",

}
# SECTION_DIAGRAM_TYPE_MAP: 每个章节对应的 Mermaid 图表类型
# flowchart TD / graph TD / graph LR / pie / sequenceDiagram / mindmap
SECTION_DIAGRAM_TYPE_MAP: dict[str, str] = {
    "sec_4":   "flowchart TD",
    "sec_5":   "flowchart TD",
    "sec_5_2": "flowchart TD",
    "sec_5_3": "flowchart TD",
    "sec_3":   "flowchart TD",
    "sec_3_1": "sequenceDiagram",
    "sec_3_2": "flowchart TD",
}




def _decrypt_api_key(hex_str: str) -> str:
    # Delegate to llm_client (unified decrypt)
    return decrypt_api_key(hex_str)



    # _sse → sse_event (移入 services/sse_utils.py)

def _build_system_prompt(plan_type: str = "*", style_preference: dict | None = None, advanced_overrides: dict | None = None) -> str:
    """构建系统提示词，优先风格参数，fallback 到数据库模板。"""
    return build_system_prompt_with_style(plan_type, style_preference, advanced_overrides)

def _get_mermaid_instruction(section_key: str | None, section_title: str, diagram_preference: str = "mermaid") -> str | None:
    """Return a Mermaid-specific prompt instruction if this section needs a flowchart."""
    if diagram_preference == "none":
        return None
    if not section_key:
        return None
    flow_label = FLOWCHART_SECTION_MAP.get(section_key)
    if not flow_label:
        return None
    diagram_type = SECTION_DIAGRAM_TYPE_MAP.get(section_key, "flowchart TD")
    template = get_diagram_prompt(diagram_type)
    if template:
        return render_template(template, {"flow_label": flow_label, "section_title": section_title, "diagram_type": diagram_type})
    return (
        "\n\n---\n"
        f"请在以上正文内容之后，额外输出一个 Mermaid flowchart 流程图，描述「{flow_label}」。\n"
        f"要求：\n"
        f"1. 使用 flowchart TD（自上而下）或 flowchart LR（从左到右）布局\n"
        f"2. 包含关键节点：触发条件、报告程序、响应启动、处置执行、结束/恢复等\n"
        f"3. 节点用方括号[]或圆角括号()表示，关键决策节点用菱形{{}}表示\n"
        f"4. 流程图放在单独的 ```mermaid 代码块中，放在章节正文末尾\n"
        f"5. 节点文字使用中文，简洁明了（每节点不超过15个字）\n"
    )

def _build_section_prompt(section_title: str, enterprise_data: dict, custom_instruction: str | None = None, section_number: int | None = None, section_key: str | None = None, plan_type: str = "*", accident_type: str | None = None, diagram_preference: str = "mermaid") -> str:
    """构建章节提示词，优先使用数据库模板，未命中则用代码拼接兜底。"""
    # 尝试从数据库获取模板
    if plan_type != "*" and section_key:
        tmpl = get_section_prompt(plan_type, section_key)
        if tmpl and tmpl.get("user_prompt_template"):
            variables = {"enterprise_data": json.dumps(enterprise_data, ensure_ascii=False, indent=2), "accident_type": accident_type or ""}
            prompt = render_template(tmpl["user_prompt_template"], variables)
            if tmpl.get("system_prompt"):
                prompt = tmpl["system_prompt"] + "\n\n---\n\n" + prompt
            mermaid_inst = _get_mermaid_instruction(section_key, section_title, diagram_preference)
            if mermaid_inst:
                prompt += "\n\n" + mermaid_inst

            # 追加法规上下文（修复：DB 模板路径也要注入法规）
            reg_ctx = RegulationContextBuilder().get_chapter_context(
                section_key=section_key,
                section_title=section_title,
                plan_type=plan_type,
                enterprise_data=enterprise_data,
            )
            if reg_ctx:
                prompt += "\n\n" + REGULATION_WRITING_RULE + "\n\n" + reg_ctx

            return prompt

    # 兜底：代码拼接
    num_hint = f"这是应急预案的第{section_number}个章节，请在正文中使用“{section_number}.”或“{section_number}.x”的编号格式。\n" if section_number is not None else ""

    prompt = f"请撰写应急预案章节《{section_title}》的内容。\n\n"
    if accident_type:
        prompt += f"【事故类型：{accident_type}】请围绕{accident_type}事故的特点、风险源、致灾机理、典型后果和针对性处置措施撰写以下内容，避免与其他事故类型的预案雷同。\n\n"

    prompt += f"企业信息：\n{json.dumps(enterprise_data, ensure_ascii=False, indent=2)}\n\n"

    if num_hint:

        prompt += num_hint + "\n"

    if custom_instruction:

        prompt += f"额外要求：{custom_instruction}\n\n"

    mermaid_inst = _get_mermaid_instruction(section_key, section_title, diagram_preference)

    if mermaid_inst:

        prompt += mermaid_inst + "\n"

    prompt += "请直接输出章节正文内容，不要重复章节标题作为正文第一行。"

    reg_ctx = RegulationContextBuilder().get_chapter_context(
        section_key=section_key,
        section_title=section_title,
        plan_type=plan_type,
        enterprise_data=enterprise_data,
    )
    if reg_ctx:
        prompt += "\n\n" + REGULATION_WRITING_RULE + "\n\n" + reg_ctx

    return prompt

def _collect_enterprise_data(enterprise: Enterprise, risk_sources: list, resources: list) -> dict:

    return {

        "name": enterprise.name, "address": enterprise.address,

        "industry": enterprise.industry, "business_scope": enterprise.business_scope,

        "employee_count": enterprise.employee_count, "building_overview": enterprise.building_overview,

        "org_structure": enterprise.org_structure, "surrounding_info": enterprise.surrounding_info,

        "legal_representative": enterprise.legal_representative,

        "credit_code": enterprise.credit_code,

        "economic_type": enterprise.economic_type,

        "established_date": str(enterprise.established_date) if enterprise.established_date else None,

        "registered_capital": enterprise.registered_capital,

        "phone": enterprise.phone,

        "land_area": enterprise.land_area,

        "building_area": enterprise.building_area,

        "safety_officer": enterprise.safety_officer,

        "safety_standardization": enterprise.safety_standardization,

        "fire_approval": enterprise.fire_approval,

        "main_products": enterprise.main_products,

        "hazardous_chemicals": enterprise.hazardous_chemicals,

        "special_equipment": enterprise.special_equipment,

        "risk_sources": [{"categories": r.categories, "name": r.name, "location": r.location, "description": r.description, "risk_level": r.risk_level, "control_measures": r.control_measures} for r in risk_sources],

        "emergency_resources": [{"category": r.category, "name": r.name, "specification": r.specification, "quantity": r.quantity, "unit": r.unit, "location": r.location} for r in resources],

    }



async def _enrich_with_reports(enterprise_data: dict, enterprise_id: str, db: AsyncSession) -> dict:

    ra = (await db.execute(

        select(RiskAssessmentReport).where(

            RiskAssessmentReport.enterprise_id == enterprise_id,

            RiskAssessmentReport.status == "completed",

        )

    )).scalar_one_or_none()

    if ra and ra.summary:

        enterprise_data["risk_assessment"] = ra.summary

    ri = (await db.execute(

        select(ResourceInvestigationReport).where(

            ResourceInvestigationReport.enterprise_id == enterprise_id,

            ResourceInvestigationReport.status == "completed",

        )

    )).scalar_one_or_none()

    if ri and ri.summary:

        enterprise_data["resource_investigation"] = ri.summary

    return enterprise_data









async def _pre_render_mermaid_svgs(md_text: str) -> dict:

    """Extract Mermaid codes from Markdown, render to SVG, return {hash: svg} dict."""

    codes = extract_mermaid_from_markdown(md_text)

    if not codes:

        return {}

    result = {}

    for code in codes:

        try:

            h = _mermaid_hash(code)

            svg = await render_mermaid_svg(code)

            result[h] = svg

            logger.info("Pre-rendered Mermaid SVG for hash %s", h)
        except Exception as e:
            logger.warning("Failed to pre-render Mermaid SVG: %s", e)
    return result


def _embed_mermaid_svgs(html_content: str, svgs: dict[str, str]) -> str:
    """Replace <code class="language-mermaid"> blocks with pre-rendered inline SVGs.
    Eliminates the frontend re-rendering path entirely.
    """
    if not svgs:
        return html_content
    
    import html as _html
    import hashlib as _hashlib
    import re as _re
    
    pattern = r'<pre><code class="language-mermaid">(.*?)</code></pre>'
    
    def _replace(m):
        code = _html.unescape(m.group(1).strip())
        h = _hashlib.sha256(code.encode('utf-8')).hexdigest()[:16]
        svg = svgs.get(h)
        if svg:
            return f'<div class="mermaid-rendered" data-mermaid-hash="{h}">{svg}</div>'
        # No pre-rendered SVG - mark for frontend fallback render
        escaped = _html.escape(code)
        return f'<pre><code class="language-mermaid" data-mermaid-unrendered>{escaped}</code></pre>'
    
    return _re.sub(pattern, _replace, html_content, flags=_re.DOTALL)



def _fix_markdown_tables(md_text: str) -> str:

    """Preprocess Markdown to fix malformed tables before HTML conversion.

    

    Handles cases where AI-generated content has:

    - Heading text merged with table header on same line

    - Tables without blank lines before them

    - Non-table text immediately after table rows

    """

    lines = md_text.split('\n')

    result = []

    in_table = False

    i = 0



    while i < len(lines):

        stripped = lines[i].strip()

        if not stripped:

            result.append('')

            in_table = False

            i += 1

            continue



        is_pipe_start = stripped.startswith('|')

        is_sep_line = bool(re.match(r'^\|[\s\-:|]+\|$', stripped))



        # Case 1: Heading text merged with table header on same line

        if not is_pipe_start and '|' in stripped:

            pipe_idx = stripped.find('|')

            if pipe_idx > 0:

                heading = stripped[:pipe_idx].strip()

                table_part = stripped[pipe_idx:].strip()

                if result and result[-1].strip():

                    result.append('')

                result.append(heading)

                result.append('')

                result.append(table_part)

                in_table = True

                i += 1

                continue



        # Case 2: Non-table line after table rows - insert blank line separator

        if not is_pipe_start and not is_sep_line and in_table:

            result.append('')

            in_table = False



        if is_sep_line:

            if not in_table and result and result[-1].strip():

                result.append('')

            result.append(lines[i])

            in_table = True

        elif is_pipe_start:

            if not in_table and result and result[-1].strip():
                result.append('')
            result.append(lines[i])
            in_table = True

        else:

            result.append(lines[i])



        i += 1



    return '\n'.join(result)

async def _stream_llm_chunks(prompt: str, ai_config: AIConfig, plan_type: str = "*", style_preference=None, advanced_overrides=None):
    try:
        messages = [
            {"role": "system", "content": _build_system_prompt(plan_type, style_preference, advanced_overrides)},
            {"role": "user", "content": prompt},
        ]
        gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=120)
        async for chunk in gen:
            yield chunk
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


async def _stream_llm(prompt: str, ai_config: AIConfig, plan_type: str = "*", style_preference=None, advanced_overrides=None) -> str:
    messages = [
        {"role": "system", "content": _build_system_prompt(plan_type, style_preference, advanced_overrides)},
        {"role": "user", "content": prompt},
    ]
    return await llm_collect_all(messages, ai_config, timeout=120)

@router.post("/{plan_id}/generate/batch")

async def generate_batch(plan_id: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):

    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()

    if not p: raise HTTPException(404, "预案不存在")

    ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()

    if not ai_config: raise HTTPException(400, "请先配置 AI 模型")



    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()

    risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()

    ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}

    if ent:

        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)



    try:

        body = await request.json()

        keys = body.get("section_keys")

    except Exception:

        keys = None



    all_sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()

    target_sections = [s for s in all_sections if (not keys or s.section_key in keys)]



    p.status = "generating"

    await db.commit()

    _active_generations[plan_id] = True

    plan_type = p.plan_type

    # Use a queue to stream events from background task to SSE

    import asyncio as _asyncio

    event_queue: _asyncio.Queue = _asyncio.Queue()



    # Collect section keys for background task

    section_tuples = [(s.section_key, s.title) for s in target_sections]



    async def run_background():

        completed = 0

        failed = 0

        try:

            await event_queue.put(sse_event("progress", message=f"开始批量生成 {len(section_tuples)} 个章节...", current=0, total=len(section_tuples)))

            async with async_session() as bg_db:

                bg_sections = (await bg_db.execute(

                    select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)

                )).scalars().all()

                bg_section_map = {s.section_key: s for s in bg_sections}



                for i, (section_key, section_title) in enumerate(section_tuples):

                    if not _active_generations.get(plan_id):

                        await event_queue.put(sse_event("error", message="生成已取消"))

                        return

                    s = bg_section_map.get(section_key)

                    if not s:

                        continue

                    await event_queue.put(sse_event("progress", message=f"正在生成「{section_title}」({i+1}/{len(section_tuples)})", current=i+1, total=len(section_tuples), section_key=section_key))

                    try:

                        prompt_text = _build_section_prompt(section_title, ent_data, section_number=i+1, section_key=section_key, plan_type=p.plan_type, accident_type=p.accident_type, diagram_preference="mermaid")

                        full = ""

                        async for chunk_content in _stream_llm_chunks(prompt_text, ai_config, plan_type, p.style_preference, p.advanced_prompt_overrides):

                            full += chunk_content

                            await event_queue.put(sse_event("chunk", content=chunk_content, section_key=section_key))

                        s.content = _md_to_html(full); s.ai_generated = True

                        s.mermaid_svgs = await _pre_render_mermaid_svgs(full)
                        await bg_db.commit()

                        completed += 1

                        await event_queue.put(sse_event("section_done", section_key=section_key, message=f"「{section_title}」生成完成", completed=completed, failed=failed))

                    except Exception as e:

                        failed += 1

                        await event_queue.put(sse_event("error", message=f"「{section_title}」生成失败: {e}", section_key=section_key))



                updated = (await bg_db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id))).scalars().all()

                p2 = (await bg_db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()

                if p2:

                    if all(sec.content and sec.content.strip() for sec in updated):

                        p2.status = "completed"

                    else:

                        p2.status = "draft"

                # ponytail: auto-create version snapshot after generation
                try:
                    ver_snapshot = {"title": p2.title, "sections": [{"section_key": s.section_key, "title": s.title, "content": s.content, "ai_generated": s.ai_generated} for s in updated]}
                    new_ver = PlanVersion(plan_project_id=plan_id, version_number=p2.current_version + 1, created_by="auto", description="AI 一键生成完成", snapshot=ver_snapshot)
                    bg_db.add(new_ver)
                    p2.current_version = p2.current_version + 1
                    logger.info(f"Auto-created version {p2.current_version} for plan {plan_id}")
                except Exception as ver_e:
                    logger.error(f"Failed to auto-create version: {ver_e}")
                await bg_db.commit()

                await event_queue.put(sse_event("batch_done", message="批量生成完成", completed=completed, failed=failed))

        except Exception as e:

            try:

                await event_queue.put(sse_event("error", message=str(e)))

            except Exception:

                pass

        finally:

            await event_queue.put(None)  # Sentinel to close SSE



    task = _asyncio.create_task(run_background())

    _background_tasks[plan_id] = task



    async def event_generator():

        while True:

            event = await event_queue.get()

            if event is None:

                break

            yield event



    return EventSourceResponse(event_generator())



@router.post("/{plan_id}/generate/stop")

async def stop_generation(plan_id: str):

    _active_generations[plan_id] = False

    return {"code": 0, "message": "已请求停止生成"}





@router.post("/{plan_id}/generate/batch/background")

async def generate_batch_background(plan_id: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):

    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()

    if not p: raise HTTPException(404, "预案不存在")

    if p.status == "generating":

        if not _active_generations.get(plan_id):

            logger.warning(f"Plan {plan_id} has stale generating status - resetting to draft")

            p.status = "draft"

            await db.commit()

        else:

            return {"code": 0, "message": "正在生成中"}

    ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()

    if not ai_config: raise HTTPException(400, "请先配置 AI 模型")

    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()

    risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()

    ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}

    if ent:

        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)

    try:

        body = await request.json()

        keys = body.get("section_keys")

    except Exception:

        keys = None

    all_sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()

    target_sections = [s for s in all_sections if (not keys or s.section_key in keys)]

    if not target_sections:

        return {"code": 0, "message": "没有可生成的章节"}

    p.status = "generating"

    await db.commit()

    _active_generations[plan_id] = True

    plan_type = p.plan_type

    # Collect section keys (these are plain strings, safe to pass to background)

    section_ids = [(s.section_key, s.title) for s in target_sections]



    async def run_background():

        completed = 0

        failed = 0

        try:

            async with async_session() as bg_db:

                # Re-fetch sections in the background session

                bg_sections = (await bg_db.execute(

                    select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)

                )).scalars().all()

                bg_section_map = {s.section_key: s for s in bg_sections}



                for section_key, section_title in section_ids:

                    if not _active_generations.get(plan_id):

                        break

                    s = bg_section_map.get(section_key)

                    if not s:

                        continue

                    try:

                        full = await _stream_llm(_build_section_prompt(section_title, ent_data, section_key=section_key, plan_type=p.plan_type, accident_type=p.accident_type, diagram_preference="mermaid"), ai_config, p.plan_type, p.style_preference, p.advanced_prompt_overrides)

                        s.content = _md_to_html(full)

                        s.ai_generated = True

                        s.mermaid_svgs = await _pre_render_mermaid_svgs(full)
                        await bg_db.commit()

                        completed += 1

                    except Exception:

                        failed += 1



                updated = (await bg_db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id))).scalars().all()

                p2 = (await bg_db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()

                if p2:

                    if all(sec.content and sec.content.strip() for sec in updated):

                        p2.status = "completed"

                    else:

                        p2.status = "draft"

                # ponytail: auto-create version snapshot after generation
                try:
                    ver_snapshot = {"title": p2.title, "sections": [{"section_key": s.section_key, "title": s.title, "content": s.content, "ai_generated": s.ai_generated} for s in updated]}
                    new_ver = PlanVersion(plan_project_id=plan_id, version_number=p2.current_version + 1, created_by="auto", description="AI 一键生成完成", snapshot=ver_snapshot)
                    bg_db.add(new_ver)
                    p2.current_version = p2.current_version + 1
                    logger.info(f"Auto-created version {p2.current_version} for plan {plan_id}")
                except Exception as ver_e:
                    logger.error(f"Failed to auto-create version: {ver_e}")
                await bg_db.commit()

        except Exception as e:
            logger.error(f"Background batch generation failed: {e}")
        finally:
            _active_generations.pop(plan_id, None)

    task = asyncio.create_task(run_background())

    _background_tasks[plan_id] = task

    return {"code": 0, "message": f"已在后台开始生成 {len(target_sections)} 个章节"}

@router.post("/{plan_id}/generate/{section_key}")

async def generate_section(plan_id: str, section_key: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):

    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()

    if not p: raise HTTPException(404, "预案不存在")

    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()

    if not s: raise HTTPException(404, "章节不存在")

    ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()

    if not ai_config: raise HTTPException(400, "请先在系统设置中配置 AI 模型")



    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()

    risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()

    ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}

    if ent:

        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)



    custom_instruction = None

    try:

        body = await request.json()

        custom_instruction = body.get("custom_instruction")

    except Exception:

        pass

    diagram_pref = 'mermaid'
    if p.style_preference:
        diagram_pref = p.style_preference.get('diagram_preference', 'mermaid')

    prompt = _build_section_prompt(s.title, ent_data, custom_instruction, section_number=s.sort_order + 1, section_key=section_key, plan_type=p.plan_type, accident_type=p.accident_type, diagram_preference=diagram_pref)

    p.status = "generating"

    await db.commit()



    async def event_generator():

        try:

            yield sse_event("progress", message=f"正在生成「{s.title}」...")

            full = ""

            async for chunk_content in _stream_llm_chunks(prompt, ai_config, p.plan_type, p.style_preference, p.advanced_prompt_overrides):

                full += chunk_content

                yield sse_event("chunk", content=chunk_content)

            s.content = _md_to_html(full)

            s.ai_generated = True

            s.mermaid_svgs = await _pre_render_mermaid_svgs(full)

            all_sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id))).scalars().all()

            if all(sec.content and sec.content.strip() for sec in all_sections):

                p.status = "completed"

            else:

                p.status = "draft"

            await db.commit()

            yield sse_event("done", message="生成完成")

        except Exception as e:

            p.status = "draft"

            await db.commit()

            yield sse_event("error", message=str(e))



    return EventSourceResponse(event_generator())



def _split_merged_content(text: str) -> str:

    """拆分 AI 输出中标题与表格/列表黏在同一行的情况。"""

    lines = text.split("\n")

    result = []

    for line in lines:

        stripped = line.strip()

        if not stripped:

            result.append(line)

            continue

        

        # Case A: 标题 + 表格头黏在同一行 (e.g. "7.1 内部应急联系方式 | 序号 | ...")

        if not stripped.startswith("|") and "|" in stripped:

            pipe_idx = stripped.find("|")

            heading = stripped[:pipe_idx].strip()

            table_part = stripped[pipe_idx:].strip()

            if heading and table_part.startswith("|"):

                if result and result[-1].strip():

                    result.append("")

                result.append(heading)

                result.append("")

                result.append(table_part)

                continue

        

        # Case B: 标题 + 列表项黏在同一行 (e.g. "7.3 注意事项 - 内容")

        m = re.match(r"^(\d+(?:\.\d+)*\s+\S.*?)\s+(-\s+.+)$", stripped)

        if m:

            heading = m.group(1).strip()

            list_item = m.group(2).strip()

            if result and result[-1].strip():

                result.append("")

            result.append(heading)

            result.append("")

            result.append(list_item)

            continue


        # Case C: 标题 + 正文段落黏在同一行 (e.g. "7. 紧急联系电话 为确保应急响应时...")
        m = re.match(r"^(\d+\.(?:\d+)?\s+[\u4e00-\u9fff]+)\s+([\u4e00-\u9fff].{10,})$", stripped)
        if m:
            heading = m.group(1).strip()
            content = m.group(2).strip()
            if result and result[-1].strip():
                result.append("")
            result.append(heading)
            result.append("")
            result.append(content)
            continue
        result.append(line)

    return "\n".join(result)





def _normalize_linebreaks(text: str) -> str:

    """防御性预处理：先拆分黏连内容，再给编号子节行前后插入空行。"""

    text = _split_merged_content(text)

    lines = text.split("\n")

    result = []

    for i, line in enumerate(lines):

        stripped = line.strip()

        if not stripped:

            result.append("")

            continue

        is_numbered = bool(re.match(r"^\d+(?:\.\d+)+\s+\S", stripped))

        is_top = bool(re.match(r"^\d+\.\s+\S", stripped)) and not re.match(r"^\d+\.\d", stripped)

        if is_numbered or is_top:

            if result and result[-1].strip():

                result.append("")

            result.append(line)

            if i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^\d+(?:\.\d+)*\s+\S", lines[i + 1].strip()):

                result.append("")

        else:

            result.append(line)

    return "\n".join(result)





def _md_to_html(text: str) -> str:

    """Convert AI-generated Markdown to HTML for TipTap editor."""

    if not text or text.strip().startswith("<"):

        return text

    text = _normalize_linebreaks(text)

    text = _fix_markdown_tables(text)

    return markdown.markdown(text, extensions=["tables", "fenced_code"])



@router.post("/{plan_id}/generate/batch")

async def generate_batch(plan_id: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):

    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()

    if not p: raise HTTPException(404, "预案不存在")

    ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()

    if not ai_config: raise HTTPException(400, "请先配置 AI 模型")



    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()

    risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()

    ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}

    if ent:

        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)



    try:

        body = await request.json()

        keys = body.get("section_keys")

    except Exception:

        keys = None



    all_sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()

    target_sections = [s for s in all_sections if (not keys or s.section_key in keys)]



    p.status = "generating"

    await db.commit()

    _active_generations[plan_id] = True

    plan_type = p.plan_type

    # Use a queue to stream events from background task to SSE

    import asyncio as _asyncio

    event_queue: _asyncio.Queue = _asyncio.Queue()



    # Collect section keys for background task

    section_tuples = [(s.section_key, s.title) for s in target_sections]



    async def run_background():

        completed = 0

        failed = 0

        try:

            await event_queue.put(sse_event("progress", message=f"开始批量生成 {len(section_tuples)} 个章节...", current=0, total=len(section_tuples)))

            async with async_session() as bg_db:

                bg_sections = (await bg_db.execute(

                    select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)

                )).scalars().all()

                bg_section_map = {s.section_key: s for s in bg_sections}



                for i, (section_key, section_title) in enumerate(section_tuples):

                    if not _active_generations.get(plan_id):

                        await event_queue.put(sse_event("error", message="生成已取消"))

                        return

                    s = bg_section_map.get(section_key)

                    if not s:

                        continue

                    await event_queue.put(sse_event("progress", message=f"正在生成「{section_title}」({i+1}/{len(section_tuples)})", current=i+1, total=len(section_tuples), section_key=section_key))

                    try:

                        prompt_text = _build_section_prompt(section_title, ent_data, section_number=i+1, section_key=section_key, plan_type=p.plan_type, accident_type=p.accident_type, diagram_preference="mermaid")

                        full = ""

                        async for chunk_content in _stream_llm_chunks(prompt_text, ai_config, plan_type, p.style_preference, p.advanced_prompt_overrides):

                            full += chunk_content

                            await event_queue.put(sse_event("chunk", content=chunk_content, section_key=section_key))

                        s.content = _md_to_html(full); s.ai_generated = True

                        s.mermaid_svgs = await _pre_render_mermaid_svgs(full)
                        await bg_db.commit()

                        completed += 1

                        await event_queue.put(sse_event("section_done", section_key=section_key, message=f"「{section_title}」生成完成", completed=completed, failed=failed))

                    except Exception as e:

                        failed += 1

                        await event_queue.put(sse_event("error", message=f"「{section_title}」生成失败: {e}", section_key=section_key))



                updated = (await bg_db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id))).scalars().all()

                p2 = (await bg_db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()

                if p2:

                    if all(sec.content and sec.content.strip() for sec in updated):

                        p2.status = "completed"

                    else:

                        p2.status = "draft"

                # ponytail: auto-create version snapshot after generation
                try:
                    ver_snapshot = {"title": p2.title, "sections": [{"section_key": s.section_key, "title": s.title, "content": s.content, "ai_generated": s.ai_generated} for s in updated]}
                    new_ver = PlanVersion(plan_project_id=plan_id, version_number=p2.current_version + 1, created_by="auto", description="AI 一键生成完成", snapshot=ver_snapshot)
                    bg_db.add(new_ver)
                    p2.current_version = p2.current_version + 1
                    logger.info(f"Auto-created version {p2.current_version} for plan {plan_id}")
                except Exception as ver_e:
                    logger.error(f"Failed to auto-create version: {ver_e}")
                await bg_db.commit()

                await event_queue.put(sse_event("batch_done", message="批量生成完成", completed=completed, failed=failed))

        except Exception as e:

            try:

                await event_queue.put(sse_event("error", message=str(e)))

            except Exception:

                pass

        finally:

            await event_queue.put(None)  # Sentinel to close SSE



    task = _asyncio.create_task(run_background())

    _background_tasks[plan_id] = task



    async def event_generator():

        while True:

            event = await event_queue.get()

            if event is None:

                break

            yield event



    return EventSourceResponse(event_generator())



@router.post("/{plan_id}/generate/stop")

async def stop_generation(plan_id: str):

    _active_generations[plan_id] = False

    return {"code": 0, "message": "已请求停止生成"}





@router.post("/{plan_id}/generate/batch/background")

async def generate_batch_background(plan_id: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):

    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()

    if not p: raise HTTPException(404, "预案不存在")

    if p.status == "generating":

        if not _active_generations.get(plan_id):

            logger.warning(f"Plan {plan_id} has stale generating status - resetting to draft")

            p.status = "draft"

            await db.commit()

        else:

            return {"code": 0, "message": "正在生成中"}

    ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()

    if not ai_config: raise HTTPException(400, "请先配置 AI 模型")

    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()

    risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()

    ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}

    if ent:

        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)

    try:

        body = await request.json()

        keys = body.get("section_keys")

    except Exception:

        keys = None

    all_sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()

    target_sections = [s for s in all_sections if (not keys or s.section_key in keys)]

    if not target_sections:

        return {"code": 0, "message": "没有可生成的章节"}

    p.status = "generating"

    await db.commit()

    _active_generations[plan_id] = True

    plan_type = p.plan_type

    # Collect section keys (these are plain strings, safe to pass to background)

    section_ids = [(s.section_key, s.title) for s in target_sections]



    async def run_background():

        completed = 0

        failed = 0

        try:

            async with async_session() as bg_db:

                # Re-fetch sections in the background session

                bg_sections = (await bg_db.execute(

                    select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)

                )).scalars().all()

                bg_section_map = {s.section_key: s for s in bg_sections}



                for section_key, section_title in section_ids:

                    if not _active_generations.get(plan_id):

                        break

                    s = bg_section_map.get(section_key)

                    if not s:

                        continue

                    try:

                        full = await _stream_llm(_build_section_prompt(section_title, ent_data, section_key=section_key, plan_type=p.plan_type, accident_type=p.accident_type, diagram_preference="mermaid"), ai_config, p.plan_type, p.style_preference, p.advanced_prompt_overrides)

                        s.content = _md_to_html(full)

                        s.ai_generated = True

                        s.mermaid_svgs = await _pre_render_mermaid_svgs(full)
                        await bg_db.commit()

                        completed += 1

                    except Exception:

                        failed += 1



                updated = (await bg_db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id))).scalars().all()

                p2 = (await bg_db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()

                if p2:

                    if all(sec.content and sec.content.strip() for sec in updated):

                        p2.status = "completed"

                    else:

                        p2.status = "draft"

                # ponytail: auto-create version snapshot after generation
                try:
                    ver_snapshot = {"title": p2.title, "sections": [{"section_key": s.section_key, "title": s.title, "content": s.content, "ai_generated": s.ai_generated} for s in updated]}
                    new_ver = PlanVersion(plan_project_id=plan_id, version_number=p2.current_version + 1, created_by="auto", description="AI 一键生成完成", snapshot=ver_snapshot)
                    bg_db.add(new_ver)
                    p2.current_version = p2.current_version + 1
                    logger.info(f"Auto-created version {p2.current_version} for plan {plan_id}")
                except Exception as ver_e:
                    logger.error(f"Failed to auto-create version: {ver_e}")
                await bg_db.commit()

        except Exception as e:
            logger.error(f"Background batch generation failed: {e}")
        finally:
            _active_generations.pop(plan_id, None)

    task = asyncio.create_task(run_background())

    _background_tasks[plan_id] = task

    return {"code": 0, "message": f"已在后台开始生成 {len(target_sections)} 个章节"}

@router.post("/{plan_id}/generate/{section_key}")

async def generate_section(plan_id: str, section_key: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):

    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()

    if not p: raise HTTPException(404, "预案不存在")

    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()

    if not s: raise HTTPException(404, "章节不存在")

    ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()

    if not ai_config: raise HTTPException(400, "请先在系统设置中配置 AI 模型")



    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()

    risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()

    ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}

    if ent:

        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)



    custom_instruction = None

    try:

        body = await request.json()

        custom_instruction = body.get("custom_instruction")

    except Exception:

        pass




    diagram_pref = "mermaid"
    if p.style_preference:
        diagram_pref = p.style_preference.get("diagram_preference", "mermaid")
    prompt = _build_section_prompt(s.title, ent_data, custom_instruction, section_number=s.sort_order + 1, section_key=section_key, plan_type=p.plan_type, accident_type=p.accident_type, diagram_preference=diagram_pref)

    p.status = "generating"

    await db.commit()



    async def event_generator():

        try:

            yield sse_event("progress", message=f"正在生成「{s.title}」...")

            full = ""

            async for chunk_content in _stream_llm_chunks(prompt, ai_config, p.plan_type, p.style_preference, p.advanced_prompt_overrides):

                full += chunk_content

                yield sse_event("chunk", content=chunk_content)

            s.content = _md_to_html(full)

            s.ai_generated = True

            s.mermaid_svgs = await _pre_render_mermaid_svgs(full)

            all_sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id))).scalars().all()

            if all(sec.content and sec.content.strip() for sec in all_sections):

                p.status = "completed"

            else:

                p.status = "draft"

            await db.commit()

            yield sse_event("done", message="生成完成")

        except Exception as e:

            p.status = "draft"

            await db.commit()

            yield sse_event("error", message=str(e))



    return EventSourceResponse(event_generator())





@router.post("/{plan_id}/sections/{section_key}/regenerate")
async def regenerate_selection(
    plan_id: str, section_key: str, body: RegenerateRequest,
    request: Request, current_user=Depends(get_current_user), db=Depends(get_db)
):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")

    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()
    if not s: raise HTTPException(404, "章节不存在")

    ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()
    if not ai_config: raise HTTPException(400, "请先在系统设置中配置 AI 模型")

    # 收集企业数据
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()
    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()
    ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}
    if ent:
        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)

    # 收集全文上下文
    all_sections = (await db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)
    )).scalars().all()

    full_context_parts = []
    for sec in all_sections:
        if sec.content and sec.content.strip():
            full_context_parts.append(f"## {sec.title}\n{sec.content}")
    full_context = "\n\n".join(full_context_parts)

    # 构建用户 prompt
    user_prompt = f"""以下是应急预案全文作为参考上下文：

{full_context}

---

请对以下【选中段落】进行修改或重写。要求：
1. 保持与全文风格一致
2. 仅修改选中段落的内容，不要增加其他章节
3. 修改要求：{body.custom_instruction or "优化表达，补充细节，使内容更加完善"}

【上文上下文】
{body.surrounding_context_before or "（无）"}

【选中段落——需要修改的部分】
{body.selected_text}

【下文上下文】
{body.surrounding_context_after or "（无）"}

请直接输出修改后的段落文本，不要输出"修改后："等前缀，不要用引号包裹。"""

    
    async def event_generator():
        try:
            yield sse_event("progress", message=f"正在重生成「{s.title}」选中段落...")

            async for chunk_content in _stream_llm_chunks(user_prompt, ai_config, p.plan_type, p.style_preference, p.advanced_prompt_overrides):
                yield sse_event("chunk", content=chunk_content)

            p.status = "draft"
            await db.commit()

            yield sse_event("done", message="重生成完成")

        except Exception as e:
            p.status = "draft"
            await db.commit()
            yield sse_event("error", message=str(e))

    return EventSourceResponse(event_generator())

class PreviewRequest(BaseModel):
    section_key: str = "sec_1"
    max_tokens: int = 300


@router.post("/{plan_id}/generate/preview")
async def generate_preview(
    plan_id: str, body: PreviewRequest,
    request: Request, current_user=Depends(get_current_user), db=Depends(get_db)
):
    """生成风格预览片段（短文本，不落库）。"""
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id
    ))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")

    s = (await db.execute(select(PlanSection).where(
        PlanSection.plan_project_id == plan_id,
        PlanSection.section_key == body.section_key
    ))).scalar_one_or_none()
    if not s: raise HTTPException(404, "章节不存在")

    ai_config = (await db.execute(select(AIConfig).where(
        AIConfig.user_id == current_user.id
    ))).scalar_one_or_none()
    if not ai_config: raise HTTPException(400, "请先配置 AI 模型")

    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == p.enterprise_id
    ))).scalar_one_or_none()
    risk_sources = (await db.execute(select(RiskSource).where(
        RiskSource.enterprise_id == p.enterprise_id
    ))).scalars().all()
    resources = (await db.execute(select(EmergencyResource).where(
        EmergencyResource.enterprise_id == p.enterprise_id
    ))).scalars().all()
    ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}
    if ent:
        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)

    diagram_pref = "mermaid"
    if p.style_preference:
        diagram_pref = p.style_preference.get("diagram_preference", "mermaid")

    prompt = _build_section_prompt(
        s.title, ent_data, section_key=body.section_key,
        plan_type=p.plan_type, accident_type=p.accident_type,
        diagram_preference=diagram_pref,
    )

    async def event_generator():
        try:
            full = ""
            async for chunk in _stream_llm_chunks(
                prompt, ai_config, p.plan_type,
                p.style_preference, p.advanced_prompt_overrides
            ):
                full += chunk
                yield sse_event("chunk", content=chunk)
                if len(full) > body.max_tokens:
                    yield sse_event("done", message="预览完成")
                    return
            yield sse_event("done", message="预览完成")
        except Exception as e:
            yield sse_event("error", message=str(e))

    return EventSourceResponse(event_generator())

