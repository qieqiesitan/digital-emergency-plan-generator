"""企业数据完成度聚合（6 模块加权）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enterprise import Enterprise, EmergencyResource
from app.models.risk_management import RiskEvent, RiskObject, RiskUnit
from app.models.hazardous_chemicals import HazardousChemical
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport

MODULE_WEIGHTS = {
    "enterprise_info": 10,
    "org_structure": 15,
    "risk_chemical": 30,
    "resources": 15,
    "surrounding": 10,
    "reports": 20,
}

MODULE_LABELS = {
    "enterprise_info": "企业信息",
    "org_structure": "组织架构",
    "risk_chemical": "风险与危化品",
    "resources": "应急资源",
    "surrounding": "周边环境",
    "reports": "报告",
}


async def compute_completion(enterprise_id: str, db: AsyncSession) -> dict:
    """返回 {percent, modules: [{key,label,weight,done}]}。"""
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        raise ValueError("企业不存在")

    done = {}
    done["enterprise_info"] = bool(ent.name and ent.address and ent.industry)
    done["org_structure"] = _org_done(ent.org_structure)

    # RiskEvent 无 enterprise_id 列，经 RiskObject 归属企业（object 级 + unit 级）
    object_events = (await db.execute(
        select(RiskEvent).join(RiskObject, RiskEvent.object_id == RiskObject.id)
        .where(RiskObject.enterprise_id == enterprise_id)
    )).scalars().all()
    unit_events = (await db.execute(
        select(RiskEvent).join(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
        .join(RiskObject, RiskUnit.object_id == RiskObject.id)
        .where(RiskObject.enterprise_id == enterprise_id)
    )).scalars().all()
    # 事件要么挂 object 要么挂 unit，dict 去重防重复计数
    events = list(dict.fromkeys([*object_events, *unit_events]))
    chemicals = (await db.execute(select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id))).scalars().all()
    linked = any(e.chemical_id for e in events)
    done["risk_chemical"] = bool(events) or (bool(chemicals) and linked)

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == enterprise_id))).scalars().all()
    done["resources"] = bool(resources)

    surrounding = ent.surrounding_info or {}
    done["surrounding"] = bool(surrounding.get("nearby_units")) or bool(surrounding.get("sensitive_targets"))

    ra = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id,
        RiskAssessmentReport.status == "completed",
    ))).scalars().all()
    ri = (await db.execute(select(ResourceInvestigationReport).where(
        ResourceInvestigationReport.enterprise_id == enterprise_id,
        ResourceInvestigationReport.status == "completed",
    ))).scalars().all()
    done["reports"] = bool(ra) and bool(ri)

    total = 0
    modules = []
    for key, weight in MODULE_WEIGHTS.items():
        d = done[key]
        if d:
            total += weight
        modules.append({"key": key, "label": MODULE_LABELS[key], "weight": weight, "done": d})
    return {"percent": total, "modules": modules}


def _org_done(org_structure: list | None) -> bool:
    for group in org_structure or []:
        for member in group.get("members", []):
            role = str(member.get("role", "") or "")
            if member.get("name") and ("总指挥" in role or role == "chief" or role == "commander"):
                return True
    return False
