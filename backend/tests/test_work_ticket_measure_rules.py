"""措施"是否涉及"建议引擎：条件三态、保守策略、正文锚定。

映射不再写在引擎里（改由 work_ticket_measure_conditions 表注入），
故本文件显式构造 conditions_map，聚焦判定逻辑本身。
"""

from app.services.work_ticket_condition_loader import measure_ref
from app.services.work_ticket_measure_rules import (
    APPLICABLE,
    NOT_APPLICABLE,
    UNKNOWN,
    MeasureContext,
    suggest_measures,
)

# 精简条文（真实条文的可辨识前缀）——仅用于构造锚点，不依赖标准文本
TEXT = {
    1: "动火设备内部构件清洗干净",
    2: "与动火设备相连接的所有管线已断开",
    4: "油气罐区动火点同一防火堤内和防火间距内的油品储罐未进行脱水",
    7: "乙炔气瓶直立放置",
    9: "电焊机所处位置已考虑防火防爆要求",
    13: "用于连续检测的移动式可燃气体检测仪已配备到位",
    16: "其他安全措施：编制人：",
}

LABELS = {
    "internal_work": "本次动火在设备内部",
    "connected_pipeline": "作业设备连接有管线/阀门",
    "in_tank_area": "作业点在油气罐区防火堤内",
    "gas_welding": "本次动火使用气焊/气割",
    "electric_welding": "本次动火使用电焊",
    "height_work": "本次作业涉及高处作业",
}


def _measures(order: list[int] | None = None) -> list[dict]:
    keys = order if order is not None else sorted(TEXT)
    return [{"sort_order": o, "measure_text": TEXT[o]} for o in keys]


def _map(**mapping: list[str]) -> dict[tuple[str, str], tuple[str, ...]]:
    """把 {措施序号: [条件]} 构造成以正文锚点为键的映射表。"""
    out: dict[tuple[str, str], tuple[str, ...]] = {}
    for order_str, conds in mapping.items():
        out[("DHZY", measure_ref(TEXT[int(order_str)]))] = tuple(conds)
    return out


def _by_order(context, conditions_map, order=None) -> dict[int, dict]:
    rows = suggest_measures(
        _measures(order), context, conditions_map=conditions_map, labels=LABELS
    )
    return {row["sort_order"]: row for row in rows}


def test_condition_false_yields_not_applicable():
    out = _by_order(
        MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False}),
        _map(**{"4": ["in_tank_area"]}),
    )
    assert out[4]["suggest"] == NOT_APPLICABLE
    assert "罐区" in out[4]["reason"]


def test_condition_true_yields_applicable():
    out = _by_order(
        MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": True}),
        _map(**{"4": ["in_tank_area"]}),
    )
    assert out[4]["suggest"] == APPLICABLE


def test_missing_condition_yields_unknown():
    """条件是 None（未确定）时必须 unknown —— 不允许把"不知道"当成"不涉及"。"""
    out = _by_order(
        MeasureContext(ticket_type="DHZY", conditions={}), _map(**{"4": ["in_tank_area"]})
    )
    assert out[4]["suggest"] == UNKNOWN
    assert out[4]["reason"] == "现场条件未确定"


def test_composite_condition_true_beats_unknown():
    """复合条件里只要有一个为真，结论就是"涉及"，不受同一措施其他条件未知影响。"""
    out = _by_order(
        MeasureContext(ticket_type="DHZY", conditions={"electric_welding": True}),
        _map(**{"13": ["gas_welding", "electric_welding"]}),
    )
    assert out[13]["suggest"] == APPLICABLE


def test_measure_without_mapping_is_unknown():
    out = _by_order(
        MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False}),
        _map(**{"4": ["in_tank_area"]}),
    )
    assert out[16]["suggest"] == UNKNOWN
    assert out[16]["reason"] is None


def test_no_conditions_map_yields_all_unknown():
    """未注入映射表时的安全默认：全部 unknown，绝不猜。"""
    rows = suggest_measures(_measures(), MeasureContext(ticket_type="DHZY", conditions={}))
    assert {row["suggest"] for row in rows} == {UNKNOWN}


def test_other_ticket_type_has_no_mapping():
    """映射按票种隔离：动火的映射不会作用到其它票种。"""
    context = MeasureContext(ticket_type="QZDZ", conditions={"in_tank_area": False})
    rows = suggest_measures(_measures(), context, conditions_map=_map(**{"4": ["in_tank_area"]}))
    assert {row["suggest"] for row in rows} == {UNKNOWN}


def test_accepts_objects_with_measure_text_attribute():
    """既接受 dict，也接受 ORM/TemplateMeasure 对象。"""

    class _Measure:
        sort_order = 4
        measure_text = TEXT[4]

    context = MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False})
    rows = suggest_measures(
        [_Measure()], context, conditions_map=_map(**{"4": ["in_tank_area"]}), labels=LABELS
    )
    assert rows[0]["suggest"] == NOT_APPLICABLE


def test_anchor_survives_reordering():
    """锚定稳定性：措施顺序打乱后，判定结果仍跟着同一正文走。"""
    conditions_map = _map(**{"4": ["in_tank_area"]})
    context = MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False})
    normal = _by_order(context, conditions_map)
    shuffled = _by_order(context, conditions_map, order=[16, 4, 1, 13, 9, 7, 2])
    assert normal[4]["suggest"] == shuffled[4]["suggest"] == NOT_APPLICABLE
    assert shuffled[1]["suggest"] == UNKNOWN  # 第 1 条没有映射，与顺序无关


# ── 自动推断规则（conditions_from_scenario） ──────────────────────────────


def test_auto_night_work_from_period():
    from app.services.work_ticket_measure_rules import conditions_from_scenario

    night = conditions_from_scenario(
        ticket_type="DLZY",
        work_period=["2026-09-21T21:00:00+08:00", "2026-09-21T23:00:00+08:00"],
    )
    assert night["night_work"] is True
    day = conditions_from_scenario(
        ticket_type="DLZY",
        work_period=["2026-09-21T08:00:00+08:00", "2026-09-21T16:00:00+08:00"],
    )
    assert day["night_work"] is False
    # 无时段时不判定夜间（has_other_tickets 对所有票种都会推断，故不断言整体为空）
    assert "night_work" not in conditions_from_scenario(ticket_type="DLZY")


def test_auto_above_30m_from_height_field():
    from app.services.work_ticket_measure_rules import conditions_from_scenario

    assert conditions_from_scenario(
        ticket_type="GCZY", field_values={"work_height": "32"}
    )["above_30m"] is True
    assert conditions_from_scenario(
        ticket_type="GCZY", field_values={"work_height": 12}
    )["above_30m"] is False
    assert "above_30m" not in conditions_from_scenario(ticket_type="GCZY")
    assert "above_30m" not in conditions_from_scenario(
        ticket_type="GCZY", field_values={"work_height": "未定"}
    )


def test_auto_deep_excavation_from_dig_depth():
    from app.services.work_ticket_measure_rules import conditions_from_scenario

    assert conditions_from_scenario(
        ticket_type="PTZY", field_values={"dig_depth": 1.5}
    )["deep_excavation"] is True
    assert conditions_from_scenario(
        ticket_type="PTZY", field_values={"dig_depth": "0.8"}
    )["deep_excavation"] is False


def test_auto_level_1_or_2_only_for_lifting():
    from app.services.work_ticket_measure_rules import conditions_from_scenario

    assert conditions_from_scenario(
        ticket_type="QZDZ", level="一级"
    )["level_1_or_2"] is True
    assert conditions_from_scenario(
        ticket_type="QZDZ", level="三级"
    )["level_1_or_2"] is False
    assert "level_1_or_2" not in conditions_from_scenario(ticket_type="DHZY", level="二级")
