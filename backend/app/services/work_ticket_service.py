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

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.user import User
from app.models.work_ticket import (
    WorkTicketAuditLog,
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketFlowTemplate,
    WorkTicketNodeRecord,
    WorkTicketFlowNode,
    WorkTicketTemplate,
)
from app.services.work_ticket_flow import (
    can_transition,
    lifecycle_target,
    LIFECYCLE_LABELS,
    next_node,
    sign_requirement_met,
)

logger = logging.getLogger("work_ticket_service")

GAS_TEST_MAX_AGE = timedelta(minutes=30)

# 强制气体检测的作业类型。依据 GB 30871-2022 第 5 章（动火）与第 6 章（受限空间）：
# 这两类作业在作业前及作业过程中必须进行气体分析。其余类型不作强制。
GAS_TEST_REQUIRED_TYPES = ("DHZY", "YXKJ")


def requires_gas_test(ticket_type: str) -> bool:
    """该类型是否强制气体检测。"""
    return ticket_type in GAS_TEST_REQUIRED_TYPES


class SubmitValidationError(ValueError):
    """提交前校验未通过。"""


class WorkTicketError(ValueError):
    """作业票状态或数据错误。"""


class WorkTicketPermissionError(WorkTicketError):
    """当前用户无权执行该审批动作（W0-2：操作人资格校验）。"""


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
    values_meta: Optional[dict] = None,
    measures_meta: Optional[dict] = None,
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

    # AI 生成的值必须逐个人工确认（规格 §2.3）。只针对 source=ai，
    # 其他来源与无 meta 的老票一律不新增阻断。
    for field in getattr(template, "fields", []) or []:
        if not getattr(field, "is_required", False):
            continue
        meta = (values_meta or {}).get(field.field_key) or {}
        if meta.get("source") == "ai" and not meta.get("confirmed_at"):
            errors.append(
                f"「{getattr(field, 'label', field.field_key)}」为 AI 生成内容，尚未经人工确认"
            )

    mandatory = [m for m in measures if getattr(m, "is_mandatory", True)]
    # 表态口径：confirmed_measures（老路径）∪ measures_meta 中的 confirmed/not_applicable
    stated = set(confirmed_measure_orders or [])
    for key, meta in (measures_meta or {}).items():
        if not isinstance(meta, dict):
            continue
        state = meta.get("state")
        if state == "not_applicable" and not (meta.get("reason_text") or "").strip():
            errors.append(f"第 {key} 条措施标记为「本票不涉及」，但未填写理由")
        if state in ("confirmed", "not_applicable"):
            try:
                stated.add(int(key))
            except (TypeError, ValueError):
                continue
    missing = [m for m in mandatory if getattr(m, "sort_order", 0) not in stated]
    if missing:
        errors.append(
            f"还有 {len(missing)} 条安全措施未表态（如「{missing[0].measure_text[:20]}…」）"
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
    values_meta: Optional[dict] = None,
    measures_meta: Optional[dict] = None,
    batch_id: Optional[str] = None,
    user_id: Optional[str] = None,
    commit: bool = True,
) -> WorkTicketInstance:
    """开票（草稿态）。编号冲突时重试，最终由数据库唯一约束兜底。

    `commit=False` 供作业包批量生成使用：整包建票必须同事务，
    否则中途失败会留下半成品包（见 services/work_ticket_batch.add_tickets）。
    """
    day = datetime.now(timezone.utc)
    prefix = f"{ticket_type}-{enterprise_code}-{day.strftime('%Y%m%d')}-"
    # 并发发号保护：同一企业内「读 MAX(seq) → 插入」必须串行，否则并发开票会撞
    # uq_wti_ent_code 唯一约束（实测 8 并发 → 6 个 500 而非重试）。
    # 锁粒度=单企业行，持锁时间=一次 seq 查询 + INSERT，不影响其他企业。
    await db.execute(
        select(Enterprise.id).where(Enterprise.id == enterprise_id).with_for_update()
    )
    res = await db.execute(
        select(WorkTicketInstance.code).where(
            WorkTicketInstance.enterprise_id == enterprise_id,
            WorkTicketInstance.code.like(f"{prefix}%"),
        )
    )
    seq = next_code_seq([row[0] for row in res.all()])
    flow_template_id = await resolve_flow_template_id(db, template_id)

    instance = WorkTicketInstance(
        enterprise_id=enterprise_id,
        template_id=template_id,
        flow_template_id=flow_template_id,
        code=build_ticket_code(ticket_type, enterprise_code, day, seq),
        ticket_type=ticket_type,
        level=level,
        status="draft",
        values=values or {},
        values_meta=values_meta or {},
        measures_meta=measures_meta or {},
        batch_id=batch_id,
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
    if commit:
        await db.commit()
    else:
        await db.flush()
    return instance


async def resolve_flow_template_id(db: AsyncSession, template_id: str) -> str:
    """取模板对应的启用中审批流程。

    计划原文的 `open_ticket` 没有绑定 `flow_template_id`，而 `_advance_to_first_active_node`
    依赖它推进节点——不绑定的话每张票提交时都会抛"作业票未绑定审批流程"。
    这里在开票时解析并绑定；模板没配流程则当场报错，不留下永远提交不了的草稿。
    """
    res = await db.execute(
        select(WorkTicketFlowTemplate)
        .where(
            WorkTicketFlowTemplate.template_id == template_id,
            WorkTicketFlowTemplate.is_active.is_(True),
        )
        .order_by(WorkTicketFlowTemplate.created_at)
        .limit(1)
    )
    flow = res.scalar_one_or_none()
    if flow is None:
        raise WorkTicketError("该作业票模板尚未配置审批流程，无法开票")
    return flow.id


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
    owner_id = (await db.execute(
        select(Enterprise.user_id).where(Enterprise.id == instance.enterprise_id)
    )).scalar_one_or_none()
    if user_id and owner_id and user_id != owner_id:
        raise WorkTicketPermissionError("只有企业所有者可以提交作业票")

    tpl_res = await db.execute(
        select(WorkTicketTemplate).where(WorkTicketTemplate.id == instance.template_id)
    )
    template = tpl_res.scalar_one_or_none()
    values = instance.values or {}
    # 检测记录 = 本票检测 + 所属作业包的包级检测（同一次检修常同批检测）。
    # 30 分钟时效规则对包级记录同样适用，不做豁免。
    gas_conditions = [WorkTicketGasTest.instance_id == instance_id]
    if instance.batch_id:
        gas_conditions.append(WorkTicketGasTest.batch_id == instance.batch_id)
    gas_res = await db.execute(select(WorkTicketGasTest).where(or_(*gas_conditions)))
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
        requires_gas_test=requires_gas_test(instance.ticket_type),
        values_meta=instance.values_meta or {},
        measures_meta=instance.measures_meta or {},
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

    node_res = await db.execute(
        select(WorkTicketFlowNode).where(
            WorkTicketFlowNode.flow_template_id == instance.flow_template_id,
            WorkTicketFlowNode.node_key == instance.current_node_key,
        )
    )
    node = node_res.scalar_one_or_none()
    if node is None:
        raise WorkTicketError("当前节点配置缺失")

    eligible = await eligible_users_for_node(db, node, enterprise_id=instance.enterprise_id)
    if not eligible:
        raise WorkTicketPermissionError(
            "当前节点未配置会签资格人，请先在「组织与人员」中为该岗位/单位配置成员"
        )
    if not user_id or user_id not in eligible:
        raise WorkTicketPermissionError("当前用户不是该节点的会签人")

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

    rec_res = await db.execute(
        select(WorkTicketNodeRecord.acted_by).where(
            WorkTicketNodeRecord.instance_id == instance_id,
            WorkTicketNodeRecord.node_key == node.node_key,
            WorkTicketNodeRecord.action == "approve",
        )
    )
    signed = [row[0] for row in rec_res.all()]
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


async def eligible_users_for_node(
    db: AsyncSession,
    node,
    *,
    enterprise_id: Optional[str] = None,
) -> list[str]:
    """取节点的会签资格人。

    两种来源：
    - `role_code`：按角色取人（适用于"安全管理部门审批"这类）；
    - `countersign_units`：按部门取人（适用于动土这种多单位会签）。

    两者都为空时返回空列表——会签将判定为未完成，**不会被静默跳过**。
    本项目的公司组织节点保存在 `enterprises.org_structure` JSONB，成员任职保存在
    `member_positions`（主岗 + 兼岗），因此按单位取人要沿组织树向上匹配、并覆盖兼岗。
    尚未回填 `member_positions` 的旧企业回落到 `enterprise_members.org_node_id`。
    """
    units = {u for u in (getattr(node, "countersign_units", None) or []) if u}
    role_code = (getattr(node, "role_code", None) or "").strip() or None

    async def _by_system_role() -> list[str]:
        if not role_code:
            return []
        # 本项目的用户与角色是"字符串对码"关系（`User.role` 存 `Role.code`），
        # 不存在 `users.role_id` 外键，因此按值匹配而不是 JOIN。
        res = await db.execute(select(User.id).where(User.role == role_code))
        return [row[0] for row in res.all()]

    names = set(units)
    if role_code and not units:
        # 标准附录里的审批岗位（如「主管领导」「安全管理部门」）保存在 role_code，
        # 与系统角色码（admin/user/super_admin）不同名，按组织岗位名匹配成员。
        names.add(role_code)
    if not names:
        return []

    if not enterprise_id:
        if units:
            res = await db.execute(
                select(EnterpriseMember.user_id).where(EnterpriseMember.user_id.is_not(None))
            )
            return [row[0] for row in res.all()]
        return await _by_system_role()

    from app.models.enterprise_org import MemberPosition

    res = await db.execute(
        select(EnterpriseMember.user_id, MemberPosition.org_node_id)
        .join(MemberPosition, MemberPosition.member_id == EnterpriseMember.id)
        .where(
            EnterpriseMember.enterprise_id == enterprise_id,
            EnterpriseMember.enabled.is_(True),
            EnterpriseMember.user_id.is_not(None),
        )
    )
    # 同一人可能有多条任职，去重后逐一判定
    members = sorted({(row[0], row[1]) for row in res.all()})
    if not members:
        # 旧企业兜底：任职表尚未回填时仍按主岗镜像列取人，行为不退化
        res = await db.execute(
            select(EnterpriseMember.user_id, EnterpriseMember.org_node_id).where(
                EnterpriseMember.enterprise_id == enterprise_id,
                EnterpriseMember.enabled.is_(True),
                EnterpriseMember.user_id.is_not(None),
            )
        )
        members = [(row[0], row[1]) for row in res.all()]
    ent_res = await db.execute(
        select(Enterprise.org_structure).where(Enterprise.id == enterprise_id)
    )
    org_nodes = ent_res.scalar_one_or_none() or []
    node_map = {
        n.get("id"): n
        for n in org_nodes
        if isinstance(n, dict) and n.get("id")
    }

    def _in_names(org_node_id: Optional[str]) -> bool:
        current = org_node_id
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            org_node = node_map.get(current)
            if not org_node:
                return False
            if org_node.get("name") in names:
                return True
            current = org_node.get("parent_id")
        return False

    matched = [user_id for user_id, org_node_id in members if _in_names(org_node_id)]
    if matched:
        return matched
    # 组织树未命中时兼容"role_code 就是系统角色码"的既有配置
    return await _by_system_role()


async def expire_overdue_tickets(db: AsyncSession, *, now: Optional[datetime] = None) -> int:
    """把批准后超过有效期仍未开工的票置为 expired。由调度器/运维端点周期调用。"""
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


# 集群安全：与隐患扫描同一套 advisory lock 思路，避免多 worker 重复处理
WORK_TICKET_EXPIRY_LOCK_KEY = 0x57544B31  # "WTK1"


async def expire_overdue_tickets_leader_only(
    db: AsyncSession, *, now: Optional[datetime] = None
) -> Optional[int]:
    """集群安全入口：只有抢到 advisory lock 的进程执行过期扫描；抢不到返回 None。

    2026-09-18 补：`expire_overdue_tickets` 的 docstring 一直写着"由调度器周期调用"，
    但全仓没有任何调用方——于是批准后超过有效期的作业票**永远停在「已批准」**，
    状态机里的 `expired` 只能靠用户手动点"开始作业"触发（N-16 加的超期保护）。
    """
    from sqlalchemy import text

    locked = (await db.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": WORK_TICKET_EXPIRY_LOCK_KEY}
    )).scalar()
    if not locked:
        logger.debug("作业票过期扫描：其他 worker 正在执行，本进程跳过")
        return None
    try:
        return await expire_overdue_tickets(db, now=now)
    finally:
        await db.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": WORK_TICKET_EXPIRY_LOCK_KEY}
        )


# --- 审批待办（"我的待办"）-------------------------------------------------


async def _current_node_sign_state(
    db: AsyncSession,
    instances: Sequence,
    *,
    enterprise_id: str,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """批量解析审批中票据的「当前节点可签人」与「当前节点已签人」。

    返回 `(eligible_by_instance, signed_by_instance)`；非 approving / 无当前节点 /
    节点配置缺失的票不会出现在结果里（调用方据此自然过滤掉）。
    """
    targets = [i for i in instances if i.status == "approving" and i.current_node_key]
    if not targets:
        return {}, {}

    flow_ids = {i.flow_template_id for i in targets if i.flow_template_id}
    nodes: dict[tuple[str, str], object] = {}
    if flow_ids:
        node_res = await db.execute(
            select(WorkTicketFlowNode).where(
                WorkTicketFlowNode.flow_template_id.in_(list(flow_ids))
            )
        )
        nodes = {(n.flow_template_id, n.node_key): n for n in node_res.scalars().all()}

    eligible: dict[str, set[str]] = {}
    for inst in targets:
        node = nodes.get((inst.flow_template_id, inst.current_node_key))
        if node is None:
            continue
        users = await eligible_users_for_node(db, node, enterprise_id=enterprise_id)
        eligible[inst.id] = {u for u in users if u}
    if not eligible:
        return {}, {}

    node_key_by_instance = {i.id: i.current_node_key for i in targets}
    signed: dict[str, set[str]] = {}
    rec_res = await db.execute(
        select(
            WorkTicketNodeRecord.instance_id,
            WorkTicketNodeRecord.node_key,
            WorkTicketNodeRecord.acted_by,
        ).where(
            WorkTicketNodeRecord.instance_id.in_(list(eligible.keys())),
            WorkTicketNodeRecord.action == "approve",
        )
    )
    for instance_id, node_key, acted_by in rec_res.all():
        if acted_by and node_key == node_key_by_instance.get(instance_id):
            signed.setdefault(instance_id, set()).add(acted_by)
    return eligible, signed


async def tickets_pending_for_user(
    db: AsyncSession,
    instances: Sequence,
    *,
    user_id: Optional[str],
    enterprise_id: str,
) -> list:
    """筛出「当前审批节点轮到该用户签、且该用户还没签」的票（前端"我的待办"）。"""
    if not user_id:
        return []
    eligible, signed = await _current_node_sign_state(db, instances, enterprise_id=enterprise_id)
    return [
        inst
        for inst in instances
        if inst.id in eligible
        and user_id in eligible[inst.id]
        and user_id not in signed.get(inst.id, set())
    ]


async def member_can_view_ticket(
    db: AsyncSession,
    instance,
    *,
    user_id: Optional[str],
    enterprise_id: str,
) -> bool:
    """非企业主的成员可见性：轮到自己签，或自己在这张票上签过（可回看/打印）。"""
    if not user_id:
        return False
    pending = await tickets_pending_for_user(
        db, [instance], user_id=user_id, enterprise_id=enterprise_id
    )
    if pending:
        return True
    acted = (await db.execute(
        select(WorkTicketNodeRecord.id).where(
            WorkTicketNodeRecord.instance_id == instance.id,
            WorkTicketNodeRecord.acted_by == user_id,
        ).limit(1)
    )).scalar_one_or_none()
    return acted is not None


# --- 生命周期推进（开始作业 / 完工 / 归档 / 作废）-------------------------


async def transition_ticket(
    db: AsyncSession,
    *,
    instance_id: str,
    action: str,
    user_id: Optional[str] = None,
    opinion: Optional[str] = None,
) -> dict:
    """按状态机推进作业票生命周期。

    `approved --start--> working --finish--> finished --close--> closed`，
    `cancel` 可从 draft/submitted/approving/approved 触发（状态机 TRANSITIONS 决定）。
    没有这组动作时，票批准后就永远停在「已批准」，无法完工与归档（本轮补）。

    特殊保护：批准后若已超过有效期（`valid_to < now`）不允许开工，
    票据直接置为 `expired` 并留痕，提示重新开票。
    """
    instance = (await db.execute(
        select(WorkTicketInstance).where(WorkTicketInstance.id == instance_id)
    )).scalar_one_or_none()
    if instance is None:
        raise WorkTicketError("作业票不存在")

    target = lifecycle_target(action)  # 未知动作 → FlowError（ValueError 子类）
    if not can_transition(instance.status, action):
        raise WorkTicketError(
            f"当前状态（{instance.status}）不能执行「{LIFECYCLE_LABELS.get(action, action)}」"
        )

    now = datetime.now(timezone.utc)
    if action == "start" and instance.valid_to and instance.valid_to < now:
        from_status = instance.status
        instance.status = "expired"
        db.add(WorkTicketAuditLog(
            instance_id=instance.id,
            action="expire",
            from_status=from_status,
            to_status="expired",
            detail={"reason": "超过有效期未开工", "valid_to": instance.valid_to.isoformat()},
            acted_by=user_id,
        ))
        await db.commit()
        raise WorkTicketError("作业票已超过有效期，不能开工；请重新开票")

    from_status = instance.status
    instance.status = target
    if action in ("finish", "close", "cancel"):
        # 终态/完工后不应再指向审批节点
        instance.current_node_key = None
        instance.current_order = 0
    db.add(WorkTicketAuditLog(
        instance_id=instance.id,
        action=action,
        from_status=from_status,
        to_status=target,
        detail={"opinion": opinion} if opinion else {},
        acted_by=user_id,
    ))
    await db.commit()
    await db.refresh(instance)
    return {
        "instance_id": instance.id,
        "action": action,
        "from_status": from_status,
        "status": instance.status,
    }
