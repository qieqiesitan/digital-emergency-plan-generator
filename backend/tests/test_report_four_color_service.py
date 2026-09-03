import tempfile
from pathlib import Path

from PIL import Image

from app.services.report_four_color_service import (
    four_color_images_markdown,
    hex_to_rgba,
    insert_figure_block,
    polygon_points_to_pixels,
    render_four_color_png,
)


def test_hex_to_rgba():
    assert hex_to_rgba("#ff4d4f") == (255, 77, 79, 255)
    assert hex_to_rgba("#ff4d4f", alpha=90) == (255, 77, 79, 90)


def test_polygon_points_to_pixels():
    pts = [{"x": 0, "y": 0}, {"x": 100, "y": 100}]
    out = polygon_points_to_pixels(pts, 1200, 900)
    assert out[0] == (0, 0)
    assert out[1] == (1200, 900)


def test_four_color_images_markdown():
    md = four_color_images_markdown([
        {"floor_id": "f1", "floor_name": "默认总图",
         "url": "/uploads/enterprises/e1/four-color/f1.png"},
    ])
    assert "![默认总图 四色分布图](/uploads/enterprises/e1/four-color/f1.png)" in md


def test_insert_figure_block_between_sections():
    content = "# 企业报告\n\n## 二、危险有害因素辨识汇总\n\n汇总内容\n\n## 三、风险等级评估\n\n评估内容"
    out = insert_figure_block(content, "图块", "三、风险等级评估")
    assert out.index("图块") > out.index("二、危险有害因素辨识汇总")
    assert out.index("图块") < out.index("三、风险等级评估")


def test_insert_figure_block_idempotent():
    content = "# 标题\n\n## 三、风险等级评估\n\n内容"
    once = insert_figure_block(content, "![图](url)", "三、风险等级评估")
    twice = insert_figure_block(once, "![图](url)", "三、风险等级评估")
    assert twice == once


def test_render_four_color_png_creates_image(tmp_path):
    floor = {"name": "一层", "floor_plan_url": None}
    zones = [{
        "name": "机房",
        "effective_color": "#ff4d4f",
        "polygons": [{"label": "机房", "points": [
            {"x": 10, "y": 10}, {"x": 50, "y": 10},
            {"x": 50, "y": 50}, {"x": 10, "y": 50},
        ]}],
    }]
    points = [{"name": "配电柜", "x": 30, "y": 30}]
    out = tmp_path / "f1.png"
    render_four_color_png(floor, zones, points, str(out), font_path=None)
    assert out.exists()
    with Image.open(out) as im:
        assert im.size == (1200, 900)
