"""事故类型共享模块测试：GB 6441-2025 27 类清单、新旧映射、normalize/split。"""
from app.services.accident_types import (
    ACCIDENT_TYPES_2025,
    LEGACY_TO_NEW_MAP,
    normalize_accident_type,
    split_accident_values,
)


def test_accident_types_2025_complete_and_ordered():
    expected = [
        "物体打击", "厂（场）内车辆致害", "道路（轨道）车辆致害", "机械致害", "起重致害",
        "触电", "淹溺", "灼烫", "火灾", "高处坠落", "跌落", "坍塌", "水害", "容器爆炸",
        "管道爆炸", "可燃气体爆炸", "可燃液体蒸气爆炸", "粉尘爆炸", "民用爆炸物品爆炸",
        "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "中毒", "窒息", "滑坡",
        "泄漏", "其他",
    ]
    assert ACCIDENT_TYPES_2025 == expected
    assert len(ACCIDENT_TYPES_2025) == 27
    assert len(set(ACCIDENT_TYPES_2025)) == 27


def test_legacy_map_covers_all_old_standard_and_presets():
    old_standard = [
        "物体打击", "车辆伤害", "机械伤害", "起重伤害", "触电", "淹溺", "灼烫", "火灾",
        "高处坠落", "坍塌", "冒顶片帮", "透水", "放炮", "火药爆炸", "瓦斯爆炸", "锅炉爆炸",
        "容器爆炸", "其他爆炸", "中毒和窒息", "其他伤害",
    ]
    for old in old_standard:
        assert old in LEGACY_TO_NEW_MAP, old
        assert LEGACY_TO_NEW_MAP[old] in ACCIDENT_TYPES_2025
    assert LEGACY_TO_NEW_MAP["爆炸"] == "其他"
    assert LEGACY_TO_NEW_MAP["中毒窒息"] == "中毒"
    assert LEGACY_TO_NEW_MAP["瓦斯爆炸"] == "可燃气体爆炸"
    assert LEGACY_TO_NEW_MAP["锅炉爆炸"] == "容器爆炸"


def test_normalize_three_states():
    assert normalize_accident_type("火灾") == "火灾"
    assert normalize_accident_type("中毒和窒息") == "中毒"
    assert normalize_accident_type("设备损坏/数据丢失") == "设备损坏/数据丢失"
    assert normalize_accident_type("") == ""
    assert normalize_accident_type(None) == ""


def test_split_accident_values():
    assert split_accident_values("火灾、触电") == ["火灾", "触电"]
    assert split_accident_values("火灾,爆炸") == ["火灾", "爆炸"]
    assert split_accident_values("火灾") == ["火灾"]
    assert split_accident_values("") == []
