"""Chat dispatch — 全覆盖系统 API 操作函数。"""

import json
import logging
import asyncio
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.enterprise import (
    Enterprise, RiskSource, EmergencyResource, PlanProject,
    PlanSection, PlanTemplate,
)
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport
from app.services.enterprise_autofill import autofill
from app.services.enterprise_cleanup_service import delete_enterprise_complete
from app.services.floor_plan_storage_service import remove_enterprise_uploads
from app.services.risk_context_builder import build_risk_management_context
from app.services.risk_stats_service import count_user_risk_events
from app.services.plan_generation_service import start_batch_generation, get_failed_sections
from app.services.enterprise_knowledge_service import EnterpriseKnowledgeStore
from app.services.user_preference_service import get_preferences, set_preferences
from app.services.workflow.models import WorkflowRun, WorkflowRunStep
from app.services.workflow.runner import WorkflowRunner
from app.regulations import get_graph, get_vector_store
import os
from app.routers.export import generate_plan_docx as generate_plan_docx_func

logger = logging.getLogger(__name__)


def _schedule_enterprise_index_rebuild(enterprise_id: str) -> None:
    """企业画像相关写操作提交后异步重建索引（不阻塞主流程）。"""
    if not enterprise_id:
        return
    try:
        from app.database import async_session
        from app.services.enterprise_knowledge_service import build_enterprise_index

        async def _rebuild():
            try:
                async with async_session() as session:
                    await build_enterprise_index(enterprise_id, session)
            except Exception as e:  # 索引重建失败不影响主流程
                logger.warning("企业画像索引重建失败 enterprise=%s: %s", enterprise_id, e)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("无运行中事件循环，跳过企业画像索引重建 enterprise=%s", enterprise_id)
            return
        loop.create_task(_rebuild())
    except Exception as e:
        logger.warning("企业画像索引重建调度失败: %s", e)

# 聊天工具描述使用中文类型名（综合应急预案/专项应急预案/现场处置方案），
# 模板表 plan_type 为英文枚举——兼容映射，避免模板查找失败导致章节未初始化
PLAN_TYPE_ALIASES = {
    "综合应急预案": "comprehensive",
    "综合": "comprehensive",
    "专项应急预案": "special",
    "专项": "special",
    "现场处置方案": "onsite",
    "现场": "onsite",
}

# ── dispatch ──

def _parse_date(val):
    """Parse date string like '2020-06-03' or '2020-06-03T00:00:00' to datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d")
    except Exception:
        return None


def _parse_int(val):
    """Parse int, handling string values."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    try:
        return int(str(val))
    except Exception:
        return None


async def dispatch(db: AsyncSession, user: User, fn_name: str, args: dict) -> str:
    fn = _FUNCTIONS.get(fn_name)
    if not fn:
        return json.dumps({"error": f"未知操作: {fn_name}"}, ensure_ascii=False)
    try:
        result = await fn(db, user, args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        # ponytail: rollback on error so session stays usable for later calls
        try:
            await db.rollback()
        except Exception:
            pass
        return json.dumps({"error": str(e), "verified": False}, ensure_ascii=False)


# ── 仪表盘 ──
# -- Generic CRUD infrastructure --
class _ErrorDict(Exception):
    def __init__(self, data):
        self.data = data if isinstance(data, dict) else {"error": data, "verified": False}


async def _verify_enterprise_ownership(db, user, enterprise_id):
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == user.id)
    )).scalar_one_or_none()
    if not ent:
        raise _ErrorDict({"error": "企业不存在或无权访问", "verified": False})
    return ent


# Generic CRUD helpers (list, create, update, delete)
# Each takes a config dict with: model, name_cn, id_arg_name, return_plural, display_fields,
# required_fields, create_fields, update_fields, order_by
# All entity-specific configuration is moved to ENTITY_REGISTRY below.


async def _generic_list(db, user, args, cfg):
    model = cfg["model"]
    query = select(model)
    ent_id = args.get("enterprise_id", "")
    if not ent_id:
        return {"error": "请提供 enterprise_id", "verified": False}
    if cfg.get("enterprise_check", True):
        await _verify_enterprise_ownership(db, user, ent_id)
    query = query.where(model.enterprise_id == ent_id)
    order_col = getattr(model, cfg.get("order_by", "id"), model.id)
    query = query.order_by(order_col)
    rows = (await db.execute(query.limit(50))).scalars().all()
    fields = cfg["display_fields"]
    return {cfg["return_plural"]: [{f: getattr(r, f) for f in fields} for r in rows]}


async def _generic_create(db, user, args, cfg):
    model = cfg["model"]
    for f in cfg.get("required_fields", []):
        if not args.get(f):
            return {"error": f"请提供 {f}", "verified": False}
    ent_id = args.get("enterprise_id", "")
    if cfg.get("enterprise_check", True) and ent_id:
        await _verify_enterprise_ownership(db, user, ent_id)
    kwargs = {}
    for f in cfg["create_fields"]:
        if f in args:
            kwargs[f] = args[f]
    if "id" not in kwargs:
        kwargs["id"] = str(uuid4())
    user_field = cfg.get("user_id_field", "")
    if user_field:
        kwargs[user_field] = user.id
    entity = model(**kwargs)
    db.add(entity)
    await db.commit()
    if cfg.get("rebuild_enterprise_index") and getattr(entity, "enterprise_id", None):
        _schedule_enterprise_index_rebuild(entity.enterprise_id)
    return {"id": entity.id, "name": getattr(entity, "name", ""), "message": f"{cfg['name_cn']}创建成功", "verified": True}


async def _generic_update(db, user, args, cfg):
    model = cfg["model"]
    entity_id = args.get(cfg["id_arg_name"], "")
    if not entity_id:
        return {"error": f"请提供 {cfg['id_arg_name']}", "verified": False}
    query = select(model).where(model.id == entity_id)
    user_field = cfg.get("user_id_field", "")
    if user_field:
        query = query.where(getattr(model, user_field) == user.id)
    elif cfg.get("enterprise_ownership"):
        # 无 user_id 列的表（如应急资源）经 enterprise→user 链路校验归属
        query = query.join(Enterprise, model.enterprise_id == Enterprise.id).where(
            Enterprise.user_id == user.id
        )
    entity = (await db.execute(query)).scalar_one_or_none()
    if not entity:
        return {"error": f"{cfg['name_cn']}不存在", "verified": False}
    for f in cfg.get("update_fields", []):
        if f in args and args[f] is not None:
            setattr(entity, f, args[f])
    await db.commit()
    if cfg.get("rebuild_enterprise_index") and getattr(entity, "enterprise_id", None):
        _schedule_enterprise_index_rebuild(entity.enterprise_id)
    return {"id": entity.id, "name": getattr(entity, "name", ""), "message": f"{cfg['name_cn']}更新成功", "verified": True}


async def _generic_delete(db, user, args, cfg):
    model = cfg["model"]
    entity_id = args.get(cfg["id_arg_name"], "")
    if not entity_id:
        return {"error": f"请提供 {cfg['id_arg_name']}", "verified": False}
    query = select(model).where(model.id == entity_id)
    user_field = cfg.get("user_id_field", "")
    if user_field:
        query = query.where(getattr(model, user_field) == user.id)
    elif cfg.get("enterprise_ownership"):
        # 无 user_id 列的表（如应急资源）经 enterprise→user 链路校验归属
        query = query.join(Enterprise, model.enterprise_id == Enterprise.id).where(
            Enterprise.user_id == user.id
        )
    entity = (await db.execute(query)).scalar_one_or_none()
    if not entity:
        return {"error": f"{cfg['name_cn']}不存在", "verified": False}
    name = getattr(entity, "name", "")
    enterprise_id = getattr(entity, "enterprise_id", None)
    await db.delete(entity)
    await db.commit()
    if cfg.get("rebuild_enterprise_index") and enterprise_id:
        _schedule_enterprise_index_rebuild(enterprise_id)
    return {"message": f"{cfg['name_cn']}「{name}」已删除", "verified": True}


async def _delegate_generic(op, db, user, args, cfg):
    """generic CRUD 委托样板：统一捕获 _ErrorDict 返回其 data。"""
    try:
        return await op(db, user, args, cfg)
    except _ErrorDict as e:
        return e.data


# Entity registry - config for each model
_RS_CFG = {
    "model": None, "name_cn": None, "id_arg_name": None, "return_plural": None,
    "display_fields": None, "required_fields": None, "create_fields": None,
    "update_fields": None, "order_by": None, "enterprise_check": True,
}
_RES_CFG = dict(_RS_CFG)
_RS_CFG.update({
    "model": RiskSource,
    "name_cn": "风险源",
    "id_arg_name": "risk_source_id",
    "return_plural": "risk_sources",
    "display_fields": ["id", "name", "categories", "risk_level", "location", "description", "control_measures"],
    "required_fields": ["enterprise_id", "name"],
    "create_fields": ["enterprise_id", "name", "categories", "location", "description", "risk_level", "control_measures", "likelihood", "severity"],
    "update_fields": ["name", "categories", "location", "description", "risk_level", "control_measures", "likelihood", "severity"],
    "order_by": "sort_order",
})
_RES_CFG.update({
    "model": EmergencyResource,
    "name_cn": "应急资源",
    "id_arg_name": "resource_id",
    "return_plural": "resources",
    "display_fields": ["id", "name", "category", "quantity", "unit", "location", "responsible_person", "contact_phone"],
    "required_fields": ["enterprise_id", "name"],
    "create_fields": ["enterprise_id", "name", "category", "specification", "quantity", "unit", "location", "responsible_person", "contact_phone"],
    "update_fields": ["name", "category", "specification", "quantity", "unit", "location", "responsible_person", "contact_phone"],
    "order_by": "id",
    "rebuild_enterprise_index": True,
    "enterprise_ownership": True,
})

_ENT_CFG = {
    "model": Enterprise,
    "name_cn": "企业",
    "id_arg_name": "enterprise_id",
    "return_plural": "enterprise",
    "display_fields": [],
    "required_fields": ["name"],
    "create_fields": ["name", "industry", "address", "employee_count", "phone", "business_scope", "credit_code", "legal_representative"],
    "update_fields": ["name", "industry", "address", "employee_count", "phone", "business_scope", "credit_code", "legal_representative"],
    "order_by": "name",
    "user_id_field": "user_id",
    "enterprise_check": False,
}

_PLAN_CFG = dict(_RS_CFG)
_PLAN_CFG.update({
    "model": PlanProject,
    "name_cn": "预案",
    "id_arg_name": "plan_id",
    "return_plural": "plans",
    "display_fields": [],
    "required_fields": [],
    "create_fields": [],
    "update_fields": [],
    "order_by": "updated_at",
    "user_id_field": "user_id",
    "enterprise_check": False,
})





async def _get_dashboard(db, user, args):
    ent_count = (await db.execute(select(func.count(Enterprise.id)).where(Enterprise.user_id == user.id))).scalar() or 0
    plan_count = (await db.execute(select(func.count(PlanProject.id)).where(PlanProject.user_id == user.id))).scalar() or 0
    completed = (await db.execute(select(func.count(PlanProject.id)).where(PlanProject.user_id == user.id, PlanProject.status == "completed"))).scalar() or 0
    rs_count = (await db.execute(select(func.count(RiskSource.id)).join(Enterprise).where(Enterprise.user_id == user.id))).scalar() or 0
    res_count = (await db.execute(select(func.count(EmergencyResource.id)).join(Enterprise).where(Enterprise.user_id == user.id))).scalar() or 0
    generating = (await db.execute(select(func.count(PlanProject.id)).where(PlanProject.user_id == user.id, PlanProject.status == "generating"))).scalar() or 0
    risk_event_count = await count_user_risk_events(db, user.id)
    return {"enterprise_count": ent_count, "plan_count": plan_count, "completed_plan_count": completed, "generating_plan_count": generating, "risk_source_count": rs_count, "risk_event_count": risk_event_count, "resource_count": res_count}


# ── 企业 + 自动填充 ──

async def _list_enterprises(db, user, args):
    keyword = args.get("keyword", "")
    query = select(Enterprise).where(Enterprise.user_id == user.id)
    if keyword:
        query = query.where(Enterprise.name.ilike(f"%{keyword}%"))
    rows = (await db.execute(query.order_by(Enterprise.updated_at.desc()).limit(30))).scalars().all()
    return {"enterprises": [{"id": e.id, "name": e.name, "industry": e.industry, "address": e.address, "plan_count": len(e.plans or [])} for e in rows]}


async def _get_enterprise(db, user, args):
    ent_id = args.get("enterprise_id", "")
    name = args.get("name", "")
    if ent_id:
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    elif name:
        ent = (await db.execute(select(Enterprise).where(Enterprise.name.ilike(f"%{name}%"), Enterprise.user_id == user.id))).scalars().first()
    else:
        return {"error": "请提供 enterprise_id 或 name"}
    if not ent:
        return {"error": "企业不存在"}
    context = await build_risk_management_context(ent.id, db)
    return {
        "id": ent.id, "name": ent.name, "industry": ent.industry, "address": ent.address,
        "employee_count": ent.employee_count, "credit_code": ent.credit_code,
        "legal_representative": ent.legal_representative, "phone": ent.phone,
        "safety_officer": ent.safety_officer, "safety_officer_phone": ent.safety_officer_phone,
        "risk_sources": context.get("risk_sources", []),
        "resources": [{"id": r.id, "name": r.name, "category": r.category, "quantity": r.quantity, "unit": r.unit, "location": r.location} for r in (ent.resources or [])],
        "plans": [{"id": p.id, "title": p.title, "plan_type": p.plan_type, "status": p.status} for p in (ent.plans or [])],
    }


async def _autofill_enterprise(db, user, args):
    """自动填充 + 创建企业：先用QCC查工商数据，再入库。自动校准公司全称。"""
    name = args.get("name", "")
    if not name:
        return {"error": "请提供企业名称", "verified": False}
    # Step 1: QCC lookup
    fill_result = await autofill(user.id, name)
    if fill_result["ok"]:
        canonical_name = fill_result.get("name", name)
        fields = fill_result.get("fields", {})
        # 校准名称
        ent_name = canonical_name if canonical_name and canonical_name != name else name
    else:
        reason = fill_result.get("reason", "network_error")
        # 查询失败时仍用原名创建
        ent_name = name
        fields = {}
    # Step 2: 查重（同名企业已存在时直接返回，避免重复创建）
    existing = (await db.execute(
        select(Enterprise).where(
            Enterprise.user_id == user.id,
            func.lower(Enterprise.name) == ent_name.strip().lower(),
        )
    )).scalar_one_or_none()
    if existing:
        # 用 QCC 数据补充已有企业
        for fld in ["industry", "address", "employee_count", "credit_code",
                     "legal_representative", "registered_capital", "business_scope"]:
            val = fields.get(fld)
            if val and getattr(existing, fld) is None:
                setattr(existing, fld, val)
        await db.commit()
        fill_info = "已通过工商数据自动填充" if fill_result.get("ok") else f"QCC查询失败({fill_result.get('reason', '')})，仅更新基础信息"
        return {
            "id": existing.id, "name": existing.name,
            "message": f"企业「{existing.name}」已存在，已更新基础信息",
            "fill_info": fill_info, "original_query": name, "verified": True,
            "filled_fields": list(fields.keys()) if fields else [],
        }

    # Step 3: 创建企业
    ent = Enterprise(
        id=str(uuid4()), user_id=user.id, name=ent_name,
        industry=args.get("industry") or fields.get("industry", ""),
        address=args.get("address") or fields.get("address", ""),
        employee_count=_parse_int(args.get("employee_count")) or _parse_int(fields.get("employee_count")),
        credit_code=args.get("credit_code") or fields.get("credit_code"),
        legal_representative=args.get("legal_representative") or fields.get("legal_representative"),
        phone=args.get("phone") or "",
        business_scope=args.get("business_scope") or fields.get("business_scope", ""),
        registered_capital=fields.get("registered_capital"),
        economic_type=fields.get("economic_type"),
        established_date=_parse_date(fields.get("established_date")),
    )
    db.add(ent)
    await db.commit()
    await db.refresh(ent)
    # auto-verify
    verify_ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent.id))).scalar_one_or_none()
    verified = verify_ent is not None
    fill_info = "已通过工商数据自动填充" if fill_result["ok"] else f"QCC查询失败({fill_result.get('reason','')})，仅创建基础信息"
    return {
        "id": ent.id, "name": ent.name, "message": "企业创建成功",
        "fill_info": fill_info, "original_query": name, "verified": verified,
        "filled_fields": list(fields.keys()) if fields else [],
    }


async def _create_enterprise(db, user, args):
    # 查重：同名企业已存在时直接返回
    name = args.get("name", "")
    if name:
        from sqlalchemy import func as _func
        existing = (await db.execute(
            select(Enterprise).where(
                Enterprise.user_id == user.id,
                _func.lower(Enterprise.name) == name.strip().lower(),
            )
        )).scalar_one_or_none()
        if existing:
            return {"id": existing.id, "name": existing.name, "message": "企业已存在，无需重复创建", "verified": True}
    return await _delegate_generic(_generic_create, db, user, args, _ENT_CFG)


async def _update_enterprise(db, user, args):
    return await _delegate_generic(_generic_update, db, user, args, _ENT_CFG)


async def _delete_enterprise(db, user, args):
    try:
        enterprise_id = args.get("enterprise_id", "")
        if not enterprise_id:
            return {"error": "请提供 enterprise_id", "verified": False}
        ent = await _verify_enterprise_ownership(db, user, enterprise_id)
        counts = await delete_enterprise_complete(db, enterprise_id)
        await db.commit()
        remove_enterprise_uploads(enterprise_id)
        return {"message": f"企业「{ent.name}」已删除", "deleted_counts": counts, "verified": True}
    except _ErrorDict as e:
        return e.data


# ── 风险源 ──

async def _list_risk_sources(db, user, args):
    ent_id = args.get("enterprise_id", "")
    if not ent_id:
        return {"error": "请提供 enterprise_id"}
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == ent_id,
            Enterprise.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    context = await build_risk_management_context(ent_id, db)
    return {"risk_sources": context.get("risk_sources", [])}


# ── 应急资源 ──

async def _list_resources(db, user, args):
    return await _delegate_generic(_generic_list, db, user, args, _RES_CFG)


async def _create_resource(db, user, args):
    return await _delegate_generic(_generic_create, db, user, args, _RES_CFG)


async def _update_resource(db, user, args):
    return await _delegate_generic(_generic_update, db, user, args, _RES_CFG)


async def _delete_resource(db, user, args):
    return await _delegate_generic(_generic_delete, db, user, args, _RES_CFG)


# ── 预案 ──

async def _list_plans(db, user, args):
    keyword = args.get("keyword", "")
    status = args.get("status", "")
    plan_type = args.get("plan_type", "")
    ent_id = args.get("enterprise_id", "")
    query = select(PlanProject).where(PlanProject.user_id == user.id)
    if keyword:
        query = query.where(PlanProject.title.ilike(f"%{keyword}%"))
    if status:
        query = query.where(PlanProject.status == status)
    if plan_type:
        query = query.where(PlanProject.plan_type == plan_type)
    if ent_id:
        query = query.where(PlanProject.enterprise_id == ent_id)
    rows = (await db.execute(query.order_by(PlanProject.updated_at.desc()).limit(30))).scalars().all()
    items = []
    for p in rows:
        ent_name = p.enterprise.name if p.enterprise else ""
        total_s = len(p.sections or [])
        comp_s = sum(1 for s in (p.sections or []) if s.content and s.content.strip())
        items.append({"id": p.id, "title": p.title, "plan_type": p.plan_type, "status": p.status, "accident_type": p.accident_type, "enterprise_name": ent_name, "enterprise_id": p.enterprise_id, "completed_sections": comp_s, "total_sections": total_s})
    return {"plans": items}


async def _get_plan(db, user, args):
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "请提供 plan_id"}
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id))).scalar_one_or_none()
    if not p:
        return {"error": "预案不存在"}
    sections = [{"key": s.section_key, "title": s.title, "level": s.level, "has_content": bool(s.content and s.content.strip()), "ai_generated": s.ai_generated} for s in (p.sections or [])]
    return {"id": p.id, "title": p.title, "plan_type": p.plan_type, "status": p.status, "accident_type": p.accident_type, "enterprise_id": p.enterprise_id, "enterprise_name": p.enterprise.name if p.enterprise else "", "current_version": p.current_version, "sections": sections}


async def _create_plan(db, user, args):
    ent_id = args.get("enterprise_id", "")
    title = args.get("title", "")
    raw_plan_type = args.get("plan_type", "comprehensive")
    plan_type = PLAN_TYPE_ALIASES.get(raw_plan_type, raw_plan_type)
    if not ent_id or not title:
        return {"error": "请提供 enterprise_id 和 title"}
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    tmpl = (await db.execute(select(PlanTemplate).where(PlanTemplate.plan_type == plan_type, PlanTemplate.is_active == True).limit(1))).scalar_one_or_none()
    p = PlanProject(id=str(uuid4()), user_id=user.id, enterprise_id=ent_id, plan_type=plan_type, title=title, accident_type=args.get("accident_type"), status="draft")
    db.add(p)
    await db.flush()
    if tmpl and tmpl.structure:
        from app.routers.plans import _create_sections_from_template
        _create_sections_from_template(db, p.id, tmpl.structure)
    await db.commit()
    await db.refresh(p)
    return {"id": p.id, "title": p.title, "plan_type": p.plan_type, "message": "预案创建成功", "verified": True}


async def _delete_plan(db, user, args):
    return await _delegate_generic(_generic_delete, db, user, args, _PLAN_CFG)


# ── 模板 ──

async def _list_templates(db, user, args):
    plan_type = args.get("plan_type", "")
    query = select(PlanTemplate).where(PlanTemplate.is_active == True)
    if plan_type:
        query = query.where(PlanTemplate.plan_type == plan_type)
    rows = (await db.execute(query)).scalars().all()
    return {"templates": [{"id": t.id, "name": t.name, "plan_type": t.plan_type, "description": t.description} for t in rows]}


# ── 风险评估报告 ──

async def _verify_report_access(db, user, report_model, report_id):
    """report → enterprise → user 归属校验；返回 (report, error_dict)。"""
    if not report_id:
        return None, {"error": "请提供 report_id"}
    r = (await db.execute(select(report_model).where(report_model.id == report_id))).scalar_one_or_none()
    if not r:
        return None, {"error": "报告不存在或无权访问"}
    owned = (await db.execute(select(Enterprise.id).where(
        Enterprise.id == r.enterprise_id,
        Enterprise.user_id == user.id,
    ))).scalar_one_or_none()
    if not owned:
        return None, {"error": "报告不存在或无权访问"}
    return r, None


async def _list_risk_assessments(db, user, args):
    ent_id = args.get("enterprise_id", "")
    query = select(RiskAssessmentReport)
    if ent_id:
        owned = (await db.execute(select(Enterprise.id).where(
            Enterprise.id == ent_id, Enterprise.user_id == user.id
        ))).scalar_one_or_none()
        if not owned:
            return {"error": "企业不存在或无权访问", "verified": False}
        query = query.where(RiskAssessmentReport.enterprise_id == ent_id)
    else:
        user_ent_ids = (await db.execute(select(Enterprise.id).where(Enterprise.user_id == user.id))).scalars().all()
        query = query.where(RiskAssessmentReport.enterprise_id.in_(user_ent_ids))
    rows = (await db.execute(query.order_by(RiskAssessmentReport.created_at.desc()).limit(20))).scalars().all()
    return {"assessments": [{"id": r.id, "enterprise_id": r.enterprise_id, "status": r.status, "created_at": str(r.created_at)} for r in rows]}


async def _get_risk_assessment(db, user, args):
    r, err = await _verify_report_access(db, user, RiskAssessmentReport, args.get("report_id", ""))
    if err:
        return err
    return {"id": r.id, "enterprise_id": r.enterprise_id, "status": r.status, "content": r.content[:3000] if r.content else "", "created_at": str(r.created_at)}


# ── 应急资源调查报告 ──

async def _list_resource_investigations(db, user, args):
    ent_id = args.get("enterprise_id", "")
    query = select(ResourceInvestigationReport)
    if ent_id:
        owned = (await db.execute(select(Enterprise.id).where(
            Enterprise.id == ent_id, Enterprise.user_id == user.id
        ))).scalar_one_or_none()
        if not owned:
            return {"error": "企业不存在或无权访问", "verified": False}
        query = query.where(ResourceInvestigationReport.enterprise_id == ent_id)
    else:
        user_ent_ids = (await db.execute(select(Enterprise.id).where(Enterprise.user_id == user.id))).scalars().all()
        query = query.where(ResourceInvestigationReport.enterprise_id.in_(user_ent_ids))
    rows = (await db.execute(query.order_by(ResourceInvestigationReport.created_at.desc()).limit(20))).scalars().all()
    return {"investigations": [{"id": r.id, "enterprise_id": r.enterprise_id, "status": r.status, "created_at": str(r.created_at)} for r in rows]}


async def _get_resource_investigation(db, user, args):
    r, err = await _verify_report_access(db, user, ResourceInvestigationReport, args.get("report_id", ""))
    if err:
        return err
    return {"id": r.id, "enterprise_id": r.enterprise_id, "status": r.status, "content": r.content[:3000] if r.content else "", "created_at": str(r.created_at)}


# ── 法规库（内存图谱）──

async def _get_regulation_stats(db, user, args):
    """法规库统计：总数、现行数、废止数、已索引条数"""
    graph = get_graph()
    s = graph.stats()
    vs = get_vector_store()
    s["indexed_articles"] = vs.collection_count() if vs else 0
    return s


async def _list_regulations(db, user, args):
    """法规列表（从内存图谱读取）"""
    keyword = args.get("keyword", "")
    status = args.get("status", "all")
    page = args.get("page", 1)
    page_size = args.get("page_size", 20)
    graph = get_graph()
    result = graph.list_nodes(
        node_type=None, status=status, keyword=keyword,
        page=page, page_size=page_size,
    )
    return {"regulations": result.get("items", []), "total": result.get("total", 0), "page": page, "page_size": page_size}


async def _search_regulations(db, user, args):
    """法规语义搜索（内存向量库 + 图谱关键词兜底）"""
    query = args.get("query", "")
    if not query:
        return {"error": "请提供 query"}
    vs = get_vector_store()
    if vs:
        try:
            results = vs.search(query, top_k=5)
            return {"results": [{"content": item["text"][:500], "metadata": item["metadata"]} for item in results], "source": "vector_search"}
        except Exception:
            pass
    # fallback: keyword search via graph
    graph = get_graph()
    result = graph.list_nodes(keyword=query, page_size=5)
    return {"results": [{"id": n.get("id"), "full_name": n.get("full_name", n.get("title", "")), "node_type": n.get("node_type"), "status": n.get("status")} for n in result.get("items", [])], "source": "graph_fallback"}
# -- 法规条文检索(聊天助手引用用) --

# 向量召回候选数：先宽召回（30），再按 query 关键词命中加权重排后截断回 top_k
_REGULATION_RECALL_TOP_K = 30

# 法规问答中常见的疑问词/语气助词/无信息动词（按长度降序剔除，避免短词破坏领域短语）
_REG_QUERY_NOISE = (
    "有什么规定和要求", "有没有规定", "有没有要求", "有什么规定", "有什么要求",
    "有哪些规定", "有哪些要求", "有什么标准", "有什么条件", "有什么措施",
    "有什么程序", "有什么内容", "有什么义务", "有什么责任", "有什么处罚",
    "有何规定", "有何要求", "有什么", "有哪些", "什么样", "什么", "哪些",
    "如何", "怎样", "怎么", "做什么", "怎么做", "怎么办", "应做什么",
    "应怎么做", "要做什么", "需要做什么", "应当做", "应该做", "该怎么",
    "怎样做", "如何做", "是否", "能不能", "可不可以",
    "需不需要", "应不应该", "要不要", "是否需要", "应该", "应当", "需要",
    "必须", "可否", "是否要", "应做好", "应做", "做好", "进行", "予以",
    "依法", "以及", "或者", "吗", "呢", "啊", "吧", "了", "的",
)

# 2 字滑窗中的高频通用词：命中信息量低且会放大长表格/附录类噪声，不参与加权
_REG_WINDOW_STOP = frozenset({
    "安全", "生产", "作业", "单位", "企业", "管理", "规定", "要求", "标准",
    "人员", "工作", "组织", "实施", "制定", "建立", "部门", "机构", "相关",
    "有关", "以及", "或者", "进行", "应当", "必须", "其他", "内容", "情况",
    "负责", "国家", "地方", "政府", "按照", "根据", "符合", "加强", "各级",
})


def _extract_regulation_keywords(query: str) -> list[str]:
    """从法规问答中提取中文关键词（2+ 字）。

    仓库未依赖 jieba：先剔除常见疑问词/助词，再按标点与连接词切分，
    对剩余中文片段取 2-4 字滑窗去重 —— "储存距离""消防通道""备案"
    "演练频次" 等短领域短语天然被保留。
    """
    import re

    text = (query or "").strip().lower()
    if not text:
        return []
    for noise in sorted(_REG_QUERY_NOISE, key=len, reverse=True):
        text = text.replace(noise, "")
    segments = [
        s for s in re.split(
            r"[a-z0-9\s，。、；：？！?！?（）()\[\]《》<>“”‘’\"'\-—_/…~·]+|[和与及或]",
            text,
        )
        if s
    ]
    keywords: set[str] = set()
    for seg in segments:
        n = len(seg)
        if n < 2:
            continue
        for wlen in range(2, min(4, n) + 1):
            for i in range(n - wlen + 1):
                word = seg[i:i + wlen]
                if word.isalnum() and word not in _REG_WINDOW_STOP:
                    keywords.add(word)
    return sorted(keywords, key=lambda w: (-len(w), w))


def _rerank_regulation_articles(query: str, candidates: list[dict]) -> list[dict]:
    """向量召回候选按 query 关键词命中加权重排。

    加权分 = Σ(min(关键词命中次数, 3) × 长度²)
             + 关键词命中法规名/文号时的固定加分；
    加权分相同时按向量相似度降序作为次级排序。
    """
    keywords = _extract_regulation_keywords(query)
    if not keywords:
        return sorted(
            candidates,
            key=lambda a: float(a.get("similarity_score", 0.0) or 0.0),
            reverse=True,
        )
    scored = []
    for article in candidates:
        text_hay = (
            ((article.get("article_text") or "") + "\n"
             + (article.get("article_number") or ""))
        ).lower()
        name_hay = (
            ((article.get("regulation_full_name") or "") + " "
             + (article.get("regulation_code") or ""))
        ).lower()
        score = 0.0
        for kw in keywords:
            occ = text_hay.count(kw)
            if occ:
                score += min(occ, 3) * len(kw) * len(kw)
            if kw in name_hay:
                score += 10
        scored.append((score, article))
    scored.sort(
        key=lambda pair: (
            pair[0],
            float(pair[1].get("similarity_score", 0.0) or 0.0),
        ),
        reverse=True,
    )
    return [article for _, article in scored]


def _regulation_corpus_texts(store) -> list | None:
    """读取已入库的全部条文文本（词面召回用）。失败返回 None，由调用方忽略。"""
    col = getattr(store, "_collection", None)
    if col is None:
        return None
    try:
        data = col.get(include=["documents", "metadatas"])
        docs = data.get("documents")
        metas = data.get("metadatas")
        if not isinstance(docs, list) or not isinstance(metas, list):
            return None
        return [(docs[i] or "", metas[i] or {}) for i in range(len(docs))]
    except Exception:
        return None


def _corpus_lexical_matches(store, keywords: list[str]):
    """全库词面匹配：返回 (命中条文列表, 关键词 df, 条文总数)。

    向量语义对中文法规问句召回不稳定，直接按词面扫全库；
    返回 None 表示词面召回不可用（如 mock/未初始化），调用方应忽略。
    """
    if not keywords:
        return None
    corpus = _regulation_corpus_texts(store)
    if not corpus:
        return None
    df = {kw: 0 for kw in keywords}
    matches = []
    for text, meta in corpus:
        hay = ((text or "") + "\n" + (meta.get("article_number") or "")).lower()
        score = 0.0
        for kw in keywords:
            occ = hay.count(kw)
            if occ:
                score += min(occ, 3) * len(kw) * len(kw)
                df[kw] += 1
        if score > 0:
            matches.append({"text": text, "metadata": meta, "distance": 1.0})
    return matches, df, len(corpus)


def _regulation_candidate_score(article: dict, keywords: list[str],
                                df: dict | None, total: int) -> float:
    """词面加权分（重排用）：IDF × 命中次数(上限3) × 长度² + 法规名加分。

    有全库 df 时加入逆文档频率与文本长度归一化（抑制长表格/附录噪声）；
    无 df（纯向量候选）退化为朴素命中加权。返回分数越大越相关。
    """
    import math

    text_hay = (
        ((article.get("article_text") or "") + "\n"
         + (article.get("article_number") or ""))
    ).lower()
    score = 0.0
    for kw in keywords:
        occ = text_hay.count(kw)
        if not occ:
            continue
        weight = len(kw) * len(kw)
        if df:
            kw_df = df.get(kw, 0) or 1
            weight *= 1.0 + math.log(float(total + 1) / (kw_df + 1))
        score += min(occ, 3) * weight
    if df:
        score /= (1.0 + len(text_hay) / 600.0)
    name_hay = (
        ((article.get("regulation_full_name") or "") + " "
         + (article.get("regulation_code") or ""))
    ).lower()
    name_bonus = sum(12 for kw in keywords if kw in name_hay)
    return score + min(name_bonus, 60)


async def _search_regulation_articles(db, user, args):
    """法规条文检索：向量召回 + 词面召回 → 关键词相关度重排；图谱兜底。"""
    query = args.get("query", "")
    if not query:
        return {"error": "请提供 query"}

    top_k = _parse_int(args.get("top_k", 8)) or 8
    top_k = max(3, min(top_k, 15))
    try:
        store = get_vector_store()
        # 向量召回供重排挑选（先执行以完成 collection 初始化，最终仍截断回 top_k）
        hits = list(store.search_articles(query, top_k=_REGULATION_RECALL_TOP_K) or [])
        keywords = _extract_regulation_keywords(query)
        # 词面召回：向量语义对中文问句召回不稳定，直接按关键词扫全库条文
        lexical = _corpus_lexical_matches(store, keywords)
        if lexical:
            seen = {
                ((h.get("metadata") or {}).get("regulation_id", ""),
                 (h.get("metadata") or {}).get("article_number", ""))
                for h in hits
            }
            for hit in lexical[0]:
                meta = hit.get("metadata") or {}
                key = (meta.get("regulation_id", ""), meta.get("article_number", ""))
                if key in seen:
                    continue
                seen.add(key)
                hits.append(hit)
        if hits:
            graph = get_graph()
            candidates = []
            for hit in hits:
                meta = hit.get("metadata") or {}
                reg_id = meta.get("regulation_id", "")
                node = graph.get_node(reg_id) if reg_id else None
                if not node or node.get("status") == "abolished":
                    continue
                candidates.append({
                    "article_text": hit.get("text", ""),
                    "article_number": meta.get("article_number", ""),
                    "regulation_full_name": node.get("full_name", node.get("title", "")),
                    "regulation_code": node.get("code", ""),
                    "status": node.get("status", ""),
                    "similarity_score": round(1 - float(hit.get("distance", 1)), 4),
                })
            if candidates:
                df = lexical[1] if lexical else None
                total = lexical[2] if lexical else 0
                articles = sorted(
                    candidates,
                    key=lambda art: (
                        _regulation_candidate_score(art, keywords, df, total),
                        float(art.get("similarity_score", 0.0) or 0.0),
                    ),
                    reverse=True,
                )
                return {"articles": articles[:top_k], "count": len(articles[:top_k]),
                        "source": "vector"}
    except Exception as e:
        logger.warning("向量法规检索失败，回退关键词: %s", e)
    return await _regulation_keyword_fallback(query, top_k)


async def _regulation_keyword_fallback(query: str, top_k: int) -> dict:
    """图谱关键词搜索 + 文件加载原文。供聊天助手回答法规问题时使用。

    流程: graph.list_nodes(keyword=query) -> 加载 texts/*.md 条文 -> 关键词子串匹配。
    """

    import os, re as _re

    graph = get_graph()

    # ── 多策略节点发现（修复：支持"法规名 第X条"组合查询）──
    nodes = []
    seen_node_ids = set()

    def _collect_node(nid, data):
        if nid in seen_node_ids:
            return
        if data.get("status") == "abolished":
            return
        node = dict(data)
        node["id"] = nid
        seen_node_ids.add(nid)
        nodes.append(node)

    # 策略1：完整查询字符串匹配
    raw_result = graph.list_nodes(keyword=query, page_size=top_k)
    for n in raw_result.get("items", []):
        _collect_node(n.get("id", ""), {k: v for k, v in n.items() if k != "id"})

    # 策略2：拆分成单个关键词分别匹配图谱中的所有节点
    if not nodes:
        segments = _re.split(r"[\s、]+|的(?=第)|(?<=法)的", query)
        individual_kw = [s.strip() for s in segments if len(s.strip()) >= 2]
        if not individual_kw:
            individual_kw = [kw.strip() for kw in query.split() if len(kw.strip()) >= 2]

        import os as _os
        tdir = _os.path.join(_os.path.dirname(__file__), "..", "regulations", "data", "texts")
        for nid, data in graph._g.nodes(data=True):
            if data.get("node_type") in ("topic", "article"):
                continue
            full = (data.get("full_name") or "").lower()
            label = (data.get("label") or "").lower()
            code = (data.get("code") or "").lower()
            for kw in individual_kw:
                if kw.lower() in full or kw.lower() in label or kw.lower() in code:
                    if _os.path.exists(_os.path.join(tdir, f"{nid}.md")):
                        _collect_node(nid, dict(data))
                        break

    if not nodes:
        return {"articles": [], "count": 0, "source": "graph_fallback",
                "message": "法规库中暂未找到与您问题直接相关的法规。"}

    texts_dir = os.path.join(os.path.dirname(__file__), "..", "regulations", "data", "texts")
    keywords = [kw.strip() for kw in query.split() if len(kw.strip()) >= 2]

    articles = []
    seen_ids = set()

    for node in nodes:
        nid = node.get("id", "")
        if nid in seen_ids:
            continue
        seen_ids.add(nid)

        if node.get("status") == "abolished":
            continue

        full_name = node.get("full_name", node.get("title", ""))
        reg_code = node.get("code", "")

        fpath = os.path.join(texts_dir, f"{nid}.md")
        if not os.path.exists(fpath):
            continue

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception:
            continue

        blocks = _re.split(r"\n(?=##\s)", file_content)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            article_number = lines[0].lstrip("#").strip() if lines else ""
            article_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

            if not article_text or len(article_text) < 10 or len(article_number) > 30:
                continue
            # Skip preamble/metadata blocks (not actual articles)
            if any(kw in article_number for kw in ["发布机关", "发布日期", "施行日期", "适用主题", "上位法依据"]):
                continue

            score = 0
            query_lower = query.lower()
            # 条文编号也参与匹配（标题行如"第一条"）
            text_lower = (article_number + " " + article_text).lower()
            for kw in keywords:
                count = text_lower.count(kw.lower())
                if count > 0:
                    score += count * 10
                # 条文编号精确匹配大幅加分
                if kw.lower() == article_number.lower():
                    score += 100
            if query_lower in text_lower:
                score += 50

            if score > 0:
                articles.append({
                    "article_text": article_text[:500],
                    "article_number": article_number,
                    "regulation_id": nid,
                    "regulation_full_name": full_name,
                    "regulation_code": reg_code,
                    "regulation_status": node.get("status", "effective"),
                    "relevance_score": score,
                })

    articles.sort(key=lambda a: a["relevance_score"], reverse=True)
    articles = articles[:top_k]

    if not articles:
        return {
            "articles": [],
            "count": 0,
            "source": "graph_fallback",
            "message": "法规库中暂未找到与该问题直接相关的条文。以下是与关键词匹配的法规列表供参考：",
            "matched_regulations": [
                {"id": n.get("id"), "full_name": n.get("full_name", n.get("title", "")),
                 "code": n.get("code", "")}
                for n in nodes[:5]
            ],
        }

    return {"articles": articles, "count": len(articles), "source": "graph_fallback"}

# ── AI 配置 ──

async def _get_ai_config(db, user, args):
    from app.services.ai_config_service import get_system_ai_config
    cfg = await get_system_ai_config(db)
    if not cfg:
        return {"configured": False, "message": "尚未配置 AI"}
    return {"configured": True, "provider": cfg.provider, "model": cfg.model_name}


# ── 导出 ──

async def _export_plan_docx(db, user, args):
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "请提供 plan_id"}
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id))).scalar_one_or_none()
    if not p:
        return {"error": "预案不存在"}
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    sections = (await db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)
    )).scalars().all()
    sections_data = []
    for s in sections:
        if not s.content or not s.content.strip():
            continue
        content = s.content
        try:
            from app.routers.export import _strip_section_heading
            content = _strip_section_heading(content, s.title)
        except Exception:
            pass
        sections_data.append({
            "title": s.title, "level": s.level,
            "content": content, "mermaid_svgs": s.mermaid_svgs or {},
        })
    if not p.plan_number or not p.version_number:
        return {"error": "请先设置预案编号与版本号"}
    try:
        from app.routers.export import _build_signers_from_org
        import asyncio
        import re as _re
        signers = _build_signers_from_org(ent.org_structure or [])
        doc = await asyncio.to_thread(
            generate_plan_docx_func,
            company_name=ent.name,
            plan_title=p.title,
            plan_type=p.plan_type,
            plan_number=p.plan_number,
            version_number=p.version_number,
            sections=sections_data,
            signers=signers or None,
        )
        export_dir = os.environ.get("EXPORT_DIR", "/app/exports")
        os.makedirs(export_dir, exist_ok=True)
        safe_title = _re.sub(r'[\/*?:"<>|]', "_", p.title)
        filename = f"{safe_title}.docx"
        filepath = os.path.join(export_dir, filename)
        doc.save(filepath)
        return {"message": "导出成功", "filename": filename, "verified": True}
    except Exception as e:
        return {"error": f"导出失败: {str(e)}"}


# ── 图文报告生成 ──

async def _collect_risk_distribution(db, user, args=None):
    """风险源按等级分布（跨企业汇总）。"""
    ents = (await db.execute(select(Enterprise).where(
        Enterprise.user_id == user.id).limit(50))).scalars().all()
    dist: dict[str, int] = {}
    for ent in ents:
        ctx = await build_risk_management_context(ent.id, db)
        for rs in ctx.get("risk_sources", []):
            lvl = rs.get("risk_level") or "未分级"
            dist[lvl] = dist.get(lvl, 0) + 1
    return dist


async def _collect_resource_coverage(db, user, args=None):
    """应急资源按类别统计。"""
    rows = (await db.execute(
        select(EmergencyResource).join(Enterprise)
        .where(Enterprise.user_id == user.id))).scalars().all()
    dist: dict[str, int] = {}
    for r in rows:
        cat = r.category or "未分类"
        dist[cat] = dist.get(cat, 0) + 1
    return dist


async def _collect_regulation_compliance(db, user, args=None):
    """法规库统计 + 用户预案引用概况（轻量）。"""
    stats = await _get_regulation_stats(db, user, {})
    plans = (await db.execute(select(PlanProject).where(
        PlanProject.user_id == user.id))).scalars().all()
    return {"regulation_stats": stats, "plan_total": len(plans)}


# 报告主题 → 额外采集器：命中主题时把采集数据并入 data_context，未命中回退既有逻辑
REPORT_EXTRA_COLLECTORS = {
    "风险分布": _collect_risk_distribution,
    "资源覆盖": _collect_resource_coverage,
    "法规合规": _collect_regulation_compliance,
}


async def _generate_report(db, user, args):
    """生成图文并茂的分析报告（Markdown + Mermaid 图表）。

    流程：收集系统数据 → 构建 prompt → 调 LLM 生成 Markdown（内含 Mermaid 图表）。
    返回报告内容由 chat 端点流式输出给用户。
    """
    topic = args.get("topic", "系统概览")
    report_type = args.get("report_type", "summary")

    # 收集数据
    dash = await _get_dashboard(db, user, {})
    plans = await _list_plans(db, user, {})
    enterprises = await _list_enterprises(db, user, {})

    collector = REPORT_EXTRA_COLLECTORS.get(topic)
    if collector:
        extra = await collector(db, user, {})
        data_context = json.dumps({"dashboard": dash, "extra": extra},
                                  ensure_ascii=False, indent=2)
    else:
        data_context = json.dumps({
            "dashboard": dash,
            "recent_plans": plans.get("plans", [])[:5],
            "enterprises": enterprises.get("enterprises", [])[:5],
        }, ensure_ascii=False, indent=2)

    prompt = f"""请根据以下系统数据，生成一份「{topic}」的专业分析报告。

【报告要求】
- 根据数据实际情况和特征，选择最合适的组织方式，不必强制按固定章节模板
- 在恰当的位置使用 Mermaid 图表辅助表达。仅使用以下 Mermaid 支持的图表类型：
  · 占比/比例 → pie（示例：pie title "标题" "A": 30 "B": 70）
  · 层级/关联关系 → graph TD（示例：graph TD; A-->B; A-->C）
  · 流程/步骤 → flowchart TD（示例：flowchart TD; A[开始]-->B[处理]-->C[结束]）
  · 切勿使用 bar、xychart、或自造的图表语法——这些 Mermaid 不支持
- 多维度数据对比请优先使用 Markdown 表格，效果比图表更好
- 不必每段都放图表，仅在图表能增强理解时使用
- 语言：简体中文，专业、简洁
- 结尾给出基于数据的具体、可操作的总结和建议
- 不要在报告中出现「根据数据」「数据显示」「数据不足」等元描述，直接呈现分析内容

【系统数据】
{data_context}

请直接输出报告内容："""
    system_prompt = f"""你是一位应急管理与安全生产领域的专业分析师，擅长从数据中提取洞察并撰写结构清晰的分析报告。

本次报告主题：{topic}
行业背景：生产经营单位应急预案管理、安全生产法规合规、风险管控与应急资源调度。

写作原则：
- 读者是企业管理者和安全负责人
- 数据驱动，不做无依据的推测
- 图表服务于分析，不滥用
- 数据少时定性分析优先，不必强行凑图表"""

    # 返回 prompt 和元信息，由 chat 端点调 LLM 生成
    return {
        "type": "report_prompt",
        "topic": topic,
        "report_type": report_type,
        "prompt": prompt,
        "system_prompt": system_prompt,
        "data_summary": {
            "enterprises": dash.get("enterprise_count", 0),
            "plans": dash.get("plan_count", 0),
            "completed": dash.get("completed_plan_count", 0),
            "risk_sources": dash.get("risk_source_count", 0),
        },
        "message": "报告数据已就绪，正在生成图文报告...",
    }



# ── 预案内容生成 ──

async def _generate_plan_content(db, user, args):
    """聊天触发后台批量生成。"""
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "请提供 plan_id"}
    p = (await db.execute(
        select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id)
    )).scalar_one_or_none()
    if not p:
        return {"error": "预案不存在", "verified": False}
    out = await start_batch_generation(plan_id, db, user, keys=None, background=True)
    out["plan_id"] = plan_id
    out["verified"] = out.get("started", False)
    return out


async def _get_generation_progress(db, user, args):
    """查询聊天触发的后台生成进度。"""
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "请提供 plan_id"}
    p = (await db.execute(
        select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id)
    )).scalar_one_or_none()
    if not p:
        return {"error": "预案不存在", "verified": False}
    # B4：失败章节由 plan_generation_service._run_background 写入，此处统一查询 service
    failed = get_failed_sections(plan_id)
    sections = p.sections or []
    filled = sum(1 for s in sections if s.content and s.content.strip())
    return {
        "plan_id": plan_id, "title": p.title,
        "status": p.status, "filled_sections": filled, "total_sections": len(sections),
        "failed_sections": failed,
        "message": ("生成完成" if p.status == "completed"
                    else "正在生成中" if p.status == "generating"
                    else "未在生成"),
        "verified": True,
    }



# ── 企业画像问答 ──

async def _query_enterprise_knowledge(db, user, args):
    """基于企业画像（风险/评估/资源）语义问答。"""
    ent_id = args.get("enterprise_id", "")
    question = args.get("question", "")
    if not ent_id or not question:
        return {"error": "请提供 enterprise_id 和 question"}
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在或无权访问", "verified": False}
    try:
        hits = EnterpriseKnowledgeStore().search(ent_id, question, top_k=6)
    except Exception as e:
        logger.warning("企业画像检索失败: %s", e)
        hits = []
    if not hits:
        return {"enterprise_id": ent_id, "hits": [],
                "message": "该企业暂无画像数据（请先完成风险辨识或生成评估报告）", "verified": True}
    return {"enterprise_id": ent_id, "hits": [{"text": h["text"][:500],
                                               "similarity": round(1 - float(h["distance"]), 4)}
                                              for h in hits],
            "message": "已检索到相关画像片段", "verified": True}


# ── 端到端工作流 + 用户偏好工具（阶段3 任务6）──

_WF_PREF_STRING_KEYS = frozenset({
    "style_preference", "detail_level", "extra",
})
_WF_PREF_JSON_LIST_KEYS = frozenset({
    "report_topics", "common_enterprise_ids",
})


async def _run_workflow(db, user, args):
    """启动端到端工作流：经 WorkflowRunner.start_workflow 建 run + 步骤记录并后台执行。"""
    workflow_name = args.get("workflow_name", "")
    if not workflow_name:
        return {"error": "请提供 workflow_name", "verified": False}
    params = args.get("params") or {}
    run = await WorkflowRunner(db).start_workflow(
        user, workflow_name, params, background=True)
    return {
        "run_id": run.id,
        "workflow_name": workflow_name,
        "status": run.status,
        "current_step": run.current_step,
        "message": f"工作流 {workflow_name} 已启动，可用 get_workflow_progress 查询进度",
        "verified": True,
    }


async def _confirm_workflow_step(db, user, args):
    """确认工作流门控步骤（run 处于 paused 且 current_step=step_name 时放行继续）。"""
    run_id = args.get("run_id", "")
    step_name = args.get("step_name", "")
    if not run_id or not step_name:
        return {"error": "请提供 run_id 和 step_name", "verified": False}
    run_owned = (await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id, WorkflowRun.user_id == user.id)
    )).scalar_one_or_none()
    if not run_owned:
        return {"error": "工作流不存在或无权访问", "verified": False}
    try:
        run = await WorkflowRunner(db).confirm_workflow_step(run_id, step_name)
    except ValueError as e:
        return {"error": str(e), "verified": False}
    return {
        "run_id": run.id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "current_step": run.current_step,
        "message": f"已确认步骤 {step_name}，工作流继续执行",
        "verified": True,
    }


async def _get_workflow_progress(db, user, args):
    """查询 workflow_runs 运行状态 + 步骤列表（归属校验）。"""
    run_id = args.get("run_id", "")
    if not run_id:
        return {"error": "请提供 run_id", "verified": False}
    run = (await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id, WorkflowRun.user_id == user.id)
    )).scalar_one_or_none()
    if not run:
        return {"error": "工作流不存在或无权访问", "verified": False}
    steps = (await db.execute(
        select(WorkflowRunStep)
        .where(WorkflowRunStep.run_id == run_id)
        .order_by(WorkflowRunStep.step_name)
    )).scalars().all()
    return {
        "run_id": run.id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "current_step": run.current_step,
        "steps": [{
            "step_name": s.step_name,
            "status": s.status,
            "error": s.error,
        } for s in steps],
        "verified": True,
    }


async def _get_preferences(db, user, args):
    """查看当前用户偏好（user_preference_service 缓存）。"""
    prefs = await get_preferences(db, user.id)
    return {"user_id": user.id, "preferences": prefs, "verified": True}


async def _set_preferences(db, user, args):
    """设置用户偏好：标量键存字符串；report_topics/common_enterprise_ids 存数组。"""
    key = args.get("key", "")
    value = args.get("value")
    if not key:
        return {"error": "请提供 key", "verified": False}
    if value is None or value == "":
        return {"error": "请提供 value", "verified": False}
    if key in _WF_PREF_JSON_LIST_KEYS:
        if isinstance(value, str):
            try:
                final_value = json.loads(value)
            except json.JSONDecodeError:
                return {"error": f"{key} 需为 JSON 数组（如 [\"风险分布\"]）", "verified": False}
        else:
            final_value = value
        if not isinstance(final_value, list):
            return {"error": f"{key} 需为数组（如 [\"风险分布\"]）", "verified": False}
    elif key in _WF_PREF_STRING_KEYS:
        if not isinstance(value, str):
            return {"error": f"{key} 需为字符串", "verified": False}
        final_value = value
    else:
        return {"error": "未知偏好键，可用：style_preference/detail_level/report_topics/common_enterprise_ids/extra",
                "verified": False}
    prefs = await set_preferences(db, user.id, {key: final_value})
    await db.commit()
    return {"message": f"偏好已更新：{key}", "preferences": prefs, "verified": True}


# ── 函数注册表 ──

_FUNCTIONS = {
    "get_dashboard": _get_dashboard,
    "autofill_enterprise": _autofill_enterprise,
    "list_enterprises": _list_enterprises,
    "get_enterprise": _get_enterprise,
    "create_enterprise": _create_enterprise,
    "update_enterprise": _update_enterprise,
    "delete_enterprise": _delete_enterprise,
    "list_risk_sources": _list_risk_sources,
    "list_resources": _list_resources,
    "create_resource": _create_resource,
    "update_resource": _update_resource,
    "delete_resource": _delete_resource,
    "list_plans": _list_plans,
    "get_plan": _get_plan,
    "create_plan": _create_plan,
    "delete_plan": _delete_plan,
    "list_templates": _list_templates,
    "list_risk_assessments": _list_risk_assessments,
    "get_risk_assessment": _get_risk_assessment,
    "list_resource_investigations": _list_resource_investigations,
    "get_resource_investigation": _get_resource_investigation,
    "get_regulation_stats": _get_regulation_stats,
    "list_regulations": _list_regulations,
    "search_regulations": _search_regulations,
    "search_regulation_articles": _search_regulation_articles,
    "get_ai_config": _get_ai_config,
    "export_plan_docx": _export_plan_docx,
    "generate_report": _generate_report,
    "generate_plan_content": _generate_plan_content,
    "get_generation_progress": _get_generation_progress,
    "query_enterprise_knowledge": _query_enterprise_knowledge,
    "run_workflow": _run_workflow,
    "confirm_workflow_step": _confirm_workflow_step,
    "get_workflow_progress": _get_workflow_progress,
    "get_preferences": _get_preferences,
    "set_preferences": _set_preferences,
}
