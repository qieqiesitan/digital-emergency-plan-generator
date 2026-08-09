"""企业数据完成度聚合（6 模块加权）与资料 LLM 提取/模块识别。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enterprise import Enterprise, EmergencyResource
from app.models.risk_management import RiskEvent, RiskObject, RiskUnit
from app.models.hazardous_chemicals import HazardousChemical
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport
from app.services.ai_config_service import get_system_ai_config
from app.services.llm_client import llm_text_completion
from app.services.risk_ai_service import _parse_ai_json

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


async def compute_completion(
    enterprise_id: str, db: AsyncSession, enterprise: Enterprise | None = None
) -> dict:
    """返回 {percent, modules: [{key,label,weight,done}]}。"""
    ent = enterprise
    if ent is None:
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
        if not isinstance(group, dict):
            continue
        for member in group.get("members") or []:
            if not isinstance(member, dict):
                continue
            role = str(member.get("role", "") or "")
            if member.get("name") and ("总指挥" in role or role == "chief" or role == "commander"):
                return True
    return False


MODULE_SCHEMA_HINTS = {
    "enterprise_info": "企业名称/统一社会信用代码/法定代表人/地址/行业/经营范围/员工人数等",
    "org_structure": "应急指挥部/总指挥/副总指挥/应急小组及组长成员（姓名电话留空由用户填）",
    "risk_chemical": "风险区域/对象/单元/事件（事故类型、风险等级、触发条件、后果）与危险化学品（名称/CAS/闪点/储量）",
    "resources": "应急物资（类别/名称/规格/数量/位置/责任人）与外部救援力量（单位/距离/电话）",
    "surrounding": "周边单位与敏感目标（名称/方位/距离/类型/主要风险）",
}


async def extract_candidates(module: str, text: str, db) -> list[dict]:
    """按模块 schema 从文本提取候选。返回候选 list[dict]。"""
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise ValueError("系统未配置 AI 模型，请联系管理员")
    hint = MODULE_SCHEMA_HINTS.get(module, "")
    prompt = (
        "你是企业应急预案数据提取助手。请从以下资料中提取结构化数据。\n"
        f"提取目标（模块：{module}）：{hint}\n"
        "要求：只提取资料中明确出现的信息，不得编造；姓名/电话如无明确内容则留空。\n"
        "输出严格 JSON：{\"items\": [...]}，不要输出其他文字。\n\n"
        f"资料内容：\n{text[:12000]}"
    )
    raw = await llm_text_completion(
        [{"role": "system", "content": "你是结构化数据提取器，只输出 JSON。"},
         {"role": "user", "content": prompt}],
        ai_config,
    )
    parsed = _parse_ai_json(raw)
    return parsed.get("items", [])


async def classify_modules(text: str, db) -> list[str]:
    """判断资料文本属于哪些模块，返回模块 key 列表。"""
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise ValueError("系统未配置 AI 模型，请联系管理员")
    known = "、".join(MODULE_SCHEMA_HINTS.keys())
    prompt = (
        "判断以下企业资料属于哪些数据模块。可选模块：" + known + "。\n"
        "输出严格 JSON：{\"modules\": [\"module_key\", ...]}，只输出 JSON。\n\n"
        f"资料内容：\n{text[:12000]}"
    )
    raw = await llm_text_completion(
        [{"role": "system", "content": "你是企业资料分类器，只输出 JSON。"},
         {"role": "user", "content": prompt}],
        ai_config,
    )
    parsed = _parse_ai_json(raw)
    return [m for m in parsed.get("modules", []) if m in MODULE_SCHEMA_HINTS]
