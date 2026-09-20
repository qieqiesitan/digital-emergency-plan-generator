"""作业票 API。"""

import json
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.work_ticket import (
    WorkTicketAuditLog,
    WorkTicketBatch,
    WorkTicketFlowNode,
    WorkTicketFlowTemplate,
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketNodeRecord,
    WorkTicketPrintSnapshot,
    WorkTicketTemplate,
)
from app.schemas.work_ticket import (
    AiPrefillIn,
    BatchCreateIn,
    BatchOut,
    BatchTicketsIn,
    BatchTransitionIn,
    BatchUpdateIn,
    DraftSaveIn,
    GasTestIn,
    NodeActionIn,
    OpenTicketIn,
    TicketOut,
    TicketTransitionIn,
)
from app.models.enterprise import Enterprise, EnterpriseFloor
from app.models.risk_management import RiskObject, RiskZone
from app.services.access_control import (
    ensure_enterprise_owned,
    ensure_enterprise_visible,
    ensure_ticket_owned,
)
from app.services.work_ticket_docx import build_snapshot, content_hash, render_ticket_docx
from app.services.filename_safety import safe_filename
from app.services.work_ticket_service import (
    SubmitValidationError,
    WorkTicketError,
    WorkTicketPermissionError,
    act_on_node,
    open_ticket,
    submit_ticket,
    member_can_view_ticket,
    tickets_pending_for_user,
    transition_ticket,
)
from app.services.work_ticket_ai_service import prefill as ai_prefill
from app.services.work_ticket_batch import (
    add_tickets,
    batch_counts,
    build_related_map,
    create_batch,
    next_batch_status,
    submit_all,
    tickets_of_batch,
    update_batch_shared,
)
from app.services.work_ticket_prefill import _last_ticket, build_prefill

router = APIRouter(prefix="/work-ticket", tags=["WorkTicket"], dependencies=[Depends(get_current_user)])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


def _gas_query(ticket_id: str, batch_id: str | None):
    """票面检测记录 = 本票检测 + 所属作业包的包级检测（同一次检修常同批检测）。"""
    conditions = [WorkTicketGasTest.instance_id == ticket_id]
    if batch_id:
        conditions.append(WorkTicketGasTest.batch_id == batch_id)
    return (
        select(WorkTicketGasTest)
        .where(or_(*conditions))
        .order_by(WorkTicketGasTest.sampled_at)
    )


async def _visible_ticket(db: AsyncSession, user, ticket_id: str) -> WorkTicketInstance:
    """读/签字入口的可见性判定（失败统一 404，不泄露票据是否存在）。

    - 企业主：可见全部票据；
    - 绑定成员：仅可见「当前节点轮到自己签」或「自己签过」的票。
    """
    instance = (await db.execute(
        select(WorkTicketInstance).where(WorkTicketInstance.id == ticket_id)
    )).scalar_one_or_none()
    if instance is None:
        raise HTTPException(404, "作业票不存在")
    _ent, is_owner = await ensure_enterprise_visible(
        db, user, instance.enterprise_id, detail="作业票不存在"
    )
    if is_owner:
        return instance
    if not await member_can_view_ticket(
        db,
        instance,
        user_id=getattr(user, "id", None),
        enterprise_id=instance.enterprise_id,
    ):
        raise HTTPException(404, "作业票不存在")
    return instance


@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db)):
    """列出启用的作业票模板及其审批流程节点。"""
    res = await db.execute(
        select(WorkTicketTemplate)
        .where(WorkTicketTemplate.is_enabled.is_(True))
        .order_by(WorkTicketTemplate.sort_order)
    )
    templates = list(res.scalars().all())
    template_ids = [t.id for t in templates]
    flows_by_template: dict[str, WorkTicketFlowTemplate] = {}
    nodes_by_flow: dict[str, list[WorkTicketFlowNode]] = {}
    if template_ids:
        flow_res = await db.execute(
            select(WorkTicketFlowTemplate)
            .where(
                WorkTicketFlowTemplate.template_id.in_(template_ids),
                WorkTicketFlowTemplate.is_active.is_(True),
            )
            .order_by(WorkTicketFlowTemplate.created_at)
        )
        flows = list(flow_res.scalars().all())
        for flow in flows:
            flows_by_template.setdefault(flow.template_id, flow)
        flow_ids = [flow.id for flow in flows_by_template.values()]
        if flow_ids:
            node_res = await db.execute(
                select(WorkTicketFlowNode)
                .where(WorkTicketFlowNode.flow_template_id.in_(flow_ids))
                .order_by(WorkTicketFlowNode.sort_order)
            )
            for node in node_res.scalars().all():
                nodes_by_flow.setdefault(node.flow_template_id, []).append(node)
    return _ok(
        [
            {
                "id": t.id,
                "code": t.code,
                "name": t.name,
                "level": t.level,
                "is_graded": t.is_graded,
                "fields": [
                    {
                        "field_key": f.field_key,
                        "label": f.label,
                        "field_type": f.field_type,
                        "group_name": f.group_name,
                        "is_required": f.is_required,
                        "options": f.options,
                        "allow_ai_prefill": f.allow_ai_prefill,
                    }
                    for f in sorted(t.fields, key=lambda x: x.sort_order)
                ],
                "measures": [
                    {
                        "sort_order": m.sort_order,
                        "measure_text": m.measure_text,
                        "article_anchor": m.article_anchor,
                    }
                    for m in sorted(t.measures, key=lambda x: x.sort_order)
                ],
                "flow_nodes": [
                    {
                        "node_key": n.node_key,
                        "name": n.name,
                        "sort_order": n.sort_order,
                        "sign_policy": n.sign_policy,
                        "countersign_units": n.countersign_units or [],
                    }
                    for n in nodes_by_flow.get(
                        flows_by_template.get(t.id).id if flows_by_template.get(t.id) else "",
                        [],
                    )
                ],
            }
            for t in templates
        ]
    )


@router.get("/tickets")
async def list_tickets(
    enterprise_id: str = Query(...),
    ticket_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    assigned_to_me: bool = Query(
        default=False,
        description="只返回当前用户在当前节点可签署的票",
    ),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """票列表。单入口 + 类型筛选的落点：前端只调这一个端点换筛选条件。"""
    _ent, is_owner = await ensure_enterprise_visible(db, user, enterprise_id)
    stmt = select(WorkTicketInstance).where(WorkTicketInstance.enterprise_id == enterprise_id)
    if ticket_type:
        stmt = stmt.where(WorkTicketInstance.ticket_type == ticket_type)
    if status:
        stmt = stmt.where(WorkTicketInstance.status == status)
    stmt = stmt.order_by(WorkTicketInstance.created_at.desc())
    res = await db.execute(stmt)
    instances = list(res.scalars().all())
    # 企业主看全部；绑定成员（非所有者）无论是否显式传参，都只看到与自己有关的票
    if assigned_to_me or not is_owner:
        instances = await tickets_pending_for_user(
            db,
            instances,
            user_id=getattr(user, "id", None),
            enterprise_id=enterprise_id,
        )
    return _ok([TicketOut.model_validate(t) for t in instances])


@router.post("/tickets")
async def api_open_ticket(
    payload: OpenTicketIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        await ensure_enterprise_owned(db, user, payload.enterprise_id)
        instance = await open_ticket(
            db,
            enterprise_id=payload.enterprise_id,
            enterprise_code=payload.enterprise_code,
            ticket_type=payload.ticket_type,
            template_id=payload.template_id,
            level=payload.level,
            values=payload.values,
            user_id=getattr(user, "id", None),
        )
    except WorkTicketError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(TicketOut.model_validate(instance))


@router.post("/tickets/{ticket_id}/gas-tests")
async def api_add_gas_test(
    ticket_id: str,
    payload: GasTestIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await ensure_ticket_owned(db, user, ticket_id)
    db.add(WorkTicketGasTest(instance_id=ticket_id, **payload.model_dump()))
    await db.commit()
    return _ok({"ticket_id": ticket_id})


@router.post("/tickets/{ticket_id}/submit")
async def api_submit(
    ticket_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    try:
        await ensure_ticket_owned(db, user, ticket_id)
        out = await submit_ticket(db, instance_id=ticket_id, user_id=getattr(user, "id", None))
    except WorkTicketPermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except SubmitValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except WorkTicketError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _ok(out)


@router.post("/tickets/{ticket_id}/node-action")
async def api_node_action(
    ticket_id: str,
    payload: NodeActionIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        await _visible_ticket(db, user, ticket_id)
        out = await act_on_node(
            db,
            instance_id=ticket_id,
            action=payload.action,
            user_id=getattr(user, "id", None) or "",
            opinion=payload.opinion,
        )
    except WorkTicketPermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except WorkTicketError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _ok(out)


@router.post("/tickets/{ticket_id}/transition")
async def api_transition_ticket(
    ticket_id: str,
    payload: TicketTransitionIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """生命周期推进：开始作业 / 完工 / 归档 / 作废（仅企业主；每次变更都写审计日志）。

    审批节点上的「同意/退回」走 `/node-action`，两者语义不同，故分开两个端点。
    """
    try:
        await ensure_ticket_owned(db, user, ticket_id)
        out = await transition_ticket(
            db,
            instance_id=ticket_id,
            action=payload.action,
            user_id=getattr(user, "id", None),
            opinion=payload.opinion,
        )
    except WorkTicketError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _ok(out)


@router.get("/tickets/{ticket_id}")
async def api_ticket_detail(
    ticket_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    """票详情：实例 + 气体检测 + 审批记录。

    计划原文的端点清单只有列表与打印，而详情页要展示"气体检测表 + 审批记录时间线"，
    这两块数据无处可取，故补这一个只读端点（与列表同为统一信封）。
    """
    instance = await _visible_ticket(db, user, ticket_id)
    gas_res = await db.execute(_gas_query(ticket_id, instance.batch_id))
    rec_res = await db.execute(
        select(WorkTicketNodeRecord)
        .where(WorkTicketNodeRecord.instance_id == ticket_id)
        .order_by(WorkTicketNodeRecord.created_at)
    )
    audit_res = await db.execute(
        select(WorkTicketAuditLog)
        .where(WorkTicketAuditLog.instance_id == ticket_id)
        .order_by(WorkTicketAuditLog.created_at)
    )
    return _ok(
        {
            "ticket": TicketOut.model_validate(instance),
            "gas_tests": [_gas_out(g) for g in gas_res.scalars().all()],
            "node_records": [
                {
                    "id": r.id,
                    "node_key": r.node_key,
                    "action": r.action,
                    "acted_by": r.acted_by,
                    "opinion": r.opinion,
                    "created_at": r.created_at,
                }
                for r in rec_res.scalars().all()
            ],
            # 全量流转留痕（开票/提交/审批/开始作业/完工/归档/作废/过期）——
            # 审批记录只覆盖审批节点，生命周期动作只在审计表里有记录（本轮补）
            "audit_logs": [
                {
                    "id": a.id,
                    "action": a.action,
                    "from_status": a.from_status,
                    "to_status": a.to_status,
                    "detail": a.detail,
                    "acted_by": a.acted_by,
                    "created_at": a.created_at,
                }
                for a in audit_res.scalars().all()
            ],
        }
    )


@router.get("/tickets/{ticket_id}/print.docx")
async def api_print_ticket(ticket_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """打印法定票面。**每次打印生成一份不可变快照**，版本号递增。"""
    instance = await _visible_ticket(db, user, ticket_id)

    tpl_res = await db.execute(
        select(WorkTicketTemplate).where(WorkTicketTemplate.id == instance.template_id)
    )
    template = tpl_res.scalar_one_or_none()

    rec_res = await db.execute(
        select(WorkTicketNodeRecord)
        .where(WorkTicketNodeRecord.instance_id == ticket_id)
        .order_by(WorkTicketNodeRecord.created_at)
    )
    node_records = [
        {
            "node_key": r.node_key,
            "action": r.action,
            "acted_by": r.acted_by,
            "opinion": r.opinion,
            "created_at": r.created_at,
        }
        for r in rec_res.scalars().all()
    ]
    gas_res = await db.execute(_gas_query(ticket_id, instance.batch_id))
    gas_tests = [
        {
            "sampled_at": g.sampled_at,
            "location": g.location,
            "gas_type": g.gas_type,
            "result": g.result,
            "tester": g.tester,
            "conclusion": g.conclusion,
            "origin": "batch" if g.batch_id else "ticket",
        }
        for g in gas_res.scalars().all()
    ]

    snapshot = build_snapshot(
        instance=instance, template=template, node_records=node_records, gas_tests=gas_tests
    )
    snap_res = await db.execute(
        select(WorkTicketPrintSnapshot)
        .where(WorkTicketPrintSnapshot.instance_id == ticket_id)
        .order_by(WorkTicketPrintSnapshot.version.desc())
        .limit(1)
    )
    latest = snap_res.scalar_one_or_none()
    db.add(
        WorkTicketPrintSnapshot(
            instance_id=ticket_id,
            version=(latest.version + 1) if latest else 1,
            content_hash=content_hash(snapshot),
            snapshot=snapshot,
            printed_by=getattr(user, "id", None),
        )
    )
    await db.commit()

    try:
        doc = render_ticket_docx(snapshot=snapshot)
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        safe = safe_filename(instance.code, fallback="ticket")
        filename = f"{safe}.docx"
        filepath = os.path.join(settings.EXPORT_DIR, filename)
        doc.save(filepath)
    except Exception as exc:
        raise HTTPException(500, f"票面生成失败: {exc}") from exc

    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/prefill")
async def api_prefill(
    enterprise_id: str = Query(...),
    template_id: str = Query(...),
    level: str | None = Query(default=None),
    risk_object_id: str | None = Query(default=None),
    fire_method: str | None = Query(default=None),
    scenario: str | None = Query(
        default=None, description='作业情景 JSON，如 {"in_tank_area": false}'
    ),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """确定性预填：按来源优先级取数，不调用 AI（进页面即调，必须快）。"""
    await ensure_enterprise_owned(db, user, enterprise_id)
    template = (
        await db.execute(
            select(WorkTicketTemplate).where(WorkTicketTemplate.id == template_id)
        )
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(404, "模板不存在")
    location_text = None
    zone_name = None
    if risk_object_id:
        obj = (
            await db.execute(select(RiskObject).where(RiskObject.id == risk_object_id))
        ).scalar_one_or_none()
        if obj is not None:
            location_text = obj.location or obj.name
            if obj.zone_id:
                zone = (
                    await db.execute(select(RiskZone).where(RiskZone.id == obj.zone_id))
                ).scalar_one_or_none()
                zone_name = zone.name if zone is not None else None
    scenario_dict = None
    if scenario:
        try:
            parsed = json.loads(scenario)
            scenario_dict = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            scenario_dict = None
    payload = await build_prefill(
        db,
        enterprise_id=enterprise_id,
        template=template,
        level=level,
        risk_object_location=location_text,
        zone_name=zone_name,
        fire_method=fire_method,
        scenario=scenario_dict,
    )
    return _ok(payload)


@router.get("/last-ticket")
async def api_last_ticket(
    enterprise_id: str = Query(...),
    template_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """上次同类票摘要，供开票页「参考上次」入口（无历史票时返回 null）。"""
    await ensure_enterprise_visible(db, user, enterprise_id)
    last = await _last_ticket(db, enterprise_id=enterprise_id, template_id=template_id)
    if last is None:
        return _ok(None)
    values = last.values or {}
    return _ok(
        {
            "id": last.id,
            "code": last.code,
            "created_at": last.created_at,
            "work_content": values.get("work_content"),
            "risk_identification": values.get("risk_identification"),
        }
    )


@router.get("/locations")
async def api_locations(
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """作业地点候选：楼层 → 区域 → 对象（含地点文本）。"""
    await ensure_enterprise_visible(db, user, enterprise_id)
    floors = (
        (
            await db.execute(
                select(EnterpriseFloor)
                .where(EnterpriseFloor.enterprise_id == enterprise_id)
                .order_by(EnterpriseFloor.sort_order)
            )
        )
        .scalars()
        .all()
    )
    zones = (
        (
            await db.execute(
                select(RiskZone)
                .where(RiskZone.enterprise_id == enterprise_id)
                .order_by(RiskZone.sort_order)
            )
        )
        .scalars()
        .all()
    )
    objects = (
        (await db.execute(select(RiskObject).where(RiskObject.enterprise_id == enterprise_id)))
        .scalars()
        .all()
    )
    return _ok(
        {
            "floors": [{"id": f.id, "name": f.name} for f in floors],
            "zones": [
                {"id": z.id, "name": z.name, "floor_id": z.floor_id} for z in zones
            ],
            "objects": [
                {
                    "id": o.id,
                    "name": o.name,
                    "location": o.location,
                    "zone_id": o.zone_id,
                    "floor_id": o.floor_id,
                }
                for o in objects
            ],
        }
    )


@router.post("/ai/prefill")
async def api_ai_prefill(
    payload: AiPrefillIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AI 预填：用户显式点击才调用；未配置/停用/超时/异常一律降级返回。"""
    await ensure_enterprise_owned(db, user, payload.enterprise_id)
    from app.services.ai_config_service import get_system_ai_config

    ai_config = await get_system_ai_config(db)
    result = await ai_prefill(
        ticket_type=payload.ticket_type,
        level=payload.level,
        location_text=None,
        work_content=payload.work_content,
        ai_config=ai_config,
    )
    return _ok(result)


@router.patch("/tickets/{ticket_id}")
async def api_save_draft(
    ticket_id: str,
    payload: DraftSaveIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """草稿保存（仅 draft 状态）。"""
    instance = await ensure_ticket_owned(db, user, ticket_id)
    if instance.status != "draft":
        raise HTTPException(409, "只有草稿状态的作业票可以保存")
    instance.values = payload.values
    instance.values_meta = payload.values_meta
    instance.measures_meta = payload.measures_meta
    await db.commit()
    return _ok(TicketOut.model_validate(instance))


# ── 作业包（一次检修的同地点同时段多张票） ────────────────────────────────


async def _batch_owned(db: AsyncSession, user, batch_id: str) -> WorkTicketBatch:
    batch = (
        await db.execute(select(WorkTicketBatch).where(WorkTicketBatch.id == batch_id))
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(404, "作业包不存在")
    await ensure_enterprise_owned(db, user, batch.enterprise_id, detail="作业包不存在")
    return batch


def _gas_out(gas: WorkTicketGasTest) -> dict:
    return {
        "id": gas.id,
        "sampled_at": gas.sampled_at,
        "location": gas.location,
        "gas_type": gas.gas_type,
        "result": gas.result,
        "tester": gas.tester,
        "conclusion": gas.conclusion,
        "origin": "batch" if gas.batch_id else "ticket",
    }


@router.post("/batches")
async def api_create_batch(
    payload: BatchCreateIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await ensure_enterprise_owned(db, user, payload.enterprise_id)
    batch = await create_batch(
        db,
        enterprise_id=payload.enterprise_id,
        payload=payload,
        user_id=getattr(user, "id", None),
    )
    return _ok(BatchOut.model_validate(batch))


@router.get("/batches")
async def api_list_batches(
    enterprise_id: str = Query(...),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await ensure_enterprise_visible(db, user, enterprise_id)
    stmt = select(WorkTicketBatch).where(WorkTicketBatch.enterprise_id == enterprise_id)
    if status:
        stmt = stmt.where(WorkTicketBatch.status == status)
    rows = (
        await db.execute(stmt.order_by(WorkTicketBatch.created_at.desc()))
    ).scalars().all()
    return _ok([BatchOut.model_validate(batch) for batch in rows])


@router.get("/batches/{batch_id}")
async def api_batch_detail(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    batch = await _batch_owned(db, user, batch_id)
    tickets, gas = await tickets_of_batch(db, batch_id=batch_id)
    return _ok(
        {
            "batch": BatchOut.model_validate(batch),
            "tickets": [TicketOut.model_validate(t) for t in tickets],
            "package_gas_tests": [_gas_out(g) for g in gas],
        }
    )


@router.patch("/batches/{batch_id}")
async def api_update_batch(
    batch_id: str,
    payload: BatchUpdateIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    batch = await _batch_owned(db, user, batch_id)
    return _ok(await update_batch_shared(db, batch=batch, payload=payload))


@router.post("/batches/{batch_id}/tickets")
async def api_add_batch_tickets(
    batch_id: str,
    payload: BatchTicketsIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    batch = await _batch_owned(db, user, batch_id)
    enterprise = (
        await db.execute(select(Enterprise).where(Enterprise.id == batch.enterprise_id))
    ).scalar_one_or_none()
    enterprise_code = (getattr(enterprise, "credit_code", None) or batch.enterprise_id)[:20]
    try:
        created = await add_tickets(
            db,
            batch=batch,
            enterprise_code=enterprise_code,
            specs=[spec.model_dump() for spec in payload.tickets],
            user_id=getattr(user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok([TicketOut.model_validate(t) for t in created])


@router.delete("/batches/{batch_id}/tickets/{ticket_id}")
async def api_remove_batch_ticket(
    batch_id: str,
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await _batch_owned(db, user, batch_id)
    ticket = (
        await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == ticket_id))
    ).scalar_one_or_none()
    if ticket is None or ticket.batch_id != batch_id:
        raise HTTPException(404, "作业票不存在")
    if ticket.status != "draft":
        raise HTTPException(409, "只有草稿状态的作业票可以移出作业包")
    await db.delete(ticket)
    await db.flush()
    # 同步包内其余票的关联票号：移除一张票后，其他票的 related_tickets 必须一致
    rest, _ = await tickets_of_batch(db, batch_id=batch_id, include_package_gas=False)
    related = build_related_map([(t.id, t.code) for t in rest])
    for other in rest:
        values = dict(other.values or {})
        values["related_tickets"] = related[other.id]
        other.values = values
    await db.commit()
    return _ok({"removed": ticket_id, "affected": len(rest)})


@router.post("/batches/{batch_id}/gas-tests")
async def api_add_package_gas_test(
    batch_id: str,
    payload: GasTestIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """包级检测：同包内的动火/受限空间票共享（不豁免 30 分钟时效）。"""
    await _batch_owned(db, user, batch_id)
    db.add(WorkTicketGasTest(batch_id=batch_id, **payload.model_dump()))
    await db.commit()
    return _ok({"batch_id": batch_id})


@router.post("/batches/{batch_id}/submit-all")
async def api_submit_all(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """逐票提交：失败的票单独返回，不影响其他票。"""
    await _batch_owned(db, user, batch_id)
    return _ok(await submit_all(db, batch_id=batch_id, user_id=getattr(user, "id", None)))


@router.post("/batches/{batch_id}/transition")
async def api_batch_transition(
    batch_id: str,
    payload: BatchTransitionIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    batch = await _batch_owned(db, user, batch_id)
    submitted, total = await batch_counts(db, batch_id=batch_id)
    try:
        batch.status = next_batch_status(
            batch.status, submitted=submitted, total=total, action=payload.action
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return _ok(BatchOut.model_validate(batch))
