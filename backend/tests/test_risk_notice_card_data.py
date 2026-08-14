"""风险告知卡常量数据测试：标志映射覆盖 GB 6441 全部 20 类。"""
from app.services.risk_notice_card_data import (
    SIGN_GROUPS,
    DEFAULT_SIGN_GROUP,
    EMERGENCY_TEMPLATES,
    SIGN_CATEGORY_ORDER,
    GB6441_ACCIDENT_TYPES,
)


def test_sign_groups_cover_all_gb6441_types():
    assert set(SIGN_GROUPS.keys()) == set(GB6441_ACCIDENT_TYPES)


def test_sign_groups_are_non_empty_and_ordered():
    order_index = {c: i for i, c in enumerate(SIGN_CATEGORY_ORDER)}
    for accident_type, signs in SIGN_GROUPS.items():
        assert signs, f"{accident_type} 缺少标志"
        cats = [s["category"] for s in signs]
        indexes = [order_index[c] for c in cats]
        assert indexes == sorted(indexes), (
            f"{accident_type} 标志顺序应为 "
            f"{[c for c in SIGN_CATEGORY_ORDER if c in cats]}"
        )


def test_every_sign_refers_to_known_svg():
    from pathlib import Path
    sign_dir = Path(__file__).resolve().parents[1] / "app" / "static" / "signs"
    for accident_type, signs in SIGN_GROUPS.items():
        for s in signs:
            assert (sign_dir / f"{s['svg_name']}.svg").exists(), s["svg_name"]


def test_default_sign_group_and_emergency_templates():
    assert DEFAULT_SIGN_GROUP
    assert EMERGENCY_TEMPLATES["火灾"]
    assert len(EMERGENCY_TEMPLATES["火灾"]) >= 2


def test_emergency_templates_cover_all_types():
    assert set(EMERGENCY_TEMPLATES) == set(GB6441_ACCIDENT_TYPES)
    for accident_type, steps in EMERGENCY_TEMPLATES.items():
        assert len(steps) >= 2, accident_type


def test_eyewash_not_mapped_to_thermal_burn_or_inhalation():
    """洗眼台仅用于化学灼伤/腐蚀品溅眼，不应出现在热烫伤与吸入中毒的通用标志组。"""
    for accident_type in ("灼烫", "中毒和窒息"):
        names = [s["name"] for s in SIGN_GROUPS[accident_type]]
        assert "洗眼台" not in names, f"{accident_type} 不应包含洗眼台"
