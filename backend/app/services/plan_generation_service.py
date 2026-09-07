"""预案批量生成公共实现：从 generation.py 抽取，路由与聊天助手共用。"""
import asyncio
import logging
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.enterprise import PlanProject, PlanSection, Enterprise, EmergencyResource, PlanVersion
from app.models.hazardous_chemicals import HazardousChemical
from app.services.agent.agents import LAYER_PARAMS
from app.services.ai_config_service import get_system_ai_config
from app.services.risk_context_builder import build_risk_management_context
from app.services.markdown_utils import md_to_html
from app.services.prompt_cache import ensure_loaded
from app.routers.versions import _build_snapshot

logger = logging.getLogger(__name__)

_background_tasks: dict[str, asyncio.Task] = {}

# 聊天触发后台生成的失败章节记录：_run_background 完成后写入，
# 供 chat_dispatch.get_generation_progress 查询（B4：与 chat_dispatch 空 dict 合一）。
_failed_sections: dict[str, list] = {}


def get_failed_sections(plan_id: str) -> list:
    """查询指定预案最近一次后台生成失败章节列表（无记录返回空列表）。"""
    return _failed_sections.get(plan_id, [])


async def collect_batch_context(plan_id, db, keys=None):
    """批量生成公共准备。keys=None 表示全部章节；否则仅 keys 中章节。"""
    from app.routers.generation import (
        _collect_enterprise_data, _enrich_with_reports, _load_org_members,
    )
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    resources = (await db.execute(
        select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id)
    )).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    chemicals_rows = (await db.execute(
        select(HazardousChemical).where(HazardousChemical.enterprise_id == p.enterprise_id)
    )).scalars().all()
    chemicals = {c.id: c for c in chemicals_rows}
    org_members = await _load_org_members(db, p.enterprise_id) if ent else []
    ent_data = _collect_enterprise_data(ent, risk_context, resources, chemicals,
                                        org_members=org_members) if ent else {}
    if ent:
        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)
    all_sections = (await db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id)
        .order_by(PlanSection.sort_order)
    )).scalars().all()
    target_sections = [s for s in all_sections if (not keys or s.section_key in keys)]
    return p, ai_config, ent_data, target_sections


async def start_batch_generation(plan_id, db, current_user, keys=None, background=True):
    """触发批量生成。background=True 时注册后台任务，立即返回。"""
    p, ai_config, ent_data, target_sections = await collect_batch_context(plan_id, db, keys)
    empty = [s for s in target_sections if not s.content or not s.content.strip()]
    if not empty:
        return {"started": False, "message": f"预案「{p.title}」章节均已填写完成"}
    # B24：原子置位（status != 'generating' 才允许抢占），rowcount=0 说明并发请求已置位
    result = await db.execute(
        update(PlanProject)
        .where(PlanProject.id == plan_id, PlanProject.status != "generating")
        .values(status="generating")
    )
    if result.rowcount == 0:
        return {"started": False, "message": "预案正在生成中，请稍候", "status": "generating"}
    await db.commit()
    section_tuples = [(s.section_key, s.title) for s in empty]
    if not background:
        raise NotImplementedError("同步模式由 0.4.1 审查修订依赖实现")
    task = asyncio.create_task(_run_background(
        plan_id, p.plan_type, p.accident_type, p.style_preference,
        p.advanced_prompt_overrides, section_tuples, ai_config, ent_data))
    _background_tasks[plan_id] = task
    return {
        "started": True, "plan_id": plan_id, "total": len(target_sections),
        "empty": len(empty),
        "message": f"已开始后台生成，共 {len(empty)} 个空章节，可随时询问生成进度",
        "verified": True,
    }


async def _run_background(plan_id, plan_type, accident_type, style_preference,
                          advanced_overrides, section_tuples, ai_config, ent_data):
    """后台执行：独立 session 逐章生成 + 收尾。"""
    try:
        async with async_session() as bg_db:
            result = await run_batch_generation(
                bg_db=bg_db, plan_id=plan_id, section_tuples=section_tuples,
                ai_config=ai_config, ent_data=ent_data, plan_type=plan_type,
                accident_type=accident_type, style_preference=style_preference,
                advanced_overrides=advanced_overrides, use_section_number=False,
            )
            await finalize_batch_result(bg_db, plan_id, result["completed"],
                                        result["failed"], result["failed_sections"])
            _failed_sections[plan_id] = result["failed_sections"]
            logger.info("聊天触发批量生成完成 plan=%s %s", plan_id, result)
    except Exception:
        logger.exception("聊天触发批量生成失败 plan=%s", plan_id)
        # B5：异常时回滚 status，避免预案永久卡在 generating
        try:
            async with async_session() as rollback_db:
                p_rollback = (await rollback_db.execute(
                    select(PlanProject).where(PlanProject.id == plan_id)
                )).scalar_one_or_none()
                if p_rollback and p_rollback.status == "generating":
                    p_rollback.status = "draft"
                    await rollback_db.commit()
        except Exception as rollback_e:
            logger.error(f"Failed to reset plan status after failure: {rollback_e}")
    finally:
        _background_tasks.pop(plan_id, None)
        from app.services import generation_progress as _gp
        _gp.clear_progress(plan_id)


async def run_batch_generation(
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
    from app.routers.generation import (
        _build_section_prompt, _collect_previous_context, _collect_stream_text,
        _pre_render_mermaid_svgs, _attach_diagrams, _GenerationCancelled,
    )
    from app.services import generation_progress as _gp
    from app.services.thinking_brief import CaptionThrottle
    import time as _time
    await ensure_loaded()
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
                previous_context=_collect_previous_context(bg_sections, section_key),
            )
            if use_section_number:
                prompt_kwargs["section_number"] = i + 1
            prompt_text = _build_section_prompt(section_title, ent_data, **prompt_kwargs)
            async def _fetch_full():
                if stream_fn is None:
                    state = _gp.get_progress(plan_id)
                    started_at = state.get("started_at") or _time.time()
                    _gp.set_progress(
                        plan_id, phase="thinking", section_key=section_key,
                        section_title=section_title, index=i + 1, total=len(section_tuples),
                        thinking_brief=None, started_at=started_at,
                    )
                    throttle = CaptionThrottle(section_title)

                    def _on_reasoning(piece: str) -> None:
                        caption = throttle.push(piece)
                        if caption:
                            _gp.set_progress(plan_id, thinking_brief=caption)

                    def _on_content_start() -> None:
                        _gp.set_progress(plan_id, phase="writing", thinking_brief=None)

                    return await _collect_stream_text(
                        prompt_text, ai_config, plan_type, style_preference,
                        advanced_overrides, payload_overrides=LAYER_PARAMS["generate"],
                        reasoning_cb=_on_reasoning, on_content_start=_on_content_start,
                    )
                return await stream_fn(prompt_text, ai_config, plan_type, style_preference, advanced_overrides)

            full = await _fetch_full()
            if not full or not full.strip():
                logger.warning("Section %s 空返回，自动重试", section_key)
                full = await _fetch_full()
            if not full or not full.strip():
                raise ValueError("AI 返回内容为空，生成失败")
            s.content = md_to_html(full, normalize=True)
            s.ai_generated = True
            s.mermaid_svgs = await _pre_render_mermaid_svgs(full)
            _attach_diagrams(s, plan_type, ent_data)
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


async def finalize_batch_result(
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
