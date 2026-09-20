"""章节「数据依赖已变更」检测（D-3）。

背景：`plan_sections.data_dependencies` 早已按模板落库（真实取值如
`["risk_sources"]`、`["risk_sources","emergency_resources"]`、`["org_structure"]`），
但全项目没有任何消费方 → 用户改完企业数据后，已生成的章节正文仍是旧数据，
系统不会提示"该重新生成"。

口径：某依赖域**变更时间 > 章节正文更新时间** → 该章节标记待更新。
变更时间 = max(依赖表自身时间戳, `enterprise_data_marks` 打点)：
- 表时间戳覆盖新增/修改（含导入、批量、AI 生成等所有写入路径）；
- 打点表专门覆盖**删除**（删子行不会更新任何父行时间戳），由删除类端点显式写入。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_mark import EnterpriseDataMark
from app.models.emergency_org import (
    EmergencyOrgAssignment,
    EmergencyOrgRole,
    EmergencyOrgUnit,
)
from app.models.enterprise import EmergencyResource, Enterprise
from app.models.risk_management import (
    RiskEvent,
    RiskMeasure,
    RiskObject,
    RiskUnit,
    RiskZone,
)

DOMAIN_RISK = "risk_sources"
DOMAIN_RESOURCES = "emergency_resources"
DOMAIN_ORG = "org_structure"

# 与 plan_sections.data_dependencies 的取值保持一致
TRACKED_DOMAINS = (DOMAIN_RISK, DOMAIN_RESOURCES, DOMAIN_ORG)

DOMAIN_LABELS = {
    DOMAIN_RISK: "风险分级管控",
    DOMAIN_RESOURCES: "应急资源",
    DOMAIN_ORG: "应急组织",
}


async def mark_data_changed(db: AsyncSession, enterprise_id: str, domain: str) -> None:
    """打点：记录某企业某数据域刚发生变更（upsert，不 commit）。"""
    if domain not in TRACKED_DOMAINS:
        raise ValueError(f"未知数据域：{domain}")
    stmt = pg_insert(EnterpriseDataMark).values(
        enterprise_id=enterprise_id, domain=domain, changed_at=func.now()
    )
    await db.execute(stmt.on_conflict_do_update(
        index_elements=[EnterpriseDataMark.enterprise_id, EnterpriseDataMark.domain],
        set_={"changed_at": func.now()},
    ))


def _risk_subqueries(enterprise_id: str) -> list:
    """风险五层里各自的 max(updated_at)（单元/事件/措施经对象归属企业）。"""
    ev_join = or_(
        RiskEvent.object_id == RiskObject.id,
        RiskUnit.object_id == RiskObject.id,
    )
    return [
        select(func.max(RiskZone.updated_at))
        .where(RiskZone.enterprise_id == enterprise_id).scalar_subquery(),
        select(func.max(RiskObject.updated_at))
        .where(RiskObject.enterprise_id == enterprise_id).scalar_subquery(),
        select(func.max(RiskUnit.updated_at))
        .join(RiskObject, RiskUnit.object_id == RiskObject.id)
        .where(RiskObject.enterprise_id == enterprise_id).scalar_subquery(),
        select(func.max(RiskEvent.updated_at))
        .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
        .join(RiskObject, ev_join)
        .where(RiskObject.enterprise_id == enterprise_id).scalar_subquery(),
        select(func.max(RiskMeasure.updated_at))
        .join(RiskEvent, RiskMeasure.event_id == RiskEvent.id)
        .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
        .join(RiskObject, ev_join)
        .where(RiskObject.enterprise_id == enterprise_id).scalar_subquery(),
    ]


def _resource_subqueries(enterprise_id: str) -> list:
    return [
        select(func.max(EmergencyResource.updated_at))
        .where(EmergencyResource.enterprise_id == enterprise_id).scalar_subquery(),
        select(func.max(EmergencyResource.created_at))
        .where(EmergencyResource.enterprise_id == enterprise_id).scalar_subquery(),
    ]


def _org_subqueries(enterprise_id: str) -> list:
    return [
        select(func.max(Enterprise.updated_at))
        .where(Enterprise.id == enterprise_id).scalar_subquery(),
        select(func.max(EmergencyOrgUnit.updated_at))
        .where(EmergencyOrgUnit.enterprise_id == enterprise_id).scalar_subquery(),
        select(func.max(EmergencyOrgRole.updated_at))
        .where(EmergencyOrgRole.enterprise_id == enterprise_id).scalar_subquery(),
        select(func.max(EmergencyOrgAssignment.created_at))
        .where(EmergencyOrgAssignment.enterprise_id == enterprise_id).scalar_subquery(),
    ]


def domain_timestamp_query(domain: str, enterprise_id: str):
    """该域最新变更时间查询（GREATEST 忽略 NULL：无数据时为 NULL）。"""
    builders = {
        DOMAIN_RISK: _risk_subqueries,
        DOMAIN_RESOURCES: _resource_subqueries,
        DOMAIN_ORG: _org_subqueries,
    }
    return select(func.greatest(*builders[domain](enterprise_id)))


def _as_aware(dt: datetime | None) -> datetime | None:
    """naive 时间按 UTC 处理，避免与 timestamptz 比较时报错。"""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def load_marks(db: AsyncSession, enterprise_id: str) -> dict[str, datetime]:
    rows = (await db.execute(
        select(EnterpriseDataMark.domain, EnterpriseDataMark.changed_at)
        .where(EnterpriseDataMark.enterprise_id == enterprise_id)
    )).all()
    return {r[0]: r[1] for r in rows}


async def stale_domains_for_sections(
    db: AsyncSession,
    enterprise_id: str,
    sections,
) -> dict[str, list[str]]:
    """返回 {section_key: [已变更但章节未更新的依赖域]}，仅含非空项。"""
    needed: set[str] = set()
    for s in sections or []:
        if not (getattr(s, "content", None) or "").strip():
            continue
        for d in (getattr(s, "data_dependencies", None) or []):
            if d in TRACKED_DOMAINS:
                needed.add(d)
    if not needed:
        return {}
    marks = await load_marks(db, enterprise_id)
    changed: dict[str, datetime | None] = {}
    for domain in needed:
        table_ts = (await db.execute(domain_timestamp_query(domain, enterprise_id))).scalar()
        candidates = [x for x in (_as_aware(marks.get(domain)), _as_aware(table_ts)) if x]
        changed[domain] = max(candidates) if candidates else None

    out: dict[str, list[str]] = {}
    for s in sections or []:
        if not (getattr(s, "content", None) or "").strip():
            continue
        base = _as_aware(getattr(s, "updated_at", None))
        if base is None:
            continue
        stale = [
            d for d in (getattr(s, "data_dependencies", None) or [])
            if changed.get(d) and changed[d] > base
        ]
        if stale:
            out[s.section_key] = stale
    return out
