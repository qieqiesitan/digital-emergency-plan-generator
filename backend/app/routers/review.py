"""预案 AI 审查路由。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise, PlanProject, PlanSection, PlanVersion
from app.routers.versions import _build_snapshot
from app.services.plan_review_service import review_plan

router = APIRouter(prefix="/plans", tags=["Plan Review"])


class ReviewApplyRequest(BaseModel):
    mode: str = "auto"  # auto=仅规则修复；llm=含 LLM 重写
    section_keys: list[str] | None = None


@router.get("/{plan_id}/review")
async def get_plan_review(plan_id: str, current_user=Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    sections = (await db.execute(select(PlanSection).where(
        PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()
    result = review_plan(p, ent, sections)
    return {"plan_id": plan_id, "title": p.title, **result}


async def _apply_llm_revision(section, issue_text, plan, ent_data, db) -> str:
    """LLM 重写章节：构造修订提示词 → _stream_llm 流式收集 → 返回新 HTML 内容。"""
    from app.routers.generation import _stream_llm
    from app.services.ai_config_service import get_system_ai_config
    cfg = await get_system_ai_config(db)
    if not cfg:
        raise HTTPException(400, "系统未配置 AI 模型")
    prompt = (
        "你是应急预案编制专家。以下章节存在质量问题，请仅重写该章节正文（输出 HTML），"
        "保留章节标题语义，修正问题，不得编造企业数据。\n"
        f"【问题】{issue_text}\n"
        f"【原内容】{section.content or ''}\n"
        f"【企业上下文】{str(ent_data)[:800]}\n"
        "直接输出修订后的章节 HTML："
    )
    return await _stream_llm(prompt, cfg, plan.plan_type)


@router.post("/{plan_id}/review/apply")
async def apply_plan_review(plan_id: str, current_user=Depends(get_current_user),
                            db: AsyncSession = Depends(get_db),
                            body: ReviewApplyRequest | None = None,
                            mode: str | None = None,
                            section_keys: list[str] | None = None):
    """应用 AI 审查修订：auto 仅规则标记、llm 重写章节；修订前保存版本快照可回退。"""
    body = body or ReviewApplyRequest()
    if mode is not None:
        body.mode = mode
    if section_keys is not None:
        body.section_keys = section_keys
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    sections = (await db.execute(select(PlanSection).where(
        PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()
    result = review_plan(p, ent, sections)
    target_keys = set(body.section_keys or [s.section_key for s in sections])
    issue_map = {}
    for it in result["issues"]:
        if it.get("section_key") in target_keys:
            issue_map.setdefault(it["section_key"], []).append(it.get("issue", ""))

    applied = []
    if issue_map:
        # 修订前保存版本快照（可回退）
        snapshot = _build_snapshot(p, sections)
        new_ver = p.current_version + 1
        db.add(PlanVersion(plan_project_id=plan_id, version_number=new_ver,
                           created_by="ai_review", description="AI 审查修订前快照",
                           snapshot=snapshot))
        p.current_version = new_ver
        for s in sections:
            if s.section_key not in issue_map:
                continue
            issue_text = "；".join(issue_map[s.section_key])
            if body.mode == "llm":
                s.content = await _apply_llm_revision(s, issue_text, p, ent, db)
                s.ai_generated = True
            else:
                # auto 模式：占位符替换为明确标记（不编造）
                s.content = (s.content or "").replace("（待补充）", "（待补充——请人工补充）")
            applied.append(s.section_key)
        await db.commit()
    return {"plan_id": plan_id, "applied": applied, "snapshot_version": p.current_version}
