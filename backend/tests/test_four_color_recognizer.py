"""四色分布图识别器单测：合成图覆盖颜色分类、清理、轮廓、透视、管线。"""
import io

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.four_color_recognizer import (
    classify_pixels,
    clean_mask,
    mask_to_polygons,
    normalize_points,
)

PALETTE_BGR = {
    "红": (0, 0, 255),
    "橙": (0, 127, 255),
    "黄": (0, 255, 255),
    "蓝": (255, 0, 0),
}


def _bgr_img(width=200, height=200):
    return np.full((height, width, 3), 255, dtype=np.uint8)


def _png_bytes(img_rgb: Image.Image) -> bytes:
    buf = io.BytesIO()
    img_rgb.save(buf, format="PNG")
    return buf.getvalue()


def _four_rect_rgb(width=600, height=450):
    """四个标准四色矩形（RGB 值），供管线测试。"""
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    rects = [
        (40, 40, 280, 180, (255, 0, 0)),
        (320, 40, 560, 180, (255, 127, 0)),
        (40, 230, 280, 410, (255, 255, 0)),
        (320, 230, 560, 410, (0, 0, 255)),
    ]
    for x0, y0, x1, y1, color in rects:
        d.rectangle([x0, y0, x1, y1], fill=color)
    return img


def test_classify_pixels_assigns_each_palette_color():
    img = _bgr_img()
    for i, name in enumerate(PALETTE_BGR):
        x0 = 25 + i * 50
        img[50:150, x0:x0 + 40] = PALETTE_BGR[name]
    masks = classify_pixels(img)
    for i, name in enumerate(PALETTE_BGR):
        cx = 25 + i * 50 + 20
        assert masks[name][100, cx] == 255, f"{name} 区域应命中"
        for other in PALETTE_BGR:
            if other != name:
                assert masks[other][100, cx] == 0, f"{other} 掩码不应包含 {name} 区域"
    assert masks["红"][10, 10] == 0, "白色背景不应命中任何颜色"


def test_classify_pixels_tolerates_print_shift():
    img = _bgr_img()
    img[50:150, 50:150] = (20, 20, 200)  # 略暗的红（BGR）
    masks = classify_pixels(img)
    assert masks["红"][100, 100] == 255


def test_classify_pixels_returns_uint8_binary():
    img = _bgr_img()
    masks = classify_pixels(img)
    assert set(masks["红"].flat) <= {0, 255}


def test_clean_mask_removes_small_noise():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:90, 10:90] = 255
    mask[2:4, 2:4] = 255  # 2x2 噪点
    cleaned = clean_mask(mask, kernel_size=3)
    assert cleaned[50, 50] == 255
    assert cleaned[3, 3] == 0


def test_mask_to_polygons_simplifies_rectangle():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:90, 10:90] = 255
    polys = mask_to_polygons(mask, 100, 100, min_area=100.0, epsilon=2.0)
    assert len(polys) == 1
    assert len(polys[0]) == 4
    area = cv2.contourArea(polys[0].astype(np.float32))
    assert 5000 < area < 7000


def test_mask_to_polygons_filters_small_areas():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:20, 10:20] = 255   # 100 px
    mask[40:80, 40:80] = 255   # 1600 px
    polys = mask_to_polygons(mask, 100, 100, min_area=500.0, epsilon=1.0)
    assert len(polys) == 1
    assert cv2.contourArea(polys[0].astype(np.float32)) > 1000


def test_normalize_points_clamps_and_rounds():
    points = [(-5.0, 55.0), (100.5, 33.333), (25.0, 0.0)]
    out = normalize_points(points, 100, 100)
    assert out == [{"x": 0.0, "y": 55.0}, {"x": 100.0, "y": 33.33}, {"x": 25.0, "y": 0.0}]
