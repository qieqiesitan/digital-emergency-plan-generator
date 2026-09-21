"""作业票确定性预填：字段来源优先级与取数拼装。

来源（按字段各自的优先级，见 FIELD_SOURCES）：
  enterprise      企业档案
  history         同企业同模板的上一张非草稿票
  member          企业成员台账（含特种作业证照）
  risk_object     作业对象（楼层→区域→对象）
  system_default  系统默认（申请时间、默认 8 小时时段）
  template_link   向导内联动（级别）
  batch           作业包（由批量开票计划写入）

硬原则：候选值为空一律跳过，绝不写猜测值；**未登记的字段一律不预填**
（作业高度、吊装质量、盲板编号这类现场事实宁可留空）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.work_ticket import WorkTicketInstance
from app.services.work_ticket_condition_loader import (
    load_condition_labels,
    load_conditions,
)
from app.services.work_ticket_measure_rules import (
    MeasureContext,
    conditions_from_scenario,
    suggest_measures,
)

DEFAULT_WORK_HOURS = 8

# 现场事实类字段：即使历史里有值也不直接采用（由用户现场填写）
NEVER_INHERIT = {"fire_location", "space_location", "dig_location", "road_position"}

# 字段 → 来源优先级（左优先）
FIELD_SOURCES: dict[str, tuple[str, ...]] = {
    "applicant_unit": ("enterprise", "history"),
    "work_unit": ("history", "enterprise"),
    "apply_time": ("system_default", "history"),
    "work_period": ("batch", "history", "system_default"),
    "fire_level": ("template_link", "history"),
    "high_level": ("template_link", "history"),
    "lift_level": ("template_link", "history"),
    "work_leader": ("member", "history"),
    "guardian": ("member", "history"),
    "fire_person": ("member", "history"),
    "electrician": ("member", "history"),
    "lift_commander": ("member", "history"),
    "logout_person": ("history",),
    "fire_location": ("risk_object", "history"),
    "space_location": ("risk_object", "history"),
    "dig_location": ("risk_object", "history"),
    "road_position": ("risk_object", "history"),
    "pipe_position": ("risk_object", "history"),
    "work_content": ("batch", "history"),
    "risk_identification": ("history",),
    "related_tickets": ("batch", "history"),
}

_EMPTY = (None, "", [], {})

_POSITION_HINTS: dict[str, tuple[str, ...]] = {
    "work_leader": ("负责人",),
    "guardian": ("监护",),
    "fire_person": ("焊工", "动火"),
    "electrician": ("电工",),
    "lift_commander": ("起重", "指挥"),
}


def pick_value(
    field_key: str, *, candidates: Mapping[str, Any]
) -> tuple[Any, str | None]:
    """按该字段的来源优先级取第一个非空候选值。"""
    # 未登记的字段一律不预填：票种专有字段（作业高度、吊装质量、盲板编号等）
    # 属于现场事实，宁可留空让人填，也不从历史票搬一个可能错的数字过来。
    for source in FIELD_SOURCES.get(field_key, ()):
        value = candidates.get(source)
        if value not in _EMPTY:
            return value, source
    return None, None


def build_values(
    fields: Sequence[Mapping[str, Any]], *, candidates: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """按模板字段清单产出 (values, values_meta)。

    只处理模板里真实存在的字段；空值字段既不进 values 也不进 meta。
    """
    values: dict[str, Any] = {}
    meta: dict[str, dict[str, Any]] = {}
    for field in fields:
        key = field["field_key"]
        value, source = pick_value(key, candidates=candidates)
        if value is None:
            continue
        values[key] = value
        meta[key] = {"source": source, "source_ref": {}, "edited": False}
    return values, meta


def default_period(now: datetime | None = None) -> list[str]:
    """默认作业时段：申请时间起，8 小时。"""
    start = now or datetime.now(timezone.utc)
    return [start.isoformat(), (start + timedelta(hours=DEFAULT_WORK_HOURS)).isoformat()]


def _member_text(members: Iterable[EnterpriseMember], field_key: str) -> str | None:
    """按岗位关键词挑一个成员作为建议值；证书号自动拼接（规格 §2.6）。

    落库格式与改造前完全一致（"姓名 证书号"），因此打印、docx、历史票零改动。
    """
    hints = _POSITION_HINTS.get(field_key)
    if not hints:
        return None
    for member in members:
        if not member.position or not any(h in member.position for h in hints):
            continue
        cert_no = next(
            (c.get("no") for c in (member.certificates or []) if c.get("no")), None
        )
        return f"{member.name} {cert_no}".strip() if cert_no else member.name
    return None


async def _last_ticket(
    db: AsyncSession, *, enterprise_id: str, template_id: str
) -> WorkTicketInstance | None:
    """同企业同模板的上一张非草稿票（继承源）。"""
    res = await db.execute(
        select(WorkTicketInstance)
        .where(
            WorkTicketInstance.enterprise_id == enterprise_id,
            WorkTicketInstance.template_id == template_id,
            WorkTicketInstance.status != "draft",
        )
        .order_by(WorkTicketInstance.created_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _members(db: AsyncSession, enterprise_id: str) -> list[EnterpriseMember]:
    res = await db.execute(
        select(EnterpriseMember)
        .where(
            EnterpriseMember.enterprise_id == enterprise_id,
            EnterpriseMember.enabled.is_(True),
        )
        .order_by(EnterpriseMember.name)
    )
    return list(res.scalars().all())


async def build_prefill(
    db: AsyncSession,
    *,
    enterprise_id: str,
    template,
    level: str | None = None,
    risk_object_location: str | None = None,
    zone_name: str | None = None,
    fire_method: str | None = None,
    scenario: Mapping[str, bool | None] | None = None,
    other_ticket_types: Sequence[str] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    """确定性预填的取数入口。返回 values/values_meta 与页面所需的候选数据。"""
    enterprise = (
        await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))
    ).scalar_one_or_none()
    last = await _last_ticket(db, enterprise_id=enterprise_id, template_id=template.id)
    members = await _members(db, enterprise_id)
    history_values = dict(last.values or {}) if last else {}
    # 现场事实类字段即使历史里有值也不直接采用
    for key in NEVER_INHERIT:
        history_values.pop(key, None)
    # 内部簿记字段不是票面字段，不参与继承
    history_values.pop("confirmed_measures", None)

    values: dict[str, Any] = {}
    meta: dict[str, dict[str, Any]] = {}
    for field in template.fields:
        key = field.field_key
        candidates: dict[str, Any] = {
            "enterprise": getattr(enterprise, "name", None),
            "history": history_values.get(key),
            "member": _member_text(members, key),
            "risk_object": risk_object_location,
            "system_default": (
                default_period(now)
                if key == "work_period"
                else (
                    (now or datetime.now(timezone.utc)).isoformat()
                    if key == "apply_time"
                    else None
                )
            ),
            "template_link": level,
            "batch": None,
        }
        value, source = pick_value(key, candidates=candidates)
        if value is None:
            continue
        values[key] = value
        meta[key] = {"source": source, "source_ref": {}, "edited": False}
    # 措施"是否涉及"建议：由作业情景（用户勾选）+ 可推断条件（动火方式、区域名、
    # 同包其他票）共同决定；建议只影响分组，落地仍需人工点击。
    conditions = conditions_from_scenario(
        ticket_type=template.code,
        fire_method=fire_method or history_values.get("fire_method"),
        zone_name=zone_name,
        work_period=values.get("work_period") or None,
        field_values=values,
        level=level,
        other_ticket_types=other_ticket_types,
        scenario=scenario,
    )
    # 映射与标签都从表里取（表由 YAML + 生成器产出）：这样标准文本更新后
    # 只需重跑生成器，不需要改代码。
    conditions_map = await load_conditions(db)
    condition_labels = await load_condition_labels(db)
    measures_suggestions = suggest_measures(
        list(getattr(template, "measures", []) or []),
        MeasureContext(ticket_type=template.code, conditions=conditions),
        conditions_map=conditions_map,
        labels=condition_labels,
    )
    return {
        "values": values,
        "values_meta": meta,
        "last_ticket_id": str(last.id) if last else None,
        "measures_suggestions": measures_suggestions,
        "members": [
            {
                "id": str(m.id),
                "name": m.name,
                "position": m.position,
                "certificates": m.certificates or [],
            }
            for m in members
        ],
    }
