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
- `/records/{rid}/rectify|review|close`：整改/复查/销号（任务 7 §10，状态机
  接线；rectify/review 执行=本人或企业主/启用 enterprise_admin，其余由状态机
  按本人校验分层 422；close 仅企业主/启用 enterprise_admin 403；rectify 成功
  后按字典 deadline_rules.review 生成复查期限提醒通知）
- `/ai/grade`：AI 分级建议（major/general 码值，失败降级 available:false，§16）
- `/ai/governance-plan`：AI 治理方案草稿（五键，人工确认后随 grade 落库，§9）
- `/ai/plan-builder`：AI 一键生成排查计划（2-6 套，责任人/分区为姓名与名称
  文本，确认后映射 id 落库；失败降级 available:false，§3.7 #2/§6/§16）
- `/ai/schedule-suggestion`：AI 排程建议（频次码值 + 责任人 id 建议，不校验
  存在性、确认后落库前校验；失败降级 available:false，§6/§16）
- `/ai/checklist`：AI 清单补全（≤8 项建议新增项，勾选后合并去重；失败降级
  available:false，§6/§16）
- `/ai/setup-wizard`：智能引导（复用组织建树/plan-builder/checklist-template
  三函数预填三块，分步确认落库；失败降级 available:false，§3.8/§16）
- `/publicity`：隐患公示企业内列表（任务 10 §11.2；scope 口径来自数据字典
  publicity_scope，默认 all；读=企业主/启用成员 404）
- `/publicity-token`：生成/重置公示公开 token（仅企业主/启用 enterprise_admin
  403；返回 token + 公开链接 /h/{token}）
- `/dashboard`：驾驶舱指标/图表/未读角标（任务 11 §12，读=企业主/启用成员）
- `/export/ledger.xlsx`：企业内台账导出（3 sheet openpyxl，含敏感字段）
- `/export/report.xlsx`：监管上报台账导出（脱敏 8 列白名单）

权限与归属：
- 读路径企业归属校验（不属于 → 404）；写路径企业主或 `enterprise_members`
  中 role=enterprise_admin 且 enabled 的成员（其余 403），对齐既有
  `enterprise_org.py` 的 `_get_owned_ent`/403 惯例，并将成员纳入读范围
  （责任人/执行人场景必须能访问任务）。
- 全部响应走 `ApiResponse` 信封（code==0 + data）。
"""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import json
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.hazard_management import (
    HazardApproval,
    HazardChecklistTemplate,
    HazardInspectionItem,
    HazardInspectionPlan,
    HazardInspectionTask,
    HazardNotification,
    HazardRecord,
    HazardRectification,
)
from app.models.risk_management import RiskEvent, RiskMeasure, RiskObject, RiskUnit, RiskZone
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.data_dict_service import get_dict_map
from app.services.hazard_export_service import (
    build_ledger_workbook,
    build_report_workbook,
    resolve_department_name,
)
from app.services.hazard_ai_service import (
    ai_grade,
    ai_governance_plan,
    build_inspection_plans,
    generate_checklist_template,
    record_assist,
    run_setup_wizard,
    suggest_checklist_items,
    suggest_schedule,
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


class RectifyRequest(BaseModel):
    """整改提交请求（任务 7，§10）：content 必填非空；evidence 可选照片数组；
    reviewer_user_id 必填——指定复查人（启用成员，且 ≠ 整改人）。"""

    content: str = Field(..., min_length=1)
    evidence: Optional[list[str]] = None
    reviewer_user_id: str


class ReviewRequest(BaseModel):
    """复查/二次复核请求（任务 7，§10）：result 必填 pass/fail；comment/evidence 可选。"""

    result: str
    comment: Optional[str] = None
    evidence: Optional[list[str]] = None


class CloseRequest(BaseModel):
    """销号请求（任务 7，§10）：comment 可选（仅企业主/启用 enterprise_admin）。"""

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


class PlanBuilderRequest(BaseModel):
    """AI 一键生成排查计划请求（§3.7 #2/§6）：区域清单/频次偏好均必填非空。"""

    areas: str = Field(..., max_length=4000)
    frequency_preference: str = Field(..., max_length=1000)


class ScheduleSuggestionRequest(BaseModel):
    """AI 排程建议请求（§6）：plan_draft 必填非空；分区风险/历史隐患提示可选。"""

    plan_draft: str = Field(..., max_length=4000)
    zone_risk_hints: Optional[str] = None
    history_hints: Optional[str] = None


class ChecklistSuggestionRequest(BaseModel):
    """AI 清单补全请求（§6）：task_context 必填非空。"""

    task_context: str = Field(..., max_length=4000)


class SetupWizardRequest(BaseModel):
    """智能引导向导请求（§3.8）：industry/areas 必填非空；人数/频次偏好可空。"""

    industry: str = Field(..., max_length=1000)
    areas: str = Field(..., max_length=4000)
    employee_count: Optional[str] = Field(None, max_length=100)
    frequency_preference: Optional[str] = Field(None, max_length=1000)


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


# ── 整改 / 复查 / 销号（任务 7，§10）：rectify → review → close，状态机接线 ──

def _dict_rule_days(rules: dict, key: str) -> Optional[int]:
    """从归一化 deadline_rules 取天数（与状态机 `_rule_days` 兼容：
    {"days": N} / 直接 N / JSON 字符串，取不到返回 None）。"""
    entry = (rules or {}).get(key)
    if isinstance(entry, dict):
        days = entry.get("days")
        return int(days) if isinstance(days, (int, float)) else None
    if isinstance(entry, (int, float)):
        return int(entry)
    if isinstance(entry, str):
        try:
            parsed = json.loads(entry)
            if isinstance(parsed, dict) and isinstance(parsed.get("days"), (int, float)):
                return int(parsed["days"])
        except (TypeError, ValueError):
            return None
    return None


async def _map_actor_role(
    db: AsyncSession,
    ent: Enterprise,
    record: HazardRecord,
    user_id: str,
    *,
    self_attr: str,
    self_role: str,
) -> str:
    """把执行者映射为状态机 ROLE_GATE 角色（任务 7 §10，与任务 6 企业主先例一致）。

    - 本人（record.rectification_user_id / reviewer_user_id）→ self_role
      （rectifier / reviewer）；
    - 企业主或启用 enterprise_admin 成员 → enterprise_admin（代整改/代复查例外）；
    - 其余启用成员 → 仍以 self_role 传入状态机，由状态机按本人校验抛 422
      （非企业人员已由 `_get_ent` 404 拦截，此处不预设 403，错误码由状态机分层）。
    """
    if getattr(record, self_attr) == user_id:
        return self_role
    if ent.user_id == user_id or await _is_enabled_member(
        db, ent.id, user_id, role="enterprise_admin"
    ):
        return "enterprise_admin"
    return self_role


@router.post("/records/{rid}/rectify", response_model=ApiResponse[dict])
async def rectify_record(
    enterprise_id: str,
    rid: str,
    body: RectifyRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """整改提交（§10）：rectifying → reviewing，写 hazard_rectifications + 复查期限提醒。

    权限：记录须属于该企业（404）；执行=整改人本人（record.rectification_user_id）
    或企业主/启用 enterprise_admin（enterprise_admin 例外由状态机放行）；其余用户
    由状态机按整改人身份校验抛 422（非企业人员经 `_get_ent` 404 拦截）。
    校验：content 必填非空（422）；reviewer_user_id 必填、须为该企业启用成员
    （422）、且 ≠ 整改人（422）。
    actor_role 映射：本人 → rectifier、企业主/启用 enterprise_admin →
    enterprise_admin（与 ROLE_GATE 一致，复用任务 6 企业主判定后按动作传角色）。
    复查期限：rectify 成功后按数据字典 `deadline_rules.review` 天数计算复查期限
    （date.today() + days），创建 type=review_due 的 HazardNotification 给复查人
    （message 含「请于 YYYY-MM-DD 前完成复查」），供任务 8 超期扫描使用；字典缺
    review 天数时不创建通知（无期限依据，避免无意义打扰）——取舍见 docstring。
    返回 data 为记录字典 + review_deadline（复查期限 ISO 或 null）。
    """
    ent = await _get_ent(enterprise_id, current_user.id, db)
    record = await _get_record(enterprise_id, rid, db)
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(422, "content 不能为空")
    if body.reviewer_user_id == record.rectification_user_id:
        raise HTTPException(422, "复查人不能为整改人")
    await _validate_responsible(db, enterprise_id, body.reviewer_user_id)
    actor_role = await _map_actor_role(
        db, ent, record, current_user.id, self_attr="rectification_user_id", self_role="rectifier"
    )
    await apply_transition(
        db, record, "rectify", current_user, actor_role,
        {
            "content": content,
            "evidence": list(body.evidence or []),
            "reviewer_user_id": body.reviewer_user_id,
        },
        ent,
    )
    review_deadline = None
    rules = await _deadline_rules(db, enterprise_id)
    review_days = _dict_rule_days(rules, "review")
    if review_days:
        review_deadline = date.today() + timedelta(days=review_days)
        db.add(HazardNotification(
            enterprise_id=enterprise_id,
            user_id=body.reviewer_user_id,
            record_id=record.id,
            type="review_due",
            message=f"请于 {review_deadline.isoformat()} 前完成复查",
        ))
    await db.commit()
    await db.refresh(record)
    data = _record_dict(record)
    data["review_deadline"] = review_deadline.isoformat() if review_deadline else None
    return ApiResponse(data=data)


@router.post("/records/{rid}/review", response_model=ApiResponse[dict])
async def review_record(
    enterprise_id: str,
    rid: str,
    body: ReviewRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """复查/二次复核（§10）：review pass/fail 全路径由状态机决定，路由透传。

    权限：记录须属于该企业（404）；执行=指定复查人（record.reviewer_user_id）
    或企业主/启用 enterprise_admin；其余用户由状态机按复查人身份校验抛 422。
    actor_role 映射：本人 → reviewer、企业主/启用 enterprise_admin →
    enterprise_admin（与 ROLE_GATE 一致）。
    状态机语义（路由透传）：pass 后 standard/一般停留 reviewing、strict+重大 →
    second_review、second_review pass 停留；fail → 退回 rectifying。
    """
    ent = await _get_ent(enterprise_id, current_user.id, db)
    record = await _get_record(enterprise_id, rid, db)
    result = (body.result or "").strip()
    if result not in ("pass", "fail"):
        raise HTTPException(422, "复查结果 result 必须为 pass 或 fail")
    actor_role = await _map_actor_role(
        db, ent, record, current_user.id, self_attr="reviewer_user_id", self_role="reviewer"
    )
    await apply_transition(
        db, record, "review", current_user, actor_role,
        {"result": result, "comment": body.comment, "evidence": list(body.evidence or [])},
        ent,
    )
    await db.commit()
    await db.refresh(record)
    return ApiResponse(data=_record_dict(record))


@router.post("/records/{rid}/close", response_model=ApiResponse[dict])
async def close_record(
    enterprise_id: str,
    rid: str,
    body: CloseRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """销号（§10）：reviewing/second_review → closed，写 review_type=close + closed_at。

    权限：仅企业主/启用 enterprise_admin（其余 403，对齐 `_get_admin_ent` 惯例）；
    记录须属于该企业（404）。状态非 reviewing/second_review → 409；
    严格模式+重大未 second_review → 409（均由状态机校验，路由透传）。
    """
    ent = await _get_admin_ent(enterprise_id, current_user.id, db)
    record = await _get_record(enterprise_id, rid, db)
    await apply_transition(
        db, record, "close", current_user, "enterprise_admin",
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


# ── AI 排查计划一键生成/排程建议/清单补全/智能引导（任务 12，§3.7/§3.8/§6/§16） ──

@router.post("/ai/plan-builder", response_model=ApiResponse[dict])
async def ai_plan_builder(
    enterprise_id: str,
    body: PlanBuilderRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """AI 一键生成排查计划（§3.7 #2/§6）：区域清单 + 频次偏好 → 2-6 套计划建议。

    plans 元素中 responsible_user_name / zone_names 为责任人建议姓名与分区名称
    （文本），页面整批确认或逐条调整后映射为企业成员 id 与分区 id，再经
    POST /plans 落库——本端点不落库。未配置/异常/超时/返回不合法由服务兜底
    available:false（200，§16），不阻塞手动创建。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    areas = (body.areas or "").strip()
    frequency_preference = (body.frequency_preference or "").strip()
    if not areas or not frequency_preference:
        raise HTTPException(422, "areas 与 frequency_preference 不能为空")
    try:
        ai_config = await _get_ai_config(current_user.id, db)
    except HTTPException:
        # 系统未配置 AI 模型 → 由服务兜底 available:false（与既有 AI 端点惯例一致）
        ai_config = None
    result = await build_inspection_plans(areas, frequency_preference, ai_config)
    return ApiResponse(data=result)


@router.post("/ai/schedule-suggestion", response_model=ApiResponse[dict])
async def ai_schedule_suggestion(
    enterprise_id: str,
    body: ScheduleSuggestionRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """AI 排程建议（§6）：计划草稿 + 可选分区风险/历史隐患提示 → 频次/责任人建议。

    suggested_frequency 为 daily/weekly/monthly/custom 码值；suggested_
    responsible_user_id 为建议用户 id——服务不校验存在性，页面确认后落库前再
    校验；AI 无法给出时 null + reason 说明。未配置/异常/超时/返回不合法由服务
    兜底 available:false（200，§16）；本端点不落库。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    plan_draft = (body.plan_draft or "").strip()
    if not plan_draft:
        raise HTTPException(422, "plan_draft 不能为空")
    try:
        ai_config = await _get_ai_config(current_user.id, db)
    except HTTPException:
        ai_config = None
    result = await suggest_schedule(
        plan_draft, ai_config,
        zone_risk_hints=body.zone_risk_hints,
        history_hints=body.history_hints,
    )
    return ApiResponse(data=result)


@router.post("/ai/checklist", response_model=ApiResponse[dict])
async def ai_checklist_suggestion(
    enterprise_id: str,
    body: ChecklistSuggestionRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """AI 清单补全（§6）：任务上下文 → 8 项以内建议新增项（content/expected_note）。

    页面勾选后与既有清单项合并去重再落库，本端点不落库。未配置/异常/超时/
    返回不合法由服务兜底 available:false（200，§16），任务仍可执行。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    task_context = (body.task_context or "").strip()
    if not task_context:
        raise HTTPException(422, "task_context 不能为空")
    try:
        ai_config = await _get_ai_config(current_user.id, db)
    except HTTPException:
        ai_config = None
    result = await suggest_checklist_items(task_context, ai_config)
    return ApiResponse(data=result)


@router.post("/ai/setup-wizard", response_model=ApiResponse[dict])
async def ai_setup_wizard(
    enterprise_id: str,
    body: SetupWizardRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """智能引导向导（§3.8/#7）：行业 + 主要区域 → 预填 组织树/排查计划/检查表。

    三块复用既有服务：org_suggestion=suggest_org_tree（enterprise_org_service，
    同型建树）、plans_suggestion=plan-builder、checklist_suggestion=
    checklist-template——报告方式为直接调用既有服务函数，避免重复实现。分步
    确认后由组织/计划/模板落库端点写库，本端点不落库。industry/areas 必填
    非空（422）；未配置/异常/三块全失败由服务兜底 available:false（200，§16）。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    industry = (body.industry or "").strip()
    areas = (body.areas or "").strip()
    if not industry or not areas:
        raise HTTPException(422, "industry 与 areas 不能为空")
    try:
        ai_config = await _get_ai_config(current_user.id, db)
    except HTTPException:
        ai_config = None
    result = await run_setup_wizard(
        industry,
        areas,
        (body.employee_count or "").strip() or None,
        (body.frequency_preference or "").strip() or None,
        ai_config,
    )
    return ApiResponse(data=result)


# ── 隐患公示（任务 10，§11.2）：企业内公示列表 + 公开 token 生成/重置 ──

PUBLICITY_SCOPE_FALLBACK = {"ongoing", "closed", "all"}


async def _dict_labels(db: AsyncSession, enterprise_id: str, dict_type: str) -> dict[str, str]:
    """数据字典 label 映射 {code: label}（企业覆盖 > 系统默认，get_dict_map 语义）。"""
    dict_map = await get_dict_map(db, enterprise_id, dict_type)
    return {code: (entry.get("label") or code) for code, entry in dict_map.items()}


async def _resolve_publicity_scopes(db: AsyncSession, enterprise_id: str) -> set[str]:
    """公示口径码值集合：来自数据字典 `publicity_scope`（企业覆盖 > 系统默认）。

    系统种子为 ongoing/closed/all（§3.6/§5.10），企业覆盖同 code 时以企业条目
    为准（get_dict_map 合并语义）。字典为空（未种子/全部禁用）时回退内置三档，
    保证端点不因配置缺失而不可用——取舍：字典驱动 + 内置兜底双保险。
    """
    dict_map = await get_dict_map(db, enterprise_id, "publicity_scope")
    scopes = set(dict_map)
    return scopes or set(PUBLICITY_SCOPE_FALLBACK)


async def _latest_rectifications(
    db: AsyncSession, record_ids: list[str]
) -> dict[str, HazardRectification]:
    """批量取每个记录最近整改记录（created_at 倒序取首条），供公示整改情况摘要。"""
    if not record_ids:
        return {}
    rows = list((await db.execute(
        select(HazardRectification)
        .where(HazardRectification.record_id.in_(record_ids))
        .order_by(HazardRectification.created_at.desc())
    )).scalars().all())
    latest: dict[str, HazardRectification] = {}
    for row in rows:
        latest.setdefault(row.record_id, row)
    return latest


def _rectification_summary(record, latest: Optional[HazardRectification]) -> str:
    """整改情况摘要：最近整改记录 content > 治理方案 goal > 「未提交整改」。

    §11.2 公示口径：已整改展示最近一次整改内容；未提交整改但已有治理方案时
    展示目标摘要（goal），便于公众了解整改方向；两者皆无显示「未提交整改」。
    """
    if latest and (latest.content or "").strip():
        return latest.content
    plan = record.rectification_plan or {}
    goal = (plan.get("goal") or "").strip()
    if goal:
        return goal
    return "未提交整改"


def _publicity_row(record, status_labels: dict[str, str],
                   source_labels: dict[str, str], rectification: str) -> dict:
    """公示行（企业内/公开共用）：编号/标题/等级/状态标签/整改情况/排查来源标签。

    字段均为展示口径——不含责任人/联系方式/照片/位置/内部备注（§11.2 脱敏），
    故公开页可直接复用同一行构造（public_hazard.py），仅额外脱敏企业名称。
    """
    return {
        "code": record.code,
        "title": record.title,
        "level": record.level or "",
        "status": status_labels.get(record.status, record.status),
        "rectification": rectification,
        "source_type": source_labels.get(record.source_type, record.source_type),
    }


def _mask_enterprise_name(name: str) -> str:
    """企业名称脱敏（公开公示）：仅保留首字符，其余以 ** 代替。

    §11.2 公开页不暴露企业全称；规则「首字符 + **」（如「甲公司」→「甲**」），
    空名称兜底返回「**」。
    """
    name = (name or "").strip()
    return (name[0] if name else "") + "**"


@router.get("/publicity", response_model=ApiResponse[list])
async def list_publicity(
    enterprise_id: str,
    scope: str = Query("all"),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """企业内隐患公示列表（§11.2）：编号/标题/等级/状态/整改情况/排查来源。

    口径：scope 来自数据字典 `publicity_scope` 码值（ongoing/closed/all，企业
    覆盖 > 系统默认），默认 all；ongoing=status != closed、closed=status ==
    closed，非法 scope → 422。
    排序：created_at 倒序；全量返回（与 plans/tasks 等既有列表惯例一致，公示
    列表规模可控，暂不分页——取舍：列表体量小，先满足展示，分页留待前端需要
    时追加）。
    权限：读 = 企业主或启用成员（非归属 404，`_get_ent`）。
    整改情况摘要：最近整改记录 content > 治理方案 goal > 「未提交整改」。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    scopes = await _resolve_publicity_scopes(db, enterprise_id)
    if scope not in scopes:
        raise HTTPException(422, f"scope 非法: {scope}，可选 {sorted(scopes)}")
    q = select(HazardRecord).where(HazardRecord.enterprise_id == enterprise_id)
    if scope == "ongoing":
        q = q.where(HazardRecord.status != "closed")
    elif scope == "closed":
        q = q.where(HazardRecord.status == "closed")
    records = list((await db.execute(
        q.order_by(HazardRecord.created_at.desc())
    )).scalars().all())
    status_labels = await _dict_labels(db, enterprise_id, "record_status_label")
    source_labels = await _dict_labels(db, enterprise_id, "source_type")
    latest = await _latest_rectifications(db, [r.id for r in records])
    return ApiResponse(data=[
        _publicity_row(r, status_labels, source_labels,
                       _rectification_summary(r, latest.get(r.id)))
        for r in records
    ])


@router.post("/publicity-token", response_model=ApiResponse[dict])
async def generate_publicity_token(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """生成/重置隐患公示公开 token（§5.10/§11.2/§14）。

    首次生成与重置统一端点：每次调用生成新 64 位 token
    （secrets.token_hex(32)，与风险公示/告知卡 token 先例一致），旧链接即刻失效。
    权限：仅企业主/启用 enterprise_admin（其余 403，`_get_admin_ent`）。
    返回 token 与完整公开链接 `/h/{token}`（SPA 路由，公开页前端路由 §15；
    后端 API 路径为 /public/hazard/{token}）。
    """
    ent = await _get_admin_ent(enterprise_id, current_user.id, db)
    ent.hazard_public_token = secrets.token_hex(32)
    await db.commit()
    return ApiResponse(data={
        "token": ent.hazard_public_token,
        "link": f"/h/{ent.hazard_public_token}",
    })


# ── 驾驶舱 / 台账 / 监管上报导出（任务 11，§12/§14） ──


def _field(row, name: str, idx: int):
    """行值归一化：ORM Row / 元组 / dict 均可用（dashboard 聚合输入）。"""
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, row[idx] if len(row) > idx else None)


def _month_bounds(today: date) -> tuple[date, date]:
    """当前自然月 [月初, 下月初) 边界（跨年安全）。"""
    month_start = today.replace(day=1)
    if today.month == 12:
        return month_start, date(today.year + 1, 1, 1)
    return month_start, date(today.year, today.month + 1, 1)


def _shift_month_start(month_start: date, delta: int) -> date:
    """月份平移（月初）：delta 可为负（环比/趋势窗口）。"""
    total = month_start.year * 12 + (month_start.month - 1) + delta
    return date(total // 12, total % 12 + 1, 1)


def _today() -> date:
    """当前自然日（可注入：测试 patch 本函数而非 immutable 的 date.today）。"""
    return date.today()


def _dashboard_payload(
    records,
    tasks,
    approved_ids,
    unread_rows,
    owned_rows,
    all_status_rows,
    user_id: str,
    today: Optional[date] = None,
) -> dict:
    """驾驶舱统计纯函数（任务 11 §12）：输入为查询结果，输出指标/图表/未读。

    统计口径（自然月滚动，以传入 today 为准）：
    - 未闭环：status != "closed" 记录数 + 去重 object_id 风险点数；
    - 整改及时率：本月应闭环 = deadline 在本月内 且（已 closed 或已超期
      rectifying 且 deadline < today）；按期闭环 = closed 且 closed_at.date()
      <= deadline；rate = 按期/应闭环 * 100（应闭环为 0 → None，前端显示「—」）；
    - 平均整改周期：本月闭环记录 (closed_at - created_at) 平均天数，1 位小数；
    - 重大挂牌：major_count = 当前 major 未闭环数（专表同口径），major_approved =
      有 approve 审批记录或当前 pending_approval 的记录数（进入过挂牌流程）；
    - 超期：overdue_records = rectifying 且 deadline < today；overdue_tasks =
      HazardInspectionTask.status == "overdue"；overdue_count 为两者之和；
    - 月度隐患：当月 created_at 新增数；环比 = (本月-上月)/上月*100（上月为
      0 → None）；
    - 扫码待确认：source_type == "report" 且 status == "registered"。
    图表：
    - type_distribution：hazard_type 分组计数（None → "未分类"，按数量降序）；
    - monthly_trend：近 12 个自然月（含当月）新增折线数据，["YYYY-MM"] 升序；
    - major_records：major 记录 code/title/deadline/status，deadline 升序
      （None 最后）；
    - enterprise_comparison：当前用户账号名下各企业未闭环数（含 0），按未闭环
      降序（口径：enterprises.user_id == 当前用户，同账号多企业）。
    未读数：hazard_notifications 该企业 read_at IS NULL 计数——total=全企业、
    mine=当前用户、by_type=按通知类型分组（消息角标口径）。
    """
    today = today or _today()
    month_start, next_month = _month_bounds(today)

    open_records = [r for r in records if r.status != "closed"]
    open_risk_points = len({r.object_id for r in open_records if r.object_id})

    due_records = [
        r for r in records
        if r.deadline and month_start <= r.deadline < next_month
        and (r.status == "closed"
             or (r.status == "rectifying" and r.deadline < today))
    ]
    on_time_closed = [
        r for r in due_records
        if r.status == "closed" and r.closed_at and r.closed_at.date() <= r.deadline
    ]
    rectification_rate = (
        round(len(on_time_closed) / len(due_records) * 100, 1) if due_records else None
    )
    closed_this_month = [
        r for r in records
        if r.status == "closed" and r.closed_at
        and month_start <= r.closed_at.date() < next_month
    ]
    cycle_days = [
        (r.closed_at - r.created_at).total_seconds() / 86400
        for r in closed_this_month if r.created_at
    ]
    avg_rectification_days = (
        round(sum(cycle_days) / len(cycle_days), 1) if cycle_days else None
    )

    major_unclosed = [r for r in records if r.level == "major" and r.status != "closed"]
    major_approved = len({
        r.id for r in records
        if r.id in approved_ids or r.status == "pending_approval"
    })

    overdue_records = [
        r for r in records
        if r.status == "rectifying" and r.deadline and r.deadline < today
    ]
    overdue_tasks = [t for t in tasks if t.status == "overdue"]

    monthly_new = [
        r for r in records
        if r.created_at and month_start <= r.created_at.date() < next_month
    ]
    last_month_start = _shift_month_start(month_start, -1)
    last_month_count = sum(
        1 for r in records
        if r.created_at and last_month_start <= r.created_at.date() < month_start
    )
    monthly_new_mom = (
        round((len(monthly_new) - last_month_count) / last_month_count * 100, 1)
        if last_month_count else None
    )
    scan_pending = [
        r for r in records if r.source_type == "report" and r.status == "registered"
    ]

    type_counts: dict[str, int] = {}
    for r in records:
        key = r.hazard_type or "未分类"
        type_counts[key] = type_counts.get(key, 0) + 1
    type_distribution = sorted(
        [{"hazard_type": k, "count": v} for k, v in type_counts.items()],
        key=lambda x: (-x["count"], x["hazard_type"]),
    )
    monthly_trend = []
    for i in range(11, -1, -1):
        start = _shift_month_start(month_start, -i)
        end = _shift_month_start(start, 1)
        monthly_trend.append({
            "month": start.strftime("%Y-%m"),
            "count": sum(
                1 for r in records
                if r.created_at and start <= r.created_at.date() < end
            ),
        })
    major_rows = sorted(
        [r for r in records if r.level == "major"],
        key=lambda r: (r.deadline is None, r.deadline or date.max,
                       r.created_at or datetime.min),
    )
    major_records = [
        {
            "code": r.code,
            "title": r.title,
            "deadline": r.deadline.isoformat() if r.deadline else None,
            "status": r.status,
        }
        for r in major_rows
    ]
    open_by_ent: dict[str, int] = {}
    for row in all_status_rows:
        eid = _field(row, "enterprise_id", 0)
        if eid is not None and _field(row, "status", 1) != "closed":
            open_by_ent[eid] = open_by_ent.get(eid, 0) + 1
    enterprise_comparison = sorted(
        [
            {
                "enterprise_id": _field(r, "id", 0),
                "name": _field(r, "name", 1),
                "open_count": open_by_ent.get(_field(r, "id", 0), 0),
            }
            for r in owned_rows
        ],
        key=lambda x: (-x["open_count"], x["name"]),
    )

    unread_list = [
        (_field(row, "user_id", 0), _field(row, "type", 1)) for row in unread_rows
    ]
    unread_by_type: dict[str, int] = {}
    for uid, ntype in unread_list:
        if ntype:
            unread_by_type[ntype] = unread_by_type.get(ntype, 0) + 1
    return {
        "metrics": {
            "open_hazards": len(open_records),
            "open_risk_points": open_risk_points,
            "rectification_rate": rectification_rate,
            "on_time_closed": len(on_time_closed),
            "due_this_month": len(due_records),
            "avg_rectification_days": avg_rectification_days,
            "major_count": len(major_unclosed),
            "major_approved": major_approved,
            "overdue_count": len(overdue_records) + len(overdue_tasks),
            "overdue_records": len(overdue_records),
            "overdue_tasks": len(overdue_tasks),
            "monthly_new": len(monthly_new),
            "monthly_new_mom": monthly_new_mom,
            "scan_pending": len(scan_pending),
        },
        "charts": {
            "type_distribution": type_distribution,
            "monthly_trend": monthly_trend,
            "major_records": major_records,
            "enterprise_comparison": enterprise_comparison,
        },
        "unread": {
            "total": len(unread_list),
            "mine": sum(1 for uid, _ in unread_list if uid == user_id),
            "by_type": dict(
                sorted(unread_by_type.items(), key=lambda x: (-x[1], x[0]))
            ),
        },
    }


@router.get("/dashboard", response_model=ApiResponse[dict])
async def hazard_dashboard(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """隐患驾驶舱（任务 11 §12）：指标卡 + 图表 + 未读角标。

    权限：读 = 企业主/启用成员（非归属 404，`_get_ent`）。口径全部集中在
    `_dashboard_payload`（docstring 逐项说明，测试直接覆盖公式）。
    企业对比口径：当前用户账号名下企业（enterprises.user_id == 当前用户）。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    records = list((await db.execute(
        select(HazardRecord).where(HazardRecord.enterprise_id == enterprise_id)
    )).scalars().all())
    tasks = list((await db.execute(
        select(HazardInspectionTask).where(
            HazardInspectionTask.enterprise_id == enterprise_id,
        )
    )).scalars().all())
    approved_ids = set((await db.execute(
        select(HazardApproval.record_id)
        .join(HazardRecord, HazardRecord.id == HazardApproval.record_id)
        .where(
            HazardRecord.enterprise_id == enterprise_id,
            HazardApproval.action == "approve",
        )
    )).scalars().all())
    unread_rows = list((await db.execute(
        select(HazardNotification.user_id, HazardNotification.type)
        .where(
            HazardNotification.enterprise_id == enterprise_id,
            HazardNotification.read_at.is_(None),
        )
    )).all())
    owned_rows = list((await db.execute(
        select(Enterprise.id, Enterprise.name).where(
            Enterprise.user_id == current_user.id,
        )
    )).all())
    all_status_rows = []
    if owned_rows:
        owned_ids = [_field(r, "id", 0) for r in owned_rows]
        all_status_rows = list((await db.execute(
            select(HazardRecord.enterprise_id, HazardRecord.status).where(
                HazardRecord.enterprise_id.in_(owned_ids),
            )
        )).all())
    return ApiResponse(data=_dashboard_payload(
        records, tasks, approved_ids, unread_rows, owned_rows, all_status_rows,
        current_user.id,
    ))


async def _id_names(db: AsyncSession, model, ids, name_attr: str = "name") -> dict:
    """批量取模型 id→展示名映射（导出名称解析；空集合跳过查询）。"""
    if not ids:
        return {}
    rows = (await db.execute(
        select(model.id, getattr(model, name_attr)).where(model.id.in_(ids))
    )).all()
    return {row[0]: row[1] for row in rows}


@router.get("/export/ledger.xlsx")
async def export_hazard_ledger(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """台账导出（企业内，含敏感字段）：3 sheet openpyxl + StreamingResponse。

    文件流方式：BytesIO 内存流 + StreamingResponse（media_type
    application/vnd.openxmlformats-officedocument.spreadsheetml.sheet），
    filename=hazard_ledger.xlsx（与 risk_management control-list/export 惯例一致）。
    字段选取与名称解析见 `hazard_export_service.build_ledger_workbook` docstring。
    权限：读 = 企业主/启用成员（非归属 404，`_get_ent`）。
    """
    await _get_ent(enterprise_id, current_user.id, db)
    records = list((await db.execute(
        select(HazardRecord).where(HazardRecord.enterprise_id == enterprise_id)
    )).scalars().all())
    user_ids = {
        uid for r in records
        for uid in (r.rectification_user_id, r.reviewer_user_id, r.created_by)
        if uid
    }
    user_names = await _id_names(db, User, user_ids)
    object_names = await _id_names(
        db, RiskObject, {r.object_id for r in records if r.object_id},
    )
    measure_names = await _id_names(
        db, RiskMeasure, {r.measure_id for r in records if r.measure_id},
        name_attr="description",
    )
    status_labels = await _dict_labels(db, enterprise_id, "record_status_label")
    source_labels = await _dict_labels(db, enterprise_id, "source_type")
    hazard_type_labels = await _dict_labels(db, enterprise_id, "hazard_type")
    buf = BytesIO()
    build_ledger_workbook(
        records,
        object_names=object_names,
        measure_names=measure_names,
        user_names=user_names,
        status_labels=status_labels,
        source_labels=source_labels,
        hazard_type_labels=hazard_type_labels,
    ).save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=hazard_ledger.xlsx"},
    )


@router.get("/export/report.xlsx")
async def export_hazard_report(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """监管上报台账导出（脱敏）：8 列白名单 openpyxl + StreamingResponse。

    脱敏口径（§12）：不含责任人姓名/联系方式/照片等敏感字段，白名单见
    `hazard_export_service.build_report_workbook`。
    责任单位 = 整改责任人（rectification_user_id）经 enterprise_members
    org_node_id → 组织节点 → 部门节点名推导（`resolve_department_name`），
    无组织归属/无部门祖先缺省「—」。
    整改进度 = 最近整改记录 content；无整改记录取状态标签（数据字典
    record_status_label，未命中回退原始码值）。
    文件流方式与 filename：同台账（hazard_report.xlsx）。
    权限：读 = 企业主/启用成员（非归属 404，`_get_ent`）。
    """
    ent = await _get_ent(enterprise_id, current_user.id, db)
    records = list((await db.execute(
        select(HazardRecord).where(HazardRecord.enterprise_id == enterprise_id)
    )).scalars().all())
    latest = await _latest_rectifications(db, [r.id for r in records])
    status_labels = await _dict_labels(db, enterprise_id, "record_status_label")
    members = list((await db.execute(
        select(EnterpriseMember).where(
            EnterpriseMember.enterprise_id == enterprise_id,
            EnterpriseMember.enabled.is_(True),
        )
    )).scalars().all())
    node_map = {
        n.get("id"): n for n in (ent.org_structure or [])
        if isinstance(n, dict) and n.get("id")
    }
    org_dept_map = {
        m.user_id: resolve_department_name(m.org_node_id, node_map)
        for m in members if m.user_id
    }
    progress_map = {}
    for r in records:
        rect = latest.get(r.id)
        if rect and (rect.content or "").strip():
            progress_map[r.id] = rect.content
        else:
            progress_map[r.id] = status_labels.get(r.status, r.status)
    buf = BytesIO()
    build_report_workbook(
        records,
        org_dept_map=org_dept_map,
        progress_map=progress_map,
    ).save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=hazard_report.xlsx"},
    )
