import logging, shutil, uuid
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image
from app.config import settings

logger = logging.getLogger(__name__)
UPLOAD_DIR = Path(settings.UPLOAD_DIR if hasattr(settings, "UPLOAD_DIR") else Path(__file__).resolve().parents[2] / "uploads")
ALLOWED = {"image/png", "image/jpeg", "image/webp"}
EXT_BY_CONTENT_TYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXEL = 12000


def normalize_floor_plan_url(url: str | None) -> str | None:
    """写入 floor_plan_url 前校验：只接受空值或 /uploads/ 前缀，防止路径穿越。"""
    if url is None or url == "":
        return None
    if not isinstance(url, str) or not url.startswith("/uploads/"):
        raise HTTPException(422, "floor_plan_url 必须以 /uploads/ 开头或为空")
    if ".." in url.split("/"):
        raise HTTPException(422, "floor_plan_url 不能包含路径穿越片段")
    return url


def _declared_size(file: UploadFile) -> int | None:
    """从 multipart 的 Content-Length（Starlette 已解析到 size）或请求头读取声明大小。"""
    size = getattr(file, "size", None)
    if size is None:
        headers = getattr(file, "headers", {}) or {}
        raw = headers.get("content-length")
        if raw:
            try:
                size = int(raw)
            except (TypeError, ValueError):
                size = None
    return size


async def save_floor_plan(enterprise_id: str, floor_id: str, file: UploadFile) -> tuple[str, int, int]:
    if file.content_type not in ALLOWED:
        raise HTTPException(422, "仅支持 PNG/JPEG/WebP 图片")
    declared = _declared_size(file)
    if declared is not None and declared > MAX_BYTES:
        raise HTTPException(413, "文件不能超过 20MB")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "文件不能超过 20MB")
    # 扩展名按内容类型生成，不接受客户端任意扩展名
    ext = EXT_BY_CONTENT_TYPE.get(file.content_type, ".png")
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
    root = UPLOAD_DIR.resolve()
    target = (UPLOAD_DIR / rel).resolve()
    if target == root or not target.is_relative_to(root):
        logger.warning("拒绝删除上传目录之外的文件: %s", url)
        return
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("删除旧平面图失败: %s (%s)", url, exc)


def remove_floor_plan_dir(enterprise_id: str, floor_id: str):
    """事务提交后调用：尽力删除楼层平面图目录（含孤儿文件），失败仅记日志。"""
    target = (UPLOAD_DIR / "enterprises" / enterprise_id / "floors" / floor_id).resolve()
    root = UPLOAD_DIR.resolve()
    if target == root or not target.is_relative_to(root):
        logger.warning("拒绝删除上传目录之外的路径: %s", target)
        return
    try:
        if target.exists():
            shutil.rmtree(target)
    except OSError as exc:
        logger.warning("删除楼层平面图目录失败: %s (%s)", target, exc)


def remove_enterprise_uploads(enterprise_id: str):
    """事务提交后调用：尽力删除企业上传目录，失败仅记日志，不回滚业务。"""
    target = (UPLOAD_DIR / "enterprises" / enterprise_id).resolve()
    root = UPLOAD_DIR.resolve()
    if target == root or not target.is_relative_to(root):
        logger.warning("拒绝删除上传目录之外的路径: %s", target)
        return
    try:
        if target.exists():
            shutil.rmtree(target)
    except OSError as exc:
        logger.warning("删除企业上传目录失败: %s (%s)", target, exc)
