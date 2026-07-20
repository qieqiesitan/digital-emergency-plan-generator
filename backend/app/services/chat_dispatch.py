"""Chat dispatch — 全覆盖系统 API 操作函数。"""

import json
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.enterprise import (
    Enterprise, RiskSource, EmergencyResource, PlanProject,
    PlanSection, PlanTemplate, AIConfig as AIConfigModel,
)

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

async def _get_dashboard(db, user, args):
    ent_count = (await db.execute(select(func.count(Enterprise.id)).where(Enterprise.user_id == user.id))).scalar() or 0
    plan_count = (await db.execute(select(func.count(PlanProject.id)).where(PlanProject.user_id == user.id))).scalar() or 0
    completed = (await db.execute(select(func.count(PlanProject.id)).where(PlanProject.user_id == user.id, PlanProject.status == "completed"))).scalar() or 0
    rs_count = (await db.execute(select(func.count(RiskSource.id)).join(Enterprise).where(Enterprise.user_id == user.id))).scalar() or 0
    res_count = (await db.execute(select(func.count(EmergencyResource.id)).join(Enterprise).where(Enterprise.user_id == user.id))).scalar() or 0
    generating = (await db.execute(select(func.count(PlanProject.id)).where(PlanProject.user_id == user.id, PlanProject.status == "generating"))).scalar() or 0
    return {"enterprise_count": ent_count, "plan_count": plan_count, "completed_plan_count": completed, "generating_plan_count": generating, "risk_source_count": rs_count, "resource_count": res_count}


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
    return {
        "id": ent.id, "name": ent.name, "industry": ent.industry, "address": ent.address,
        "employee_count": ent.employee_count, "credit_code": ent.credit_code,
        "legal_representative": ent.legal_representative, "phone": ent.phone,
        "safety_officer": ent.safety_officer, "safety_officer_phone": ent.safety_officer_phone,
        "risk_sources": [{"id": r.id, "name": r.name, "categories": r.categories, "risk_level": r.risk_level} for r in (ent.risk_sources or [])],
        "resources": [{"id": r.id, "name": r.name, "category": r.category, "quantity": r.quantity, "unit": r.unit, "location": r.location} for r in (ent.resources or [])],
        "plans": [{"id": p.id, "title": p.title, "plan_type": p.plan_type, "status": p.status} for p in (ent.plans or [])],
    }


async def _autofill_enterprise(db, user, args):
    """自动填充 + 创建企业：先用QCC查工商数据，再入库。自动校准公司全称。"""
    name = args.get("name", "")
    if not name:
        return {"error": "请提供企业名称", "verified": False}
    # Step 1: QCC lookup
    from app.services.enterprise_autofill import autofill as do_autofill
    fill_result = await do_autofill(user.id, name)
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
    # Step 2: 创建企业
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
    name = args.get("name", "")
    if not name:
        return {"error": "企业名称不能为空", "verified": False}
    ent = Enterprise(
        id=str(uuid4()), user_id=user.id, name=name,
        industry=args.get("industry", ""), address=args.get("address", ""),
        employee_count=args.get("employee_count"),
        credit_code=args.get("credit_code"), legal_representative=args.get("legal_representative"),
        phone=args.get("phone"), business_scope=args.get("business_scope"),
    )
    db.add(ent)
    await db.commit()
    await db.refresh(ent)
    verify_ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent.id))).scalar_one_or_none()
    verified = verify_ent is not None
    return {"id": ent.id, "name": ent.name, "message": "企业创建成功", "verified": verified}


async def _update_enterprise(db, user, args):
    ent_id = args.get("enterprise_id", "")
    if not ent_id:
        return {"error": "请提供 enterprise_id"}
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    for field in ["name", "industry", "address", "employee_count", "phone", "business_scope", "credit_code", "legal_representative"]:
        if field in args and args[field] is not None:
            setattr(ent, field, args[field])
    await db.commit()
    return {"id": ent.id, "name": ent.name, "message": "企业更新成功", "verified": True}


async def _delete_enterprise(db, user, args):
    ent_id = args.get("enterprise_id", "")
    if not ent_id:
        return {"error": "请提供 enterprise_id"}
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    ent_name = ent.name
    await db.delete(ent)
    await db.commit()
    return {"message": f"企业「{ent_name}」已删除", "verified": True}


# ── 风险源 ──

async def _list_risk_sources(db, user, args):
    ent_id = args.get("enterprise_id", "")
    if not ent_id:
        return {"error": "请提供 enterprise_id"}
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    rows = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == ent_id).order_by(RiskSource.sort_order))).scalars().all()
    return {"risk_sources": [{"id": r.id, "name": r.name, "categories": r.categories, "risk_level": r.risk_level, "location": r.location, "description": r.description, "control_measures": r.control_measures} for r in rows]}


async def _create_risk_source(db, user, args):
    ent_id = args.get("enterprise_id", "")
    name = args.get("name", "")
    if not ent_id or not name:
        return {"error": "请提供 enterprise_id 和 name"}
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    rs = RiskSource(id=str(uuid4()), enterprise_id=ent_id, name=name, categories=args.get("categories", ""), location=args.get("location"), description=args.get("description"), risk_level=args.get("risk_level"), control_measures=args.get("control_measures"), likelihood=args.get("likelihood", 3), severity=args.get("severity", 3))
    db.add(rs)
    await db.commit()
    return {"id": rs.id, "name": rs.name, "message": "风险源创建成功", "verified": True}


async def _update_risk_source(db, user, args):
    rs_id = args.get("risk_source_id", "")
    if not rs_id:
        return {"error": "请提供 risk_source_id"}
    rs = (await db.execute(select(RiskSource).where(RiskSource.id == rs_id))).scalar_one_or_none()
    if not rs:
        return {"error": "风险源不存在"}
    for field in ["name", "categories", "location", "description", "risk_level", "control_measures", "likelihood", "severity"]:
        if field in args and args[field] is not None:
            setattr(rs, field, args[field])
    await db.commit()
    return {"id": rs.id, "name": rs.name, "message": "风险源更新成功", "verified": True}


async def _delete_risk_source(db, user, args):
    rs_id = args.get("risk_source_id", "")
    if not rs_id:
        return {"error": "请提供 risk_source_id"}
    rs = (await db.execute(select(RiskSource).where(RiskSource.id == rs_id))).scalar_one_or_none()
    if not rs:
        return {"error": "风险源不存在"}
    await db.delete(rs)
    await db.commit()
    return {"message": f"风险源「{rs.name}」已删除", "verified": True}


# ── 应急资源 ──

async def _list_resources(db, user, args):
    ent_id = args.get("enterprise_id", "")
    if not ent_id:
        return {"error": "请提供 enterprise_id"}
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    rows = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == ent_id))).scalars().all()
    return {"resources": [{"id": r.id, "name": r.name, "category": r.category, "quantity": r.quantity, "unit": r.unit, "location": r.location, "responsible_person": r.responsible_person, "contact_phone": r.contact_phone} for r in rows]}


async def _create_resource(db, user, args):
    ent_id = args.get("enterprise_id", "")
    name = args.get("name", "")
    if not ent_id or not name:
        return {"error": "请提供 enterprise_id 和 name"}
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    res = EmergencyResource(id=str(uuid4()), enterprise_id=ent_id, name=name, category=args.get("category", ""), specification=args.get("specification"), quantity=args.get("quantity", 0), unit=args.get("unit"), location=args.get("location"), responsible_person=args.get("responsible_person"), contact_phone=args.get("contact_phone"))
    db.add(res)
    await db.commit()
    return {"id": res.id, "name": res.name, "message": "应急资源创建成功", "verified": True}


async def _update_resource(db, user, args):
    res_id = args.get("resource_id", "")
    if not res_id:
        return {"error": "请提供 resource_id"}
    r = (await db.execute(select(EmergencyResource).where(EmergencyResource.id == res_id))).scalar_one_or_none()
    if not r:
        return {"error": "应急资源不存在"}
    for field in ["name", "category", "specification", "quantity", "unit", "location", "responsible_person", "contact_phone"]:
        if field in args and args[field] is not None:
            setattr(r, field, args[field])
    await db.commit()
    return {"id": r.id, "name": r.name, "message": "应急资源更新成功", "verified": True}


async def _delete_resource(db, user, args):
    res_id = args.get("resource_id", "")
    if not res_id:
        return {"error": "请提供 resource_id"}
    r = (await db.execute(select(EmergencyResource).where(EmergencyResource.id == res_id))).scalar_one_or_none()
    if not r:
        return {"error": "应急资源不存在"}
    await db.delete(r)
    await db.commit()
    return {"message": f"应急资源「{r.name}」已删除", "verified": True}


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
    plan_type = args.get("plan_type", "comprehensive")
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
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "请提供 plan_id"}
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id))).scalar_one_or_none()
    if not p:
        return {"error": "预案不存在"}
    title = p.title
    await db.delete(p)
    await db.commit()
    return {"message": f"预案「{title}」已删除", "verified": True}


# ── 模板 ──

async def _list_templates(db, user, args):
    plan_type = args.get("plan_type", "")
    query = select(PlanTemplate).where(PlanTemplate.is_active == True)
    if plan_type:
        query = query.where(PlanTemplate.plan_type == plan_type)
    rows = (await db.execute(query)).scalars().all()
    return {"templates": [{"id": t.id, "name": t.name, "plan_type": t.plan_type, "description": t.description} for t in rows]}


# ── 风险评估报告 ──

async def _list_risk_assessments(db, user, args):
    from app.models.risk_assessment import RiskAssessmentReport
    ent_id = args.get("enterprise_id", "")
    query = select(RiskAssessmentReport)
    if ent_id:
        query = query.where(RiskAssessmentReport.enterprise_id == ent_id)
    else:
        user_ent_ids = (await db.execute(select(Enterprise.id).where(Enterprise.user_id == user.id))).scalars().all()
        query = query.where(RiskAssessmentReport.enterprise_id.in_(user_ent_ids))
    rows = (await db.execute(query.order_by(RiskAssessmentReport.created_at.desc()).limit(20))).scalars().all()
    return {"assessments": [{"id": r.id, "enterprise_id": r.enterprise_id, "status": r.status, "created_at": str(r.created_at)} for r in rows]}


async def _get_risk_assessment(db, user, args):
    from app.models.risk_assessment import RiskAssessmentReport
    report_id = args.get("report_id", "")
    if not report_id:
        return {"error": "请提供 report_id"}
    r = (await db.execute(select(RiskAssessmentReport).where(RiskAssessmentReport.id == report_id))).scalar_one_or_none()
    if not r:
        return {"error": "报告不存在"}
    return {"id": r.id, "enterprise_id": r.enterprise_id, "status": r.status, "content": r.content[:3000] if r.content else "", "created_at": str(r.created_at)}


# ── 应急资源调查报告 ──

async def _list_resource_investigations(db, user, args):
    from app.models.resource_investigation import ResourceInvestigationReport
    ent_id = args.get("enterprise_id", "")
    query = select(ResourceInvestigationReport)
    if ent_id:
        query = query.where(ResourceInvestigationReport.enterprise_id == ent_id)
    else:
        user_ent_ids = (await db.execute(select(Enterprise.id).where(Enterprise.user_id == user.id))).scalars().all()
        query = query.where(ResourceInvestigationReport.enterprise_id.in_(user_ent_ids))
    rows = (await db.execute(query.order_by(ResourceInvestigationReport.created_at.desc()).limit(20))).scalars().all()
    return {"investigations": [{"id": r.id, "enterprise_id": r.enterprise_id, "status": r.status, "created_at": str(r.created_at)} for r in rows]}


async def _get_resource_investigation(db, user, args):
    from app.models.resource_investigation import ResourceInvestigationReport
    report_id = args.get("report_id", "")
    if not report_id:
        return {"error": "请提供 report_id"}
    r = (await db.execute(select(ResourceInvestigationReport).where(ResourceInvestigationReport.id == report_id))).scalar_one_or_none()
    if not r:
        return {"error": "报告不存在"}
    return {"id": r.id, "enterprise_id": r.enterprise_id, "status": r.status, "content": r.content[:3000] if r.content else "", "created_at": str(r.created_at)}


# ── 法规库（内存图谱）──

async def _get_regulation_stats(db, user, args):
    """法规库统计：总数、现行数、废止数、已索引条数"""
    from app.regulations import get_graph, get_vector_store
    graph = get_graph()
    s = graph.stats()
    vs = get_vector_store()
    s["indexed_articles"] = vs.collection_count() if vs else 0
    return s


async def _list_regulations(db, user, args):
    """法规列表（从内存图谱读取）"""
    from app.regulations import get_graph
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
    from app.regulations import get_vector_store, get_graph
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

async def _search_regulation_articles(db, user, args):
    """法规条文检索 -- 图谱关键词搜索 + 文件加载原文。供聊天助手回答法规问题时使用。

    流程: graph.list_nodes(keyword=query) -> 加载 texts/*.md 条文 -> 关键词子串匹配。
    """
    query = args.get("query", "")
    if not query:
        return {"error": "请提供 query"}

    top_k = _parse_int(args.get("top_k", 8)) or 8
    top_k = max(3, min(top_k, 15))

    from app.regulations import get_graph
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
        return {"articles": [], "count": 0, "message": "法规库中暂未找到与您问题直接相关的法规。"}

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

            if not article_text or len(article_text) < 10:
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
            "message": "法规库中暂未找到与该问题直接相关的条文。以下是与关键词匹配的法规列表供参考：",
            "matched_regulations": [
                {"id": n.get("id"), "full_name": n.get("full_name", n.get("title", "")),
                 "code": n.get("code", "")}
                for n in nodes[:5]
            ],
        }

    return {"articles": articles, "count": len(articles)}

# ── AI 配置 ──

async def _get_ai_config(db, user, args):
    cfg = (await db.execute(select(AIConfigModel).where(AIConfigModel.user_id == user.id))).scalar_one_or_none()
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
    import os
    from app.routers.export import generate_plan_docx as do_export
    export_dir = os.environ.get("EXPORT_DIR", "/app/exports")
    os.makedirs(export_dir, exist_ok=True)
    try:
        filepath = await do_export(p.id, db)
        return {"message": "导出成功", "filename": os.path.basename(filepath), "verified": True}
    except Exception as e:
        return {"error": f"导出失败: {str(e)}"}


# ── 图文报告生成 ──

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
    """触发 AI 批量生成预案所有空章节。返回触发状态，由前端生成页执行实际生成。"""
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "请提供 plan_id"}
    p = (await db.execute(
        select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id)
    )).scalar_one_or_none()
    if not p:
        return {"error": "预案不存在"}
    if p.status == "generating":
        return {"message": "预案正在生成中，请稍候", "status": "generating", "verified": True}

    empty_sections = [s for s in (p.sections or []) if not s.content or not s.content.strip()]
    total = len(p.sections or [])
    if not empty_sections:
        return {"message": f"预案「{p.title}」共{total}个章节，均已填写完成", "verified": True}

    # 标记为 generating，前端会自动检测并触发实际生成 API
    p.status = "generating"
    await db.commit()

    return {
        "message": f"预案「{p.title}」共{total}个章节，{len(empty_sections)}个空章节已标记为生成中状态。请在前端预案编辑页点击「批量生成」按钮触发实际AI生成，或在本对话中回复「确定开始生成」继续。",
        "plan_id": plan_id,
        "status": "generating",
        "total_sections": total,
        "empty_count": len(empty_sections),
        "verified": True,
        "action_required": "请在前端页面点击「批量生成」按钮，或回复「确定开始生成」开始AI内容生成",
    }



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
    "create_risk_source": _create_risk_source,
    "update_risk_source": _update_risk_source,
    "delete_risk_source": _delete_risk_source,
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
}
