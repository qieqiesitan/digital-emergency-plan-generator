"""隐患排查治理路由（任务 3）：排查计划 CRUD + 任务/清单项端点。

前缀 `/enterprises/{enterprise_id}/hazard-inspection`：
- `/plans`：计划 CRUD（写=企业主/企业管理员成员，读=企业主/启用成员）
- `/tasks`：任务列表/详情/核对提交/一键转隐患

权限与归属：
- 读路径企业归属校验（不属于 → 404）；写路径企业主或 `enterprise_members`
  中 role=enterprise_admin 且 enabled 的成员（其余 403），对齐既有
  `enterprise_org.py` 的 `_get_owned_ent`/403 惯例，并将成员纳入读范围
  （责任人/执行人场景必须能访问任务）。
- 全部响应走 `ApiResponse` 信封（code==0 + data）。
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.hazard_management import (
    HazardChecklistTemplate,
    HazardInspectionItem,
    HazardInspectionPlan,
    HazardInspectionTask,
    HazardRecord,
)
from app.models.risk_management import RiskZone
from app.schemas.common import ApiResponse
from app.services.hazard_service import generate_tasks_for_plan, next_hazard_code


router = APIRouter(prefix="/enterprises/{enterprise_id}/hazard-inspection", tags=["Hazard Management"])

PLAN_CATEGORIES = {"daily", "comprehensive", "special", "holiday"}
PLAN_FREQUENCIES = {"daily", "weekly", "monthly", "custom"}
ITEM_RESULTS = {"pending", "normal", "abnormal", "na"}


# ── 请求模型（B 规格 §5.1-5.3） ──

class PlanCreate(BaseModel):
    name: str = Field(..., max_length=255)
    category: str
    frequency: str
    weekdays: Optional[list[int]] = None
    zone_ids: list[str]
    template_id: Optional[str] = None
    responsible_user_id: Optional[str] = None
    ai_suggestion: Optional[dict] = None
    enabled: Optional[bool] = True


class PlanUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = None
    frequency: Optional[str] = None
    weekdays: Optional[list[int]] = None
    zone_ids: Optional[list[str]] = None
    template_id: Optional[str] = None
    responsible_user_id: Optional[str] = None
    ai_suggestion: Optional[dict] = None
    enabled: Optional[bool] = None


class TaskItemSubmit(BaseModel):
    item_id: str
    result: str
    remark: Optional[str] = None
    photo_urls: Optional[list[str]] = None


class TaskSubmitBody(BaseModel):
    items: list[TaskItemSubmit]


class ToRecordBody(BaseModel):
    item_id: str
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


# ── 响应序列化 ──

def _dt(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _plan_dict(plan) -> dict:
    return {
        "id": plan.id,
        "enterprise_id": plan.enterprise_id,
        "name": plan.name,
        "category": plan.category,
        "frequency": plan.frequency,
        "weekdays": plan.weekdays,
        "zone_ids": plan.zone_ids,
        "template_id": plan.template_id,
        "responsible_user_id": plan.responsible_user_id,
        "ai_suggestion": plan.ai_suggestion,
        "enabled": plan.enabled,
        "created_at": _dt(plan.created_at),
        "updated_at": _dt(plan.updated_at),
    }


def _task_dict(task) -> dict:
    return {
        "id": task.id,
        "plan_id": task.plan_id,
        "enterprise_id": task.enterprise_id,
        "title": task.title,
        "status": task.status,
        "responsible_user_id": task.responsible_user_id,
        "due_at": _dt(task.due_at),
        "completed_at": _dt(task.completed_at),
        "overdue_notified_at": _dt(task.overdue_notified_at),
        "created_at": _dt(task.created_at),
        "updated_at": _dt(task.updated_at),
    }


def _item_dict(item) -> dict:
    return {
        "id": item.id,
        "task_id": item.task_id,
        "object_id": item.object_id,
        "measure_id": item.measure_id,
        "content": item.content,
        "expected_note": item.expected_note,
        "result": item.result,
        "remark": item.remark,
        "photo_urls": item.photo_urls,
        "created_at": _dt(item.created_at),
        "updated_at": _dt(item.updated_at),
    }


def _record_dict(record) -> dict:
    return {
        "id": record.id,
        "enterprise_id": record.enterprise_id,
        "code": record.code,
        "source_type": record.source_type,
        "source_task_id": record.source_task_id,
        "source_item_id": record.source_item_id,
        "object_id": record.object_id,
        "measure_id": record.measure_id,
        "title": record.title,
        "description": record.description,
        "photo_urls": record.photo_urls,
        "status": record.status,
        "created_by": record.created_by,
        "created_at": _dt(record.created_at),
        "updated_at": _dt(record.updated_at),
    }


# ── 权限与归属 helper ──

async def _enterprise(enterprise_id: str, db: AsyncSession) -> Optional[Enterprise]:
    return (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id)
    )).scalar_one_or_none()


async def _is_enabled_member(
    db: AsyncSession,
    enterprise_id: str,
    user_id: str,
    role: Optional[str] = None,
) -> bool:
    """企业启用成员判断（可选 role 限定），供读归属/责任人/管理员校验复用。"""
    q = select(EnterpriseMember.id).where(
        EnterpriseMember.enterprise_id == enterprise_id,
        EnterpriseMember.user_id == user_id,
        EnterpriseMember.enabled.is_(True),
    )
    if role:
        q = q.where(EnterpriseMember.role == role)
    return (await db.execute(q)).first() is not None


async def _get_ent(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    """读路径企业归属校验：企业存在且属主或属启用成员，否则 404。"""
    ent = await _enterprise(enterprise_id, db)
    if not ent:
        raise HTTPException(404, "企业不存在")
    if ent.user_id == user_id:
        return ent
    if await _is_enabled_member(db, enterprise_id, user_id):
        return ent
    raise HTTPException(404, "企业不存在")


async def _get_admin_ent(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    """写路径：企业不存在 → 404；存在但非企业主且非企业管理员成员 → 403。"""
    ent = await _enterprise(enterprise_id, db)
    if not ent:
        raise HTTPException(404, "企业不存在")
    if ent.user_id == user_id:
        return ent
    if await _is_enabled_member(db, enterprise_id, user_id, role="enterprise_admin"):
        return ent
    raise HTTPException(403, "无权限操作该企业")


async def _require_task_actor(ent: Enterprise, user_id: str, task, db: AsyncSession) -> None:
    """任务核对/转隐患提交人：任务责任人本人或企业主/企业管理员，其余 403。"""
    if task.responsible_user_id == user_id:
        return
    if ent.user_id == user_id:
        return
    if await _is_enabled_member(db, ent.id, user_id, role="enterprise_admin"):
        return
    raise HTTPException(403, "仅任务责任人本人或企业管理员可提交")


# ── 业务校验 helper ──

def _validate_category(category: str) -> None:
    if category not in PLAN_CATEGORIES:
        raise HTTPException(422, f"category 非法: {category}，可选 {sorted(PLAN_CATEGORIES)}")


def _validate_frequency(frequency: str) -> None:
    if frequency not in PLAN_FREQUENCIES:
        raise HTTPException(422, f"frequency 非法: {frequency}，可选 {sorted(PLAN_FREQUENCIES)}")


def _check_frequency_weekdays(frequency: str, weekdays) -> None:
    """weekly/custom 时 weekdays 必填（B 规格 §5.1）。"""
    if frequency in ("weekly", "custom") and not weekdays:
        raise HTTPException(422, "frequency 为 weekly/custom 时 weekdays 必填")


async def _validate_zone_ids(db: AsyncSession, enterprise_id: str, zone_ids: list[str]) -> None:
    """zone_ids 非空且每个分区都属于该企业；不属于 → 422 并列出分区 id。"""
    if not zone_ids:
        raise HTTPException(422, "zone_ids 不能为空")
    unique = list(dict.fromkeys(zone_ids))
    rows = list((await db.execute(
        select(RiskZone.id).where(
            RiskZone.enterprise_id == enterprise_id,
            RiskZone.id.in_(unique),
        )
    )).scalars().all())
    missing = [zid for zid in unique if zid not in set(rows)]
    if missing:
        raise HTTPException(422, f"分区不属于该企业: {', '.join(missing)}")


async def _validate_responsible(db: AsyncSession, enterprise_id: str, user_id: Optional[str]) -> None:
    """责任人必须是该企业启用成员（enterprise_members enabled=true）。"""
    if not user_id:
        return
    if not await _is_enabled_member(db, enterprise_id, user_id):
        raise HTTPException(422, "责任人必须是该企业的启用成员")


async def _validate_template(db: AsyncSession, enterprise_id: str, template_id: Optional[str]) -> None:
    """模板必须是系统模板（enterprise_id NULL）或本企业模板，否则 422。"""
    if not template_id:
        return
    template = (await db.execute(
        select(HazardChecklistTemplate).where(HazardChecklistTemplate.id == template_id)
    )).scalar_one_or_none()
    if not template:
        raise HTTPException(422, "检查表模板不存在")
    if template.enterprise_id is not None and template.enterprise_id != enterprise_id:
        raise HTTPException(422, "检查表模板不属于该企业")


async def _get_plan(enterprise_id: str, plan_id: str, db: AsyncSession) -> HazardInspectionPlan:
    plan = (await db.execute(
        select(HazardInspectionPlan).where(
            HazardInspectionPlan.id == plan_id,
            HazardInspectionPlan.enterprise_id == enterprise_id,
        )
    )).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "排查计划不存在")
    return plan


async def _get_task(enterprise_id: str, task_id: str, db: AsyncSession) -> HazardInspectionTask:
    task = (await db.execute(
        select(HazardInspectionTask).where(
            HazardInspectionTask.id == task_id,
            HazardInspectionTask.enterprise_id == enterprise_id,
        )
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "排查任务不存在")
    return task


# ── 排查计划 CRUD ──

@router.post("/plans", response_model=ApiResponse[dict], status_code=201)
async def create_plan(
    enterprise_id: str,
    body: PlanCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_admin_ent(enterprise_id, current_user.id, db)
    _validate_category(body.category)
    _validate_frequency(body.frequency)
    _check_frequency_weekdays(body.frequency, body.weekdays)
    await _validate_zone_ids(db, enterprise_id, body.zone_ids)
    await _validate_responsible(db, enterprise_id, body.responsible_user_id)
    await _validate_template(db, enterprise_id, body.template_id)
    plan = HazardInspectionPlan(
        enterprise_id=enterprise_id,
        name=body.name,
        category=body.category,
        frequency=body.frequency,
        weekdays=body.weekdays,
        zone_ids=list(dict.fromkeys(body.zone_ids)),
        template_id=body.template_id,
        responsible_user_id=body.responsible_user_id,
        ai_suggestion=body.ai_suggestion,
        enabled=True if body.enabled is None else body.enabled,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return ApiResponse(data=_plan_dict(plan))


@router.get("/plans", response_model=ApiResponse[list])
async def list_plans(
    enterprise_id: str,
    enabled: Optional[bool] = Query(None),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """计划列表：支持 enabled 过滤（缺省全量），按创建时间倒序。"""
    await _get_ent(enterprise_id, current_user.id, db)
    q = select(HazardInspectionPlan).where(HazardInspectionPlan.enterprise_id == enterprise_id)
    if enabled is not None:
        q = q.where(HazardInspectionPlan.enabled.is_(enabled))
    rows = list((await db.execute(q.order_by(HazardInspectionPlan.created_at.desc()))).scalars().all())
    return ApiResponse(data=[_plan_dict(p) for p in rows])


@router.get("/plans/{plan_id}", response_model=ApiResponse[dict])
async def get_plan(
    enterprise_id: str,
    plan_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    plan = await _get_plan(enterprise_id, plan_id, db)
    return ApiResponse(data=_plan_dict(plan))


@router.put("/plans/{plan_id}", response_model=ApiResponse[dict])
async def update_plan(
    enterprise_id: str,
    plan_id: str,
    body: PlanUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """更新计划：仅校验显式传入字段；频次/星期组合按生效值（更新值优先）校验。"""
    await _get_admin_ent(enterprise_id, current_user.id, db)
    plan = await _get_plan(enterprise_id, plan_id, db)
    values = body.model_dump(exclude_unset=True)
    if "category" in values:
        _validate_category(values["category"])
    if "frequency" in values:
        _validate_frequency(values["frequency"])
    frequency = values.get("frequency", plan.frequency)
    weekdays = values.get("weekdays", plan.weekdays)
    _check_frequency_weekdays(frequency, weekdays)
    if "zone_ids" in values:
        await _validate_zone_ids(db, enterprise_id, values["zone_ids"])
        values["zone_ids"] = list(dict.fromkeys(values["zone_ids"]))
    if "responsible_user_id" in values:
        await _validate_responsible(db, enterprise_id, values["responsible_user_id"])
    if "template_id" in values:
        await _validate_template(db, enterprise_id, values["template_id"])
    for key, value in values.items():
        setattr(plan, key, value)
    await db.commit()
    await db.refresh(plan)
    return ApiResponse(data=_plan_dict(plan))


@router.delete("/plans/{plan_id}")
async def delete_plan(
    enterprise_id: str,
    plan_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """删除计划：软删（enabled=false），保留历史任务/清单项留痕。

    取舍说明：硬删会经 FK CASCADE 级联删除 `hazard_inspection_tasks` 及
    `hazard_inspection_items`，破坏排查留痕与 to-record 转出隐患的来源回填
    （source_task_id/source_item_id 悬空），故按规格 §5.1 FK CASCADE 语义
    选择软删停用计划。
    """
    await _get_admin_ent(enterprise_id, current_user.id, db)
    plan = await _get_plan(enterprise_id, plan_id, db)
    plan.enabled = False
    await db.commit()
    return ApiResponse(data=None, message="已删除")


# ── 任务 / 清单项端点 ──

@router.get("/tasks", response_model=ApiResponse[list])
async def list_tasks(
    enterprise_id: str,
    responsible_user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    overdue: Optional[bool] = Query(None),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """任务列表：支持责任人（仅本企业启用成员）/status/overdue 过滤，按 due_at 排序。"""
    await _get_ent(enterprise_id, current_user.id, db)
    q = select(HazardInspectionTask).where(HazardInspectionTask.enterprise_id == enterprise_id)
    if responsible_user_id:
        await _validate_responsible(db, enterprise_id, responsible_user_id)
        q = q.where(HazardInspectionTask.responsible_user_id == responsible_user_id)
    if status:
        q = q.where(HazardInspectionTask.status == status)
    if overdue:
        # 超期未完成 = due_at < now 且 status in (pending, processing)
        q = q.where(
            HazardInspectionTask.due_at < datetime.now(timezone.utc),
            HazardInspectionTask.status.in_(("pending", "processing")),
        )
    rows = list((await db.execute(q.order_by(HazardInspectionTask.due_at))).scalars().all())
    return ApiResponse(data=[_task_dict(t) for t in rows])


@router.get("/tasks/{task_id}", response_model=ApiResponse[dict])
async def get_task(
    enterprise_id: str,
    task_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """任务详情：含清单项 items 列表。"""
    await _get_ent(enterprise_id, current_user.id, db)
    task = await _get_task(enterprise_id, task_id, db)
    items = list((await db.execute(
        select(HazardInspectionItem).where(HazardInspectionItem.task_id == task.id).order_by(HazardInspectionItem.created_at)
    )).scalars().all())
    return ApiResponse(data={**_task_dict(task), "items": [_item_dict(i) for i in items]})


@router.put("/tasks/{task_id}", response_model=ApiResponse[dict])
async def submit_task(
    enterprise_id: str,
    task_id: str,
    body: TaskSubmitBody,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """提交核对结果：更新清单项 result/remark/photo_urls。

    全部项已核对（无 pending 剩余）→ status=done + completed_at；
    部分核对 → status=processing。存在 abnormal 时任务仍 done，
    隐患通过 POST /tasks/{task_id}/to-record 转出。
    """
    ent = await _get_ent(enterprise_id, current_user.id, db)
    task = await _get_task(enterprise_id, task_id, db)
    await _require_task_actor(ent, current_user.id, task, db)
    if not body.items:
        raise HTTPException(422, "items 不能为空")
    item_ids = [i.item_id for i in body.items]
    for submit in body.items:
        if submit.result not in ITEM_RESULTS:
            raise HTTPException(422, f"result 非法: {submit.result}，可选 {sorted(ITEM_RESULTS)}")
    items = list((await db.execute(
        select(HazardInspectionItem).where(
            HazardInspectionItem.task_id == task.id,
            HazardInspectionItem.id.in_(item_ids),
        )
    )).scalars().all())
    by_id = {i.id: i for i in items}
    missing = [iid for iid in dict.fromkeys(item_ids) if iid not in by_id]
    if missing:
        raise HTTPException(422, f"清单项不属于该任务: {', '.join(missing)}")
    for submit in body.items:
        item = by_id[submit.item_id]
        item.result = submit.result
        item.remark = submit.remark
        item.photo_urls = submit.photo_urls
    remaining = (await db.execute(
        select(func.count(HazardInspectionItem.id)).where(
            HazardInspectionItem.task_id == task.id,
            HazardInspectionItem.result == "pending",
        )
    )).scalar() or 0
    if remaining == 0:
        task.status = "done"
        task.completed_at = datetime.now(timezone.utc)
    else:
        task.status = "processing"
        task.completed_at = None
    await db.commit()
    await db.refresh(task)
    return ApiResponse(data=_task_dict(task))


@router.post("/tasks/{task_id}/to-record", response_model=ApiResponse[dict], status_code=201)
async def task_to_record(
    enterprise_id: str,
    task_id: str,
    body: ToRecordBody,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """一键转隐患：把任务下 result=abnormal 的清单项转成 hazard_record。

    source_type=inspection、source_task_id/source_item_id 回填、
    object_id/measure_id 取清单项；title 由 body 传入或 content 截断 255；
    description 由 body 传入或 content（+ remark）；photo_urls 取清单项照片。
    """
    ent = await _get_ent(enterprise_id, current_user.id, db)
    task = await _get_task(enterprise_id, task_id, db)
    await _require_task_actor(ent, current_user.id, task, db)
    item = (await db.execute(
        select(HazardInspectionItem).where(
            HazardInspectionItem.id == body.item_id,
            HazardInspectionItem.task_id == task.id,
        )
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "排查项不存在")
    if item.result != "abnormal":
        raise HTTPException(422, "仅 result=abnormal 的排查项可转隐患")
    title = (body.title or "").strip() or (item.content or "")[:255] or "排查发现的隐患"
    description = (body.description or "").strip()
    if not description:
        description = item.content or ""
        if item.remark:
            description = f"{description}；备注：{item.remark}"
    record = HazardRecord(
        enterprise_id=enterprise_id,
        code=await next_hazard_code(db, enterprise_id),
        source_type="inspection",
        source_task_id=task.id,
        source_item_id=item.id,
        object_id=item.object_id,
        measure_id=item.measure_id,
        title=title[:255],
        description=description,
        photo_urls=list(item.photo_urls or []),
        created_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=_record_dict(record))
