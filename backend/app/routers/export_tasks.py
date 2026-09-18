import os
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise

router = APIRouter(prefix="/export", tags=["Export Tasks"])

# 业务导出物命名规范：risk-notice-<完整企业UUID>-<时间戳>.docx
# 只有能解析出企业归属的文件才允许下载，历史开发产物（_*.py/_*.pdf 等）一律拒绝。
_RISK_NOTICE_RE = re.compile(
    r"^risk-notice-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    r"-\d{14}-\d{6}\.docx$"
)


@router.get("/tasks/{task_id}")
async def get_export_task_status(task_id: str, _=Depends(get_current_user)):
    # Synchronous export - always completed
    return {"code": 0, "data": {"task_id": task_id, "status": "completed", "progress": 100, "download_url": None, "error_message": None}}


@router.get("/download/{file_key}")
async def download_export(
    file_key: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not re.match(r"^[\w\-.]+$", file_key):
        raise HTTPException(400, "无效文件名")
    matched = _RISK_NOTICE_RE.match(file_key)
    if not matched:
        # 非业务导出物（含历史开发脚本/样例文件）：不暴露、不区分存在性
        raise HTTPException(404, "文件不存在")
    owned = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == matched.group(1),
            Enterprise.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not owned:
        raise HTTPException(404, "文件不存在")
    path = os.path.join(settings.EXPORT_DIR, file_key)
    if not os.path.isfile(path):
        raise HTTPException(404, "文件不存在")
    return FileResponse(path, filename=file_key)
