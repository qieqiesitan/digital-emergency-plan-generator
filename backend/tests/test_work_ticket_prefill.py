"""确定性预填：来源优先级、空值跳过、meta 正确。"""

from app.services.work_ticket_prefill import build_values, pick_value

_FIELDS = [
    {"field_key": "applicant_unit", "label": "作业申请单位"},
    {"field_key": "work_unit", "label": "作业单位"},
    {"field_key": "apply_time", "label": "作业申请时间"},
    {"field_key": "fire_level", "label": "动火作业级别"},
    {"field_key": "work_content", "label": "作业内容"},
]


def test_applicant_unit_prefers_enterprise_over_history():
    value, source = pick_value(
        "applicant_unit", candidates={"enterprise": "某某化工有限公司", "history": "旧单位"}
    )
    assert (value, source) == ("某某化工有限公司", "enterprise")


def test_work_unit_prefers_history_over_enterprise():
    value, source = pick_value(
        "work_unit", candidates={"enterprise": "某某化工", "history": "维保班组"}
    )
    assert (value, source) == ("维保班组", "history")


def test_blank_candidate_falls_through():
    value, source = pick_value("work_unit", candidates={"enterprise": "", "history": "维保班组"})
    assert (value, source) == ("维保班组", "history")


def test_no_candidate_returns_none():
    assert pick_value("work_unit", candidates={}) == (None, None)


def test_build_values_writes_meta_only_for_prefilled_fields():
    values, meta = build_values(
        _FIELDS,
        candidates={
            "enterprise": "某某化工有限公司",
            "history": "",
            "member": "",
            "risk_object": "",
            "system_default": "2026-09-20T10:00:00+08:00",
            "template_link": "二级",
        },
    )
    assert values["applicant_unit"] == "某某化工有限公司"
    assert values["fire_level"] == "二级"
    assert values["apply_time"].startswith("2026-09-20")
    assert "work_content" not in values
    assert meta["applicant_unit"]["source"] == "enterprise"
    assert meta["fire_level"]["source"] == "template_link"
    assert "work_content" not in meta


def test_build_values_ignores_keys_not_in_template():
    values, meta = build_values(
        [{"field_key": "applicant_unit", "label": "作业申请单位"}],
        candidates={"enterprise": "E", "member": "张三"},
    )
    assert set(values) == {"applicant_unit"}
    assert set(meta) == {"applicant_unit"}


def test_unregistered_field_is_never_prefilled():
    """票种专有字段（作业高度/吊装质量/盲板编号…）不在来源表里 → 一律不预填。"""
    values, meta = build_values(
        [{"field_key": "work_height", "label": "作业高度(m)"}],
        candidates={"history": "12", "member": "张三", "enterprise": "E"},
    )
    assert values == {}
    assert meta == {}


def test_default_period_is_eight_hours():
    from datetime import datetime, timezone

    from app.services.work_ticket_prefill import default_period

    start = datetime(2026, 9, 20, 8, 0, tzinfo=timezone.utc)
    begin, end = default_period(start)
    assert begin.startswith("2026-09-20T08:00")
    assert end.startswith("2026-09-20T16:00")
