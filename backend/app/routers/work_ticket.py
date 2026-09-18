"""作业票 API。"""

import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.work_ticket import (
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketNodeRecord,
    WorkTicketPrintSnapshot,
    WorkTicketTemplate,
)
from app.schemas.work_ticket import GasTestIn, NodeActionIn, OpenTicketIn, TicketOut
from app.services.work_ticket_docx import build_snapshot, content_hash, render_ticket_docx
from app.services.work_ticket_service import (
    SubmitValidationError,
    WorkTicketError,
    act_on_node,
    open_ticket,
    submit_ticket,
)

router = APIRouter(prefix="/work-ticket", tags=["WorkTicket"])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db)):
    """列出启用的作业票模板（本计划只有动火/受限空间）。"""
    res = await db.execute(
        select(WorkTicketTemplate)
        .where(WorkTicketTemplate.is_enabled.is_(True))
        .order_by(WorkTicketTemplate.sort_order)
    )
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
            }
            for t in res.scalars().all()
        ]
    )


@router.get("/tickets")
async def list_tickets(
    enterprise_id: str = Query(...),
    ticket_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """票列表。单入口 + 类型筛选的落点：前端只调这一个端点换筛选条件。"""
    stmt = select(WorkTicketInstance).where(WorkTicketInstance.enterprise_id == enterprise_id)
    if ticket_type:
        stmt = stmt.where(WorkTicketInstance.ticket_type == ticket_type)
    if status:
        stmt = stmt.where(WorkTicketInstance.status == status)
    stmt = stmt.order_by(WorkTicketInstance.created_at.desc())
    res = await db.execute(stmt)
    return _ok([TicketOut.model_validate(t) for t in res.scalars().all()])


@router.post("/tickets")
async def api_open_ticket(
    payload: OpenTicketIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
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
    ticket_id: str, payload: GasTestIn, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == ticket_id))
    if res.scalar_one_or_none() is None:
        raise HTTPException(404, "作业票不存在")
    db.add(WorkTicketGasTest(instance_id=ticket_id, **payload.model_dump()))
    await db.commit()
    return _ok({"ticket_id": ticket_id})


@router.post("/tickets/{ticket_id}/submit")
async def api_submit(
    ticket_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    try:
        out = await submit_ticket(db, instance_id=ticket_id, user_id=getattr(user, "id", None))
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
        out = await act_on_node(
            db,
            instance_id=ticket_id,
            action=payload.action,
            user_id=getattr(user, "id", None) or "",
            opinion=payload.opinion,
        )
    except WorkTicketError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _ok(out)


@router.get("/tickets/{ticket_id}")
async def api_ticket_detail(ticket_id: str, db: AsyncSession = Depends(get_db)):
    """票详情：实例 + 气体检测 + 审批记录。

    计划原文的端点清单只有列表与打印，而详情页要展示"气体检测表 + 审批记录时间线"，
    这两块数据无处可取，故补这一个只读端点（与列表同为统一信封）。
    """
    res = await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == ticket_id))
    instance = res.scalar_one_or_none()
    if instance is None:
        raise HTTPException(404, "作业票不存在")
    gas_res = await db.execute(
        select(WorkTicketGasTest)
        .where(WorkTicketGasTest.instance_id == ticket_id)
        .order_by(WorkTicketGasTest.sampled_at)
    )
    rec_res = await db.execute(
        select(WorkTicketNodeRecord)
        .where(WorkTicketNodeRecord.instance_id == ticket_id)
        .order_by(WorkTicketNodeRecord.created_at)
    )
    return _ok(
        {
            "ticket": TicketOut.model_validate(instance),
            "gas_tests": [
                {
                    "id": g.id,
                    "sampled_at": g.sampled_at,
                    "location": g.location,
                    "gas_type": g.gas_type,
                    "result": g.result,
                    "tester": g.tester,
                    "conclusion": g.conclusion,
                }
                for g in gas_res.scalars().all()
            ],
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
        }
    )


@router.get("/tickets/{ticket_id}/print.docx")
async def api_print_ticket(ticket_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """打印法定票面。**每次打印生成一份不可变快照**，版本号递增。"""
    res = await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == ticket_id))
    instance = res.scalar_one_or_none()
    if instance is None:
        raise HTTPException(404, "作业票不存在")

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
    gas_res = await db.execute(
        select(WorkTicketGasTest)
        .where(WorkTicketGasTest.instance_id == ticket_id)
        .order_by(WorkTicketGasTest.sampled_at)
    )
    gas_tests = [
        {
            "sampled_at": g.sampled_at,
            "location": g.location,
            "gas_type": g.gas_type,
            "result": g.result,
            "tester": g.tester,
            "conclusion": g.conclusion,
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
        safe = re.sub(r'[\\/*?:"<>|]', "_", instance.code)
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
