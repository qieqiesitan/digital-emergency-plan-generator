"""运维扫描端点 + 作业票过期扫描接线（2026-09-18 补）。

背景：`expire_overdue_tickets` 的 docstring 写着"由调度器周期调用"，
但全仓没有任何调用方 → 批准后超过有效期的作业票永远停在「已批准」（状态机的 expired 不可达）。
本轮把它接进调度器，并补上文档里承诺、实际不存在的"内部触发端点"。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers import maintenance
from app.services import work_ticket_service as wts


@pytest.mark.asyncio
async def test_leader_only_skips_when_lock_not_acquired():
    db = MagicMock()
    result = MagicMock()
    result.scalar.return_value = False
    db.execute = AsyncMock(return_value=result)

    with patch.object(wts, "expire_overdue_tickets", AsyncMock()) as inner:
        assert await wts.expire_overdue_tickets_leader_only(db) is None
    inner.assert_not_awaited()


@pytest.mark.asyncio
async def test_leader_only_releases_lock_and_returns_count():
    db = MagicMock()
    result = MagicMock()
    result.scalar.return_value = True
    db.execute = AsyncMock(return_value=result)

    with patch.object(wts, "expire_overdue_tickets", AsyncMock(return_value=2)) as inner:
        assert await wts.expire_overdue_tickets_leader_only(db) == 2
    inner.assert_awaited()
    # 加锁 + 解锁各一次
    assert db.execute.await_count == 2
    assert "pg_advisory_unlock" in str(db.execute.await_args_list[-1].args[0])


@pytest.mark.asyncio
async def test_run_scans_endpoint_returns_counts_and_reports_lock_skip():
    db = MagicMock()
    with patch.object(maintenance, "run_hazard_scans_leader_only",
                      AsyncMock(return_value={"generated": 1})), \
         patch.object(maintenance, "expire_overdue_tickets_leader_only",
                      AsyncMock(return_value=3)):
        out = await maintenance.run_scans(db=db, _=MagicMock())
    assert out.data["hazard_scans"] == {"generated": 1}
    assert out.data["expired_tickets"] == 3
    assert out.data["skipped_by_lock"] is False

    with patch.object(maintenance, "run_hazard_scans_leader_only", AsyncMock(return_value=None)), \
         patch.object(maintenance, "expire_overdue_tickets_leader_only", AsyncMock(return_value=0)):
        out2 = await maintenance.run_scans(db=db, _=MagicMock())
    assert out2.data["skipped_by_lock"] is True


def test_scheduler_job_calls_ticket_expiry():
    """守护：调度器作业必须同时跑隐患扫描与作业票过期扫描（否则前者白写）。"""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    job_block = src.split("_run_hazard_scans_job", 1)[1].split("scheduler = AsyncIOScheduler", 1)[0]
    assert "expire_overdue_tickets_leader_only" in job_block
