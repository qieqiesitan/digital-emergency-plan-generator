"""旧版 RiskSource 迁移到风险分级管控五层结构的服务。"""
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import RiskSource
from app.models.risk_management import RiskZone, RiskObject, RiskEvent, RiskMeasure
from app.services.risk_mapping_service import ensure_default_floor
from app.services.risk_method_engine import compute_risk, get_active_method_config


def split_control_measures(text: str | None) -> list[str]:
    """把旧控制措施自由文本按常见分隔符拆成多条措施。"""
    if not text or not text.strip():
        return []
    parts = re.split(r"[\n；;]+", text)
    return [p.strip() for p in parts if p.strip()]


def _clamp_ls(value) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        return 3
    return num if 1 <= num <= 5 else 3


def build_default_mapping(source: RiskSource) -> dict:
    """构造旧风险源到新五层的默认映射。"""
    categories = [
        c.strip()
        for c in (source.categories or "").split(",")
        if c.strip()
    ]
    return {
        "source_id": source.id,
        "source_name": source.name,
        "source_location": source.location,
        "source_categories": categories,
        "suggested_zone": "历史风险源",
        "suggested_object": source.name,
        "suggested_event": source.name or "安全生产事故",
        "suggested_params": {
            "l": _clamp_ls(source.likelihood),
            "s": _clamp_ls(source.severity),
        },
        "control_measures": source.control_measures,
    }


async def build_migration_preview(
    db: AsyncSession,
    enterprise_id: str,
    ai_mappings: list[dict] | None = None,
) -> dict:
    """返回未迁移旧风险源的默认映射，可叠加 AI 建议。"""
    sources = (
        await db.execute(
            select(RiskSource).where(
                RiskSource.enterprise_id == enterprise_id,
                RiskSource.migrated.is_(False),
            ).order_by(RiskSource.sort_order)
        )
    ).scalars().all()
    items = [build_default_mapping(s) for s in sources]
    migrated_total = (
        await db.execute(
            select(RiskSource).where(
                RiskSource.enterprise_id == enterprise_id,
                RiskSource.migrated.is_(True),
            )
        )
    ).scalars().all()

    if ai_mappings:
        by_id = {m.get("source_id"): m for m in ai_mappings if isinstance(m, dict)}
        for item in items:
            ai = by_id.get(item["source_id"], {})
            item["suggested_zone"] = ai.get("suggested_zone") or item["suggested_zone"]
            item["suggested_object"] = ai.get("suggested_object") or item["suggested_object"]
            item["suggested_event"] = (
                ai.get("suggested_accident_type")
                or ai.get("suggested_event")
                or item["suggested_event"]
            )
            params = ai.get("suggested_params") or item["suggested_params"]
            if isinstance(params, dict):
                item["suggested_params"] = {
                    "l": _clamp_ls(params.get("l")),
                    "s": _clamp_ls(params.get("s")),
                }

    return {
        "items": items,
        "total": len(items),
        "migrated_total": len(migrated_total),
    }


async def execute_migration(
    db: AsyncSession,
    enterprise_id: str,
    mappings: list,
) -> dict:
    """单事务迁移旧风险源到新五层，并写回 migrated。"""
    source_ids = [m.source_id for m in mappings]
    sources = (
        await db.execute(
            select(RiskSource).where(
                RiskSource.id.in_(source_ids),
                RiskSource.enterprise_id == enterprise_id,
                RiskSource.migrated.is_(False),
            )
        )
    ).scalars().all()
    source_map = {s.id: s for s in sources}
    floor = await ensure_default_floor(db, enterprise_id)
    config = await get_active_method_config(db, enterprise_id, "LS")
    if not config:
        config = {
            "risk_thresholds": [
                {"min": 20, "max": 25, "level": "重大", "action": "立即整改", "deadline": "立即"},
                {"min": 15, "max": 19, "level": "较大", "action": "限期整改", "deadline": "1 个月"},
                {"min": 10, "max": 14, "level": "一般", "action": "限期整改", "deadline": "3 个月"},
                {"min": 1, "max": 9, "level": "低", "action": "加强日常管理", "deadline": "持续"},
            ]
        }
    created = {"zones": 0, "objects": 0, "events": 0, "measures": 0}
    migrated = 0
    skipped = 0

    try:
        for mapping in mappings:
            source = source_map.get(mapping.source_id)
            if not source:
                skipped += 1
                continue

            existing = (
                await db.execute(
                    select(RiskObject).where(
                        RiskObject.enterprise_id == enterprise_id,
                        RiskObject.legacy_source_id == mapping.source_id,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                source.migrated = True
                migrated += 1
                continue

            zone = (
                await db.execute(
                    select(RiskZone).where(
                        RiskZone.enterprise_id == enterprise_id,
                        RiskZone.floor_id == floor.id,
                        RiskZone.name == mapping.zone_name,
                    )
                )
            ).scalar_one_or_none()
            if not zone:
                zone = RiskZone(
                    enterprise_id=enterprise_id,
                    floor_id=floor.id,
                    name=mapping.zone_name,
                )
                db.add(zone)
                await db.flush()
                created["zones"] += 1

            categories = [
                c.strip()
                for c in (source.categories or "").split(",")
                if c.strip()
            ]
            obj = RiskObject(
                enterprise_id=enterprise_id,
                zone_id=zone.id,
                floor_id=floor.id,
                name=mapping.object_name or source.name,
                category=categories[0] if categories else None,
                location=source.location,
                location_x=source.location_x,
                location_y=source.location_y,
                description=source.description,
                legacy_source_id=source.id,
            )
            db.add(obj)
            await db.flush()
            created["objects"] += 1

            params = {
                "l": _clamp_ls(mapping.method_params.get("l", source.likelihood)),
                "s": _clamp_ls(mapping.method_params.get("s", source.severity)),
            }
            rating = compute_risk("LS", params, config)
            event = RiskEvent(
                object_id=obj.id,
                accident_type=mapping.accident_type,
                description=source.description or "",
                method_type="LS",
                method_params=params,
                risk_level=rating.risk_level,
                risk_score=rating.risk_score,
            )
            db.add(event)
            await db.flush()
            created["events"] += 1

            for text in split_control_measures(source.control_measures):
                db.add(RiskMeasure(
                    event_id=event.id,
                    measure_category="management",
                    measure_type="旧数据迁移",
                    description=text,
                ))
                created["measures"] += 1

            source.migrated = True
            migrated += 1

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "migrated": migrated,
        "skipped": skipped,
        "created": created,
    }
