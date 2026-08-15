"""隐患排查治理定时扫描服务（任务 8：APScheduler 任务生成 + 超期扫描 + 提前提醒）。

四个扫描函数相互独立、可单独测试，由 `run_hazard_scans` 顺序调用并统一提交：

1. `scan_due_plans`        到期计划生成排查任务（复用 `generate_tasks_for_plan`，
                           enabled/到期/防重判断均内置在该服务，调度器只负责
                           全量扫描 enabled 计划；量级小，全量扫描可接受）。
2. `scan_overdue_records`  rectifying 记录超期（deadline < 今天）写 overdue 通知
                           + audit log；同 record 已存在 overdue 通知则跳过。
3. `scan_upcoming_tasks`   pending/processing 任务 due_at 前 2h 生成 upcoming 提醒；
                           用 `reminder_notified_at` 字段防重（方案 A）。
4. `scan_overdue_tasks`    pending/processing 任务已过 due_at → 标记 overdue +
                           `overdue_notified_at=now` + overdue 通知（规格 §6）。

时区约定（与 `hazard_service.generate_tasks_for_plan` 一致）：`due_at` 为 naive
本地时间（Asia/Shanghai 业务自然日），本模块的 `now` 默认取 `datetime.now()`
（本地 naive），按同一约定比较，避免跨时区误判。

提交责任：`run_hazard_scans` 末尾统一 `await db.commit()`（调度器作业场景需要落库）；
单个扫描函数不提交，便于 mock db 测试直接断言 `db.added`。
"""

from datetime import date, datetime, timedelta
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.hazard_management import (
    HazardAuditLog,
    HazardInspectionPlan,
    HazardInspectionTask,
    HazardNotification,
    HazardRecord,
)
from app.services.hazard_service import generate_tasks_for_plan

logger = logging.getLogger(__name__)

# 提前提醒窗口：due_at 前 2 小时（规格 §6「due_at 前 2 小时生成 upcoming 通知」）
REMINDER_HOURS = 2

# 任务超期/待办相关状态（规格 §5.2 status 值域：pending / processing / done / overdue）
TASK_ACTIVE_STATUSES = ("pending", "processing")


async def _enterprise_owner_user_id(db: AsyncSession, enterprise_id: str) -> Optional[str]:
    """取企业主（enterprises.user_id）作为通知接收兜底；查不到返回 None。"""
    return (await db.execute(
        select(Enterprise.user_id).where(Enterprise.id == enterprise_id)
    )).scalar_one_or_none()


async def scan_due_plans(
    db: AsyncSession,
    on_date: Optional[date] = None,
) -> int:
    """扫描全部 enabled 计划，到期则调用 generate_tasks_for_plan 生成任务。

    效率取舍：不按频次在 SQL 层预筛「今日到期」，而是全量扫 enabled 计划后交给
    `generate_tasks_for_plan` 内的 `_is_due` 判断——计划量级小（每企业数十个量级），
    避免把频次语义（daily/weekly/custom 星期/monthly 1 日）复制到 SQL 造成双份维护。
    返回本次新生成任务数（防重命中/非到期返回 None 不计入）。
    """
    on_date = on_date or date.today()
    plans = (await db.execute(
        select(HazardInspectionPlan).where(HazardInspectionPlan.enabled.is_(True))
    )).scalars().all()
    generated = 0
    for plan in plans:
        task = await generate_tasks_for_plan(db, plan, on_date)
        if task is not None:
            generated += 1
    return generated


async def scan_overdue_records(
    db: AsyncSession,
    now: Optional[datetime] = None,
) -> int:
    """rectifying 记录 deadline < 今天 → overdue 通知 + audit log（不改 status）。

    规格 §5.13：超期为派生标记，不改 status 值域；通知一次 + audit log 留痕。
    防重：同一 record 已存在 type="overdue" 通知则跳过（查询存在性）。
    接收人：rectification_user_id，为空则兜底企业主（enterprises.user_id）。
    deadline 未配置（None）的记录不参与扫描（SQL 层 IS NOT NULL 过滤 + 内存防御）。
    """
    now = now or datetime.now()
    today = now.date()
    records = (await db.execute(
        select(HazardRecord).where(
            HazardRecord.status == "rectifying",
            HazardRecord.deadline.is_not(None),
            HazardRecord.deadline < today,
        )
    )).scalars().all()
    notified = 0
    for record in records:
        # 内存防御：mock/边界数据不依赖 SQL 过滤（deadline 缺失/状态不符则跳过）
        if record.status != "rectifying" or not record.deadline or record.deadline >= today:
            continue
        exists = (await db.execute(
            select(HazardNotification.id).where(
                HazardNotification.record_id == record.id,
                HazardNotification.type == "overdue",
            )
        )).first()
        if exists:
            continue
        user_id = record.rectification_user_id or await _enterprise_owner_user_id(db, record.enterprise_id)
        if not user_id:
            continue  # 无接收人则跳过，避免 user_id NOT NULL 冲突
        db.add(HazardNotification(
            enterprise_id=record.enterprise_id,
            user_id=user_id,
            record_id=record.id,
            type="overdue",
            message=f"隐患 {record.code} 整改已超期，请尽快完成整改",
        ))
        db.add(HazardAuditLog(
            enterprise_id=record.enterprise_id,
            record_id=record.id,
            user_id=None,  # 系统扫描无操作人
            action="overdue",
            detail={"type": "record_overdue", "code": record.code, "deadline": str(record.deadline)},
        ))
        notified += 1
    return notified


async def scan_upcoming_tasks(
    db: AsyncSession,
    now: Optional[datetime] = None,
) -> int:
    """pending/processing 任务 due_at 前 2h → upcoming 提醒通知。

    窗口：due_at - 2h <= now < due_at。防重（方案 A）：`reminder_notified_at`
    已写入的任务跳过（SQL 层 IS NULL 过滤 + 内存防御）。
    接收人：任务责任人 responsible_user_id，为空兜底企业主。
    """
    now = now or datetime.now()
    window_start = now + timedelta(hours=REMINDER_HOURS)
    tasks = (await db.execute(
        select(HazardInspectionTask).where(
            HazardInspectionTask.status.in_(TASK_ACTIVE_STATUSES),
            HazardInspectionTask.reminder_notified_at.is_(None),
            HazardInspectionTask.due_at > now,
            HazardInspectionTask.due_at <= window_start,
        )
    )).scalars().all()
    notified = 0
    for task in tasks:
        if task.status not in TASK_ACTIVE_STATUSES or task.reminder_notified_at is not None:
            continue
        if not (now < task.due_at <= now + timedelta(hours=REMINDER_HOURS)):
            continue  # 窗口外（已过 due_at 由 scan_overdue_tasks 处理）
        user_id = task.responsible_user_id or await _enterprise_owner_user_id(db, task.enterprise_id)
        if not user_id:
            continue
        db.add(HazardNotification(
            enterprise_id=task.enterprise_id,
            user_id=user_id,
            record_id=task.id,  # §5.12 record_id 关联隐患单/任务（无 FK，允许任务 id）
            type="upcoming",
            message=f"请在 {task.due_at:%Y-%m-%d %H:%M} 前完成排查：{task.title or '排查任务'}",
        ))
        task.reminder_notified_at = now
        notified += 1
    return notified


async def scan_overdue_tasks(
    db: AsyncSession,
    now: Optional[datetime] = None,
) -> int:
    """pending/processing 任务已过 due_at → 标记 overdue + 通知。

    规格 §6「超期：扫描标记 + 上级通知」：status 置 overdue（任务 status 值域合法值）、
    `overdue_notified_at=now` 防重（与记录超期是两类，记录不改 status）。
    """
    now = now or datetime.now()
    tasks = (await db.execute(
        select(HazardInspectionTask).where(
            HazardInspectionTask.status.in_(TASK_ACTIVE_STATUSES),
            HazardInspectionTask.overdue_notified_at.is_(None),
            HazardInspectionTask.due_at < now,
        )
    )).scalars().all()
    notified = 0
    for task in tasks:
        if task.status not in TASK_ACTIVE_STATUSES or task.overdue_notified_at is not None:
            continue
        if task.due_at >= now:
            continue
        task.status = "overdue"
        task.overdue_notified_at = now
        user_id = task.responsible_user_id or await _enterprise_owner_user_id(db, task.enterprise_id)
        if user_id:
            db.add(HazardNotification(
                enterprise_id=task.enterprise_id,
                user_id=user_id,
                record_id=task.id,
                type="overdue",
                message=f"排查任务 {task.title or '未命名任务'} 已超期，请尽快完成排查",
            ))
        notified += 1
    return notified


async def run_hazard_scans(
    db: AsyncSession,
    now: Optional[datetime] = None,
    on_date: Optional[date] = None,
) -> dict:
    """调度器入口：顺序执行四个扫描并统一提交，返回各扫描计数。"""
    now = now or datetime.now()
    on_date = on_date or now.date()
    result = {
        "generated": await scan_due_plans(db, on_date=on_date),
        "overdue_records": await scan_overdue_records(db, now=now),
        "upcoming": await scan_upcoming_tasks(db, now=now),
        "overdue_tasks": await scan_overdue_tasks(db, now=now),
    }
    await db.commit()
    logger.info("hazard scans finished: %s", result)
    return result
