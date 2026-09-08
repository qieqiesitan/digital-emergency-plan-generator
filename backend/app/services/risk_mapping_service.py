from typing import Any
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.enterprise import Enterprise, EnterpriseFloor

LEVEL_ORDER = {"未评估": 0, "低": 1, "一般": 2, "较大": 3, "重大": 4}
LEVEL_COLORS = {
    "重大": "#ff4d4f",
    "较大": "#fa8c16",
    "一般": "#fadb14",
    "低": "#52c41a",
    "未评估": "#d9d9d9",
}
LEVEL_COLORS_REVERSE = {v.lower(): k for k, v in LEVEL_COLORS.items() if k != "未评估"}


def normalize_polygon(raw: dict | None, zone_name: str = "") -> dict | None:
    if not raw:
        return None
    if raw.get("version") != 2:
        points = raw.get("points") or []
        return {
            "version": 2,
            "level_mode": "auto",
            "risk_level": None,
            "polygons": [{
                "id": raw.get("id") or "legacy-polygon",
                "label": raw.get("label") or zone_name,
                "points": points,
            }],
        }
    data = dict(raw)
    if "color_source" in data:
        level = None
        if data.get("color_source") == "manual" and data.get("color"):
            level = LEVEL_COLORS_REVERSE.get(str(data["color"]).lower())
        data["level_mode"] = "manual" if level else "auto"
        data["risk_level"] = level
        data.pop("color_source", None)
        data.pop("color", None)
    else:
        data.setdefault("level_mode", "auto")
        data.setdefault("risk_level", None)
    if data["level_mode"] == "auto":
        data["risk_level"] = None
    return data


def validate_polygon_v2(polygon: dict | None) -> list[str]:
    """防御性校验 v2 多边形结构，畸形输入一律返回错误列表而非抛异常。"""
    errors: list[str] = []
    if not polygon:
        return ["floor_plan_polygon 不能为空"]
    if not isinstance(polygon, dict):
        errors.append("floor_plan_polygon 必须为对象")
        return errors
    if "color_source" in polygon:
        polygon = normalize_polygon(polygon) or polygon
    if polygon.get("version") != 2:
        errors.append("version 必须为 2")
    if polygon.get("level_mode") not in ("auto", "manual"):
        errors.append("level_mode 必须为 auto 或 manual")
    elif polygon.get("level_mode") == "manual":
        if polygon.get("risk_level") not in LEVEL_COLORS or polygon.get("risk_level") == "未评估":
            errors.append("manual 模式必须指定 risk_level（重大/较大/一般/低）")
    elif polygon.get("risk_level") is not None:
        errors.append("auto 模式不允许携带 risk_level")
    polygons = polygon.get("polygons")
    if not isinstance(polygons, list):
        errors.append("polygons 必须为非空数组")
        return errors
    if not polygons:
        errors.append("polygons 不能为空")
        return errors
    ids = []
    for p in polygons:
        if not isinstance(p, dict):
            errors.append("区域必须是对象")
            continue
        pts = p.get("points")
        if not isinstance(pts, list):
            errors.append("每个区域至少 3 个顶点")
            continue
        if len(pts) < 3:
            errors.append("每个区域至少 3 个顶点")
        for pt in pts:
            if not isinstance(pt, dict):
                errors.append("坐标必须是数值")
                continue
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
    if data:
        normalized = normalize_polygon(dict(data)) or {}
        if normalized.get("level_mode") == "manual" and normalized.get("risk_level") in LEVEL_COLORS_REVERSE.values():
            return LEVEL_COLORS[normalized["risk_level"]]
    return LEVEL_COLORS.get(max_level or "未评估", "#d9d9d9")


def max_risk_level(zone: RiskZone, mode: str = "current") -> str:
    level = "未评估"
    for obj in zone.objects:
        for ev in obj.events:
            value = ev.inherent_risk_level if mode == "inherent" else ev.risk_level
            if value and LEVEL_ORDER.get(value, 0) > LEVEL_ORDER.get(level, 0):
                level = value
        for unit in obj.units:
            for ev in unit.events:
                value = ev.inherent_risk_level if mode == "inherent" else ev.risk_level
                if value and LEVEL_ORDER.get(value, 0) > LEVEL_ORDER.get(level, 0):
                    level = value
    return level


async def ensure_default_floor(db: AsyncSession, enterprise_id: str) -> EnterpriseFloor:
    floor = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id, EnterpriseFloor.is_default.is_(True))
    )).scalar_one_or_none()
    if floor:
        return floor
    enterprise = await db.get(Enterprise, enterprise_id)
    floor = EnterpriseFloor(
        enterprise_id=enterprise_id,
        name="默认总图",
        sort_order=0,
        floor_plan_url=enterprise.floor_plan_url if enterprise else None,
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
