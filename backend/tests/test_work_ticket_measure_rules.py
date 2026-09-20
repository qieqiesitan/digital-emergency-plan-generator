"""措施"是否涉及"建议引擎：条件三态与保守策略。"""

from app.services.work_ticket_measure_rules import (
    APPLICABLE,
    NOT_APPLICABLE,
    UNKNOWN,
    MeasureContext,
    suggest_measures,
)

_FIRE_MEASURES = [{"sort_order": i} for i in range(1, 17)]


def _by_order(context: MeasureContext) -> dict[int, dict]:
    return {row["sort_order"]: row for row in suggest_measures(_FIRE_MEASURES, context)}


def test_condition_false_yields_not_applicable():
    out = _by_order(MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False}))
    assert out[4]["suggest"] == NOT_APPLICABLE
    assert "罐区" in out[4]["reason"]


def test_condition_true_yields_applicable():
    out = _by_order(MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": True}))
    assert out[4]["suggest"] == APPLICABLE


def test_missing_condition_yields_unknown():
    """条件是 None（未确定）时必须 unknown —— 不允许把"不知道"当成"不涉及"。"""
    out = _by_order(MeasureContext(ticket_type="DHZY", conditions={}))
    assert out[4]["suggest"] == UNKNOWN
    assert out[4]["reason"] == "现场条件未确定"


def test_composite_condition_true_beats_unknown():
    """复合条件里只要有一个为真，结论就是"涉及"，不受同一措施其他条件未知影响。"""
    out = _by_order(
        MeasureContext(ticket_type="DHZY", conditions={"electric_welding": True})
    )
    assert out[13]["suggest"] == APPLICABLE


def test_measure_without_condition_mapping_is_unknown():
    """第 8 条（现场配备灭火器）无条件依赖，引擎不表态，留人工处理。"""
    out = _by_order(MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False}))
    assert out[8]["suggest"] == UNKNOWN
    assert out[8]["reason"] is None


def test_other_ticket_types_stay_unknown():
    context = MeasureContext(ticket_type="QZDZ", conditions={"in_tank_area": False})
    out = suggest_measures([{"sort_order": 1}, {"sort_order": 2}], context)
    assert {row["suggest"] for row in out} == {UNKNOWN}


def test_accepts_objects_with_sort_order_attribute():
    """既接受 dict，也接受 ORM/TemplateMeasure 对象。"""

    class _Measure:
        sort_order = 4

    context = MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False})
    assert suggest_measures([_Measure()], context)[0]["suggest"] == NOT_APPLICABLE
