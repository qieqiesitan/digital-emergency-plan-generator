"""隐患排查治理路由（任务 3/4/5/6）：排查计划 CRUD + 任务/清单项端点 + 检查表模板 +
隐患登记 + 分级确认/挂牌审批 + AI 分级建议/治理方案草稿。

前缀 `/enterprises/{enterprise_id}/hazard-inspection`：
- `/plans`：计划 CRUD（写=企业主/企业管理员成员，读=企业主/启用成员）
- `/tasks`：任务列表/详情/核对提交/一键转隐患
- `/templates`：检查表模板（系统默认 + 企业 CRUD + 系统模板复制）
- `/ai/checklist-template`：AI 生成检查表模板（失败降级 available:false）
- `/records`：隐患登记（Web/移动端三渠道共用，任务 5 §8；写=企业主/启用成员，
  非归属 404——登记面向全员，权限分层对齐任务 3 读路径而非写路径）
- `/ai/record-assist`：登记 AI 摘要/分类（仅文本，失败降级 available:false，§16）
- `/records/{rid}/grade|approve|reject`：分级确认/重大挂牌审批（任务 6 §9，
  写=企业主/启用 enterprise_admin 403，记录非本企业 404）
- `/ai/grade`：AI 分级建议（major/general 码值，失败降级 available:false，§16）
- `/ai/governance-plan`：AI 治理方案草稿（五键，人工确认后随 grade 落库，§9）

权限与归属：
- 读路径企业归属校验（不属于 → 404）；写路径企业主或 `enterprise_members`
  中 role=enterprise_admin 且 enabled 的成员（其余 403），对齐既有
  `enterprise_org.py` 的 `_get_owned_ent`/403 惯例，并将成员纳入读范围
  （责任人/执行人场景必须能访问任务）。
- 全部响应走 `ApiResponse` 信封（code==0 + data）。
"""

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

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
from app.models.risk_management import RiskEvent, RiskMeasure, RiskObject, RiskUnit, RiskZone
from app.schemas.common import ApiResponse
from app.services.data_dict_service import get_dict_map
from app.services.hazard_ai_service import (
    ai_grade,
    ai_governance_plan,
    generate_checklist_template,
    record_assist,
)
from app.services.hazard_service import generate_tasks_for_plan, next_hazard_code
from app.services.hazard_state_machine import apply_transition
from app.services.risk_ai_service import _get_ai_config


router = APIRouter(prefix="/enterprises/{enterprise_id}/hazard-inspection", tags=["Hazard Management"])

PLAN_CATEGORIES = {"daily", "comprehensive", "special", "holiday"}
PLAN_FREQUENCIES = {"daily", "weekly", "monthly", "custom"}
ITEM_RESULTS = {"pending", "normal", "abnormal", "na"}
RECORD_SOURCE_TYPES = {"inspection", "report", "regulatory", "accident", "manual"}


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


class TemplateItem(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    expected_note: Optional[str] = Field(None, max_length=1000)


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: str
    items: list[TemplateItem]


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = None
    items: Optional[list[TemplateItem]] = None


class TemplateAIRequest(BaseModel):
    industry: str = Field("", max_length=2000)
    risk_points: str = Field("", max_length=4000)


class RecordCreate(BaseModel):
    """隐患登记请求（Web/移动端，任务 5 §8）：source_type 必填枚举，title/description 必填。"""

    source_type: str
    hazard_type: Optional[str] = None
    object_id: Optional[str] = None
    measure_id: Optional[str] = None
    title: str = Field(..., max_length=255)
    description: str = Field(..., min_length=1)
    photo_urls: Optional[list[str]] = None
    location: Optional[str] = Field(None, max_length=500)
    source_task_id: Optional[str] = None
    source_item_id: Optional[str] = None


class RecordAssistRequest(BaseModel):
    """登记 AI 摘要/分类请求：description 必填非空，object_id/measure_id 为可选上下文。"""

    description: str = Field(..., min_length=1)
    object_id: Optional[str] = None
    measure_id: Optional[str] = None


class GradeRequest(BaseModel):
    """分级确认请求（任务 6，§9）：level 必填；重大须提供 grading_basis 与完整治理方案。"""

    level: str
    grading_basis: Optional[str] = None
    hazard_type: Optional[str] = None
    rectification_plan: Optional[dict] = None
    rectification_user_id: Optional[str] = None
    level_source: Optional[str] = None  # ai / manual，默认 manual


class ApproveRequest(BaseModel):
    """挂牌审批请求：comment 可选；rectification_user_id 可选（approve 时设置整改责任人）。"""

    comment: Optional[str] = None
    rectification_user_id: Optional[str] = None


class RejectRequest(BaseModel):
    """挂牌驳回请求：comment 可选（退回 grading 重新定级）。"""

    comment: Optional[str] = None


class AIGradeRequest(BaseModel):
    """AI 分级建议请求（§9）：description 必填非空；judgment_points/measures_text 可选。"""

    description: str = Field(..., min_length=1)
    judgment_points: Optional[str] = None
    measures_text: Optional[str] = None


class AIGovernancePlanRequest(BaseModel):
    """AI 治理方案草稿请求（§9）：description 必填非空；judgment_points/measures_text 可选。"""

    description: str = Field(..., min_length=1)
    judgment_points: Optional[str] = None
    measures_text: Optional[str] = None


# ── 响应序列化 ──

def _dt(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _d(value):
    return value.isoformat() if isinstance(value, date) else value


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
        "location": getattr(record, "location", None),
        "hazard_type": getattr(record, "hazard_type", None),
        "level": getattr(record, "level", None),
        "level_source": getattr(record, "level_source", None),
        "grading_basis": getattr(record, "grading_basis", None),
        "rectification_plan": getattr(record, "rectification_plan", None),
        "deadline": _d(getattr(record, "deadline", None)),
        "rectification_user_id": getattr(record, "rectification_user_id", None),
        "reviewer_user_id": getattr(record, "reviewer_user_id", None),
        "closed_at": _dt(getattr(record, "closed_at", None)),
        "status": record.status,
        "created_by": record.created_by,
        "created_at": _dt(record.created_at),
        "updated_at": _dt(record.updated_at),
    }


def _template_dict(template) -> dict:
    return {
        "id": template.id,
        "enterprise_id": template.enterprise_id,
        "name": template.name,
        "category": template.category,
        "items": template.items or [],
        "is_system": template.is_system,
        # 列表按（名称,类别）合并展示时，前端可据此说明模板来源
        "source": "system" if template.is_system else "enterprise",
        "created_at": _dt(template.created_at),
        "updated_at": _dt(template.updated_at),
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


async def _get_record(enterprise_id: str, record_id: str, db: AsyncSession) -> HazardRecord:
    """取本企业隐患记录：非本企业记录按不存在处理（404，避免泄露归属信息）。"""
    record = (await db.execute(
        select(HazardRecord).where(
            HazardRecord.id == record_id,
            HazardRecord.enterprise_id == enterprise_id,
        )
    )).scalar_one_or_none()
    if not record:
        raise HTTPException(404, "隐患记录不存在")
    return record


async def _get_template(template_id: str, db: AsyncSession) -> HazardChecklistTemplate:
    template = (await db.execute(
        select(HazardChecklistTemplate).where(HazardChecklistTemplate.id == template_id)
    )).scalar_one_or_none()
    if not template:
        raise HTTPException(404, "检查表模板不存在")
    return template


async def _get_owned_template(enterprise_id: str, template_id: str, db: AsyncSession) -> HazardChecklistTemplate:
    """取本企业可编辑模板：系统模板不可直接编辑（422）；非本企业模板 404。"""
    template = await _get_template(template_id, db)
    if template.is_system:
        raise HTTPException(422, "系统模板请复制后编辑")
    if template.enterprise_id != enterprise_id:
        raise HTTPException(404, "检查表模板不存在")
    return template


async def _template_name_conflict(
    db: AsyncSession,
    enterprise_id: str,
    name: str,
    category: str,
    exclude_id: Optional[str] = None,
) -> bool:
    """企业内同名同类模板冲突检测（企业模板可覆盖系统模板，但企业内唯一）。"""
    q = select(HazardChecklistTemplate.id).where(
        HazardChecklistTemplate.enterprise_id == enterprise_id,
        HazardChecklistTemplate.name == name,
        HazardChecklistTemplate.category == category,
    )
    if exclude_id:
        q = q.where(HazardChecklistTemplate.id != exclude_id)
    return (await db.execute(q)).first() is not None


def _validate_items(items) -> list[dict]:
    """检查表 items 校验并归一化：非空数组；content 必填非空；expected_note 可空。"""
    if not items:
        raise HTTPException(422, "items 不能为空")
    normalized = []
    for idx, item in enumerate(items):
        # 创建走 pydantic 模型、更新经 model_dump 为 dict，两种形态都兼容
        raw_content = item.get("content") if isinstance(item, dict) else item.content
        raw_note = item.get("expected_note") if isinstance(item, dict) else item.expected_note
        content = str(raw_content or "").strip()
        if not content:
            raise HTTPException(422, f"items[{idx}].content 不能为空")
        expected_note = str(raw_note).strip() if raw_note is not None else None
        normalized.append({"content": content, "expected_note": expected_note or None})
    return normalized


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


# ── 检查表模板（任务 4，§5.9/§7） ──

@router.get("/templates", response_model=ApiResponse[list])
async def list_templates(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """模板列表：系统模板（enterprise_id NULL）与当前企业模板按（名称,类别）合并。

    企业条目优先覆盖同名同类的系统模板（前端可用 source/is_system 说明来源），
    其余系统模板保留展示；排序按（类别,名称）。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    system = list((await db.execute(
        select(HazardChecklistTemplate).where(HazardChecklistTemplate.enterprise_id.is_(None))
        .order_by(HazardChecklistTemplate.created_at)
    )).scalars().all())
    ent_rows = list((await db.execute(
        select(HazardChecklistTemplate).where(HazardChecklistTemplate.enterprise_id == enterprise_id)
        .order_by(HazardChecklistTemplate.created_at)
    )).scalars().all())
    merged: dict = {}
    for t in system + ent_rows:  # 后写覆盖先写 → 企业条目优先
        merged[(t.name, t.category)] = t
    rows = sorted(merged.values(), key=lambda t: (t.category, t.name))
    return ApiResponse(data=[_template_dict(t) for t in rows])


@router.post("/templates", response_model=ApiResponse[dict], status_code=201)
async def create_template(
    enterprise_id: str,
    body: TemplateCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """创建企业自定义模板。

    写权限=企业主/启用管理员（403）；items 非空且 content 必填（422）。
    企业内同名同类别冲突 → 409（取舍说明：属已存在资源的冲突而非输入
    格式问题，且与 §16「重复提交 409」语义一致；422 保留给字段校验）。
    """
    await _get_admin_ent(enterprise_id, current_user.id, db)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "name 不能为空")
    _validate_category(body.category)
    items = _validate_items(body.items)
    if await _template_name_conflict(db, enterprise_id, name, body.category):
        raise HTTPException(409, f"该企业已存在同名同类别的检查表模板：{name}（{body.category}）")
    template = HazardChecklistTemplate(
        enterprise_id=enterprise_id,
        name=name,
        category=body.category,
        items=items,
        is_system=False,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return ApiResponse(data=_template_dict(template))


@router.put("/templates/{template_id}", response_model=ApiResponse[dict])
async def update_template(
    enterprise_id: str,
    template_id: str,
    body: TemplateUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """更新企业模板（name/category/items；模型无 enabled 字段）。

    系统模板不可直接编辑 → 422「系统模板请复制后编辑」；非本企业模板 → 404。
    """
    await _get_admin_ent(enterprise_id, current_user.id, db)
    template = await _get_owned_template(enterprise_id, template_id, db)
    values = body.model_dump(exclude_unset=True)
    if "name" in values:
        name = (values["name"] or "").strip()
        if not name:
            raise HTTPException(422, "name 不能为空")
        values["name"] = name
    if "category" in values:
        _validate_category(values["category"])
    if "items" in values:
        values["items"] = _validate_items(values["items"])
    name = values.get("name", template.name)
    category = values.get("category", template.category)
    if "name" in values or "category" in values:
        if await _template_name_conflict(db, enterprise_id, name, category, exclude_id=template.id):
            raise HTTPException(409, f"该企业已存在同名同类别的检查表模板：{name}（{category}）")
    for key, value in values.items():
        setattr(template, key, value)
    await db.commit()
    await db.refresh(template)
    return ApiResponse(data=_template_dict(template))


@router.post("/templates/{template_id}/copy", response_model=ApiResponse[dict], status_code=201)
async def copy_template(
    enterprise_id: str,
    template_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """复制模板为企业模板（深拷贝 items），供「系统模板复制后编辑」。

    源模板可为系统模板或本企业模板（非本企业 → 404）；复制后保留原名/类别，
    形成企业覆盖条目，可继续编辑/删除；企业内已有同名同类模板 → 409
    （提示直接编辑既有副本，避免同名堆积）。
    """
    await _get_admin_ent(enterprise_id, current_user.id, db)
    template = await _get_template(template_id, db)
    if template.enterprise_id is not None and template.enterprise_id != enterprise_id:
        raise HTTPException(404, "检查表模板不存在")
    if await _template_name_conflict(db, enterprise_id, template.name, template.category):
        raise HTTPException(409, f"该企业已存在同名同类别的检查表模板：{template.name}（{template.category}）")
    copied = HazardChecklistTemplate(
        enterprise_id=enterprise_id,
        name=template.name,
        category=template.category,
        items=deepcopy(template.items or []),
        is_system=False,
    )
    db.add(copied)
    await db.commit()
    await db.refresh(copied)
    return ApiResponse(data=_template_dict(copied))


@router.delete("/templates/{template_id}")
async def delete_template(
    enterprise_id: str,
    template_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """删除企业模板：系统模板不可删（422，需复制后编辑）；非本企业 404。"""
    await _get_admin_ent(enterprise_id, current_user.id, db)
    template = await _get_owned_template(enterprise_id, template_id, db)
    await db.delete(template)
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


# ── AI 检查表生成（任务 4，§7/§16） ──

@router.post("/ai/checklist-template", response_model=ApiResponse[dict])
async def ai_checklist_template(
    enterprise_id: str,
    body: TemplateAIRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """AI 生成检查表模板：industry 与 risk_points 至少一项（均空 422）。

    未配置/异常/超时由服务兜底 available:false + 空 items（200，§16）；
    本端点不自动落库——页面确认后由 POST /templates 落库。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    industry = (body.industry or "").strip()
    risk_points = (body.risk_points or "").strip()
    if not industry and not risk_points:
        raise HTTPException(422, "industry 与 risk_points 至少填写一项")
    try:
        ai_config = await _get_ai_config(current_user.id, db)
    except HTTPException:
        # 系统未配置 AI 模型 → 由服务兜底 available:false（与 risk_management 惯例一致）
        ai_config = None
    result = await generate_checklist_template(industry, risk_points, ai_config)
    return ApiResponse(data=result)


# ── 隐患登记（任务 5，§8）：Web/移动端共用 POST /records + AI 摘要分类 ──

def _validate_record_source_type(source_type: str) -> None:
    if source_type not in RECORD_SOURCE_TYPES:
        raise HTTPException(422, f"source_type 非法: {source_type}，可选 {sorted(RECORD_SOURCE_TYPES)}")


async def _validate_hazard_type(db: AsyncSession, enterprise_id: str, hazard_type: str) -> None:
    """hazard_type 必须来自数据字典 `hazard_type` 码值（企业覆盖 > 系统默认）。"""
    dict_map = await get_dict_map(db, enterprise_id, "hazard_type")
    if hazard_type not in dict_map:
        raise HTTPException(422, f"hazard_type 非法: {hazard_type}，须来自数据字典 hazard_type 码值")


async def _deadline_rules(db: AsyncSession, enterprise_id: str) -> dict:
    """读取数据字典 `deadline_rules`（企业覆盖 > 系统默认）并归一化为状态机契约形态。

    字典条目结构为 {code: {label, value, description}}，其中 value 形如
    {"days": 15}；状态机 `_rule_days` 期望 {level: {"days": N}}（兼容
    {"key": N} 与 JSON 字符串），故此处把每个条目的 value 直接作为天数配置。
    """
    dict_map = await get_dict_map(db, enterprise_id, "deadline_rules")
    return {code: entry.get("value") or {} for code, entry in dict_map.items()}


async def _validate_object_ref(db: AsyncSession, enterprise_id: str, object_id: str) -> None:
    """object_id 可选：若提供必须属于该企业（风险点归属校验）。"""
    obj = (await db.execute(
        select(RiskObject.id).where(
            RiskObject.id == object_id,
            RiskObject.enterprise_id == enterprise_id,
        )
    )).first()
    if not obj:
        raise HTTPException(422, "风险点不属于该企业")


async def _validate_measure_ref(db: AsyncSession, enterprise_id: str, measure_id: str) -> None:
    """measure_id 可选：若提供必须属于该企业。

    管控措施经 risk_events 归属到对象（event.object_id）或单元
    （event.unit_id → risk_units.object_id），两路之一命中该企业即通过。
    """
    unit_object = aliased(RiskObject)
    row = (await db.execute(
        select(RiskMeasure.id)
        .join(RiskEvent, RiskEvent.id == RiskMeasure.event_id)
        .outerjoin(RiskObject, RiskObject.id == RiskEvent.object_id)
        .outerjoin(RiskUnit, RiskUnit.id == RiskEvent.unit_id)
        .outerjoin(unit_object, unit_object.id == RiskUnit.object_id)
        .where(
            RiskMeasure.id == measure_id,
            or_(
                RiskObject.enterprise_id == enterprise_id,
                unit_object.enterprise_id == enterprise_id,
            ),
        )
    )).first()
    if not row:
        raise HTTPException(422, "管控措施不属于该企业")


async def _validate_source_task(db: AsyncSession, enterprise_id: str, task_id: str) -> None:
    """source_task_id 可选：回填校验属于该企业的排查任务。"""
    task = (await db.execute(
        select(HazardInspectionTask.id).where(
            HazardInspectionTask.id == task_id,
            HazardInspectionTask.enterprise_id == enterprise_id,
        )
    )).first()
    if not task:
        raise HTTPException(422, "排查任务不属于该企业")


async def _validate_source_item(db: AsyncSession, enterprise_id: str, item_id: str) -> None:
    """source_item_id 可选：回填校验排查项所属任务属于该企业。"""
    item = (await db.execute(
        select(HazardInspectionItem.id)
        .join(HazardInspectionTask, HazardInspectionTask.id == HazardInspectionItem.task_id)
        .where(
            HazardInspectionItem.id == item_id,
            HazardInspectionTask.enterprise_id == enterprise_id,
        )
    )).first()
    if not item:
        raise HTTPException(422, "排查项不属于该企业")


@router.post("/records", response_model=ApiResponse[dict], status_code=201)
async def create_record(
    enterprise_id: str,
    body: RecordCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """隐患登记（Web/移动端，任务 5 §8）：source_type 五渠道 + 可选关联/回填。

    权限取舍：登记面向全员（企业主或启用成员，含 enterprise_admin/team_leader/
    member），故写路径沿用任务 3 读归属 `_get_ent`——非企业主且非启用成员 → 404，
    不设 403 分层（与任务 3 计划/任务的写权限 403 不同：登记不涉及资源变更，
    任何发现隐患的成员都应能登记）。

    校验：source_type 枚举（422）；title/description 必填非空（422）；
    hazard_type 须来自数据字典 hazard_type 码值（422）；object_id/measure_id 须
    属于该企业（422）；source_task_id/source_item_id 须属于该企业任务（422）。
    落库 status=registered、created_by=当前用户、code=HD-{三位序号}。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    _validate_record_source_type(body.source_type)
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(422, "title 不能为空")
    description = (body.description or "").strip()
    if not description:
        raise HTTPException(422, "description 不能为空")
    if body.hazard_type:
        await _validate_hazard_type(db, enterprise_id, body.hazard_type)
    if body.object_id:
        await _validate_object_ref(db, enterprise_id, body.object_id)
    if body.measure_id:
        await _validate_measure_ref(db, enterprise_id, body.measure_id)
    if body.source_task_id:
        await _validate_source_task(db, enterprise_id, body.source_task_id)
    if body.source_item_id:
        await _validate_source_item(db, enterprise_id, body.source_item_id)
    location = (body.location or "").strip()
    record = HazardRecord(
        enterprise_id=enterprise_id,
        code=await next_hazard_code(db, enterprise_id),
        source_type=body.source_type,
        source_task_id=body.source_task_id,
        source_item_id=body.source_item_id,
        object_id=body.object_id,
        measure_id=body.measure_id,
        title=title[:255],
        description=description,
        photo_urls=list(body.photo_urls or []),
        location=location[:500] or None,
        hazard_type=body.hazard_type,
        created_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=_record_dict(record))


@router.post("/ai/record-assist", response_model=ApiResponse[dict])
async def ai_record_assist(
    enterprise_id: str,
    body: RecordAssistRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """登记 AI 摘要/分类（§8 #6）：输入描述文字，返回 title/hazard_type/分级建议。

    仅文本处理、不读照片（§8）；未配置/异常/超时由服务兜底 available:false
    （200，§16），不阻塞登记；本端点不落库——人工确认后随 POST /records 提交。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    description = (body.description or "").strip()
    if not description:
        raise HTTPException(422, "description 不能为空")
    try:
        ai_config = await _get_ai_config(current_user.id, db)
    except HTTPException:
        # 系统未配置 AI 模型 → 由服务兜底 available:false（与既有 AI 端点惯例一致）
        ai_config = None
    result = await record_assist(description, ai_config, object_id=body.object_id, measure_id=body.measure_id)
    return ApiResponse(data=result)


# ── 分级确认 / 挂牌审批（任务 6，§9）：grade → approve/reject → rectifying ──

@router.post("/records/{rid}/grade", response_model=ApiResponse[dict])
async def grade_record(
    enterprise_id: str,
    rid: str,
    body: GradeRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """分级确认（§9）：一般 → rectifying；重大 → pending_approval（须 basis + 治理方案）。

    权限：企业主或启用 enterprise_admin 成员（其余 403，对齐 `_get_admin_ent`
    既有惯例）；记录须属于该企业（404）。
    actor_role 映射：状态机 ROLE_GATE 只认 enterprise_admin/reviewer/rectifier，
    企业主可能无 enterprise_members 行——本端点执行者恒为管理员层级，统一映射为
    enterprise_admin 角色传入。
    期限：服务端从数据字典 `deadline_rules` 读取天数（企业覆盖 > 系统默认）随
    payload 传入，由状态机内部按 major/general 天数计算 deadline。
    校验：hazard_type 字典码值（422）；rectification_user_id 须为该企业启用成员
    （422）；level_source 仅 ai/manual（422，默认 manual）；重大缺判定依据或
    治理方案五键由状态机抛 422。
    """
    ent = await _get_admin_ent(enterprise_id, current_user.id, db)
    record = await _get_record(enterprise_id, rid, db)
    if body.hazard_type:
        await _validate_hazard_type(db, enterprise_id, body.hazard_type)
    if body.rectification_user_id:
        await _validate_responsible(db, enterprise_id, body.rectification_user_id)
    level_source = (body.level_source or "manual").strip()
    if level_source not in ("ai", "manual"):
        raise HTTPException(422, "level_source 必须为 ai 或 manual")
    payload = {
        "level": body.level,
        "hazard_type": body.hazard_type,
        "grading_basis": (body.grading_basis or "").strip() or None,
        "rectification_user_id": body.rectification_user_id,
        "level_source": level_source,
        "deadline_rules": await _deadline_rules(db, enterprise_id),
        "rectification_plan": body.rectification_plan,
    }
    await apply_transition(db, record, "grade", current_user, "enterprise_admin", payload, ent)
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=_record_dict(record))


@router.post("/records/{rid}/approve", response_model=ApiResponse[dict])
async def approve_record(
    enterprise_id: str,
    rid: str,
    body: ApproveRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """重大挂牌审批（§9）：pending_approval → approve → rectifying。

    仅 pending_approval（409，状态机校验）；仅企业主/启用 enterprise_admin（403）；
    rectification_user_id 可选——approve 时设置整改责任人，若 grade 已设可省略。
    写 HazardApproval(action=approve) + audit log（状态机完成）。
    """
    ent = await _get_admin_ent(enterprise_id, current_user.id, db)
    record = await _get_record(enterprise_id, rid, db)
    if body.rectification_user_id:
        await _validate_responsible(db, enterprise_id, body.rectification_user_id)
    await apply_transition(
        db, record, "approve", current_user, "enterprise_admin",
        {"comment": body.comment, "rectification_user_id": body.rectification_user_id},
        ent,
    )
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=_record_dict(record))


@router.post("/records/{rid}/reject", response_model=ApiResponse[dict])
async def reject_record(
    enterprise_id: str,
    rid: str,
    body: RejectRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """挂牌驳回（任务 6 可选实现，契约说明 reject 语义）：pending_approval → grading。

    状态机语义：退回 grading 重新定级（材料不足可修改后重新 grade）。
    权限与状态校验同 approve（仅企业主/启用 enterprise_admin 403、仅
    pending_approval 409）；写 HazardApproval(action=reject) + audit log。
    """
    ent = await _get_admin_ent(enterprise_id, current_user.id, db)
    record = await _get_record(enterprise_id, rid, db)
    await apply_transition(
        db, record, "reject", current_user, "enterprise_admin",
        {"comment": body.comment},
        ent,
    )
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=_record_dict(record))


# ── AI 分级建议 / 治理方案草稿（任务 6，§9）：失败降级 available:false（§16） ──

@router.post("/ai/grade", response_model=ApiResponse[dict])
async def ai_grade_suggestion(
    enterprise_id: str,
    body: AIGradeRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """AI 分级建议（§9）：输入描述 + 判定要点 + 措施文本，返回等级建议/依据/置信度。

    suggested_level 统一用 major/general 码值（与 records.level 值域一致，规格
    §5.4；任务 5 record-assist 用中文「一般/重大」是另一个端点，语义不同）。
    未配置/异常/超时/返回不合法由服务兜底 available:false（200，§16）；
    本端点不落库——人工确认或修改后由 POST /records/{rid}/grade 落库（level_source）。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    description = (body.description or "").strip()
    if not description:
        raise HTTPException(422, "description 不能为空")
    try:
        ai_config = await _get_ai_config(current_user.id, db)
    except HTTPException:
        # 系统未配置 AI 模型 → 由服务兜底 available:false（与既有 AI 端点惯例一致）
        ai_config = None
    result = await ai_grade(
        description, ai_config,
        judgment_points=body.judgment_points,
        measures_text=body.measures_text,
    )
    return ApiResponse(data=result)


@router.post("/ai/governance-plan", response_model=ApiResponse[dict])
async def ai_governance_plan_draft(
    enterprise_id: str,
    body: AIGovernancePlanRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """AI 治理方案草稿（§9）：输入描述 + 判定要点 + 措施文本，返回五键中文草稿。

    未配置/异常/超时/五键不全由服务兜底 available:false（200，§16）；
    本端点不落库——人工修改确认后随 POST /records/{rid}/grade 的
    rectification_plan 落库。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    description = (body.description or "").strip()
    if not description:
        raise HTTPException(422, "description 不能为空")
    try:
        ai_config = await _get_ai_config(current_user.id, db)
    except HTTPException:
        ai_config = None
    result = await ai_governance_plan(
        description, ai_config,
        judgment_points=body.judgment_points,
        measures_text=body.measures_text,
    )
    return ApiResponse(data=result)
