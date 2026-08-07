"""四色分布图识别管线：颜色分割 → 形态学清理 → 轮廓提取 → 多边形归一化。"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
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
MAX_TILT_DEG = 2.0
MAX_ASPECT_CHANGE = 2.0
THIN_ASPECT_RATIO = 12.0
BORDER_FRAME_THICKNESS_RATIO = 0.01
SUSPECT_AREA_RATIO = 0.05
SUSPECT_SOLIDITY = 0.5
DEFAULT_CANVAS_MAX = (1600, 1000)
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


def _point_in_polygon(px: float, py: float, points: list[dict]) -> bool:
    """射线法判断归一化点是否在多边形内（points 为 [{x,y}]）。"""
    n = len(points)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = points[i]["x"], points[i]["y"]
        xj, yj = points[j]["x"], points[j]["y"]
        if (yi > py) != (yj > py):
            x_cross = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def _crop_from_zone(bgr: np.ndarray, zone: dict, width: int, height: int) -> np.ndarray:
    """按分区多边形 bbox 带 8% 边距裁剪 BGR 图（供 CLIP 判别）。"""
    pts = zone["polygons"][0]["points"]
    xs = [p["x"] / 100 * width for p in pts]
    ys = [p["y"] / 100 * height for p in pts]
    margin_x = int(0.08 * width)
    margin_y = int(0.08 * height)
    x0 = max(0, int(min(xs)) - margin_x)
    y0 = max(0, int(min(ys)) - margin_y)
    x1 = min(width, int(max(xs)) + margin_x)
    y1 = min(height, int(max(ys)) + margin_y)
    return bgr[y0:y1, x0:x1]


def fit_canvas(width: int, height: int, max_size: tuple[int, int] = DEFAULT_CANVAS_MAX) -> tuple[int, int]:
    """把画布尺寸等比缩放到默认画框内（小图放大、大图缩小），返回 (w, h)。"""
    max_w, max_h = max_size
    scale = min(max_w / max(width, 1), max_h / max(height, 1))
    return max(1, round(width * scale)), max(1, round(height * scale))


def build_output_image(processed_bgr: np.ndarray, width: int, height: int, max_size: tuple[int, int] = DEFAULT_CANVAS_MAX) -> tuple[bytes, int, int]:
    """把处理后的 BGR 图等比缩放到默认画布，返回 (PNG bytes, scaled_w, scaled_h)。"""
    _require_cv2()
    sw, sh = fit_canvas(width, height, max_size)
    resized = cv2.resize(
        processed_bgr,
        (sw, sh),
        interpolation=cv2.INTER_AREA if sw < width else cv2.INTER_LINEAR,
    )
    ok, buf = cv2.imencode(".png", resized)
    if not ok:
        raise ValueError("图片编码失败")
    return buf.tobytes(), sw, sh


@dataclass(eq=False)
class ComponentInfo:
    color: str
    points: np.ndarray
    area: float
    bbox: tuple[int, int, int, int]


@dataclass
class InterferenceResult:
    kept: list[ComponentInfo]
    excluded: list[tuple[ComponentInfo, str]]
    suspected: list[ComponentInfo]


def classify_interference(components: list[ComponentInfo], width: int, height: int) -> InterferenceResult:
    """按保守优先级过滤：极小噪点 → 贴边细框 → 细长线 → 疑似标记。"""
    tiny_area = MIN_AREA_RATIO * width * height
    border_w = BORDER_FRAME_THICKNESS_RATIO * min(width, height)
    long_axis = 0.3 * max(width, height)
    suspect_area = SUSPECT_AREA_RATIO * width * height
    kept: list[ComponentInfo] = []
    excluded: list[tuple[ComponentInfo, str]] = []
    suspected: list[ComponentInfo] = []
    for c in components:
        w_c = c.bbox[2] - c.bbox[0]
        h_c = c.bbox[3] - c.bbox[1]
        if c.area < tiny_area:
            excluded.append((c, "tiny"))
            continue
        short = max(1.0, float(min(w_c, h_c)))
        long = float(max(w_c, h_c))
        touches_border = c.bbox[0] <= 1 or c.bbox[1] <= 1 or c.bbox[2] >= width - 2 or c.bbox[3] >= height - 2
        if touches_border and short < border_w and long > long_axis:
            excluded.append((c, "border_frame"))
            continue
        if long / short > THIN_ASPECT_RATIO:
            excluded.append((c, "thin"))
            continue
        solidity = c.area / max(1.0, float(w_c * h_c))
        if c.area > suspect_area and solidity < SUSPECT_SOLIDITY:
            suspected.append(c)
        else:
            kept.append(c)
    return InterferenceResult(kept=kept, excluded=excluded, suspected=suspected)


def _kernel_size(width: int, height: int) -> int:
    k = max(3, int(min(width, height) / 400))
    return k if k % 2 == 1 else k + 1


def _order_points(pts: np.ndarray) -> np.ndarray:
    """把任意凸四边形四点排序为 TL, TR, BR, BL（对旋转/倾斜形状稳健）。"""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    tl_i = int(np.argmin(s))
    br_i = int(np.argmax(s))
    others = [i for i in range(4) if i not in (tl_i, br_i)]
    a, b = others
    if pts[a, 1] <= pts[b, 1]:
        tr_i, bl_i = a, b
    else:
        tr_i, bl_i = b, a
    return np.array([pts[tl_i], pts[tr_i], pts[br_i], pts[bl_i]], dtype=np.float32)


def _quad_max_tilt_deg(quad: np.ndarray) -> float:
    """四边形四条边相对水平/垂直轴的最大夹角（度）。轴对齐矩形为 0。"""
    tl, tr, br, bl = _order_points(quad)
    edges = [tr - tl, br - tr, bl - br, tl - bl]
    max_tilt = 0.0
    for e in edges:
        angle = abs(math.degrees(math.atan2(abs(float(e[1])), abs(float(e[0])))))
        tilt = min(angle, 90.0 - angle)
        max_tilt = max(max_tilt, tilt)
    return max_tilt


def _warp_aspect_change(img: np.ndarray, quad: np.ndarray) -> float:
    """校正前后宽高比的最大变化倍数（≥1）。"""
    tl, tr, br, bl = _order_points(quad)
    quad_w = max(float(np.linalg.norm(tr - tl)), float(np.linalg.norm(br - bl)))
    quad_h = max(float(np.linalg.norm(bl - tl)), float(np.linalg.norm(br - tr)))
    img_h, img_w = img.shape[:2]
    orig_aspect = img_w / img_h
    quad_aspect = quad_w / quad_h
    return max(orig_aspect / quad_aspect, quad_aspect / orig_aspect)


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
    quad = approx.reshape(4, 2).astype(np.float32)
    # 电子图自带的框/区域通常与图像轴对齐：倾斜过小则不需要透视校正
    if _quad_max_tilt_deg(quad) <= MAX_TILT_DEG:
        return None, None
    # 校正前后宽高比变化过大 → 更可能是内部区域而非纸张边缘
    if _warp_aspect_change(img, quad) > MAX_ASPECT_CHANGE:
        return None, "疑似检测到内部区域而非纸张边缘，已跳过透视校正"
    return quad, None


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
    excluded: list[dict] = field(default_factory=list)
    texts: list[dict] = field(default_factory=list)
    processed_image: np.ndarray | None = None


def recognize_from_bytes(data: bytes, ocr=None, clip=None) -> RecognizeResult:
    """识别管线入口：解码 → 透视校正（保守门控）→ 分类 → 清理 → 轮廓 → 干扰过滤 → 分区。"""
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
    components: list[ComponentInfo] = []
    for name in ("红", "橙", "黄", "蓝"):
        mask = clean_mask(masks[name], kernel_size)
        polys = mask_to_polygons(mask, width, height, min_area, epsilon)
        for poly in polys:
            xs = poly[:, 0]
            ys = poly[:, 1]
            components.append(ComponentInfo(
                color=name,
                points=poly,
                area=float(cv2.contourArea(poly.astype(np.float32))),
                bbox=(int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
            ))
    filtered = classify_interference(components, width, height)
    kept_ids = {id(c) for c in filtered.kept}
    suspected_ids = {id(c) for c in filtered.suspected}
    zones: list[dict] = []
    seq = 0
    for c in components:
        if id(c) not in kept_ids and id(c) not in suspected_ids:
            continue
        if len(zones) >= MAX_ZONES:
            if "识别区域过多" not in warnings:
                warnings.append("识别区域过多，已保留前 200 个")
            break
        seq += 1
        zones.append({
            "client_id": f"draft-{uuid4().hex}",
            "name": f"分区{seq}",
            "risk_level": LEVEL_BY_COLOR[c.color],
            "color": COLOR_HEX_BY_LEVEL[LEVEL_BY_COLOR[c.color]],
            "suspected": id(c) in suspected_ids,
            "polygons": [{
                "id": f"poly-{uuid4().hex}",
                "label": None,
                "points": normalize_points(c.points, width, height),
            }],
        })
    excluded_items = [{
        "color": c.color,
        "reason": reason,
        "polygons": [{
            "id": f"poly-{uuid4().hex}",
            "label": None,
            "points": normalize_points(c.points, width, height),
        }],
    } for c, reason in filtered.excluded]
    if ocr is None:
        from app.services.vision_helpers import extract_texts
        ocr = extract_texts
    if clip is None:
        from app.services.vision_helpers import classify_region
        clip = classify_region
    try:
        texts: list[dict] = ocr(bgr) or []
    except Exception:
        texts = []
    for text in texts:
        pts = text.get("points") or []
        if len(pts) < 3:
            continue
        cx = sum(p["x"] for p in pts) / len(pts) / width * 100
        cy = sum(p["y"] for p in pts) / len(pts) / height * 100
        for zone in zones:
            if zone.get("suggested_name"):
                continue
            for poly in zone["polygons"]:
                if _point_in_polygon(cx, cy, poly["points"]):
                    zone["suggested_name"] = text["text"]
                    break
    # OCR 返回像素坐标；API schema 要求 0-100 归一化，统一在管线输出前转换
    for text in texts:
        pts = text.get("points") or []
        if len(pts) >= 3:
            text["points"] = normalize_points(
                np.array([[p["x"], p["y"]] for p in pts], dtype=np.float64),
                width,
                height,
            )
    for zone in zones:
        if zone.get("suspected") and not zone.get("ai_hint"):
            try:
                hint = clip(_crop_from_zone(bgr, zone, width, height))
                if hint:
                    zone["ai_hint"] = hint
            except Exception:
                pass
    return RecognizeResult(
        zones=zones,
        warnings=warnings,
        width=width,
        height=height,
        excluded=excluded_items,
        texts=texts,
        processed_image=bgr,
    )
