from pydantic import BaseModel
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from sse_starlette.sse import EventSourceResponse

from app.database import get_db, async_session

from app.models.enterprise import Enterprise, PlanProject, PlanSection, AIConfig, EmergencyResource, PlanVersion

from app.models.risk_assessment import RiskAssessmentReport

from app.models.resource_investigation import ResourceInvestigationReport

from app.dependencies import get_current_user

import asyncio

import logging

from app.services.llm_client import llm_chat_completion, llm_collect_all, LLMError
from app.services.markdown_utils import md_to_html
from app.services.mermaid_renderer import extract_mermaid_from_markdown, render_mermaid_svg, _mermaid_hash
from app.services.sse_utils import sse_event
from app.services.prompt_cache import build_system_prompt_with_style, REGULATION_WRITING_RULE, get_section_prompt, get_diagram_prompt, render_template
from app.services.risk_context_builder import build_risk_management_context
from app.regulations.context_builder import RegulationContextBuilder

from app.schemas.plan import RegenerateRequest
from app.routers.versions import _build_snapshot

logger = logging.getLogger(__name__)



router = APIRouter(prefix="/plans", tags=["Generation"])



_active_generations: dict[str, bool] = {}

_background_tasks: dict[str, asyncio.Task] = {}

_failed_sections: dict[str, list] = {}


def _clear_generation_state(plan_id: str) -> None:
    """批量生成结束后清除生成中标记（保留失败清单供前端查询）。"""
    _active_generations[plan_id] = False


class _GenerationCancelled(Exception):
    """内部异常：SSE 批量生成被 stop 端点取消时抛出。"""




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




# 每个章节除主流程图外可附加的图类型（key 对应 plan_diagram_service 的 diagram key）
SECTION_ADDITIONAL_DIAGRAM_MAP: dict[str, str] = {
    "sec_3":   "org_chart",          # 应急组织机构及职责 → 组织架构图
    "sec_4_2": "report_sequence",    # 信息报告程序 → 上报时序图
    "sec_5":   "response_timeline",  # 应急响应 → 处置时间轴
    "sec_9_1": "drill_gantt",        # 培训与演练 → 演练甘特图
}

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

def _missing(v):
    """缺失字段统一标注，防止 LLM 编造。"""
    return v if v not in (None, "") else "（待补充）"


def _collect_enterprise_data(enterprise: Enterprise, risk_context: dict, resources: list) -> dict:

    return {

        "name": _missing(enterprise.name),
        "address": _missing(enterprise.address),

        "industry": _missing(enterprise.industry),
        "business_scope": _missing(enterprise.business_scope),

        "employee_count": enterprise.employee_count,
        "building_overview": _missing(enterprise.building_overview),

        "org_structure": enterprise.org_structure,
        "surrounding_info": _missing(enterprise.surrounding_info),

        "legal_representative": _missing(enterprise.legal_representative),

        "credit_code": _missing(enterprise.credit_code),

        "economic_type": _missing(enterprise.economic_type),

        "established_date": str(enterprise.established_date) if enterprise.established_date else None,

        "registered_capital": enterprise.registered_capital,

        "phone": _missing(enterprise.phone),

        "land_area": enterprise.land_area,

        "building_area": enterprise.building_area,

        "safety_officer": _missing(enterprise.safety_officer),

        "safety_standardization": _missing(enterprise.safety_standardization),

        "fire_approval": _missing(enterprise.fire_approval),

        "main_products": _missing(enterprise.main_products),

        "hazardous_chemicals": _missing(enterprise.hazardous_chemicals),

        "special_equipment": _missing(enterprise.special_equipment),

        "risk_sources": [
            {
                "categories": rs.get("categories", ""),
                "name": rs.get("name", ""),
                "location": rs.get("location", ""),
                "description": rs.get("description", ""),
                "risk_level": rs.get("risk_level", ""),
                "control_measures": rs.get("control_measures", ""),
                "zone": rs.get("zone", ""),
                "object": rs.get("object", ""),
                "unit": rs.get("unit", ""),
                "accident_type": rs.get("accident_type", ""),
                "triggers": rs.get("triggers", ""),
                "consequences": rs.get("consequences", ""),
            }
            for rs in risk_context.get("risk_sources", [])
        ],

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
    except LLMError as e:
        # 保持原 generation 文案（带空格）
        raise HTTPException(500, f"AI 调用失败: {e.status_code} {e.text[:300]}")
    except Exception as e:
        raise HTTPException(500, str(e))


async def _stream_llm(prompt: str, ai_config: AIConfig, plan_type: str = "*", style_preference=None, advanced_overrides=None) -> str:
    messages = [
        {"role": "system", "content": _build_system_prompt(plan_type, style_preference, advanced_overrides)},
        {"role": "user", "content": prompt},
    ]
    return await llm_collect_all(messages, ai_config, timeout=120)


async def _get_plan_or_404(plan_id: str, user, db: AsyncSession) -> PlanProject:
    """批量生成共用：查询预案，不存在抛 404。"""
    p = (await db.execute(
        select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    return p


async def _collect_batch_context(
    plan_id: str, p: PlanProject, request: Request, db: AsyncSession, current_user,
) -> tuple:
    """批量生成公共准备：AI 配置、企业上下文、目标章节。

    返回 (p, ai_config, ent_data, target_sections)。stale 守卫、空章节守卫、
    置 generating、_active_generations 赋值等端点差异逻辑留在调用端点。
    """
    ai_config = (await db.execute(
        select(AIConfig).where(AIConfig.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ai_config:
        raise HTTPException(400, "请先配置 AI 模型")

    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    resources = (await db.execute(
        select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id)
    )).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    ent_data = _collect_enterprise_data(ent, risk_context, resources) if ent else {}
    if ent:
        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)

    try:
        body = await request.json()
        keys = body.get("section_keys")
    except Exception:
        keys = None

    all_sections = (await db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)
    )).scalars().all()
    target_sections = [s for s in all_sections if (not keys or s.section_key in keys)]
    return p, ai_config, ent_data, target_sections


async def _run_batch_generation(
    *,
    bg_db,
    plan_id: str,
    section_tuples: list,
    ai_config,
    ent_data: dict,
    plan_type: str,
    accident_type: str | None = None,
    style_preference=None,
    advanced_overrides=None,
    stream_fn=None,
    on_progress=None,
    on_section_done=None,
    should_stop=None,
    use_section_number: bool = True,
) -> dict:
    """批量生成公共实现：逐章生成、写库、渲染 Mermaid、统计失败。

    stream_fn: async 函数 (prompt, ai_config, plan_type, style_preference, advanced_overrides) -> str；
    为 None 时使用 _stream_llm。
    on_progress: 可选 async 回调 (section_key, section_title, i)，每章开始前调用；
    抛出的异常（如 _GenerationCancelled）不会被计入失败，直接中断剩余章节。
    on_section_done: 可选 async 回调 (section_key, section_title, completed, failed)，
    每章成功提交后调用，用于 SSE 端恢复带计数器的 section_done 事件。
    should_stop: 可选同步可调用对象，返回 True 时中断剩余章节（用于后台批量生成的取消检查）。
    use_section_number: 为 True 时提示词传入 section_number（SSE 原行为）；为 False 时
    不传（background 原行为，避免出现「这是应急预案的第N个章节」编号提示）。
    """
    completed = 0
    failed = 0
    failed_sections = []

    bg_sections = (await bg_db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)
    )).scalars().all()
    bg_section_map = {s.section_key: s for s in bg_sections}

    for i, (section_key, section_title) in enumerate(section_tuples):
        if should_stop and should_stop():
            break
        if on_progress:
            await on_progress(section_key, section_title, i)
        s = bg_section_map.get(section_key)
        if not s:
            continue
        try:
            prompt_kwargs = dict(
                section_key=section_key, plan_type=plan_type,
                accident_type=accident_type, diagram_preference="mermaid",
            )
            if use_section_number:
                prompt_kwargs["section_number"] = i + 1
            prompt_text = _build_section_prompt(section_title, ent_data, **prompt_kwargs)
            if stream_fn is None:
                full = await _stream_llm(prompt_text, ai_config, plan_type, style_preference, advanced_overrides)
            else:
                full = await stream_fn(prompt_text, ai_config, plan_type, style_preference, advanced_overrides)
            s.content = md_to_html(full, normalize=True)
            s.ai_generated = True
            s.mermaid_svgs = await _pre_render_mermaid_svgs(full)
            await bg_db.commit()
            completed += 1
        except _GenerationCancelled:
            # 取消信号不应当计入失败：中断剩余章节（SSE 端点捕获后静默结束流）
            raise
        except Exception as e:
            logger.error(f"Section {section_key} failed: {e}")
            failed += 1
            failed_sections.append({"section_key": section_key, "title": section_title})
        else:
            if on_section_done:
                await on_section_done(section_key, section_title, completed, failed)

    return {"completed": completed, "failed": failed, "failed_sections": failed_sections}


async def _finalize_batch_result(
    bg_db,
    plan_id: str,
    completed: int,
    failed: int,
    failed_sections: list,
    updated=None,
) -> dict:
    """批量生成收尾公共实现：状态判定 + 自动版本快照 + commit。

    返回 {"completed", "failed", "failed_sections", "version"}，两个批量端点复用。
    """
    if updated is None:
        updated = (await bg_db.execute(
            select(PlanSection).where(PlanSection.plan_project_id == plan_id)
        )).scalars().all()
    p2 = (await bg_db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()
    if p2:
        if all(sec.content and sec.content.strip() for sec in updated):
            p2.status = "completed"
        else:
            p2.status = "draft"
    snapshot_version = None
    try:
        ver_snapshot = _build_snapshot(p2, updated)
        new_ver = PlanVersion(
            plan_project_id=plan_id, version_number=p2.current_version + 1,
            created_by="auto", description="AI 一键生成完成", snapshot=ver_snapshot,
        )
        bg_db.add(new_ver)
        p2.current_version = p2.current_version + 1
        snapshot_version = p2.current_version
        logger.info(f"Auto-created version {p2.current_version} for plan {plan_id}")
    except Exception as ver_e:
        logger.error(f"Failed to auto-create version: {ver_e}")
    await bg_db.commit()
    return {
        "completed": completed,
        "failed": failed,
        "failed_sections": failed_sections,
        "version": snapshot_version,
    }


@router.post("/{plan_id}/generate/batch")

async def generate_batch(plan_id: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = await _get_plan_or_404(plan_id, current_user, db)
    p, ai_config, ent_data, target_sections = await _collect_batch_context(plan_id, p, request, db, current_user)

    p.status = "generating"
    await db.commit()
    _active_generations[plan_id] = True
    plan_type = p.plan_type

    # Use a queue to stream events from background task to SSE
    event_queue: asyncio.Queue = asyncio.Queue()
    section_tuples = [(s.section_key, s.title) for s in target_sections]



    async def run_background():
        try:
            await event_queue.put(sse_event("progress", message=f"开始批量生成 {len(section_tuples)} 个章节...", current=0, total=len(section_tuples)))
            async with async_session() as bg_db:
                _failed_sections[plan_id] = []
                section_key_holder: dict = {}

                async def sse_stream(prompt, cfg, pt, sp, ao):
                    full = ""
                    key = section_key_holder.get("key")
                    title = section_key_holder.get("title", key)
                    try:
                        async for chunk in _stream_llm_chunks(prompt, cfg, pt, sp, ao):
                            full += chunk
                            await event_queue.put(sse_event("chunk", content=chunk, section_key=key))
                        return full
                    except Exception as e:
                        await event_queue.put(sse_event("error", message=f"「{title}」生成失败: {e}", section_key=key))
                        raise

                async def on_progress(section_key, section_title, i):
                    if not _active_generations.get(plan_id):
                        await event_queue.put(sse_event("error", message="生成已取消"))
                        raise _GenerationCancelled()
                    section_key_holder["key"] = section_key
                    section_key_holder["title"] = section_title
                    await event_queue.put(sse_event("progress", message=f"正在生成「{section_title}」({i+1}/{len(section_tuples)})", current=i+1, total=len(section_tuples), section_key=section_key))

                async def on_section_done(section_key, section_title, completed, failed):
                    # 与原实现契约一致：section_done 携带当前 completed/failed 计数
                    await event_queue.put(sse_event(
                        "section_done", section_key=section_key,
                        message=f"「{section_title}」生成完成",
                        completed=completed, failed=failed,
                    ))

                result = await _run_batch_generation(
                    bg_db=bg_db, plan_id=plan_id, section_tuples=section_tuples,
                    ai_config=ai_config, ent_data=ent_data,
                    plan_type=p.plan_type, accident_type=p.accident_type,
                    style_preference=p.style_preference,
                    advanced_overrides=p.advanced_prompt_overrides,
                    stream_fn=sse_stream,
                    on_progress=on_progress,
                    on_section_done=on_section_done,
                )
                failed_sections = result["failed_sections"]
                _failed_sections[plan_id] = failed_sections

                final = await _finalize_batch_result(
                    bg_db, plan_id, result["completed"], result["failed"], failed_sections,
                )
                await event_queue.put(sse_event(
                    "batch_done", message="批量生成完成",
                    completed=final["completed"], failed=final["failed"],
                    failed_sections=final["failed_sections"],
                ))
        except _GenerationCancelled:
            # 取消时恢复状态：避免预案永久停在 generating
            try:
                async with async_session() as cancel_db:
                    p_cancel = (await cancel_db.execute(
                        select(PlanProject).where(PlanProject.id == plan_id)
                    )).scalar_one_or_none()
                    if p_cancel and p_cancel.status == "generating":
                        p_cancel.status = "draft"
                        await cancel_db.commit()
            except Exception as ce:
                logger.error(f"Failed to reset plan status after cancel: {ce}")
        except Exception as e:
            try:
                await event_queue.put(sse_event("error", message=str(e)))
            except Exception:
                pass
        finally:
            _clear_generation_state(plan_id)
            await event_queue.put(None)  # Sentinel to close SSE



    task = asyncio.create_task(run_background())

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


@router.get("/{plan_id}/generate/status")
async def get_generation_status(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id
    ))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    return {
        "code": 0,
        "data": {
            "generating": _active_generations.get(plan_id, False),
            "failed_sections": _failed_sections.get(plan_id, []),
        },
    }





@router.post("/{plan_id}/generate/batch/background")

async def generate_batch_background(plan_id: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = await _get_plan_or_404(plan_id, current_user, db)
    if p.status == "generating":
        if not _active_generations.get(plan_id):
            logger.warning(f"Plan {plan_id} has stale generating status - resetting to draft")
            p.status = "draft"
            await db.commit()
        else:
            return {"code": 0, "message": "正在生成中"}
    p, ai_config, ent_data, target_sections = await _collect_batch_context(plan_id, p, request, db, current_user)

    if not target_sections:
        return {"code": 0, "message": "没有可生成的章节"}

    p.status = "generating"

    await db.commit()

    _active_generations[plan_id] = True

    plan_type = p.plan_type

    # Collect section keys (these are plain strings, safe to pass to background)

    section_ids = [(s.section_key, s.title) for s in target_sections]



    async def run_background():
        try:
            async with async_session() as bg_db:
                _failed_sections[plan_id] = []
                result = await _run_batch_generation(
                    bg_db=bg_db, plan_id=plan_id, section_tuples=section_ids,
                    ai_config=ai_config, ent_data=ent_data,
                    plan_type=p.plan_type, accident_type=p.accident_type,
                    style_preference=p.style_preference,
                    advanced_overrides=p.advanced_prompt_overrides,
                    stream_fn=None,
                    on_progress=None,
                    should_stop=lambda: not _active_generations.get(plan_id, False),
                    use_section_number=False,
                )
                failed_sections = result["failed_sections"]
                _failed_sections[plan_id] = failed_sections
                await _finalize_batch_result(
                    bg_db, plan_id, result["completed"], result["failed"], failed_sections,
                )
        except Exception as e:
            logger.error(f"Background batch generation failed: {e}")
        finally:
            _clear_generation_state(plan_id)

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

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()

    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}

    ent_data = _collect_enterprise_data(ent, risk_context, resources) if ent else {}

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

        succeeded = False
        try:

            yield sse_event("progress", message=f"正在生成「{s.title}」...")

            full = ""

            async for chunk_content in _stream_llm_chunks(prompt, ai_config, p.plan_type, p.style_preference, p.advanced_prompt_overrides):

                full += chunk_content

                yield sse_event("chunk", content=chunk_content)

            s.content = md_to_html(full, normalize=True)

            s.ai_generated = True

            s.mermaid_svgs = await _pre_render_mermaid_svgs(full)

            all_sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id))).scalars().all()

            if all(sec.content and sec.content.strip() for sec in all_sections):

                p.status = "completed"

            else:

                p.status = "draft"

            await db.commit()

            yield sse_event("done", message="生成完成")
            succeeded = True

        except Exception as e:

            p.status = "draft"

            await db.commit()

            yield sse_event("error", message=str(e))
        finally:
            # 客户端断连/取消时 CancelledError 不会被 except Exception 捕获，
            # 这里兜底恢复状态，避免预案永久停在 generating。
            if not succeeded and p.status == "generating":
                p.status = "draft"
                await db.commit()



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
    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    ent_data = _collect_enterprise_data(ent, risk_context, resources) if ent else {}
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
    resources = (await db.execute(select(EmergencyResource).where(
        EmergencyResource.enterprise_id == p.enterprise_id
    ))).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    ent_data = _collect_enterprise_data(ent, risk_context, resources) if ent else {}
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

