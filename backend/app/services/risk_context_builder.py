"""风险分级管控上下文构建器。替代旧的 build_risk_assessment_context()，消费新的五层表结构。"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent

async def build_risk_management_context(enterprise_id: str, db: AsyncSession) -> dict:
    ent_result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))
    ent = ent_result.scalar_one_or_none()
    if not ent: raise ValueError("企业不存在")
    zones_result = await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == enterprise_id)
        .options(selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures))
        .order_by(RiskZone.sort_order)
    )
    zones = zones_result.scalars().all()
    risk_sources_list = []
    for zone in zones:
        for obj in zone.objects:
            for event in obj.events:
                risk_sources_list.append({"zone":zone.name,"object":obj.name,"unit":None,"accident_type":event.accident_type,"risk_level":event.risk_level,"risk_score":event.risk_score,"description":event.description,"triggers":event.trigger_conditions,"consequences":event.consequences,"measures":[{"category":m.measure_category,"description":m.description} for m in event.measures]})
            for unit in obj.units:
                for event in unit.events:
                    risk_sources_list.append({"zone":zone.name,"object":obj.name,"unit":unit.name,"accident_type":event.accident_type,"risk_level":event.risk_level,"risk_score":event.risk_score,"description":event.description,"triggers":event.trigger_conditions,"consequences":event.consequences,"measures":[{"category":m.measure_category,"description":m.description} for m in event.measures]})
    return {
        "enterprise":{"name":ent.name,"industry":ent.industry,"address":ent.address,"employee_count":ent.employee_count,"business_scope":ent.business_scope,"building_overview":ent.building_overview,"surrounding_info":ent.surrounding_info,"fire_protection_summary":ent.fire_protection_summary,"special_equipment_detail":ent.special_equipment_detail,"main_equipment_list":ent.main_equipment_list,"natural_conditions":ent.natural_conditions,"hazardous_chemicals":ent.hazardous_chemicals},
        "risk_sources": risk_sources_list,
        "zone_count": len(zones),
        "total_events": sum(len(obj.events)+sum(len(u.events) for u in obj.units) for zone in zones for obj in zone.objects),
    }
