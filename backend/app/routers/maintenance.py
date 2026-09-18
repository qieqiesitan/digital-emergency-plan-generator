"""运维维护端点（仅管理员）：把"只能靠定时器做"的周期任务变成可手动触发。

动机：`main.py` 的调度器注释写着"外部 cron 可退化为调用 run_hazard_scans 的内部端点"，
但那个端点此前并不存在——容器里没装 APScheduler、或调度器启动失败降级时，
隐患扫描与作业票过期扫描就完全没有替代触发途径（而作业票过期扫描直到 2026-09-18
都没被任何调度器调用过）。

权限：`require_admin`（这些扫描会遍历所有企业的数据）。
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.schemas.common import ApiResponse
from app.services.hazard_scheduler import run_hazard_scans_leader_only
from app.services.work_ticket_service import expire_overdue_tickets_leader_only

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/maintenance", tags=["Maintenance"])


@router.post("/run-scans", response_model=ApiResponse[dict])
async def run_scans(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """立即执行一轮周期扫描（隐患四项 + 作业票过期），返回本轮计数。

    幂等：扫描内部都有防重（通知去重 / `reminder_notified_at` / 只在状态允许时迁移），
    重复调用不会产生重复副作用；`None` 表示本次被其他 worker 抢到锁、本进程跳过。
    """
    hazard = await run_hazard_scans_leader_only(db)
    expired_tickets = await expire_overdue_tickets_leader_only(db)
    logger.info("手动触发扫描：hazard=%s expired_tickets=%s", hazard, expired_tickets)
    return ApiResponse(data={
        "hazard_scans": hazard,
        "expired_tickets": expired_tickets,
        "skipped_by_lock": hazard is None or expired_tickets is None,
    })
