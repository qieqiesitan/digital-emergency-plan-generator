"""SVG 标志资产规范测试。"""
import xml.etree.ElementTree as ET
from pathlib import Path
from app.services.risk_notice_card_data import SIGN_GROUPS, DEFAULT_SIGN_GROUP


SIGN_DIR = Path(__file__).resolve().parents[1] / "app" / "static" / "signs"
KNOWN_PREFIXES = ("warning-", "prohibition-", "instruction-", "notice-")


def _referenced_svg_names():
    names = set()
    for signs in SIGN_GROUPS.values():
        for s in signs:
            names.add(s["svg_name"])
    for s in DEFAULT_SIGN_GROUP:
        names.add(s["svg_name"])
    return names


def test_all_referenced_svgs_exist():
    missing = [n for n in _referenced_svg_names() if not (SIGN_DIR / f"{n}.svg").exists()]
    assert not missing, f"缺失 SVG: {missing}"


def test_all_svgs_are_valid_xml():
    """每个 SVG 文件都必须是可解析的合法 XML。"""
    for svg in SIGN_DIR.glob("*.svg"):
        try:
            ET.fromstring(svg.read_text(encoding="utf-8"))
        except ET.ParseError as exc:
            raise AssertionError(f"{svg.name} XML 解析失败: {exc}")


def test_svg_shape_and_color_rules():
    """抽查每个 SVG 包含四类标志的形状/颜色要素。"""
    for svg in SIGN_DIR.glob("*.svg"):
        content = svg.read_text(encoding="utf-8")
        if svg.name.startswith("warning-"):
            assert "polygon" in content and "#FFD100" in content and "#000" in content
        elif svg.name.startswith("prohibition-"):
            assert "circle" in content and "#C8102E" in content and "#fff" in content
        elif svg.name.startswith("instruction-"):
            assert "circle" in content and "#005EB8" in content and "#fff" in content
        elif svg.name.startswith("notice-"):
            assert "#009A44" in content and "#fff" in content
        else:
            raise AssertionError(
                f"未知前缀孤儿 SVG 文件: {svg.name}（应为 {KNOWN_PREFIXES} 之一）"
            )


def test_warning_explosion_uses_burst_star():
    """warning-explosion.svg 必须是爆裂星形（星形 polygon），而非感叹号。"""
    svg = SIGN_DIR / "warning-explosion.svg"
    assert svg.exists(), "缺少 warning-explosion.svg"
    root = ET.fromstring(svg.read_text(encoding="utf-8"))
    star_polygons = [
        el
        for el in root.iter()
        if el.tag.endswith("}polygon")
        and len(el.get("points", "").replace(",", " ").split()) >= 16
    ]
    assert star_polygons, (
        "warning-explosion.svg 缺少爆裂星形（≥16 坐标点的星形 polygon），"
        "疑似回归为感叹号图形"
    )
