"""风险告知卡组装服务：规则为主，从风险数据实时组装 CardData。"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.risk_management import RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.risk_notice_card import RiskNoticeCard
from app.services.risk_notice_card_data import (
    SIGN_GROUPS, DEFAULT_SIGN_GROUP, EMERGENCY_TEMPLATES,
    LEVEL_ORDER, LEVEL_COLORS, SIGN_CATEGORY_ORDER,
    DEFAULT_EMERGENCY_TEMPLATE, SOURCE_AI,
)
from app.schemas.risk_notice_card import CardData, RightColumn


def compute_level(events: list[RiskEvent]) -> str:
    levels = {e.risk_level for e in events if e.risk_level}
    for level in LEVEL_ORDER:
        if level in levels:
            return level
    return "未评估"


def resolve_responsible(obj: RiskObject, ent: Enterprise) -> tuple[str, str, str, bool]:
    if obj.responsible_unit or obj.responsible_person or obj.contact_phone:
        return (
            obj.responsible_unit or ent.name,
            obj.responsible_person or (ent.safety_officer or ""),
            obj.contact_phone or (ent.safety_officer_phone or ""),
            False,
        )
    return (ent.name, ent.safety_officer or "", ent.safety_officer_phone or "", True)


def compute_code(objects: list[RiskObject], obj: RiskObject) -> str:
    """按对象在列表中的序号生成 FX-{序号:03d}。

    优先按 id 匹配（生产环境）；未持久化的内存对象 id 为 None，
    退化为按对象身份匹配（测试构造场景）。
    """
    for i, o in enumerate(objects):
        if o.id is not None and obj.id is not None and o.id == obj.id:
            return f"FX-{i + 1:03d}"
        if o is obj:
            return f"FX-{i + 1:03d}"
    return f"FX-{len(objects) + 1:03d}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _numbered(items: list[str]) -> list[str]:
    return [f"{i + 1}. {it}" for i, it in enumerate(items)]


def build_right_column(
    events: list[RiskEvent],
    measures: list[RiskMeasure],
    snapshot: dict | None = None,
) -> RightColumn:
    if snapshot:
        return RightColumn(
            hazard_description=snapshot.get("hazard_description", ""),
            accident_types=snapshot.get("accident_types", []),
            control_measures=snapshot.get("control_measures", []),
            emergency_measures=snapshot.get("emergency_measures", []),
        )
    hazard_parts = []
    for e in events:
        if e.trigger_conditions:
            hazard_parts.append(e.trigger_conditions)
        if e.consequences:
            hazard_parts.append(e.consequences)
    hazard = "；".join(_dedupe(hazard_parts))
    accident_types = _dedupe([e.accident_type for e in events])
    control = _numbered(_dedupe([
        m.description for m in measures
        if m.measure_category in ("engineering", "management", "ppe")
    ]))
    emergency_db = _dedupe([
        m.description for m in measures if m.measure_category == "emergency"
    ])
    emergency = _numbered(emergency_db)
    if len(emergency) < 2:
        template: list[str] = []
        for at in accident_types:
            template += EMERGENCY_TEMPLATES.get(at, [])
        if not template:
            template = DEFAULT_EMERGENCY_TEMPLATE
        merged = _dedupe(emergency_db + template)
        emergency = _numbered(merged)
    return RightColumn(
        hazard_description=hazard,
        accident_types=accident_types,
        control_measures=control,
        emergency_measures=emergency,
    )


def match_signs(accident_types: list[str]) -> list[dict]:
    """按 SIGN_GROUPS 合并去重，按 警告→禁止→指令→提示 排序，每类最多 2 个。"""
    merged: list[dict] = []
    seen: set[str] = set()
    for at in accident_types:
        group = SIGN_GROUPS.get(at, DEFAULT_SIGN_GROUP)
        for s in group:
            if s["svg_name"] not in seen:
                seen.add(s["svg_name"])
                merged.append(s)
    ordered: list[dict] = []
    counts: dict[str, int] = {}
    for category in SIGN_CATEGORY_ORDER:
        for s in merged:
            if s["category"] == category and counts.get(category, 0) < 2:
                ordered.append(s)
                counts[category] = counts.get(category, 0) + 1
    return ordered


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_stale(snapshot: RiskNoticeCard, source_updated_at: datetime | None) -> bool:
    if source_updated_at is None:
        return False
    return _as_utc(snapshot.updated_at) < _as_utc(source_updated_at)


async def get_snapshot(db: AsyncSession, object_id: str) -> RiskNoticeCard | None:
    return (
        await db.execute(
            select(RiskNoticeCard).where(RiskNoticeCard.object_id == object_id).order_by(RiskNoticeCard.version.desc())
        )
    ).scalars().first()


async def load_events_and_measures(db: AsyncSession, object_id: str) -> tuple[list[RiskEvent], list[RiskMeasure]]:
    obj = (
        await db.execute(
            select(RiskObject)
            .options(
                selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures),
                selectinload(RiskObject.events).selectinload(RiskEvent.measures),
            )
            .where(RiskObject.id == object_id)
        )
    ).scalar_one_or_none()
    if obj is None:
        return [], []
    # RiskEvent 同时有 object_id 与 unit_id 双外键，同一事件可能同时出现在
    # obj.events 和 unit.events，需按 id 保序去重后再收集措施。
    raw_events: list[RiskEvent] = list(obj.events or [])
    for unit in obj.units or []:
        raw_events.extend(unit.events or [])
    events: list[RiskEvent] = []
    seen: dict = {}
    for e in raw_events:
        key = e.id if e.id is not None else id(e)
        if key not in seen:
            seen[key] = True
            events.append(e)
    measures: list[RiskMeasure] = []
    for e in events:
        measures.extend(e.measures or [])
    return events, measures


async def build_card_data(
    db: AsyncSession,
    ent: Enterprise,
    obj: RiskObject,
    objects: list[RiskObject],
    events: list[RiskEvent],
    measures: list[RiskMeasure],
) -> CardData:
    snapshot = await get_snapshot(db, obj.id)
    col = build_right_column(events, measures, snapshot.content if snapshot else None)
    unit, person, phone, fallback = resolve_responsible(obj, ent)
    level = compute_level(events)
    timestamps = [
        t for t in (
            [obj.updated_at or obj.created_at]
            + [e.updated_at or e.created_at for e in events]
            + [m.updated_at or m.created_at for m in measures]
        )
        if t is not None
    ]
    source_updated = max(timestamps) if timestamps else None
    return CardData(
        object_id=obj.id,
        enterprise_name=ent.name,
        name=obj.name,
        code=compute_code(objects, obj),
        level=level,
        level_color=LEVEL_COLORS.get(level, "#bfbfbf"),
        responsible_unit=unit,
        responsible_person=person,
        contact_phone=phone,
        fallback_used=fallback,
        signs=match_signs(col.accident_types),
        hazard_description=col.hazard_description,
        accident_types=col.accident_types,
        control_measures=col.control_measures,
        emergency_measures=col.emergency_measures,
        snapshot={"version": snapshot.version, "source": snapshot.source} if snapshot else None,
        stale=is_stale(snapshot, source_updated) if snapshot else False,
        public_url=f"/r/{obj.public_token}",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


async def save_snapshot(
    db: AsyncSession,
    enterprise_id: str,
    object_id: str,
    user_id: str,
    content: dict,
) -> RiskNoticeCard | None:
    existing = await get_snapshot(db, object_id)
    if existing:
        existing.version += 1
        existing.content = content
        existing.source = SOURCE_AI
        existing.created_by = user_id
        await db.commit()
        await db.refresh(existing)
        return existing
    snap = RiskNoticeCard(
        enterprise_id=enterprise_id,
        object_id=object_id,
        version=1,
        content=content,
        source=SOURCE_AI,
        created_by=user_id,
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return snap
