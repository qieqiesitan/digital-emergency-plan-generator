"""四色分布图识别器单测：合成图覆盖颜色分类、清理、轮廓、透视、管线。"""
import io

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.four_color_recognizer import (
    ComponentInfo,
    InterferenceResult,
    MAX_ZONES,
    build_output_image,
    classify_pixels,
    clean_mask,
    classify_interference,
    detect_legend_clusters,
    detect_perspective_quad,
    fit_canvas,
    mask_to_polygons,
    normalize_points,
    recognize_from_bytes,
    warp_perspective,
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


def _rotated_rect_quad(cx, cy, w, h, deg):
    """围绕中心旋转 deg 度的矩形四点（float32）。"""
    ang = np.radians(deg)
    c, s = np.cos(ang), np.sin(ang)
    corners = np.array(
        [[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]],
        dtype=np.float32,
    )
    rot = np.array([[c, -s], [s, c]], dtype=np.float32)
    return (corners - np.array([cx, cy], dtype=np.float32)) @ rot.T + np.array([cx, cy], dtype=np.float32)


def _clean_map_with_dominant_rect():
    """1200x900 干净电子图：红色方形区域占面积 24%（轴对齐），不应触发透视校正。"""
    img = Image.new("RGB", (1200, 900), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([80, 80, 700, 500], fill=(255, 0, 0))
    d.rectangle([750, 80, 1120, 500], fill=(0, 0, 255))
    d.rectangle([80, 560, 700, 840], fill=(255, 127, 0))
    d.rectangle([750, 560, 1120, 840], fill=(255, 255, 0))
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


def test_detect_perspective_quad_skips_axis_aligned_frame():
    """电子图自带的轴对齐边框/区域不应被当成纸张做透视校正。"""
    img = _bgr_img(400, 500)
    img[50:350, 50:450] = 0  # 轴对齐矩形
    quad, warning = detect_perspective_quad(img)
    assert quad is None
    assert warning is None


def test_detect_perspective_quad_returns_none_for_full_image():
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    quad, warning = detect_perspective_quad(img)
    assert quad is None
    assert warning is None


def test_detect_perspective_quad_finds_tilted_paper():
    """倾斜的照片纸面（旋转 12°）应被识别为需要校正的四边形。"""
    img = _bgr_img(500, 400)
    pts = _rotated_rect_quad(250, 200, 380, 260, 12)
    cv2.fillPoly(img, [pts.astype(np.int32)], (0, 0, 0))
    quad, warning = detect_perspective_quad(img)
    assert quad is not None and len(quad) == 4
    assert warning is None


def test_detect_perspective_quad_skips_extreme_aspect_region():
    """内部竖向斜条带（宽高比与整图差异过大）不应触发校正，且给出提示。"""
    img = _bgr_img(1200, 900)
    cv2.fillPoly(img, [np.array([[60, 40], [360, 40], [300, 860], [60, 860]], np.int32)], (0, 0, 0))
    quad, warning = detect_perspective_quad(img)
    assert quad is None
    assert warning is not None and "透视校正" in warning


def test_warp_perspective_makes_tilted_quad_full_frame():
    img = _bgr_img(500, 400)
    pts = _rotated_rect_quad(250, 200, 380, 260, 12)
    cv2.fillPoly(img, [pts.astype(np.int32)], (0, 0, 0))
    quad, _ = detect_perspective_quad(img)
    assert quad is not None
    warped = warp_perspective(img, quad)
    # 校正后纸面接近整图尺寸（380x260 旋转四边形）
    assert 240 <= warped.shape[0] <= 290
    assert 360 <= warped.shape[1] <= 410
    # 校正后检测器应认为"四边形即整图"（占比 >95%）→ 返回 None
    quad2, _ = detect_perspective_quad(warped)
    assert quad2 is None
    # 纸面内容占满全图：中心像素为黑
    assert warped[warped.shape[0] // 2, warped.shape[1] // 2].mean() < 128


def test_recognize_from_bytes_keeps_clean_map_aspect():
    """干净电子图：即使存在占 24% 面积的轴对齐区域，也不做透视校正，四分区位置保真。"""
    img = _clean_map_with_dominant_rect()
    result = recognize_from_bytes(_png_bytes(img))
    assert (result.width, result.height) == (1200, 900)
    assert len(result.zones) == 4
    red = next(z for z in result.zones if z["risk_level"] == "重大")
    xs = [p["x"] for p in red["polygons"][0]["points"]]
    ys = [p["y"] for p in red["polygons"][0]["points"]]
    # 红色矩形 [80,80]-[700,500] 归一化 bbox ≈ x:6.67-58.33, y:8.89-55.56
    assert abs(min(xs) - 80 / 1200 * 100) < 2
    assert abs(max(xs) - 700 / 1200 * 100) < 2
    assert abs(min(ys) - 80 / 900 * 100) < 2
    assert abs(max(ys) - 500 / 900 * 100) < 2


def test_recognize_from_bytes_skips_warp_with_tall_legend():
    """带竖向长图例的干净电子图：整图尺寸不变，四分区全部识别。"""
    img = _clean_map_with_dominant_rect()
    d = ImageDraw.Draw(img)
    d.rectangle([1140, 100, 1190, 860], fill=(0, 0, 0))  # 窄高图例
    result = recognize_from_bytes(_png_bytes(img))
    assert (result.width, result.height) == (1200, 900)
    assert len(result.zones) == 4


def test_recognize_from_bytes_skips_warp_for_slanted_internal_region():
    """内部斜梯形区域不再触发整图校正：三个分区全部保留。"""
    img = Image.new("RGB", (1200, 900), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(60, 40), (360, 40), (300, 860), (60, 860)], fill=(255, 0, 0))
    d.rectangle([420, 80, 1120, 500], fill=(0, 0, 255))
    d.rectangle([420, 560, 1120, 840], fill=(255, 255, 0))
    result = recognize_from_bytes(_png_bytes(img))
    assert (result.width, result.height) == (1200, 900)
    assert len(result.zones) == 3


def test_recognize_from_bytes_returns_four_zones():
    png = _png_bytes(_four_rect_rgb())
    result = recognize_from_bytes(png)
    assert result.width == 600
    assert result.height == 450
    assert len(result.zones) == 4
    levels = {z["risk_level"] for z in result.zones}
    assert levels == {"重大", "较大", "一般", "低"}
    for zone in result.zones:
        points = zone["polygons"][0]["points"]
        assert len(points) >= 3
        assert all(0 <= p["x"] <= 100 and 0 <= p["y"] <= 100 for p in points)


def test_recognize_from_bytes_zone_centers_match_rects():
    png = _png_bytes(_four_rect_rgb())
    result = recognize_from_bytes(png)
    expected = {
        "重大": (160 / 600 * 100, 110 / 450 * 100),
        "较大": (440 / 600 * 100, 110 / 450 * 100),
        "一般": (160 / 600 * 100, 320 / 450 * 100),
        "低": (440 / 600 * 100, 320 / 450 * 100),
    }
    for zone in result.zones:
        points = zone["polygons"][0]["points"]
        cx = sum(p["x"] for p in points) / len(points)
        cy = sum(p["y"] for p in points) / len(points)
        ex, ey = expected[zone["risk_level"]]
        assert abs(cx - ex) < 5 and abs(cy - ey) < 5


def test_recognize_from_bytes_tolerates_text_overlay():
    img = _four_rect_rgb()
    d = ImageDraw.Draw(img)
    for cx, cy in [(160, 110), (440, 110), (160, 320), (440, 320)]:
        d.rectangle([cx - 30, cy - 12, cx + 30, cy + 12], fill=(0, 0, 0))
    result = recognize_from_bytes(_png_bytes(img))
    assert len(result.zones) == 4


def test_recognize_from_bytes_ignores_small_noise():
    img = Image.new("RGB", (600, 450), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 280, 180], fill=(255, 0, 0))
    # 间距 40px 的孤立小噪点：单独面积 12px < MIN_AREA(13.5px)，且不与邻点粘连
    for x0 in [300, 340, 380, 420, 460]:
        d.rectangle([x0, 300, x0 + 3, 302], fill=(255, 0, 0))
    result = recognize_from_bytes(_png_bytes(img))
    assert len(result.zones) == 1
    assert result.zones[0]["risk_level"] == "重大"


def test_recognize_from_bytes_empty_when_no_color():
    png = _png_bytes(Image.new("RGB", (200, 150), "white"))
    result = recognize_from_bytes(png)
    assert result.zones == []


def _comp(color, x0, y0, x1, y1, area=None):
    return ComponentInfo(
        color=color,
        points=np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32),
        area=float(area or (x1 - x0) * (y1 - y0)),
        bbox=(x0, y0, x1, y1),
    )


def test_detect_legend_clusters_marks_three_color_cluster():
    comps = [
        _comp("红", 1000, 50, 1030, 80, area=900),
        _comp("橙", 1040, 50, 1070, 80, area=900),
        _comp("黄", 1000, 90, 1030, 120, area=900),
        _comp("蓝", 1040, 90, 1070, 120, area=900),
    ]
    excluded = detect_legend_clusters(comps, 1200, 900)
    assert excluded == {0, 1, 2, 3}


def test_detect_legend_clusters_ignores_isolated_zone():
    comps = [
        _comp("红", 80, 80, 700, 500, area=620 * 420),
        _comp("蓝", 750, 80, 1120, 500, area=370 * 420),
    ]
    excluded = detect_legend_clusters(comps, 1200, 900)
    assert excluded == set()


def test_detect_legend_clusters_requires_three_colors():
    comps = [
        _comp("红", 1000, 50, 1030, 80, area=900),
        _comp("橙", 1040, 50, 1070, 80, area=900),
    ]
    excluded = detect_legend_clusters(comps, 1200, 900)
    assert excluded == set()


def test_classify_interference_marks_tiny_thin_and_border_frame():
    comps = [
        _comp("红", 0, 0, 30, 30, area=40),             # 极小噪点（<54）
        _comp("红", 500, 100, 510, 900, area=8000),     # 细长
        _comp("蓝", 0, 400, 1199, 407, area=1199 * 7),  # 贴边细框（厚度 7 < 9）
        _comp("黄", 200, 200, 600, 600, area=160000),   # 正常分区
    ]
    result = classify_interference(comps, 1200, 900)
    reasons = {r for _, r in result.excluded}
    assert reasons == {"tiny", "thin", "border_frame"}
    assert len(result.kept) == 1
    assert result.kept[0].bbox == (200, 200, 600, 600)


def test_classify_interference_marks_suspected_odd_shape():
    # L 形：面积 70000 > 5%*640000=32000，实心度 70000/160000=0.4375 < 0.5
    points = np.array([[100, 100], [500, 100], [500, 200], [200, 200], [200, 500], [100, 500]], dtype=np.float32)
    area = cv2.contourArea(points)
    comp = ComponentInfo(color="红", points=points, area=float(area), bbox=(100, 100, 500, 500))
    result = classify_interference([comp], 800, 800)
    assert result.kept == []
    assert len(result.suspected) == 1
    assert result.excluded == []


def test_classify_interference_keeps_normal_zones():
    comps = [
        _comp("红", 80, 80, 700, 500, area=620 * 420),
        _comp("蓝", 750, 80, 1120, 500, area=370 * 420),
    ]
    result = classify_interference(comps, 1200, 900)
    assert len(result.kept) == 2
    assert result.excluded == []
    assert result.suspected == []


def _legend_map():
    """1200x900：四个分区（下移留边距）+ 右上角四色图例（紧邻小色块）。"""
    img = Image.new("RGB", (1200, 900), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([80, 120, 700, 540], fill=(255, 0, 0))
    d.rectangle([750, 120, 1120, 540], fill=(0, 0, 255))
    d.rectangle([80, 600, 700, 880], fill=(255, 127, 0))
    d.rectangle([750, 600, 1120, 880], fill=(255, 255, 0))
    d.rectangle([1000, 40, 1030, 70], fill=(255, 0, 0))
    d.rectangle([1040, 40, 1070, 70], fill=(255, 127, 0))
    d.rectangle([1000, 80, 1030, 110], fill=(255, 255, 0))
    d.rectangle([1040, 80, 1070, 110], fill=(0, 0, 255))
    return img


def test_recognize_excludes_legend_and_keeps_zones():
    result = recognize_from_bytes(_png_bytes(_legend_map()))
    assert (result.width, result.height) == (1200, 900)
    assert len(result.zones) == 4
    reasons = {e["reason"] for e in result.excluded}
    assert reasons == {"legend"}
    assert len(result.excluded) == 4


def test_recognize_marks_suspected_odd_shape():
    img = Image.new("RGB", (800, 800), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(100, 100), (500, 100), (500, 200), (200, 200), (200, 500), (100, 500)], fill=(255, 0, 0))
    result = recognize_from_bytes(_png_bytes(img))
    assert any(z.get("suspected") for z in result.zones)


def test_recognize_clean_map_has_no_excluded():
    result = recognize_from_bytes(_png_bytes(_clean_map_with_dominant_rect()))
    assert result.excluded == []
    assert all(not z.get("suspected") for z in result.zones)


def test_recognize_uses_ocr_suggested_name():
    img = _clean_map_with_dominant_rect()
    called = []

    def fake_ocr(_img):
        called.append(1)
        return [{
            "points": [{"x": 200, "y": 100}, {"x": 300, "y": 100}, {"x": 300, "y": 120}, {"x": 200, "y": 120}],
            "text": "原料库",
            "confidence": 0.95,
        }]

    result = recognize_from_bytes(_png_bytes(img), ocr=fake_ocr, clip=lambda crop: None)
    assert called
    names = [z.get("suggested_name") for z in result.zones]
    assert "原料库" in names
    assert result.texts[0]["text"] == "原料库"


def test_recognize_normalizes_ocr_text_points():
    """OCR 返回的像素坐标必须在管线输出时归一化为 0-100（API schema 要求）。"""
    img = _clean_map_with_dominant_rect()  # 1200x900

    def fake_ocr(_img):
        return [{
            "points": [{"x": 80, "y": 80}, {"x": 160, "y": 80}, {"x": 160, "y": 120}, {"x": 80, "y": 120}],
            "text": "原料库",
            "confidence": 0.95,
        }]

    result = recognize_from_bytes(_png_bytes(img), ocr=fake_ocr, clip=lambda crop: None)
    pts = result.texts[0]["points"]
    assert len(pts) == 4
    assert pts == [
        {"x": 6.67, "y": 8.89},
        {"x": 13.33, "y": 8.89},
        {"x": 13.33, "y": 13.33},
        {"x": 6.67, "y": 13.33},
    ]
    # 归一化后仍应命中分区建议名
    names = [z.get("suggested_name") for z in result.zones]
    assert "原料库" in names


def test_recognize_uses_clip_ai_hint_on_suspected():
    img = Image.new("RGB", (800, 800), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(100, 100), (500, 100), (500, 200), (200, 200), (200, 500), (100, 500)], fill=(255, 0, 0))
    result = recognize_from_bytes(_png_bytes(img), ocr=lambda img: [], clip=lambda crop: "疑似Logo")
    hints = [z.get("ai_hint") for z in result.zones]
    assert "疑似Logo" in hints


def test_recognize_degrades_without_ocr_clip():
    result = recognize_from_bytes(_png_bytes(_clean_map_with_dominant_rect()))
    assert result.texts == []
    assert all(not z.get("ai_hint") for z in result.zones)


def test_fit_canvas_scales_large_image_down():
    assert fit_canvas(3200, 2000) == (1600, 1000)


def test_fit_canvas_scales_small_image_up():
    assert fit_canvas(400, 300) == (1333, 1000)


def test_fit_canvas_keeps_exact_default():
    assert fit_canvas(1600, 1000) == (1600, 1000)


def test_build_output_image_returns_scaled_png():
    img = np.full((200, 400, 3), 255, dtype=np.uint8)
    png_bytes, w, h = build_output_image(img, 400, 200)
    assert (w, h) == (1600, 800)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_recognize_returns_processed_image():
    result = recognize_from_bytes(_png_bytes(_clean_map_with_dominant_rect()))
    assert result.processed_image is not None
    assert result.processed_image.shape[1] == result.width
    assert result.processed_image.shape[0] == result.height
