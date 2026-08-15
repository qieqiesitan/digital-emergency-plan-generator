"""隐患排查治理服务层（任务 3：排查计划/任务/清单项）。

`generate_tasks_for_plan`：按计划频次生成排查任务并组装动态清单项
（风险点 + 管控措施快照 + 模板项），供任务 8 调度器复用；本模块不调用 LLM，
AI 清单补全入口在生成函数内以 TODO 注释占位（任务 12 `ai/checklist` 接入）。

`next_hazard_code`：生成企业内唯一的隐患展示编号 `HD-{三位序号}`。

weekdays 约定：周一=0 .. 周日=6（与 Python `date.weekday()` 一致），
weekly/custom 计划仅在命中的星期生成任务。
monthly 约定：每月 1 日生成（`MONTHLY_DEFAULT_DAY`）。
"""

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hazard_management import (
    HazardChecklistTemplate,
    HazardInspectionItem,
    HazardInspectionTask,
    HazardRecord,
)
from app.models.risk_management import RiskEvent, RiskMeasure, RiskObject


# weekly/custom 计划按星期生成：周一=0 .. 周日=6（date.weekday() 同约定）
MONTHLY_DEFAULT_DAY = 1  # monthly 计划默认每月 1 日生成
DEFAULT_DUE_TIME = time(18, 0)  # 任务默认截止当日 18:00


def _object_content(obj) -> str:
    """风险点清单项文案：风险点名（类别）现场核查。"""
    name = getattr(obj, "name", None) or "风险点"
    category = getattr(obj, "category", None) or "未分类"
    return f"风险点 {name}（{category}）现场核查"


def _measure_content(measure) -> str:
    """管控措施清单项文案：措施类别 + 描述。"""
    category = getattr(measure, "measure_category", None) or "管控措施"
    description = getattr(measure, "description", None) or ""
    return f"{category}：{description}" if description else category


def _join_check_items(check_items) -> Optional[str]:
    """check_items（JSONB 列表）拼成 expected_note；空则 None。"""
    if isinstance(check_items, list):
        parts = [str(x) for x in check_items if str(x).strip()]
        return "；".join(parts) if parts else None
    if check_items:
        return str(check_items)
    return None


def _is_due(plan, on_date: date) -> bool:
    """按频次判断 on_date 是否为计划到期日（weekly/custom 按 weekdays 星期匹配）。"""
    frequency = getattr(plan, "frequency", None)
    if frequency == "daily":
        return True
    if frequency == "monthly":
        return on_date.day == MONTHLY_DEFAULT_DAY
    # weekly / custom
    weekdays = getattr(plan, "weekdays", None) or []
    return on_date.weekday() in weekdays


async def _load_template(db: AsyncSession, template_id: Optional[str]) -> Optional[HazardChecklistTemplate]:
    if not template_id:
        return None
    return (await db.execute(
        select(HazardChecklistTemplate).where(HazardChecklistTemplate.id == template_id)
    )).scalar_one_or_none()


async def _build_inspection_items(db: AsyncSession, plan, task_id: str) -> list[HazardInspectionItem]:
    """按 zone_ids 组装动态清单项：风险点 + 管控措施快照 + 模板项。

    风险点取 `risk_objects` 中 `is_risk_point=true` 且分区属于计划 zone_ids 的对象；
    管控措施经 `risk_events` 关联到对象后取 `risk_measures`，形成 object/measure 快照。
    """
    items: list[HazardInspectionItem] = []
    zone_ids = getattr(plan, "zone_ids", None) or []
    objects: list[RiskObject] = []
    if zone_ids:
        objects = list((await db.execute(
            select(RiskObject).where(
                RiskObject.enterprise_id == plan.enterprise_id,
                RiskObject.zone_id.in_(zone_ids),
                RiskObject.is_risk_point.is_(True),
            ).order_by(RiskObject.sort_order)
        )).scalars().all())

    if objects:
        object_ids = [o.id for o in objects]
        events = list((await db.execute(
            select(RiskEvent).where(RiskEvent.object_id.in_(object_ids))
        )).scalars().all())
        event_ids = [e.id for e in events]
        measures: list[RiskMeasure] = []
        if event_ids:
            measures = list((await db.execute(
                select(RiskMeasure).where(RiskMeasure.event_id.in_(event_ids)).order_by(RiskMeasure.sort_order)
            )).scalars().all())
        event_object = {e.id: e.object_id for e in events}
        measures_by_object: dict[str, list[RiskMeasure]] = {}
        for measure in measures:
            obj_id = event_object.get(measure.event_id)
            if obj_id:
                measures_by_object.setdefault(obj_id, []).append(measure)

        for obj in objects:
            items.append(HazardInspectionItem(
                task_id=task_id,
                object_id=obj.id,
                content=_object_content(obj),
                expected_note=getattr(obj, "description", None) or None,
            ))
            for measure in measures_by_object.get(obj.id, []):
                items.append(HazardInspectionItem(
                    task_id=task_id,
                    object_id=obj.id,
                    measure_id=measure.id,
                    content=_measure_content(measure),
                    expected_note=_join_check_items(getattr(measure, "check_items", None)),
                ))

    template = await _load_template(db, getattr(plan, "template_id", None))
    if template and isinstance(template.items, list):
        for tpl_item in template.items:
            if not isinstance(tpl_item, dict):
                continue
            content = str(tpl_item.get("content") or "").strip()
            items.append(HazardInspectionItem(
                task_id=task_id,
                content=content or "检查表核对项",
                expected_note=tpl_item.get("expected_note") or None,
            ))

    # TODO(task 12): AI 清单补全入口——任务 12 `ai/checklist` 端点返回建议项后，
    # 在此合并（按 content 去重），AI 失败时任务仍可执行（默认项即可）。
    return items


async def generate_tasks_for_plan(
    db: AsyncSession,
    plan,
    on_date: Optional[date] = None,
) -> Optional[HazardInspectionTask]:
    """按计划到期日生成排查任务（含动态清单项），供任务 8 调度器复用。

    输入：
      db       AsyncSession（任务由调用方提交）
      plan     HazardInspectionPlan
      on_date  生成日期，缺省今天
    输出：
      None        计划已停用（enabled=False，软删后不再出任务）、
                  当天未到期（weekly/custom 星期不匹配、monthly 非 1 日）
                  或该计划当天已有任务（防重，跳过）
      HazardInspectionTask  新生成任务（items 挂载在 task.items 供读取，
                  已加入 db 待提交；title=「{计划名} · MM-DD」，status=pending，
                  responsible_user_id 取计划责任人，due_at 默认当日 18:00）

    时区约定：due_at 取 naive 本地时间当日 18:00（Asia/Shanghai 业务自然日），
    不携带 tzinfo，由应用层统一按本地时区解释——若改用 UTC 偏移会让截止
    时刻在 8 小时边界漂移、与业务「当日 18:00」的直观约定不符；调度器按
    同一 naive 约定比较 due_at，避免跨时区误判。

    主键顺序：先 db.add(task) 再 await db.flush() 生成 task.id（UUID default
    在 flush 时生效），随后以该 id 组装清单项，保证 items.task_id 非空。
    """
    on_date = on_date or date.today()
    if plan.enabled is False:
        return None  # 软删/停用计划不再生成任务（与防重返回 None 同语义）
    if not _is_due(plan, on_date):
        return None

    day_start = datetime.combine(on_date, time.min)
    day_end = datetime.combine(on_date, time.max)
    # 防重：同一计划同一天已有任务则跳过（返回 None 标记已存在）
    exists = (await db.execute(
        select(HazardInspectionTask.id).where(
            HazardInspectionTask.plan_id == plan.id,
            HazardInspectionTask.due_at >= day_start,
            HazardInspectionTask.due_at <= day_end,
        )
    )).first()
    if exists:
        return None

    task = HazardInspectionTask(
        plan_id=plan.id,
        enterprise_id=plan.enterprise_id,
        title=f"{plan.name} · {on_date.strftime('%m-%d')}",
        status="pending",
        responsible_user_id=getattr(plan, "responsible_user_id", None),
        due_at=datetime.combine(on_date, DEFAULT_DUE_TIME),
    )
    db.add(task)
    await db.flush()  # 生成 task.id（default=lambda: str(uuid4()) 在 flush 时生效）
    items = await _build_inspection_items(db, plan, task.id)
    task.items = items  # 便捷读取（非 ORM 关系字段，供调用方直接取清单项）
    for item in items:
        db.add(item)
    return task


async def next_hazard_code(db: AsyncSession, enterprise_id: str) -> str:
    """生成企业内隐患展示编号 `HD-{三位序号}`（按既有记录数+1，不复用）。

    说明：隐患单无删除端点（状态机闭环），count+1 不会产生复用冲突；
    若未来引入删除，需改为取最大序号+1 并做唯一约束冲突兜底。

    并发兜底：count+1 存在并发窗口（两个请求同时读到相同 count 会算出
    相同 code），由 `uq_hazard_records_ent_code` 唯一约束兜底——冲突提交时
    抛 IntegrityError，由上层捕获重试或按失败处理，避免重复编号入库。
    """
    count = (await db.execute(
        select(func.count(HazardRecord.id)).where(HazardRecord.enterprise_id == enterprise_id)
    )).scalar() or 0
    return f"HD-{count + 1:03d}"
