"""SVG 标志资产规范测试。"""
from pathlib import Path
from app.services.risk_notice_card_data import SIGN_GROUPS, DEFAULT_SIGN_GROUP


SIGN_DIR = Path(__file__).resolve().parents[1] / "app" / "static" / "signs"


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
