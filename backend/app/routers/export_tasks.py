from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os, re
from app.config import settings

router = APIRouter(prefix="/export", tags=["Export Tasks"])

@router.get("/tasks/{task_id}")
async def get_export_task_status(task_id: str):
    # Synchronous export - always completed
    return {"code": 0, "data": {"task_id": task_id, "status": "completed", "progress": 100, "download_url": None, "error_message": None}}

@router.get("/download/{file_key}")
async def download_export(file_key: str):
    if not re.match(r"^[\w\-.]+$", file_key):
        raise HTTPException(400, "无效文件名")
    path = os.path.join(settings.EXPORT_DIR, file_key)
    if not os.path.isfile(path):
        raise HTTPException(404, "文件不存在")
    return FileResponse(path, filename=file_key)
