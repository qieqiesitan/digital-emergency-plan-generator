"""风险分级管控上下文构建器。

替代旧的 build_risk_assessment_context()，从新的五层表结构构建
结构化的风险数据上下文，供 AI 报告生成和预案生成使用。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent


def _risk_source_item(zone: RiskZone, obj: RiskObject, unit: RiskUnit | None, event: RiskEvent) -> dict:
    params = event.method_params or {}
    measures = [
        {
            "category": m.measure_category,
            "measure_type": getattr(m, "measure_type", None),
            "description": m.description,
            "responsible_person": getattr(m, "responsible_person", None),
            "deadline": str(m.deadline) if getattr(m, "deadline", None) else None,
            "check_items": getattr(m, "check_items", None) or [],
            "status": getattr(m, "status", None),
        }
        for m in event.measures
    ]
    return {
        "zone": zone.name,
        "object": obj.name,
        "unit": unit.name if unit else None,
        "name": obj.name,
        "categories": obj.category or "",
        "location": obj.location or "",
        "accident_type": event.accident_type,
        "risk_level": event.risk_level,
        "risk_score": event.risk_score,
        "description": event.description,
        "triggers": event.trigger_conditions,
        "consequences": event.consequences,
        "chemical_id": event.chemical_id,
        "inherent_risk_level": getattr(event, "inherent_risk_level", None),
        "inherent_risk_score": getattr(event, "inherent_risk_score", None),
        "control_level": getattr(event, "control_level", None),
        "likelihood": params.get("l", 3),
        "severity": params.get("s", 3),
        "control_measures": "；".join(m["description"] for m in measures),
        "measures": measures,
    }


def _sort_key(item) -> tuple:
    """稳定排序键：sort_order → created_at → id（缺失字段退化为空值）。"""
    return (
        getattr(item, "sort_order", 0) or 0,
        str(getattr(item, "created_at", "") or ""),
        str(getattr(item, "id", "") or ""),
    )


def build_risk_sources(zones) -> list[dict]:
    """按 分区→对象→单元→事件 稳定展开风险源清单。"""
    ordered: list[dict] = []
    for zone in sorted(zones or [], key=_sort_key):
        for obj in sorted(getattr(zone, "objects", []) or [], key=_sort_key):
            for event in sorted(getattr(obj, "events", []) or [], key=_sort_key):
                ordered.append(_risk_source_item(zone, obj, None, event))
            for unit in sorted(getattr(obj, "units", []) or [], key=_sort_key):
                for event in sorted(getattr(unit, "events", []) or [], key=_sort_key):
                    ordered.append(_risk_source_item(zone, obj, unit, event))
    return ordered


async def build_risk_management_context(enterprise_id: str, db: AsyncSession) -> dict:
    """从五层表构建企业风险管控上下文。

    遍历 zones → objects → (objects.events + objects.units → units.events → events.measures)，
    构建与旧 build_risk_assessment_context 兼容的返回结构。

    Args:
        enterprise_id: 企业 UUID
        db: 数据库异步会话

    Returns:
        dict: {
            enterprise: 企业基本信息,
            risk_sources: 层级化风险源列表 (含 zone/object/unit/accident_type/risk_level/measures),
            zone_count: 分区数,
            total_events: 总事件数
        }

    Raises:
        ValueError: 企业不存在
    """
    # 获取企业信息
    ent_result = await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id)
    )
    ent = ent_result.scalar_one_or_none()
    if not ent:
        raise ValueError("企业不存在")

    # 获取完整层级树（selectin 预加载避免 N+1 查询）
    zones_result = await db.execute(
        select(RiskZone)
        .where(RiskZone.enterprise_id == enterprise_id)
        .options(
            selectinload(RiskZone.floor),
            selectinload(RiskZone.objects)
            .selectinload(RiskObject.units)
            .selectinload(RiskUnit.events)
            .selectinload(RiskEvent.measures)
        )
        .order_by(RiskZone.sort_order, RiskZone.created_at, RiskZone.id)
    )
    zones = zones_result.scalars().all()

    # 构建层级化 risk_sources 列表（分区→对象→单元→事件，稳定排序）
    zones = sorted(zones, key=_sort_key)
    risk_sources_list = build_risk_sources(zones)

    # 计算总事件数
    total_events = len(risk_sources_list)

    # 从分区推导企业楼层列表（zones 的 floor 关系已 selectin 预加载；
    # 无分区楼层可空，供疏散图按楼层分组使用）
    floors = []
    _seen_floor_ids = set()
    for zone in zones:
        fid = getattr(zone, "floor_id", None)
        if not fid or fid in _seen_floor_ids:
            continue
        _seen_floor_ids.add(fid)
        fl = getattr(zone, "floor", None)
        floors.append({
            "id": fid,
            "name": (getattr(fl, "name", None) or zone.name),
            "floor_plan_url": getattr(fl, "floor_plan_url", None),
            "sort_order": getattr(fl, "sort_order", 0),
            "is_default": getattr(fl, "is_default", False),
        })

    return {
        "enterprise": {
            "name": ent.name,
            "industry": ent.industry,
            "address": ent.address,
            "employee_count": ent.employee_count,
            "business_scope": ent.business_scope,
            "building_overview": ent.building_overview,
            "surrounding_info": ent.surrounding_info,
            "legal_representative": ent.legal_representative,
            "credit_code": ent.credit_code,
            "economic_type": ent.economic_type,
            "established_date": str(ent.established_date) if ent.established_date else None,
            "registered_capital": ent.registered_capital,
            "phone": ent.phone,
            "land_area": ent.land_area,
            "building_area": ent.building_area,
            "safety_officer": ent.safety_officer,
            "safety_standardization": ent.safety_standardization,
            "fire_approval": ent.fire_approval,
            "main_products": ent.main_products,
            "hazardous_chemicals": ent.hazardous_chemicals,
            "special_equipment": ent.special_equipment,
            "fire_protection_summary": ent.fire_protection_summary,
            "special_equipment_detail": ent.special_equipment_detail,
            "main_equipment_list": ent.main_equipment_list,
            "natural_conditions": ent.natural_conditions,
        },
        "risk_sources": risk_sources_list,
        "zone_count": len(zones),
        "total_events": total_events,
        "risk_events": [
            {
                "name": event.accident_type or (event.description or "")[:20] or "未命名风险",
                "likelihood": event.method_params.get("l", 3) if event.method_params else 3,
                "severity": event.method_params.get("s", 3) if event.method_params else 3,
                "risk_level": event.risk_level or "",
            }
            for zone in zones
            for obj in zone.objects
            for event in list(obj.events) + [e for u in obj.units for e in u.events]
        ],
        "zones": [
            {
                "name": zone.name,
                "polygon": zone.floor_plan_polygon,
                "floor_id": getattr(zone, "floor_id", None),
                "floor_name": getattr(getattr(zone, "floor", None), "name", None),
                "floor_plan_url": getattr(getattr(zone, "floor", None), "floor_plan_url", None),
            }
            for zone in zones
        ],
        "risk_objects": [
            {
                "name": obj.name,
                "location_x": obj.location_x,
                "location_y": obj.location_y,
                "floor_id": getattr(obj, "floor_id", None) or getattr(zone, "floor_id", None),
            }
            for zone in zones
            for obj in zone.objects
        ],
        "floors": floors,
    }
