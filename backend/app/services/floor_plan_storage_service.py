import logging, re, shutil, uuid
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


FOUR_COLOR_TMP = "four_color_tmp"
TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


def _floor_dir(enterprise_id: str, floor_id: str) -> Path:
    return (UPLOAD_DIR / "enterprises" / enterprise_id / "floors" / floor_id).resolve()


def _four_color_tmp_root(enterprise_id: str, floor_id: str) -> Path:
    return _floor_dir(enterprise_id, floor_id) / FOUR_COLOR_TMP


def four_color_temp_dir(enterprise_id: str, floor_id: str, token: str) -> Path | None:
    """校验 token 并返回临时目录；格式非法或目录不存在返回 None。"""
    if not TOKEN_RE.match(token):
        return None
    root = _floor_dir(enterprise_id, floor_id)
    target = (_four_color_tmp_root(enterprise_id, floor_id) / token).resolve()
    if target == root or not target.is_relative_to(root):
        return None
    if not target.is_dir():
        return None
    return target


def save_four_color_temp(enterprise_id: str, floor_id: str, data: bytes, content_type: str) -> tuple[str, str]:
    """保存识别源图临时文件，返回 (preview_url, token)。先清理同楼层旧临时目录。"""
    if content_type not in ALLOWED:
        raise HTTPException(422, "仅支持 PNG/JPEG/WebP 图片")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "文件不能超过 20MB")
    ext = EXT_BY_CONTENT_TYPE.get(content_type, ".png")
    root = _four_color_tmp_root(enterprise_id, floor_id)
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
    token = uuid.uuid4().hex
    target_dir = root / token
    target_dir.mkdir(parents=True)
    (target_dir / f"source{ext}").write_bytes(data)
    url = f"/uploads/enterprises/{enterprise_id}/floors/{floor_id}/{FOUR_COLOR_TMP}/{token}/source{ext}"
    return url, token


def promote_four_color_file(enterprise_id: str, floor_id: str, token: str) -> tuple[str, int, int]:
    """把临时源图转正为楼层正式底图，返回 (url, width, height)。"""
    tmp_dir = four_color_temp_dir(enterprise_id, floor_id, token)
    if tmp_dir is None:
        raise FileNotFoundError("导入会话不存在")
    source = next(tmp_dir.glob("source.*"), None)
    if source is None:
        raise FileNotFoundError("导入会话不存在")
    with Image.open(source) as img:
        width, height = img.size
    floor_dir = _floor_dir(enterprise_id, floor_id)
    floor_dir.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex}{source.suffix}"
    target = floor_dir / name
    shutil.move(str(source), str(target))
    return f"/uploads/enterprises/{enterprise_id}/floors/{floor_id}/{name}", width, height


def remove_four_color_temp_dir(enterprise_id: str, floor_id: str, token: str) -> None:
    """幂等删除临时目录；路径安全校验失败则仅返回。"""
    tmp_dir = four_color_temp_dir(enterprise_id, floor_id, token)
    if tmp_dir is None:
        return
    shutil.rmtree(tmp_dir, ignore_errors=True)
