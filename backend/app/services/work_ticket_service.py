"""作业票服务：开票、提交、审批推进、延期、作废、归档。

一条不可协商的规则：**法定必填项与证件有效期的校验不受任何开关影响**。
`validate_before_submit()` 据此设计——它不接受 skip/force/bypass 之类的参数，
调用方没有"跳过校验"的可能。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.work_ticket import (
    WorkTicketAuditLog,
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketNodeRecord,
    WorkTicketFlowNode,
    WorkTicketTemplate,
)
from app.services.work_ticket_flow import (
    FlowError,
    can_transition,
    next_node,
    sign_requirement_met,
)

logger = logging.getLogger("work_ticket_service")

GAS_TEST_MAX_AGE = timedelta(minutes=30)


class SubmitValidationError(ValueError):
    """提交前校验未通过。"""


class WorkTicketError(ValueError):
    """作业票状态或数据错误。"""


_CODE_SEQ = re.compile(r"-(\d{4})$")


def build_ticket_code(ticket_type: str, enterprise_code: str, day: datetime, seq: int) -> str:
    """编号规则：{类型}-{企业码}-{YYYYMMDD}-{4位序号}。"""
    return f"{ticket_type}-{enterprise_code}-{day.strftime('%Y%m%d')}-{seq:04d}"


def next_code_seq(existing_codes: Sequence[str]) -> int:
    """取当天已有序号的最大值 +1。

    用"最大值 +1"而不是"数量 +1"——删掉中间某张票后，用数量会撞上已存在的编号。
    """
    max_seq = 0
    for code in existing_codes:
        m = _CODE_SEQ.search(code or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def validate_before_submit(
    *,
    template,
    values: dict,
    measures: Sequence,
    confirmed_measure_orders: Sequence[int],
    gas_tests: Sequence[dict],
    requires_gas_test: bool,
    now: Optional[datetime] = None,
) -> list[str]:
    """提交前合规校验。返回问题清单；空列表表示可以提交。

    刻意不接受 skip/force/bypass 参数：法定必填项一律阻断，平台不提供绕过入口。
    """
    now = now or datetime.now(timezone.utc)
    errors: list[str] = []

    for field in getattr(template, "fields", []) or []:
        if not getattr(field, "is_required", False):
            continue
        key = field.field_key
        raw = values.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            errors.append(f"必填项「{getattr(field, 'label', key)}」尚未填写")

    mandatory = [m for m in measures if getattr(m, "is_mandatory", True)]
    confirmed = set(confirmed_measure_orders or [])
    missing = [m for m in mandatory if getattr(m, "sort_order", 0) not in confirmed]
    if missing:
        errors.append(
            f"还有 {len(missing)} 条安全措施未确认（如「{missing[0].measure_text[:20]}…」）"
        )

    if requires_gas_test:
        if not gas_tests:
            errors.append("动火/受限空间作业必须至少录入一次气体检测记录")
        else:
            latest = max(
                (g.get("sampled_at") for g in gas_tests if g.get("sampled_at")),
                default=None,
            )
            if latest is None:
                errors.append("气体检测记录缺少取样时间")
            else:
                if latest.tzinfo is None:
                    latest = latest.replace(tzinfo=timezone.utc)
                if now - latest > GAS_TEST_MAX_AGE:
                    errors.append(
                        "气体检测取样时间已超过 30 分钟，请重新检测后再提交"
                    )
    return errors


async def open_ticket(
    db: AsyncSession,
    *,
    enterprise_id: str,
    enterprise_code: str,
    ticket_type: str,
    template_id: str,
    level: Optional[str] = None,
    values: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> WorkTicketInstance:
    """开票（草稿态）。编号冲突时重试，最终由数据库唯一约束兜底。"""
    day = datetime.now(timezone.utc)
    prefix = f"{ticket_type}-{enterprise_code}-{day.strftime('%Y%m%d')}-"
    res = await db.execute(
        select(WorkTicketInstance.code).where(
            WorkTicketInstance.enterprise_id == enterprise_id,
            WorkTicketInstance.code.like(f"{prefix}%"),
        )
    )
    seq = next_code_seq([row[0] for row in res.all()])

    instance = WorkTicketInstance(
        enterprise_id=enterprise_id,
        template_id=template_id,
        code=build_ticket_code(ticket_type, enterprise_code, day, seq),
        ticket_type=ticket_type,
        level=level,
        status="draft",
        values=values or {},
        submitted_by=user_id,
    )
    db.add(instance)
    await db.flush()
    db.add(
        WorkTicketAuditLog(
            instance_id=instance.id,
            action="open",
            to_status="draft",
            detail={"code": instance.code},
            acted_by=user_id,
        )
    )
    await db.commit()
    return instance


async def submit_ticket(
    db: AsyncSession,
    *,
    instance_id: str,
    user_id: Optional[str] = None,
) -> dict:
    """提交审批。先过合规校验，再过状态机；任一不过即拒绝。"""
    res = await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == instance_id))
    instance = res.scalar_one_or_none()
    if instance is None:
        raise WorkTicketError("作业票不存在")
    if not can_transition(instance.status, "submit"):
        raise WorkTicketError(f"当前状态（{instance.status}）不允许提交")

    tpl_res = await db.execute(
        select(WorkTicketTemplate).where(WorkTicketTemplate.id == instance.template_id)
    )
    template = tpl_res.scalar_one_or_none()
    values = instance.values or {}
    gas_res = await db.execute(
        select(WorkTicketGasTest).where(WorkTicketGasTest.instance_id == instance_id)
    )
    gas_tests = [
        {"sampled_at": g.sampled_at, "conclusion": g.conclusion}
        for g in gas_res.scalars().all()
    ]
    measures = list(getattr(template, "measures", []) or [])
    errors = validate_before_submit(
        template=template,
        values=values,
        measures=measures,
        confirmed_measure_orders=values.get("confirmed_measures", []),
        gas_tests=gas_tests,
        requires_gas_test=instance.ticket_type in ("DHZY", "YXKJ"),
    )
    if errors:
        raise SubmitValidationError("；".join(errors))

    from_status = instance.status
    instance.status = "approving"
    node = await _advance_to_first_active_node(db, instance)
    db.add(
        WorkTicketAuditLog(
            instance_id=instance.id,
            action="submit",
            from_status=from_status,
            to_status="approving",
            detail={"first_node": getattr(node, "node_key", None)},
            acted_by=user_id,
        )
    )
    await db.commit()
    return {"instance_id": instance.id, "status": instance.status, "node": getattr(node, "node_key", None)}


async def _advance_to_first_active_node(db: AsyncSession, instance: WorkTicketInstance):
    """从 current_order 之后找第一个条件命中的节点并写回实例。"""
    if not instance.flow_template_id:
        raise WorkTicketError("作业票未绑定审批流程")
    res = await db.execute(
        select(WorkTicketFlowNode).where(
            WorkTicketFlowNode.flow_template_id == instance.flow_template_id
        )
    )
    nodes = list(res.scalars().all())
    ctx = {"level": instance.level, **(instance.values or {})}
    node = next_node(nodes, current_order=instance.current_order, ctx=ctx)
    if node is None:
        instance.status = "approved"
        instance.current_node_key = None
    else:
        instance.current_node_key = node.node_key
        instance.current_order = node.sort_order
    return node


async def act_on_node(
    db: AsyncSession,
    *,
    instance_id: str,
    action: str,
    user_id: str,
    opinion: Optional[str] = None,
) -> dict:
    """在审批节点上动作：approve / reject。会签未满足时不允许流转。"""
    res = await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == instance_id))
    instance = res.scalar_one_or_none()
    if instance is None:
        raise WorkTicketError("作业票不存在")
    if instance.status != "approving":
        raise WorkTicketError(f"当前状态（{instance.status}）不在审批中")
    if action not in ("approve", "reject"):
        raise WorkTicketError(f"未知动作：{action}")

    db.add(
        WorkTicketNodeRecord(
            instance_id=instance_id,
            node_key=instance.current_node_key or "",
            action=action,
            opinion=opinion,
            acted_by=user_id,
        )
    )

    if action == "reject":
        from_status = instance.status
        instance.status = "rejected"
        instance.current_node_key = None
        instance.current_order = 0
        db.add(
            WorkTicketAuditLog(
                instance_id=instance.id,
                action="reject",
                from_status=from_status,
                to_status="rejected",
                detail={"opinion": opinion},
                acted_by=user_id,
            )
        )
        await db.commit()
        return {"instance_id": instance.id, "status": instance.status}

    node_res = await db.execute(
        select(WorkTicketFlowNode).where(
            WorkTicketFlowNode.flow_template_id == instance.flow_template_id,
            WorkTicketFlowNode.node_key == instance.current_node_key,
        )
    )
    node = node_res.scalar_one_or_none()
    if node is None:
        raise WorkTicketError("当前节点配置缺失")

    rec_res = await db.execute(
        select(WorkTicketNodeRecord.acted_by).where(
            WorkTicketNodeRecord.instance_id == instance_id,
            WorkTicketNodeRecord.node_key == node.node_key,
            WorkTicketNodeRecord.action == "approve",
        )
    )
    signed = [row[0] for row in rec_res.all()]
    eligible = await _eligible_users(db, node)
    if not sign_requirement_met(node, signed_users=signed, eligible_users=eligible):
        await db.commit()
        return {
            "instance_id": instance.id,
            "status": instance.status,
            "pending_signs": len([u for u in eligible if u not in signed]),
        }

    from_status = instance.status
    nxt = await _advance_to_first_active_node(db, instance)
    db.add(
        WorkTicketAuditLog(
            instance_id=instance.id,
            action="approve",
            from_status=from_status,
            to_status=instance.status,
            detail={"node": node.node_key, "next": getattr(nxt, "node_key", None)},
            acted_by=user_id,
        )
    )
    await db.commit()
    return {
        "instance_id": instance.id,
        "status": instance.status,
        "node": getattr(nxt, "node_key", None),
    }


async def _eligible_users(db: AsyncSession, node) -> list[str]:
    """取该节点绑定的角色成员。没有 role_code 时返回空列表（会签将判为未完成）。

    注意：本项目的用户与角色是"字符串对码"关系（`User.role` 存 `Role.code`），
    不存在 `users.role_id` 外键，因此按值匹配而不是 JOIN。
    """
    role_code = getattr(node, "role_code", None)
    if not role_code:
        return []
    res = await db.execute(select(User.id).where(User.role == role_code))
    return [row[0] for row in res.all()]


async def expire_overdue_tickets(db: AsyncSession, *, now: Optional[datetime] = None) -> int:
    """把批准后超过有效期仍未开工的票置为 expired。由调度器周期调用。"""
    now = now or datetime.now(timezone.utc)
    res = await db.execute(
        select(WorkTicketInstance).where(
            WorkTicketInstance.status == "approved",
            WorkTicketInstance.valid_to.is_not(None),
            WorkTicketInstance.valid_to < now,
        )
    )
    rows = list(res.scalars().all())
    for instance in rows:
        from_status = instance.status
        instance.status = "expired"
        db.add(
            WorkTicketAuditLog(
                instance_id=instance.id,
                action="expire",
                from_status=from_status,
                to_status="expired",
                detail={"valid_to": instance.valid_to.isoformat() if instance.valid_to else None},
            )
        )
    if rows:
        await db.commit()
    return len(rows)
