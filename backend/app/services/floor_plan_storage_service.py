import os, uuid
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image
from app.config import settings

UPLOAD_DIR = Path(settings.UPLOAD_DIR if hasattr(settings, "UPLOAD_DIR") else Path(__file__).resolve().parents[2] / "uploads")
ALLOWED = {"image/png", "image/jpeg", "image/webp"}
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXEL = 12000

async def save_floor_plan(enterprise_id: str, floor_id: str, file: UploadFile) -> tuple[str, int, int]:
    if file.content_type not in ALLOWED:
        raise HTTPException(422, "仅支持 PNG/JPEG/WebP 图片")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(422, "文件不能超过 20MB")
    ext = os.path.splitext(file.filename or "image.png")[1].lower() or ".png"
    target_dir = UPLOAD_DIR / "enterprises" / enterprise_id / "floors" / floor_id
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex}{ext}"
    target = target_dir / name
    try:
        target.write_bytes(data)
        with Image.open(target) as img:
            width, height = img.size
        if width > MAX_PIXEL or height > MAX_PIXEL:
            raise HTTPException(422, "图片像素不能超过 12000x12000")
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception:
        target.unlink(missing_ok=True)
        raise HTTPException(422, "无法读取图片尺寸")
    return f"/uploads/enterprises/{enterprise_id}/floors/{floor_id}/{name}", width, height

def remove_floor_plan(url: str | None):
    if not url or not url.startswith("/uploads/"):
        return
    rel = url.removeprefix("/uploads/")
    try:
        (UPLOAD_DIR / rel).unlink(missing_ok=True)
    except OSError:
        pass
