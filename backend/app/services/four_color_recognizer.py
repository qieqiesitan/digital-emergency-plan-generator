"""四色分布图识别管线：颜色分割 → 形态学清理 → 轮廓提取 → 多边形归一化。"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from uuid import uuid4

import numpy as np
from PIL import Image, ImageOps

try:
    import cv2
except ImportError:
    cv2 = None

COLOR_PALETTE: dict[str, tuple[int, int, int]] = {
    "红": (0, 0, 255),    # BGR
    "橙": (0, 127, 255),  # BGR
    "黄": (0, 255, 255),  # BGR
    "蓝": (255, 0, 0),    # BGR
}
LEVEL_BY_COLOR = {"红": "重大", "橙": "较大", "黄": "一般", "蓝": "低"}
MAX_HSV_DIST = 0.35
MIN_AREA_RATIO = 5e-5
EPSILON_RATIO = 0.0025
MAX_POLYGON_POINTS = 128
MAX_ZONES = 200
COLOR_HEX_BY_LEVEL = {"重大": "#ff4d4f", "较大": "#fa8c16", "一般": "#fadb14", "低": "#52c41a"}


def _require_cv2() -> None:
    if cv2 is None:
        raise RuntimeError("缺少 opencv-python-headless 依赖，无法执行四色分布图识别")


def classify_pixels(img: np.ndarray) -> dict[str, np.ndarray]:
    """按 HSV 距离把每个像素归类到最近标准色；距离超过阈值则归为背景。"""
    _require_cv2()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    names = list(COLOR_PALETTE)
    refs = [
        cv2.cvtColor(np.uint8([[COLOR_PALETTE[n]]]), cv2.COLOR_BGR2HSV)[0, 0].astype(np.float32)
        for n in names
    ]
    dists = []
    for rh, rs, rv in refs:
        dh = np.minimum(np.abs(h - rh), 180.0 - np.abs(h - rh))
        d = (dh / 180.0) ** 2 * 2.0 + ((s - rs) / 255.0) ** 2 + ((v - rv) / 255.0) ** 2
        dists.append(d)
    dists = np.stack(dists, axis=-1)
    idx = np.argmin(dists, axis=-1)
    mind = np.min(dists, axis=-1)
    return {
        name: np.where((idx == i) & (mind <= MAX_HSV_DIST), 255, 0).astype(np.uint8)
        for i, name in enumerate(names)
    }


def clean_mask(mask: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """开运算去噪点 + 闭运算填补文字造成的小孔。"""
    _require_cv2()
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)


def mask_to_polygons(mask: np.ndarray, width: int, height: int, min_area: float, epsilon: float) -> list[np.ndarray]:
    """外轮廓提取 + Douglas-Peucker 简化 + 最小面积过滤，返回像素坐标多边形列表。"""
    _require_cv2()
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys: list[np.ndarray] = []
    for cnt in contours:
        if cv2.contourArea(cnt) < min_area:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) < 3:
            continue
        if len(approx) > MAX_POLYGON_POINTS:
            step = max(1, len(approx) // MAX_POLYGON_POINTS)
            approx = approx[::step]
            if len(approx) < 3:
                approx = approx[:3]
        polys.append(approx.reshape(-1, 2))
    return polys


def normalize_points(points: np.ndarray | list, width: int, height: int) -> list[dict]:
    """像素坐标归一化为 0-100，越界 clamp，保留 2 位小数。"""
    out = []
    for x, y in points:
        nx = round(max(0.0, min(100.0, float(x) / width * 100.0)), 2)
        ny = round(max(0.0, min(100.0, float(y) / height * 100.0)), 2)
        out.append({"x": nx, "y": ny})
    return out


def _kernel_size(width: int, height: int) -> int:
    k = max(3, int(min(width, height) / 400))
    return k if k % 2 == 1 else k + 1


def _order_points(pts: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]     # 左上
    ordered[2] = pts[np.argmax(s)]     # 右下
    diff = np.diff(pts, axis=1).ravel()
    ordered[1] = pts[np.argmin(diff)]  # 右上
    ordered[3] = pts[np.argmax(diff)]  # 左下
    return ordered


def detect_perspective_quad(img: np.ndarray) -> tuple[np.ndarray | None, str | None]:
    """检测最大近似四边形（纸张/图框边缘）。返回 (quad, warning)。"""
    _require_cv2()
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None
    cnt = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(cnt) / (w * h)
    if area_ratio < 0.2 or area_ratio > 0.95:
        return None, None
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    if len(approx) != 4:
        return None, "检测到疑似纸张边缘但无法校正透视，请尽量上传正拍图"
    return approx.reshape(4, 2).astype(np.float32), None


def warp_perspective(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """按四边形宽高比透视校正为正矩形。"""
    _require_cv2()
    src = _order_points(quad)
    tl, tr, br, bl = src
    width_top = float(np.linalg.norm(tr - tl))
    width_bottom = float(np.linalg.norm(br - bl))
    height_left = float(np.linalg.norm(bl - tl))
    height_right = float(np.linalg.norm(br - tr))
    max_w = max(int(width_top), int(width_bottom), 1)
    max_h = max(int(height_left), int(height_right), 1)
    dst = np.array([[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, matrix, (max_w, max_h))


@dataclass
class RecognizeResult:
    zones: list[dict]
    warnings: list[str]
    width: int
    height: int


def recognize_from_bytes(data: bytes) -> RecognizeResult:
    """识别管线入口：解码 → 透视校正 → 分类 → 清理 → 轮廓 → 归一化。"""
    _require_cv2()
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    rgb = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    warnings: list[str] = []
    quad, quad_warning = detect_perspective_quad(bgr)
    if quad is not None:
        bgr = warp_perspective(bgr, quad)
        height, width = bgr.shape[:2]
    if quad_warning:
        warnings.append(quad_warning)
    masks = classify_pixels(bgr)
    diag = math.hypot(width, height)
    min_area = MIN_AREA_RATIO * width * height
    epsilon = EPSILON_RATIO * diag
    kernel_size = _kernel_size(width, height)
    zones: list[dict] = []
    seq = 0
    capped = False
    for name in ("红", "橙", "黄", "蓝"):
        mask = clean_mask(masks[name], kernel_size)
        polys = mask_to_polygons(mask, width, height, min_area, epsilon)
        for poly in polys:
            if len(zones) >= MAX_ZONES:
                if not capped:
                    warnings.append("识别区域过多，已保留前 200 个")
                    capped = True
                break
            seq += 1
            zones.append({
                "client_id": f"draft-{uuid4().hex}",
                "name": f"分区{seq}",
                "risk_level": LEVEL_BY_COLOR[name],
                "color": COLOR_HEX_BY_LEVEL[LEVEL_BY_COLOR[name]],
                "polygons": [{
                    "id": f"poly-{uuid4().hex}",
                    "label": None,
                    "points": normalize_points(poly, width, height),
                }],
            })
        if len(zones) >= MAX_ZONES:
            break
    return RecognizeResult(zones=zones, warnings=warnings, width=width, height=height)
