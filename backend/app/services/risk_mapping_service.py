from typing import Any
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.enterprise import EnterpriseFloor

LEVEL_ORDER = {"未评估": 0, "低": 1, "一般": 2, "较大": 3, "重大": 4}
LEVEL_COLORS = {
    "重大": "#ff4d4f",
    "较大": "#fa8c16",
    "一般": "#fadb14",
    "低": "#52c41a",
    "未评估": "#d9d9d9",
}


def normalize_polygon(raw: dict | None, zone_name: str = "") -> dict | None:
    if not raw:
        return None
    if raw.get("version") == 2:
        return raw
    points = raw.get("points") or []
    return {
        "version": 2,
        "color_source": "auto",
        "color": None,
        "polygons": [{
            "id": raw.get("id") or "legacy-polygon",
            "label": raw.get("label") or zone_name,
            "points": points,
        }],
    }


def validate_polygon_v2(polygon: dict | None) -> list[str]:
    errors: list[str] = []
    if not polygon:
        return ["floor_plan_polygon 不能为空"]
    if polygon.get("version") != 2:
        errors.append("version 必须为 2")
    if polygon.get("color_source") not in ("auto", "manual"):
        errors.append("color_source 必须为 auto 或 manual")
    if polygon.get("color_source") == "manual" and not isinstance(polygon.get("color"), str):
        errors.append("manual 模式必须提供 color")
    polygons = polygon.get("polygons") or []
    if not isinstance(polygons, list) or not polygons:
        errors.append("polygons 不能为空")
    ids = []
    for p in polygons:
        pts = p.get("points") or []
        if len(pts) < 3:
            errors.append("每个区域至少 3 个顶点")
        for pt in pts:
            if not isinstance(pt.get("x"), (int, float)) or not isinstance(pt.get("y"), (int, float)):
                errors.append("坐标必须是数值")
            elif not (0 <= pt["x"] <= 100 and 0 <= pt["y"] <= 100):
                errors.append("坐标必须在 0-100 范围内")
        ids.append(p.get("id"))
    if len(ids) != len(set(ids)):
        errors.append("polygons.id 不能重复")
    return errors


def effective_color(polygon: dict | Any | None, max_level: str | None) -> str:
    data = polygon.model_dump() if polygon and hasattr(polygon, "model_dump") else polygon
    if data and data.get("color_source") == "manual":
        return data.get("color") or LEVEL_COLORS.get(max_level or "未评估") or "#d9d9d9"
    return LEVEL_COLORS.get(max_level or "未评估", "#d9d9d9")


def max_risk_level(zone: RiskZone) -> str:
    level = "未评估"
    for obj in zone.objects:
        for ev in obj.events:
            if ev.risk_level and LEVEL_ORDER.get(ev.risk_level, 0) > LEVEL_ORDER.get(level, 0):
                level = ev.risk_level
        for unit in obj.units:
            for ev in unit.events:
                if ev.risk_level and LEVEL_ORDER.get(ev.risk_level, 0) > LEVEL_ORDER.get(level, 0):
                    level = ev.risk_level
    return level


async def ensure_default_floor(db: AsyncSession, enterprise_id: str) -> EnterpriseFloor:
    floor = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.is_default.is_(True))
    )).scalar_one_or_none()
    if floor:
        return floor
    floor = EnterpriseFloor(
        enterprise_id=enterprise_id,
        name="默认总图",
        sort_order=0,
        floor_plan_url=None,
        is_default=True,
    )
    db.add(floor)
    await db.flush()
    return floor


async def cascade_counts(db: AsyncSession, zone_id: str) -> dict[str, int]:
    object_ids = (await db.execute(select(RiskObject.id).where(RiskObject.zone_id == zone_id))).scalars().all()
    object_count = len(object_ids)
    unit_count = 0
    event_count = 0
    measure_count = 0
    if object_ids:
        unit_ids = (await db.execute(select(RiskUnit.id).where(RiskUnit.object_id.in_(object_ids)))).scalars().all()
        unit_count = len(unit_ids)
        event_filters = [RiskEvent.object_id.in_(object_ids)]
        if unit_ids:
            event_filters.append(RiskEvent.unit_id.in_(unit_ids))
        event_ids = (await db.execute(select(RiskEvent.id).where(or_(*event_filters)))).scalars().all()
        event_count = len(event_ids)
        if event_ids:
            measure_count = (await db.execute(select(func.count(RiskMeasure.id)).where(RiskMeasure.event_id.in_(event_ids)))).scalar() or 0
    return {
        "object_count": object_count,
        "unit_count": unit_count,
        "event_count": event_count,
        "measure_count": measure_count,
    }
