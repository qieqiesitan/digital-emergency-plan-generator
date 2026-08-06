"""四色分布图识别管线：颜色分割 → 形态学清理 → 轮廓提取 → 多边形归一化。"""
from __future__ import annotations

import cv2
import numpy as np

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


def classify_pixels(img: np.ndarray) -> dict[str, np.ndarray]:
    """按 HSV 距离把每个像素归类到最近标准色；距离超过阈值则归为背景。"""
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
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)


def mask_to_polygons(mask: np.ndarray, width: int, height: int, min_area: float, epsilon: float) -> list[np.ndarray]:
    """外轮廓提取 + Douglas-Peucker 简化 + 最小面积过滤，返回像素坐标多边形列表。"""
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
