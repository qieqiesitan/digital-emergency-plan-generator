"""企业驾驶舱汇总服务。"""
from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.hazard_management import HazardRecord
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport
from app.models.risk_management import RiskEvent, RiskObject, RiskUnit, RiskZone
from app.services.onboarding_service import compute_completion

LEVEL_KEY = {"重大": "major", "较大": "larger", "一般": "general", "低": "low"}


def _classify_level(level: str | None) -> str:
    """归一化风险等级；缺失/未知按『一般』处理。"""
    return LEVEL_KEY.get(level, "general")


def _risk_index(counts: dict) -> int:
    """综合风险指数 0-100：事件平均严重度加权归一。"""
    total = counts.get("total") or (
        counts["major"] + counts["larger"] + counts["general"] + counts["low"]
    )
    if total <= 0:
        return 0
    weighted = (
        counts["major"] * 100
        + counts["larger"] * 70
        + counts["general"] * 40
        + counts["low"] * 10
    )
    return min(100, round(weighted / total))


def _event_zone_name(e: RiskEvent) -> str:
    zone = getattr(getattr(e, "object", None), "zone", None)
    if zone is None:
        unit = getattr(e, "unit", None)
        zone = getattr(getattr(unit, "object", None), "zone", None)
    return zone.name if zone else "未分区"


def _event_object(e: RiskEvent):
    obj = getattr(e, "object", None)
    if obj is None and getattr(e, "unit", None) is not None:
        obj = getattr(e.unit, "object", None)
    return obj


def _event_level(e: RiskEvent) -> str:
    return e.risk_level or "一般"


def _parse_score(raw: str | None) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def aggregate_events(events: list) -> dict:
    """纯函数：由事件列表聚合出等级分布/分区分布/TOP/风险指数。"""
    counts = {"major": 0, "larger": 0, "general": 0, "low": 0, "total": 0}
    zone_map: dict[str, dict] = {}
    object_map: dict[str, dict] = {}

    for e in events:
        key = _classify_level(_event_level(e))
        counts[key] += 1
        counts["total"] += 1

        zname = _event_zone_name(e)
        zone = zone_map.setdefault(
            zname, {"zone_name": zname, "counts": {"major": 0, "larger": 0, "general": 0, "low": 0}, "total": 0}
        )
        zone["counts"][key] += 1
        zone["total"] += 1

        obj = _event_object(e)
        oname = obj.name if obj else "未命名风险点"
        score = _parse_score(e.risk_score) or 0.0
        entry = object_map.get(oname)
        if entry is None or score > (entry.get("score") or 0):
            object_map[oname] = {
                "name": oname,
                "level": _event_level(e),
                "score": score,
                "responsible_unit": getattr(obj, "responsible_unit", None) if obj else None,
            }

    top_risks = sorted(object_map.values(), key=lambda x: x["score"] or 0, reverse=True)[:3]
    zone_risks = sorted(zone_map.values(), key=lambda z: z["total"], reverse=True)
    return {
        "risk_counts": counts,
        "zone_risks": zone_risks,
        "top_risks": top_risks,
        "risk_index": _risk_index(counts),
    }


def derive_todos(
    reports: dict,
    open_hazard_count: int,
    due_hazard_count: int,
    overdue_hazard_count: int,
    completion_modules: list,
) -> list[dict]:
    """纯函数：由报告/隐患/完成度信号派生待办（最多 3 条）。"""
    todos: list[dict] = []
    if not reports.get("assessment"):
        todos.append({"priority": "high", "title": "风险评估报告未生成", "note": "建议本周完成 · AI 可辅助生成"})
    if not reports.get("investigation"):
        todos.append({"priority": "medium", "title": "应急资源调查报告未生成", "note": "建议本周完成 · AI 可辅助生成"})
    if overdue_hazard_count > 0:
        todos.append({"priority": "high", "title": f"{overdue_hazard_count} 条隐患整改已逾期", "note": "请尽快安排整改闭环"})
    elif due_hazard_count > 0:
        todos.append({"priority": "medium", "title": f"{due_hazard_count} 条隐患整改即将到期", "note": "3 天内到期，请关注"})
    elif open_hazard_count > 0:
        todos.append({"priority": "low", "title": f"{open_hazard_count} 条隐患正在整改中", "note": "整改闭环后自动归档"})

    missing = {m["key"]: m["label"] for m in completion_modules if not m["done"]}
    if "surrounding" in missing:
        todos.append({"priority": "low", "title": "周边环境数据未更新", "note": "可用高德地图一键获取"})
    return todos[:3]


async def _fetch_events(db: AsyncSession, enterprise_id: str) -> list[RiskEvent]:
    rows = await db.execute(
        select(RiskEvent)
        .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
        .join(
            RiskObject,
            (RiskEvent.object_id == RiskObject.id) | (RiskUnit.object_id == RiskObject.id),
        )
        .join(RiskZone, RiskObject.zone_id == RiskZone.id)
        .where(RiskZone.enterprise_id == enterprise_id)
    )
    return list(dict.fromkeys(rows.scalars().all()))


async def build_cockpit_summary(
    db: AsyncSession, enterprise_id: str, enterprise: Enterprise | None = None
) -> dict:
    ent = enterprise
    if ent is None:
        ent = (
            await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))
        ).scalar_one_or_none()
    if not ent:
        raise ValueError("企业不存在")

    events = await _fetch_events(db, enterprise_id)
    aggregated = aggregate_events(events)

    completion = await compute_completion(enterprise_id, db, enterprise=ent)
    completion_payload = {
        "percent": completion["percent"],
        "modules": [
            {"key": m["key"], "label": m["label"], "done": m["done"]}
            for m in completion["modules"]
        ],
    }

    ra_done = bool(
        (
            await db.execute(
                select(func.count()).select_from(RiskAssessmentReport).where(
                    RiskAssessmentReport.enterprise_id == enterprise_id,
                    RiskAssessmentReport.status == "completed",
                )
            )
        ).scalar()
    )
    ri_done = bool(
        (
            await db.execute(
                select(func.count()).select_from(ResourceInvestigationReport).where(
                    ResourceInvestigationReport.enterprise_id == enterprise_id,
                    ResourceInvestigationReport.status == "completed",
                )
            )
        ).scalar()
    )

    today = date.today()
    open_hazards = (
        await db.execute(
            select(HazardRecord).where(
                HazardRecord.enterprise_id == enterprise_id,
                HazardRecord.status != "closed",
            )
        )
    ).scalars().all()
    due = [h for h in open_hazards if h.deadline and h.deadline <= today + timedelta(days=3)]
    overdue = [h for h in open_hazards if h.deadline and h.deadline < today]

    todos = derive_todos(
        reports={"assessment": ra_done, "investigation": ri_done},
        open_hazard_count=len(open_hazards),
        due_hazard_count=len(due),
        overdue_hazard_count=len(overdue),
        completion_modules=completion_payload["modules"],
    )
    hazard_counts = {"open": len(open_hazards), "due": len(due), "overdue": len(overdue)}

    updated_at = ent.updated_at
    recent_activities = [
        {"actor": "系统", "action": "企业档案更新", "time": updated_at.isoformat() if updated_at else ""},
    ]

    return {
        **aggregated,
        "hazard_counts": hazard_counts,
        "todos": todos,
        "completion": completion_payload,
        "recent_activities": recent_activities,
    }
