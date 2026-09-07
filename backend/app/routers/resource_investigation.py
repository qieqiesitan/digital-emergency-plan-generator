import asyncio
import json, os, logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse
from app.database import get_db, async_session
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise, EmergencyResource
from app.models.resource_investigation import ResourceInvestigationReport
from app.schemas.resource_investigation import (
    ResourceInvestigationGenerateRequest,
    ResourceInvestigationReportResponse,
    ResourceInvestigationPreviewResponse,
)
from app.schemas.common import ApiResponse
from app.services.ai_config_service import get_system_ai_config
from app.services.markdown_utils import md_to_html
from app.services.report_chapter_utils import (
    chapters_to_summary,
    get_chapters,
    upsert_chapter,
)
from app.services.report_generation_progress import save_generation_progress
from app.services.report_review_service import review_report_chapters
from app.services.sse_utils import sse_event
from app.services.background_stream import BackgroundStream
from app.services.resource_investigation_service import (
    CHAPTER_DEFINITIONS as RI_CHAPTER_DEFINITIONS,
    build_resource_investigation_context,
    build_chapter_prompt,
    get_chapter_keys,
    get_chapter_title,
    _get_ri_system_prompt,
)
from app.config import settings
from app.routers.risk_assessment import (
    _stream_chapter_events,
    _stream_llm_with_messages_chunked,
    _clean_for_docx,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enterprises", tags=["Resource Investigation"])

# 本进程内正在全量生成的企业（防多标签/重复点击并发跑同一报告）
_LIVE_RI_GENERATIONS: set[str] = set()


async def _persist_ri_generation(
    report_id: str,
    chapter_contents: list[dict],
    full_content: str,
    status: str,
) -> None:
    """把已完成章节增量落库；失败只记日志，不中断主流程。"""
    try:
        await save_generation_progress(
            ResourceInvestigationReport,
            report_id,
            chapters=[
                {"key": c["key"], "title": c["title"], "content": c["content"]}
                for c in chapter_contents
            ],
            content=full_content.strip(),
            status=status,
        )
    except Exception:
        logger.exception("resource generation progress save failed")


@router.post("/{enterprise_id}/resource-investigation/skip")
async def skip_resource_investigation(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """标记资源调查报告跳过（规格 6.6：跳过时完成度权重归入应急资源）。"""
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    generating = (await db.execute(
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status == "generating",
        )
    )).scalar_one_or_none()
    if generating:
        raise HTTPException(400, "报告正在生成中，无法跳过")
    existing_completed = (await db.execute(
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status == "completed",
        )
    )).scalar_one_or_none()
    if existing_completed:
        raise HTTPException(400, "报告已生成，无需跳过")
    # upsert：已有记录（含 draft）改写为 skipped，避免「生成→未合并→跳过」产生重复行
    existing = (await db.execute(
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status != "skipped",
        ).order_by(ResourceInvestigationReport.id)
    )).scalars().first()
    if existing:
        existing.status = "skipped"
        await db.commit()
        return ApiResponse(data={}, message="已跳过资源调查报告")
    existing_skipped = (await db.execute(
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status == "skipped",
        )
    )).scalars().first()
    if not existing_skipped:
        db.add(ResourceInvestigationReport(enterprise_id=enterprise_id, title="", status="skipped"))
        await db.commit()
    return ApiResponse(data={}, message="已跳过资源调查报告")


@router.get("/{enterprise_id}/resource-investigation")
async def get_resource_investigation(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (
        await db.execute(
            select(Enterprise).where(
                Enterprise.id == enterprise_id,
                Enterprise.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "未找到报告")

    report = (
        await db.execute(
            select(ResourceInvestigationReport).where(
                ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status.in_(["completed", "draft", "generating"]),
            )
        )
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "未找到报告")

    return ApiResponse(data=ResourceInvestigationReportResponse.model_validate(report))


@router.get("/{enterprise_id}/resource-investigation/summary")
async def get_resource_investigation_summary(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (
        await db.execute(
            select(Enterprise).where(
                Enterprise.id == enterprise_id,
                Enterprise.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "未找到报告")

    report = (
        await db.execute(
            select(ResourceInvestigationReport).where(
                ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status.in_(["completed", "draft", "generating"]),
            )
        )
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "未找到报告")

    return ApiResponse(data=report.summary or {})


@router.get("/{enterprise_id}/resource-investigation/preview")
async def preview_resource_investigation(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (
        await db.execute(
            select(Enterprise).where(
                Enterprise.id == enterprise_id,
                Enterprise.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "未找到报告")

    report = (
        await db.execute(
            select(ResourceInvestigationReport).where(
                ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status.in_(["completed", "draft", "generating"]),
            )
        )
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "未找到报告")

    html = md_to_html(_clean_for_docx(report.content))
    return ApiResponse(
        data=ResourceInvestigationPreviewResponse(
            report_id=report.id,
            title=report.title,
            html=html,
        )
    )


@router.get("/{enterprise_id}/resource-investigation/export")
async def export_resource_investigation(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (
        await db.execute(
            select(Enterprise).where(
                Enterprise.id == enterprise_id,
                Enterprise.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "未找到报告")

    report = (
        await db.execute(
            select(ResourceInvestigationReport).where(
                ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status.in_(["completed", "draft", "generating"]),
            )
        )
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "未找到报告")

    # ---- 公文版式（复用预案 docx_template 样式体系） ----
    from app.services.report_docx import (
        generate_report_docx,
        split_report_content_chapters,
    )

    chapters = ((report.summary or {}).get("chapters")) or []
    if not chapters:
        chapters = split_report_content_chapters(report.content)
    doc = generate_report_docx(
        company_name=ent.name,
        report_kind="resource",
        chapters=chapters,
        report_title=report.title or "应急资源调查报告",
    )

    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    safe_name = ent.name.replace(" ", "_") if ent else "企业"
    filename = f"{safe_name}_应急资源调查报告.docx"
    path = os.path.join(settings.EXPORT_DIR, filename)
    doc.save(path)
    return FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.post("/{enterprise_id}/resource-investigation/generate")
async def generate_resource_investigation(
    enterprise_id: str,
    request: ResourceInvestigationGenerateRequest = ResourceInvestigationGenerateRequest(),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (
        await db.execute(
            select(Enterprise).where(
                Enterprise.id == enterprise_id,
                Enterprise.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "未找到报告")

    # Check resources
    resource_count = (
        await db.execute(
            select(EmergencyResource).where(
                EmergencyResource.enterprise_id == enterprise_id
            )
        )
    ).scalars().all()
    if len(resource_count) == 0:
        raise HTTPException(400, "ERROR")

    # Check AI config
    from app.services.ai_config_service import get_system_ai_config

    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    # 并发保护：同一进程内已有全量生成在跑则拒绝；
    # 重启/断流残留的 generating 行不再拦截，允许重新生成覆盖
    if enterprise_id in _LIVE_RI_GENERATIONS:
        raise HTTPException(400, "已有正在生成的报告，请等待完成")

    # Build context
    context = await build_resource_investigation_context(enterprise_id, db)

    # Create or update report record
    report = (
        (await db.execute(
            select(ResourceInvestigationReport).where(
                ResourceInvestigationReport.enterprise_id == enterprise_id,
                ResourceInvestigationReport.status.in_(["generating", "draft", "completed"]),
            )
        )).scalars().first()
    )

    title = f"{ent.name} 应急资源调查报告"
    if report:
        report.title = title
        report.content = ""
        report.summary = {}
        report.status = "generating"
    else:
        report = ResourceInvestigationReport(
            enterprise_id=enterprise_id,
            title=title,
            status="generating",
        )
        db.add(report)
    await db.commit()

    async def event_generator():
        _LIVE_RI_GENERATIONS.add(enterprise_id)
        full_content = ""
        chapter_contents: list[dict] = []
        try:
            chapter_keys = get_chapter_keys()
            total = len(chapter_keys)
            yield sse_event("progress", message=f"开始逐章生成应急资源调查报告（共{total}章）...",
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
                    {"role": "system", "content": _get_ri_system_prompt()},
                    {"role": "user", "content": ch_prompt},
                ]
                ch_content = ""
                from app.services.thinking_brief import CaptionThrottle
                async for ev_kind, ev_payload in _stream_chapter_events(
                    messages, ai_config, CaptionThrottle(ctitle), ck,
                ):
                    if ev_kind == "thinking":
                        yield sse_event("thinking", section_key=ck, message=ev_payload)
                    elif ev_kind == "chunk":
                        ch_content += ev_payload
                        yield sse_event("chunk", content=ev_payload, section_key=ck)
                    else:
                        ch_content = ev_payload or ch_content

                chapter_contents.append({
                    "key": ck, "title": ctitle, "content": ch_content,
                })
                full_content += f"\n\n{ctitle}\n\n{ch_content}"
                yield sse_event("section_done", section_key=ck,
                           message=f"「{ctitle}」生成完成",
                           completed=i+1, total=total)
                # 逐章增量落库：断流/页面关闭/服务重启后，已完成章节不丢失
                await _persist_ri_generation(
                    report.id, chapter_contents, full_content, "generating",
                )

            # Save chapter contents to summary, set status to draft (user will merge manually)
            chapters_json = [
                {"key": c["key"], "title": c["title"], "content": c["content"]}
                for c in chapter_contents
            ]

            async with async_session() as bg_db:
                bg_report = (
                    await bg_db.execute(
                        select(ResourceInvestigationReport).where(
                            ResourceInvestigationReport.id == report.id
                        )
                    )
                ).scalar_one_or_none()
                if bg_report:
                    bg_report.status = "draft"
                    bg_report.content = full_content.strip()
                    bg_report.summary = {"chapters": chapters_json}
                    try:
                        from app.services.report_summary_utils import extract_trailing_json
                        last_ch = chapter_contents[-1] if chapter_contents else None
                        if last_ch:
                            struct = extract_trailing_json(last_ch.get("content", ""))
                            if struct:
                                bg_report.summary.update(struct)
                    except Exception:
                        pass
                    await bg_db.commit()

            import json as _json
            yield sse_event("batch_done", report_id=report.id,
                       message=f"报告生成完成，共{total}章",
                       completed=total, total=total,
                       chapters=_json.dumps(chapters_json, ensure_ascii=False))
        except asyncio.CancelledError:
            logger.warning("Resource investigation generation cancelled: %s", enterprise_id)
            await _persist_ri_generation(
                report.id, chapter_contents, full_content, "draft",
            )
            raise
        except Exception as e:
            import traceback; logger.error(f"Resource investigation generation failed: {e}\n{traceback.format_exc()}")
            await _persist_ri_generation(
                report.id, chapter_contents, full_content, "draft",
            )
            yield sse_event("error", message=str(e))
        finally:
            _LIVE_RI_GENERATIONS.discard(enterprise_id)

    stream = BackgroundStream()
    await stream.start(event_generator)

    async def event_sse():
        async for event in stream.events():
            yield event

    return EventSourceResponse(event_sse())



@router.get("/{enterprise_id}/resource-investigation/chapters")
async def get_resource_investigation_chapters():
    """Return chapter definitions for resource investigation report (used by frontend)."""
    return ApiResponse(data=[
        {"key": c["key"], "title": c["title"]}
        for c in RI_CHAPTER_DEFINITIONS
    ])


# ============================================================
# 章节级端点：单章生成/重生成（SSE）、章节保存、规则审查、
# LLM 应用修订、创作风格偏好（resource-investigation，与 risk 对称）
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


async def _prepare_ri_section_generation(
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
    resource_count = (await db.execute(
        select(EmergencyResource).where(
            EmergencyResource.enterprise_id == enterprise_id
        )
    )).scalars().all()
    if len(resource_count) == 0:
        raise HTTPException(400, "请先录入应急资源数据")
    context = await build_resource_investigation_context(enterprise_id, db)
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")
    cdef = next((c for c in RI_CHAPTER_DEFINITIONS if c["key"] == chapter_key), None)
    if not cdef:
        raise HTTPException(400, "未知章节")
    report = (await db.execute(
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status.in_(["draft", "generating", "completed"]),
        ).order_by(ResourceInvestigationReport.id)
    )).scalars().first()
    if not report:
        report = ResourceInvestigationReport(enterprise_id=enterprise_id, title="", status="draft")
        db.add(report)
    report.status = "draft"
    style_pref = report.style_preference or None
    await db.commit()
    return context, ai_config, cdef, report, style_pref


def _ri_section_event_generator(
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
                {"role": "system", "content": _get_ri_system_prompt()},
                {"role": "user", "content": ch_prompt},
            ]
            ch_content = ""
            from app.services.thinking_brief import CaptionThrottle
            async for ev_kind, ev_payload in _stream_chapter_events(
                messages, ai_config, CaptionThrottle(cdef["title"]), cdef["key"],
            ):
                if ev_kind == "thinking":
                    yield sse_event("thinking", section_key=cdef["key"], message=ev_payload)
                elif ev_kind == "chunk":
                    ch_content += ev_payload
                    yield sse_event("chunk", content=ev_payload, section_key=cdef["key"])
                else:
                    ch_content = ev_payload or ch_content
            if not ch_content.strip():
                raise Exception("AI 未返回内容，请重试")
            async with async_session() as bg_db:
                bg_report = (await bg_db.execute(
                    select(ResourceInvestigationReport).where(
                        ResourceInvestigationReport.id == report.id
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
            logger.error(
                f"Resource investigation section generation failed: {e}\n{traceback.format_exc()}"
            )
            yield sse_event("error", message=str(e))
    return event_generator


@router.post("/{enterprise_id}/resource-investigation/generate/section")
async def generate_resource_investigation_section(
    enterprise_id: str,
    body: SectionGenerateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """单章生成（SSE），完成后写入草稿 summary.chapters 并落库。"""
    context, ai_config, cdef, report, style_pref = await _prepare_ri_section_generation(
        enterprise_id, body.chapter_key, current_user, db,
    )
    gen = _ri_section_event_generator(
        context, ai_config, cdef, report, style_pref, body.custom_instruction,
    )
    return EventSourceResponse(gen())


@router.post("/{enterprise_id}/resource-investigation/sections/{chapter_key}/regenerate")
async def regenerate_resource_investigation_section(
    enterprise_id: str,
    chapter_key: str,
    body: SectionRegenerateRequest | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """单章重新生成（SSE），复用单章生成逻辑。"""
    context, ai_config, cdef, report, style_pref = await _prepare_ri_section_generation(
        enterprise_id, chapter_key, current_user, db,
    )
    gen = _ri_section_event_generator(
        context, ai_config, cdef, report, style_pref,
        body.custom_instruction if body else None,
    )
    return EventSourceResponse(gen())


@router.put("/{enterprise_id}/resource-investigation/sections/{chapter_key}")
async def save_resource_investigation_section(
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
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status.in_(["draft", "generating"]),
        )
    )).scalars().first()
    if not report:
        raise HTTPException(404, "请先生成报告")
    title = next(
        (c["title"] for c in RI_CHAPTER_DEFINITIONS if c["key"] == chapter_key),
        chapter_key,
    )
    # 拷贝章节后再 upsert，避免 JSONB 原地修改不被识别
    chapters = [dict(c) for c in get_chapters(report.summary)]
    chapters = upsert_chapter(chapters, chapter_key, title, body.content)
    report.summary = chapters_to_summary(chapters)
    await db.commit()
    return ApiResponse(data={"content_length": len(body.content)})


@router.post("/{enterprise_id}/resource-investigation/review")
async def review_resource_investigation(
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
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status.in_(["draft", "generating", "completed"]),
        )
    )).scalars().first()
    if not report:
        raise HTTPException(404, "请先生成报告")
    chapters = get_chapters(report.summary)
    keys = set(body.section_keys) if body and body.section_keys else None
    targets = [c for c in chapters if keys is None or c.get("key") in keys]
    issues = review_report_chapters(targets)
    return ApiResponse(data={"report_id": report.id, "issues": issues})


@router.post("/{enterprise_id}/resource-investigation/review/apply")
async def apply_resource_investigation_review(
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
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id,
            ResourceInvestigationReport.status.in_(["draft", "generating", "completed"]),
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
            "你是应急管理专家。以下报告章节存在质量问题，请仅重写该章节正文，"
            "保留原章节标题语义，修正问题，不得编造企业数据。\n"
            f"【问题】{issue_text}\n"
            f"【原内容】{c.get('content', '')}\n"
            "直接输出修订后的章节正文："
        )
        messages = [
            {"role": "system", "content": _get_ri_system_prompt()},
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


@router.get("/{enterprise_id}/resource-investigation/style")
async def get_resource_investigation_style(
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
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id
        )
    )).scalars().first()
    return ApiResponse(data={
        "style_preference": (report.style_preference if report else {}) or {},
    })


@router.put("/{enterprise_id}/resource-investigation/style")
async def save_resource_investigation_style(
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
        select(ResourceInvestigationReport).where(
            ResourceInvestigationReport.enterprise_id == enterprise_id
        )
    )).scalars().first()
    if not report:
        report = ResourceInvestigationReport(enterprise_id=enterprise_id, title="", status="draft")
        db.add(report)
    style = dict(body.style_preference)
    style["diagram_preference"] = "none"
    report.style_preference = style
    await db.commit()
    return ApiResponse(data={"style_preference": style})


@router.post("/{enterprise_id}/resource-investigation/merge")
async def merge_resource_investigation(
    enterprise_id: str,
    request: ResourceInvestigationGenerateRequest = ResourceInvestigationGenerateRequest(),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Merge edited chapters into final report."""
    ent = (
        await db.execute(
            select(Enterprise).where(
                Enterprise.id == enterprise_id,
                Enterprise.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "未找到报告")

    # Chapters come as JSON string in custom_instruction or as a separate field
    # We accept them via request body extension: chapters field
    import json as _json
    chapters_data = request.custom_instruction  # The frontend sends chapters here

    report = (
        (await db.execute(
            select(ResourceInvestigationReport).where(
                ResourceInvestigationReport.enterprise_id == enterprise_id,
                ResourceInvestigationReport.status.in_(["generating", "draft", "completed"]),
            )
        )).scalars().first()
    )

    if not report:
        raise HTTPException(404, "未找到报告")

    # Parse chapters from the request
    chapters = []
    try:
        if chapters_data:
            chapters = _json.loads(chapters_data)
    except Exception:
        raise HTTPException(400, "ERROR")

    if not chapters:
        raise HTTPException(400, "ERROR")

    # Merge chapters into full report
    report_title = f"#{ent.name} 应急资源调查报告"
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
        from app.services.report_summary_utils import extract_trailing_json
        last_ch = chapters[-1] if chapters else None
        if last_ch:
            struct = extract_trailing_json(last_ch.get("content", ""))
            if struct:
                report.summary.update(struct)
    except Exception:
        pass
    report.generated_at = datetime.now(timezone.utc)
    await db.commit()

    return ApiResponse(data={"report_id": report.id, "title": report_title, "status": "completed"})
