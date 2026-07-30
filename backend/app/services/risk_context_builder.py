"""风险分级管控上下文构建器。

替代旧的 build_risk_assessment_context()，从新的五层表结构构建
结构化的风险数据上下文，供 AI 报告生成和预案生成使用。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent


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
            selectinload(RiskZone.objects)
            .selectinload(RiskObject.units)
            .selectinload(RiskUnit.events)
            .selectinload(RiskEvent.measures)
        )
        .order_by(RiskZone.sort_order)
    )
    zones = zones_result.scalars().all()

    # 构建层级化 risk_sources 列表
    risk_sources_list = []

    for zone in zones:
        for obj in zone.objects:
            # 对象下直接挂载的事件（无单元场景，如"消防泵房"直接关联"设备故障"）
            for event in obj.events:
                risk_sources_list.append({
                    "zone": zone.name,
                    "object": obj.name,
                    "unit": None,
                    "accident_type": event.accident_type,
                    "risk_level": event.risk_level,
                    "risk_score": event.risk_score,
                    "description": event.description,
                    "triggers": event.trigger_conditions,
                    "consequences": event.consequences,
                    "measures": [
                        {
                            "category": m.measure_category,
                            "description": m.description,
                        }
                        for m in event.measures
                    ],
                })

            # 单元下挂载的事件（标准场景，如"1号储罐 → 罐体 → 储罐泄漏"）
            for unit in obj.units:
                for event in unit.events:
                    risk_sources_list.append({
                        "zone": zone.name,
                        "object": obj.name,
                        "unit": unit.name,
                        "accident_type": event.accident_type,
                        "risk_level": event.risk_level,
                        "risk_score": event.risk_score,
                        "description": event.description,
                        "triggers": event.trigger_conditions,
                        "consequences": event.consequences,
                        "measures": [
                            {
                                "category": m.measure_category,
                                "description": m.description,
                            }
                            for m in event.measures
                        ],
                    })

    # 计算总事件数
    total_events = sum(
        len(obj.events) + sum(len(u.events) for u in obj.units)
        for zone in zones
        for obj in zone.objects
    )

    return {
        "enterprise": {
            "name": ent.name,
            "industry": ent.industry,
            "address": ent.address,
            "employee_count": ent.employee_count,
            "business_scope": ent.business_scope,
            "building_overview": ent.building_overview,
            "surrounding_info": ent.surrounding_info,
            "fire_protection_summary": ent.fire_protection_summary,
            "special_equipment_detail": ent.special_equipment_detail,
            "main_equipment_list": ent.main_equipment_list,
            "natural_conditions": ent.natural_conditions,
            "hazardous_chemicals": ent.hazardous_chemicals,
        },
        "risk_sources": risk_sources_list,
        "zone_count": len(zones),
        "total_events": total_events,
    }
