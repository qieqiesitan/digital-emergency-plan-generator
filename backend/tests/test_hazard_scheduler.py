"""隐患排查治理调度器测试（任务 8：APScheduler 扫描函数，mock db 风格与既有一致）。

直接调用四个扫描函数（不真跑 scheduler）：到期计划生成（daily 到期/非到期/防重）、
记录超期通知（创建通知+audit、同 record 防重、无 deadline 跳过、企业主兜底）、
任务提前提醒（upcoming 创建、窗口外跳过、reminder_notified_at 防重）、
任务超期（标记 overdue + 通知 + 防重），以及 run_hazard_scans 组合提交。
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.hazard_management import (
    HazardAuditLog,
    HazardInspectionPlan,
    HazardInspectionTask,
    HazardNotification,
    HazardRecord,
)
from app.services.hazard_scheduler import (
    REMINDER_HOURS,
    run_hazard_scans,
    scan_due_plans,
    scan_overdue_records,
    scan_overdue_tasks,
    scan_upcoming_tasks,
)


# ── mock 工具（参照 tests/test_hazard_plan_api.py 的 _hazard_db 文本分发） ──

def _scalar(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _scalars(values):
    res = MagicMock()
    res.scalars.return_value.all.return_value = list(values)
    return res


def _first(value):
    res = MagicMock()
    res.first.return_value = value
    return res


def _db(*, plans=None, tasks=None, records=None, overdue_notification=None,
        dedupe_hit=None, owner="u-owner"):
    """按 SQL 文本特征分发：计划/任务/记录列表、通知存在性、企业主兜底。"""
    db = AsyncMock()
    db.added = []
    db.flush = AsyncMock()

    def fake_add(obj):
        if isinstance(obj, HazardInspectionTask) and not getattr(obj, "id", None):
            obj.id = "t-new"
        db.added.append(obj)

    db.add = MagicMock(side_effect=fake_add)

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(owner)
        if "FROM hazard_inspection_plans" in text:
            return _scalars(plans or [])
        if "FROM hazard_inspection_tasks" in text:
            if "hazard_inspection_tasks.plan_id =" in text:
                return _first(dedupe_hit)  # generate_tasks_for_plan 防重查询
            return _scalars(tasks or [])
        if "FROM hazard_records" in text:
            return _scalars(records or [])
        if "FROM hazard_notifications" in text:
            return _first(overdue_notification)  # 记录超期通知存在性
        return _scalar(None)

    db.execute.side_effect = fake_execute
    return db


def _plan(**kw):
    return HazardInspectionPlan(
        id=kw.pop("id", "p1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        name=kw.pop("name", "生产车间日排查"),
        category=kw.pop("category", "daily"),
        frequency=kw.pop("frequency", "daily"),
        weekdays=kw.pop("weekdays", None),
        zone_ids=kw.pop("zone_ids", []),
        template_id=kw.pop("template_id", None),
        responsible_user_id=kw.pop("responsible_user_id", "u1"),
        enabled=kw.pop("enabled", True),
    )


def _task(**kw):
    t = HazardInspectionTask(
        id=kw.pop("id", "t1"),
        plan_id=kw.pop("plan_id", "p1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        title=kw.pop("title", "生产车间日排查 · 08-15"),
        status=kw.pop("status", "pending"),
        responsible_user_id=kw.pop("responsible_user_id", "u1"),
        due_at=kw.pop("due_at", datetime(2026, 8, 15, 18, 0)),
        overdue_notified_at=kw.pop("overdue_notified_at", None),
        reminder_notified_at=kw.pop("reminder_notified_at", None),
    )
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def _record(**kw):
    r = HazardRecord(
        id=kw.pop("id", "r1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        code=kw.pop("code", "HD-001"),
        source_type="inspection",
        title="配电箱门缺失",
        description="配电箱门破损",
        status=kw.pop("status", "rectifying"),
        deadline=kw.pop("deadline", date(2026, 8, 1)),
        rectification_user_id=kw.pop("rectification_user_id", "u1"),
    )
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _notifications(db):
    return [o for o in db.added if isinstance(o, HazardNotification)]


# ── 补列契约：reminder_notified_at（方案 A 防重字段） ──

def test_task_model_has_reminder_notified_at():
    cols = {c.name for c in HazardInspectionTask.__table__.columns}
    assert "reminder_notified_at" in cols


# ── ① 到期计划生成 ──

@pytest.mark.asyncio
async def test_scan_due_plans_generates_daily_today():
    plan = _plan(frequency="daily")
    db = _db(plans=[plan])
    generated = await scan_due_plans(db, on_date=date(2026, 8, 15))
    assert generated == 1
    tasks = [o for o in db.added if isinstance(o, HazardInspectionTask)]
    assert len(tasks) == 1
    assert tasks[0].plan_id == "p1"
    assert tasks[0].due_at == datetime(2026, 8, 15, 18, 0)


@pytest.mark.asyncio
async def test_scan_due_plans_skips_weekly_on_non_matching_day():
    # 2026-08-15 为周六（weekday=5），weekly 仅周一（0）不命中
    plan = _plan(frequency="weekly", weekdays=[0])
    db = _db(plans=[plan])
    generated = await scan_due_plans(db, on_date=date(2026, 8, 15))
    assert generated == 0
    assert not any(isinstance(o, HazardInspectionTask) for o in db.added)


@pytest.mark.asyncio
async def test_scan_due_plans_skips_existing_task():
    # 同 plan 同日已有任务（generate_tasks_for_plan 防重返回 None）→ 不生成
    plan = _plan(frequency="daily")
    db = _db(plans=[plan], dedupe_hit=MagicMock())
    generated = await scan_due_plans(db, on_date=date(2026, 8, 15))
    assert generated == 0
    assert not any(isinstance(o, HazardInspectionTask) for o in db.added)


# ── ② 记录超期 ──

@pytest.mark.asyncio
async def test_scan_overdue_records_creates_notification_and_audit():
    record = _record(deadline=date(2026, 8, 1))
    db = _db(records=[record])
    notified = await scan_overdue_records(db, now=datetime(2026, 8, 15, 9, 0))
    assert notified == 1
    notifications = _notifications(db)
    assert len(notifications) == 1
    n = notifications[0]
    assert n.type == "overdue"
    assert n.user_id == "u1"
    assert n.record_id == "r1"
    assert n.enterprise_id == "e1"
    assert "HD-001" in n.message and "整改已超期" in n.message
    audits = [o for o in db.added if isinstance(o, HazardAuditLog)]
    assert len(audits) == 1
    assert audits[0].action == "overdue"
    assert audits[0].record_id == "r1"
    assert audits[0].detail["code"] == "HD-001"


@pytest.mark.asyncio
async def test_scan_overdue_records_dedupes_existing_notification():
    record = _record(deadline=date(2026, 8, 1))
    db = _db(records=[record], overdue_notification=MagicMock())
    notified = await scan_overdue_records(db, now=datetime(2026, 8, 15, 9, 0))
    assert notified == 0
    assert not _notifications(db)
    assert not any(isinstance(o, HazardAuditLog) for o in db.added)


@pytest.mark.asyncio
async def test_scan_overdue_records_skips_without_deadline():
    record = _record(deadline=None)
    db = _db(records=[record])
    notified = await scan_overdue_records(db, now=datetime(2026, 8, 15, 9, 0))
    assert notified == 0
    assert not db.added


@pytest.mark.asyncio
async def test_scan_overdue_records_falls_back_to_enterprise_owner():
    record = _record(deadline=date(2026, 8, 1), rectification_user_id=None)
    db = _db(records=[record], owner="u-owner")
    notified = await scan_overdue_records(db, now=datetime(2026, 8, 15, 9, 0))
    assert notified == 1
    assert _notifications(db)[0].user_id == "u-owner"


# ── ③ 任务提前提醒（due_at 前 2h） ──

@pytest.mark.asyncio
async def test_scan_upcoming_tasks_creates_notification_in_window():
    now = datetime(2026, 8, 15, 17, 0)
    task = _task(due_at=datetime(2026, 8, 15, 18, 0))  # 窗口内：16:00 <= 17:00 < 18:00
    db = _db(tasks=[task])
    notified = await scan_upcoming_tasks(db, now=now)
    assert notified == 1
    notifications = _notifications(db)
    assert len(notifications) == 1
    n = notifications[0]
    assert n.type == "upcoming"
    assert n.user_id == "u1"
    assert n.record_id == "t1"
    assert "2026-08-15 18:00" in n.message and "完成排查" in n.message
    assert task.reminder_notified_at == now


@pytest.mark.asyncio
async def test_scan_upcoming_tasks_skips_outside_window():
    now = datetime(2026, 8, 15, 15, 0)
    task = _task(due_at=datetime(2026, 8, 15, 18, 0))  # due_at-2h=16:00 > now
    db = _db(tasks=[task])
    notified = await scan_upcoming_tasks(db, now=now)
    assert notified == 0
    assert not _notifications(db)
    assert task.reminder_notified_at is None


@pytest.mark.asyncio
async def test_scan_upcoming_tasks_dedupes_by_reminder_notified_at():
    now = datetime(2026, 8, 15, 17, 0)
    task = _task(due_at=datetime(2026, 8, 15, 18, 0), reminder_notified_at=now)
    db = _db(tasks=[task])
    notified = await scan_upcoming_tasks(db, now=now)
    assert notified == 0
    assert not _notifications(db)


# ── ④ 任务超期（标记 overdue + 通知） ──

@pytest.mark.asyncio
async def test_scan_overdue_tasks_marks_and_notifies():
    now = datetime(2026, 8, 15, 18, 0)
    task = _task(due_at=datetime(2026, 8, 15, 10, 0))
    db = _db(tasks=[task])
    notified = await scan_overdue_tasks(db, now=now)
    assert notified == 1
    assert task.status == "overdue"
    assert task.overdue_notified_at == now
    notifications = _notifications(db)
    assert len(notifications) == 1
    assert notifications[0].type == "overdue"
    assert notifications[0].user_id == "u1"
    assert "已超期" in notifications[0].message


@pytest.mark.asyncio
async def test_scan_overdue_tasks_dedupes_by_overdue_notified_at():
    now = datetime(2026, 8, 15, 18, 0)
    task = _task(due_at=datetime(2026, 8, 15, 10, 0), overdue_notified_at=now)
    db = _db(tasks=[task])
    notified = await scan_overdue_tasks(db, now=now)
    assert notified == 0
    assert task.status == "pending"  # 已通知的任务不再改动
    assert not _notifications(db)


@pytest.mark.asyncio
async def test_scan_overdue_tasks_skips_future_due():
    now = datetime(2026, 8, 15, 9, 0)
    task = _task(due_at=datetime(2026, 8, 15, 18, 0))
    db = _db(tasks=[task])
    notified = await scan_overdue_tasks(db, now=now)
    assert notified == 0
    assert task.status == "pending"


# ── 调度入口：组合扫描 + 统一提交 ──

@pytest.mark.asyncio
async def test_run_hazard_scans_runs_all_and_commits():
    db = _db()
    result = await run_hazard_scans(db, now=datetime(2026, 8, 15, 9, 0))
    assert result == {
        "generated": 0,
        "overdue_records": 0,
        "upcoming": 0,
        "overdue_tasks": 0,
    }
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_hazard_scans_generates_and_notifies():
    plan = _plan(frequency="daily")
    record = _record(deadline=date(2026, 8, 1))
    task = _task(due_at=datetime(2026, 8, 15, 10, 0))
    db = _db(plans=[plan], records=[record], tasks=[task])
    now = datetime(2026, 8, 15, 18, 0)
    result = await run_hazard_scans(db, now=now)
    assert result["generated"] == 1
    assert result["overdue_records"] == 1
    assert result["upcoming"] == 0  # 已过 due_at，不进提醒窗口
    assert result["overdue_tasks"] == 1
    assert task.status == "overdue"
    db.commit.assert_awaited_once()
    assert REMINDER_HOURS == 2
