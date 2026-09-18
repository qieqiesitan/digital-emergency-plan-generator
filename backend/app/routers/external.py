"""外部系统接入 API — PROTEGO 商城对接"""
import logging, os

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.user import User
from app.models.enterprise import Enterprise, PlanProject, PlanSection, PlanTemplate, EmergencyResource
from app.models.hazardous_chemicals import HazardousChemical
from app.schemas.common import ApiResponse
from app.services.external_file_store import download_external_files
from app.services.external_service import notify_callback
from app.routers.generation import (
    _build_section_prompt, _stream_llm, _collect_enterprise_data, _load_org_members,
    _enrich_with_reports,
)
from app.services.markdown_utils import md_to_html
from app.services.prompt_cache import ensure_loaded
from app.services.docx_template import generate_plan_docx
from app.services.risk_context_builder import build_risk_management_context
from app.services.task_registry import spawn

logger = logging.getLogger("external_api")

router = APIRouter(prefix="/external", tags=["External"])
EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# W2：任务状态改跨 worker 共享（回调/状态查询可能落到不同 worker）
from app.services.runtime_state import get_state, set_state, try_acquire_lease
from app.services.filename_safety import safe_filename

EXTERNAL_TASK_TTL_SECONDS = 24 * 3600


def _external_task_key(plan_id: str) -> str:
    return f"external_task:{plan_id}"


def _external_order_key(order_id: str) -> str:
    """订单维度的幂等键：值里存已创建的 plan_id / task_id。"""
    return f"external_order:{order_id}"


async def _persist_task(plan_id: str, info: dict) -> None:
    await set_state(_external_task_key(plan_id), dict(info),
                    ttl_seconds=EXTERNAL_TASK_TTL_SECONDS)


async def _ensure_user_and_enterprise(
    db: AsyncSession, external_user_id: str, enterprise_data: dict
) -> tuple[User, Enterprise, bool]:
    email = f"ext_{external_user_id}@external.local"
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            password_hash="",
            name=enterprise_data.get("contact_name", "外部用户"),
            role="user",
        )
        db.add(user)
        await db.flush()

    ent_name = enterprise_data.get("name", "")
    result2 = await db.execute(
        select(Enterprise).where(Enterprise.name == ent_name, Enterprise.user_id == user.id)
    )
    enterprise = result2.scalar_one_or_none()
    ent_created = False
    if not enterprise:
        enterprise = Enterprise(
            user_id=user.id,
            name=ent_name,
            industry=enterprise_data.get("industry", ""),
            phone=enterprise_data.get("contact_phone", ""),
        )
        db.add(enterprise)
        await db.flush()
        ent_created = True
    return user, enterprise, ent_created


async def _run_generation_then_callback(
    plan_id: str, user_id: str, enterprise_id: str,
    callback_url: str, external_order_id: str, plan_type: str,
    accident_type: str | None,
):
    task_info = {"status": "generating", "progress": 0}
    await _persist_task(plan_id, task_info)
    try:
        await ensure_loaded()
        async with async_session() as db:
            p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()
            if not p:
                await _persist_task(plan_id, {"status": "failed", "error": "Plan not found"}); return

            from app.services.ai_config_service import get_system_ai_config
            ai_config = await get_system_ai_config(db)
            if not ai_config:
                p.status = "failed"; await db.commit()
                await _persist_task(plan_id, {"status": "failed", "error": "No AI config"}); return

            ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
            resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == enterprise_id))).scalars().all()
            risk_context = await build_risk_management_context(enterprise_id, db) if ent else {}
            chemicals_rows = (await db.execute(
                select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id)
            )).scalars().all()
            chemicals = {c.id: c for c in chemicals_rows}
            org_members = await _load_org_members(db, enterprise_id) if ent else []
            ent_data = _collect_enterprise_data(ent, risk_context, resources, chemicals, org_members=org_members) if ent else {}
            if ent:
                ent_data = await _enrich_with_reports(ent_data, enterprise_id, db)

            sections = list((await db.execute(
                select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)
            )).scalars().all())

            p.status = "generating"; await db.commit()

            total = len(sections); completed = 0
            for s in sections:
                # ponytail: pass None for previous_context since function doesn't exist yet
                prompt = _build_section_prompt(s.title, ent_data, section_key=s.section_key,
                                               plan_type=plan_type, accident_type=accident_type,
                                               previous_context=None)
                try:
                    full = await _stream_llm(prompt, ai_config, plan_type)
                    s.content = md_to_html(full, normalize=True); s.ai_generated = True
                    await db.commit(); completed += 1
                    task_info["progress"] = int(completed / total * 90)
                    await _persist_task(plan_id, task_info)
                except Exception as e:
                    logger.error(f"Section {s.section_key} failed: {e}")

            p.status = "completed" if completed == total else "draft"
            await db.commit()

            # ── DOCX export ──
            try:
                section_list = [
                    {"title": s.title, "level": s.level, "content": s.content or ""}
                    for s in sections if s.content
                ]
                if section_list:
                    doc = generate_plan_docx(
                        company_name=ent.name if ent else "",
                        plan_title=p.title,
                        plan_type=plan_type,
                        sections=section_list,
                    )
                    file_path = os.path.join(EXPORT_DIR, f"external_{plan_id}.docx")
                    doc.save(file_path)
                    task_info["files"] = [{
                        "name": f"{p.title}.docx",
                        "url": f"/api/external/plans/{plan_id}/files/{plan_id}",
                        "size": os.path.getsize(file_path),
                    }]
            except Exception as e:
                logger.error(f"DOCX failed: {e}")
                task_info["files"] = []

            task_info["progress"] = 100; task_info["status"] = "completed"
            await _persist_task(plan_id, task_info)

        if callback_url:
            await notify_callback(callback_url, {
                "task_id": plan_id,
                "external_order_id": external_order_id,
                "status": task_info.get("status", "completed"),
                "files": task_info.get("files", []),
            })
    except Exception as e:
        logger.error(f"External generation failed: {e}")
        await _persist_task(plan_id, {"status": "failed", "error": str(e)})
        if callback_url:
            await notify_callback(callback_url, {
                "task_id": plan_id, "external_order_id": external_order_id,
                "status": "failed", "files": [],
            })


# ═══════════════ Pydantic schemas ═══════════════
from pydantic import BaseModel

class ExternalEnterpriseData(BaseModel):
    name: str; industry: str = ""; contact_name: str = ""; contact_phone: str = ""

class ExternalDocument(BaseModel):
    name: str = ""; url: str = ""; type: str = "other"

class ExternalPlanCreate(BaseModel):
    external_order_id: str; external_user_id: str
    plan_type: str = "comprehensive"
    enterprise: ExternalEnterpriseData
    documents: list[ExternalDocument] = []
    callback_url: str = ""

class ExternalPlanResponse(BaseModel):
    task_id: str; status: str; estimated_minutes: int = 15

class ExternalTaskStatus(BaseModel):
    task_id: str; status: str; progress: int = 0; files: list[dict] = []


# ═══════════════ Endpoints ═══════════════

@router.post("/plans", response_model=ApiResponse[ExternalPlanResponse])
async def external_create_plan(data: ExternalPlanCreate, request: Request):
    """创建外部对接任务（幂等）。

    幂等语义（2026-09-18 补）：`external_order_id` 是外部商城侧的订单号，同一订单重复调用
    （外部系统超时重试、或签名在 5 分钟窗口内被重放）**不得再开一张预案、再跑一次 AI 生成**。
    做法：先用 `try_acquire_lease` 抢占订单租约——
      - 抢到 → 正常创建，并把 plan_id 写入 `external_order:{order_id}`（TTL 24h）；
      - 没抢到 → 读该键：有 plan_id 就原样返回同一个 task_id（真正的幂等重试）；
        还没有（首单仍在创建中）→ 409「同一订单正在处理中」，让调用方稍后查询。
    """
    order_key = _external_order_key(data.external_order_id)
    lease_ok = await try_acquire_lease(
        order_key, ttl_seconds=EXTERNAL_TASK_TTL_SECONDS, owner="external_api"
    )
    if not lease_ok:
        existing = await get_state(order_key)
        plan_id = (existing or {}).get("plan_id")
        if plan_id:
            return ApiResponse(data=ExternalPlanResponse(task_id=plan_id, status="accepted"))
        raise HTTPException(409, "同一订单正在处理中，请稍后查询任务状态")

    try:
        async with async_session() as db:
            ent_dict = data.enterprise.model_dump()
            user, enterprise, _ = await _ensure_user_and_enterprise(
                db, data.external_user_id, ent_dict
            )

            docs = [d.model_dump() for d in data.documents]
            await download_external_files(docs) if docs else None  # fire-and-forget download

            p = PlanProject(
                user_id=user.id, enterprise_id=enterprise.id,
                plan_type=data.plan_type,
                title=f"{enterprise.name}-{_plan_type_label(data.plan_type)}",
                status="pending",
            )
            db.add(p); await db.flush()

            tpl_result = await db.execute(
                select(PlanTemplate)
                .where(PlanTemplate.plan_type == data.plan_type, PlanTemplate.is_active == True)
                .order_by(PlanTemplate.version.desc()).limit(1)
            )
            template = tpl_result.scalar_one_or_none()
            if template and template.structure:
                from app.routers.plans import _create_sections_from_template
                _create_sections_from_template(db, p.id, template.structure)

            await db.commit()
        await set_state(order_key, {"plan_id": p.id}, ttl_seconds=EXTERNAL_TASK_TTL_SECONDS)
    except Exception:
        # 创建失败必须放掉订单租约，否则该订单号会被"毒化"24 小时、调用方永远重试不了
        from app.services.runtime_state import release_lease
        try:
            await release_lease(order_key, "external_api")
        except Exception:  # noqa: BLE001 — 释放失败不应掩盖原始异常
            logger.warning("释放外部订单租约失败: %s", order_key, exc_info=True)
        raise

    # 必须持有强引用（否则任务可能被 GC），异常也要落日志——统一走 task_registry
    spawn(
        _run_generation_then_callback(
            plan_id=p.id, user_id=user.id, enterprise_id=enterprise.id,
            callback_url=data.callback_url, external_order_id=data.external_order_id,
            plan_type=data.plan_type, accident_type=None,
        ),
        name=f"external-generation:{p.id}",
    )

    return ApiResponse(data=ExternalPlanResponse(task_id=p.id, status="accepted"))


@router.get("/plans/{task_id}/status", response_model=ApiResponse[ExternalTaskStatus])
async def external_plan_status(task_id: str):
    t = await get_state(_external_task_key(task_id))
    if t:
        return ApiResponse(data=ExternalTaskStatus(
            task_id=task_id, status=t.get("status", "unknown"),
            progress=t.get("progress", 0), files=t.get("files", []),
        ))

    async with async_session() as db:
        p = (await db.execute(select(PlanProject).where(PlanProject.id == task_id))).scalar_one_or_none()
        if not p:
            raise HTTPException(404, "Task not found")
        sections = (await db.execute(
            select(PlanSection).where(PlanSection.plan_project_id == task_id)
        )).scalars().all()
        total = max(len(list(sections)), 1)
        done = sum(1 for s in sections if s.content and s.content.strip())
        progress = 100 if p.status == "completed" else int(done / total * 90)

        files = []
        docx_path = os.path.join(EXPORT_DIR, f"external_{task_id}.docx")
        if os.path.isfile(docx_path):
            files = [{"name": f"{p.title}.docx", "url": f"/api/external/plans/{task_id}/files/{task_id}", "size": os.path.getsize(docx_path)}]

        return ApiResponse(data=ExternalTaskStatus(task_id=task_id, status=p.status, progress=progress, files=files))


@router.get("/plans/{task_id}/files/{file_id}")
async def external_download_file(task_id: str, file_id: str):
    docx_path = os.path.join(EXPORT_DIR, f"external_{task_id}.docx")
    if not os.path.isfile(docx_path):
        raise HTTPException(404, "File not found")

    async with async_session() as db:
        p = (await db.execute(select(PlanProject).where(PlanProject.id == task_id))).scalar_one_or_none()
    safe_name = safe_filename(p.title if p else "预案", fallback="plan") + ".docx"
    return FileResponse(docx_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=safe_name)


def _plan_type_label(pt: str) -> str:
    return {"comprehensive": "综合应急预案", "special": "专项应急预案", "on_site": "现场处置方案", "onsite": "现场处置方案", "all": "全套应急预案"}.get(pt, "应急预案")
