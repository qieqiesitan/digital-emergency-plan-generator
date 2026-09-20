"""作业包：共享槽位映射、票号回填、状态机。

槽位（slot）是"语义字段"，落到各票种的实际 field_key 由 SLOT_TARGETS 决定：
不同票种的地点字段名不同（fire_location / space_location / dig_location /
road_position / pipe_position），而高处（GCZY）、吊装（QZDZ）、临时用电（LSYD）
根本没有地点字段——**刻意不为它们新增票面字段**（GB 30871 附录A 票面样式不可自加行），
那些票种的地点信息由作业包作为上下文注入作业内容。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_ticket import (
    WorkTicketBatch,
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketTemplate,
)
from app.services.work_ticket_service import (
    SubmitValidationError,
    WorkTicketError,
    open_ticket,
    submit_ticket,
)

BATCH_SOURCE = "batch"

# "*" 表示 8 类票通用；其余按票种 code 精确匹配；未命中即跳过该槽位
SLOT_TARGETS: dict[str, dict[str, str]] = {
    "applicant_unit": {"*": "applicant_unit"},
    "work_unit": {"*": "work_unit"},
    "work_leader": {"*": "work_leader"},
    "period": {"*": "work_period"},
    "content": {"*": "work_content"},
    "risk_basis": {"*": "risk_identification"},
    "related": {"*": "related_tickets"},
    "location": {
        "DHZY": "fire_location",
        "YXKJ": "space_location",
        "MBCD": "pipe_position",
        "PTZY": "dig_location",
        "DLZY": "road_position",
    },
}

BATCH_STATUSES = ("draft", "active", "closed", "cancelled")

_EMPTY = (None, "", [], {})


def _target_key(slot: str, ticket_type: str) -> str | None:
    targets = SLOT_TARGETS.get(slot)
    if not targets:
        return None
    return targets.get(ticket_type) or targets.get("*")


def apply_slots(
    ticket_type: str, shared: Mapping[str, Any], field_keys: Iterable[str]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """把作业包的共享槽位落到该票种的字段上。

    只为"模板里真实存在"的 field_key 产出值；空槽位不产出。
    """
    keys = set(field_keys)
    values: dict[str, Any] = {}
    meta: dict[str, dict[str, Any]] = {}
    for slot, raw in shared.items():
        if raw in _EMPTY:
            continue
        target = _target_key(slot, ticket_type)
        if not target or target not in keys:
            continue
        values[target] = raw
        meta[target] = {
            "source": BATCH_SOURCE,
            "source_ref": {"slot": slot},
            "edited": False,
        }
    return values, meta


def build_related_map(items: Sequence[tuple[str, str]]) -> dict[str, str]:
    """(ticket_id, code) 列表 → {ticket_id: "包内其他票号（按票号排序，逗号分隔）"}。"""
    ordered = sorted(items, key=lambda pair: pair[1])
    out: dict[str, str] = {}
    for ticket_id, code in ordered:
        others = [c for _, c in ordered if c != code]
        out[ticket_id] = ",".join(others)
    return out


def next_batch_status(
    current: str, *, submitted: int, total: int, action: str = "refresh"
) -> str:
    """包状态推进：draft → active（首张票提交）；全部终态 → closed。

    作废（cancel）在包内已有提交票时被拒绝——已进入审批的票不能失去上下文。
    """
    if action == "cancel":
        if submitted > 0:
            raise ValueError("包内存在已提交的作业票，不能作废作业包")
        return "cancelled"
    if action == "close":
        return "closed"
    if current in ("closed", "cancelled"):
        return current
    if total and submitted >= total:
        return "closed"
    if submitted > 0:
        return "active"
    return "draft"


# ── 服务编排（取数 + 事务） ──────────────────────────────────────────────


async def _template_of(db: AsyncSession, template_id: str) -> WorkTicketTemplate | None:
    return (
        await db.execute(
            select(WorkTicketTemplate).where(WorkTicketTemplate.id == template_id)
        )
    ).scalar_one_or_none()


def _shared_payload(batch: WorkTicketBatch) -> dict[str, Any]:
    """把作业包的共享信息整理成"槽位 → 值"（时段时间格式化后覆盖 period）。"""
    shared: dict[str, Any] = dict(batch.shared_values or {})
    if batch.work_period_start and batch.work_period_end:
        shared["period"] = [
            batch.work_period_start.isoformat(),
            batch.work_period_end.isoformat(),
        ]
    if batch.location_text:
        shared["location"] = batch.location_text
    if batch.content_base:
        shared["content"] = batch.content_base
    if batch.risk_basis:
        shared["risk_basis"] = batch.risk_basis
    return shared


async def tickets_of_batch(
    db: AsyncSession, *, batch_id: str, include_package_gas: bool = True
) -> tuple[list[WorkTicketInstance], list[WorkTicketGasTest]]:
    """包内票（按创建顺序）+ 包级检测记录。"""
    tickets = list(
        (
            await db.execute(
                select(WorkTicketInstance)
                .where(WorkTicketInstance.batch_id == batch_id)
                .order_by(WorkTicketInstance.created_at)
            )
        )
        .scalars()
        .all()
    )
    gas: list[WorkTicketGasTest] = []
    if include_package_gas:
        gas = list(
            (
                await db.execute(
                    select(WorkTicketGasTest)
                    .where(WorkTicketGasTest.batch_id == batch_id)
                    .order_by(WorkTicketGasTest.sampled_at)
                )
            )
            .scalars()
            .all()
        )
    return tickets, gas


async def create_batch(
    db: AsyncSession, *, enterprise_id: str, payload, user_id: str | None
) -> WorkTicketBatch:
    batch = WorkTicketBatch(
        enterprise_id=enterprise_id,
        title=payload.title,
        floor_id=payload.floor_id,
        zone_id=payload.zone_id,
        risk_object_id=payload.risk_object_id,
        location_text=payload.location_text,
        work_period_start=payload.work_period_start,
        work_period_end=payload.work_period_end,
        shared_values=payload.shared_values or {},
        content_base=payload.content_base,
        risk_basis=payload.risk_basis,
        created_by=user_id,
    )
    db.add(batch)
    await db.commit()
    return batch


async def add_tickets(
    db: AsyncSession,
    *,
    batch: WorkTicketBatch,
    enterprise_code: str,
    specs: Sequence[Mapping[str, Any]],
    user_id: str | None,
) -> list[WorkTicketInstance]:
    """批量生成草稿票并回填互相的 related_tickets —— 全流程单事务。"""
    created: list[WorkTicketInstance] = []
    try:
        for spec in specs:
            template = await _template_of(db, str(spec["template_id"]))
            if template is None:
                raise ValueError(f"模板不存在：{spec['template_id']}")
            shared = _shared_payload(batch)
            values, meta = apply_slots(
                template.code, shared, {f.field_key for f in template.fields}
            )
            instance = await open_ticket(
                db,
                enterprise_id=batch.enterprise_id,
                enterprise_code=enterprise_code,
                ticket_type=template.code,
                template_id=template.id,
                level=spec.get("level"),
                values=values,
                values_meta=meta,
                batch_id=batch.id,
                user_id=user_id,
                commit=False,
            )
            created.append(instance)

        # 票号回填必须在同一事务内，否则会出现"A 的关联票号里有 B、B 里没有 A"
        related = build_related_map([(i.id, i.code) for i in created])
        for instance in created:
            values = dict(instance.values or {})
            values["related_tickets"] = related[instance.id]
            instance.values = values
            meta = dict(instance.values_meta or {})
            meta["related_tickets"] = {
                "source": BATCH_SOURCE,
                "source_ref": {"slot": "related"},
                "edited": False,
            }
            instance.values_meta = meta

        batch.status = next_batch_status(
            batch.status, submitted=0, total=len(created), action="refresh"
        )
        batch.updated_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    for instance in created:
        await db.refresh(instance)
    return created


async def update_batch_shared(db: AsyncSession, *, batch: WorkTicketBatch, payload) -> dict:
    """改共享槽位：只回写**未提交**的票，已提交票提示作废重开。"""
    if payload.title is not None:
        batch.title = payload.title
    if payload.location_text is not None:
        batch.location_text = payload.location_text
    if payload.work_period_start is not None:
        batch.work_period_start = payload.work_period_start
    if payload.work_period_end is not None:
        batch.work_period_end = payload.work_period_end
    if payload.content_base is not None:
        batch.content_base = payload.content_base
    if payload.risk_basis is not None:
        batch.risk_basis = payload.risk_basis
    if payload.shared_values is not None:
        batch.shared_values = payload.shared_values
    batch.updated_at = datetime.now(timezone.utc)

    tickets, _ = await tickets_of_batch(db, batch_id=batch.id, include_package_gas=False)
    shared = _shared_payload(batch)
    affected = 0
    for ticket in tickets:
        if ticket.status != "draft":
            continue
        template = await _template_of(db, ticket.template_id)
        if template is None:
            continue
        values, meta = apply_slots(
            template.code, shared, {f.field_key for f in template.fields}
        )
        ticket.values = {**(ticket.values or {}), **values}
        ticket.values_meta = {**(ticket.values_meta or {}), **meta}
        affected += 1
    await db.commit()
    return {"affected": affected, "skipped": len(tickets) - affected}


async def batch_counts(db: AsyncSession, *, batch_id: str) -> tuple[int, int]:
    """(已提交票数, 总票数)。"""
    tickets, _ = await tickets_of_batch(db, batch_id=batch_id, include_package_gas=False)
    submitted = sum(1 for t in tickets if t.status != "draft")
    return submitted, len(tickets)


async def submit_all(db: AsyncSession, *, batch_id: str, user_id: str | None) -> dict:
    """逐票提交：失败的票单独返回，不影响其他票（每票各自走法定门禁）。"""
    tickets, _ = await tickets_of_batch(db, batch_id=batch_id, include_package_gas=False)
    results: list[dict[str, Any]] = []
    for ticket in tickets:
        if ticket.status != "draft":
            results.append(
                {
                    "ticket_id": ticket.id,
                    "code": ticket.code,
                    "ok": False,
                    "errors": [f"当前状态（{ticket.status}）不允许提交"],
                }
            )
            continue
        try:
            await submit_ticket(db, instance_id=ticket.id, user_id=user_id)
            results.append({"ticket_id": ticket.id, "code": ticket.code, "ok": True, "errors": []})
        except (SubmitValidationError, WorkTicketError) as exc:
            await db.rollback()
            results.append(
                {
                    "ticket_id": ticket.id,
                    "code": ticket.code,
                    "ok": False,
                    "errors": [part for part in str(exc).split("；") if part],
                }
            )
    batch = (
        await db.execute(select(WorkTicketBatch).where(WorkTicketBatch.id == batch_id))
    ).scalar_one_or_none()
    if batch is not None:
        submitted, total = await batch_counts(db, batch_id=batch_id)
        batch.status = next_batch_status(batch.status, submitted=submitted, total=total)
        await db.commit()
    return {"results": results, "succeeded": sum(1 for r in results if r["ok"])}
