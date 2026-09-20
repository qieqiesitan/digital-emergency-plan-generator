"""作业包：模型、槽位映射、票号回填、状态机。"""

import pytest


def test_batch_model_columns():
    from app.models.work_ticket import WorkTicketBatch

    cols = WorkTicketBatch.__table__.columns
    for name in (
        "id",
        "enterprise_id",
        "title",
        "status",
        "floor_id",
        "zone_id",
        "risk_object_id",
        "location_text",
        "work_period_start",
        "work_period_end",
        "shared_values",
        "content_base",
        "risk_basis",
        "created_by",
    ):
        assert name in cols, f"WorkTicketBatch 缺少 {name}"
    assert cols["status"].nullable is False
    assert cols["shared_values"].nullable is False


def test_instance_has_batch_id_column():
    from app.models.work_ticket import WorkTicketInstance

    assert "batch_id" in WorkTicketInstance.__table__.columns


def test_gas_test_supports_package_ownership():
    from app.models.work_ticket import WorkTicketGasTest

    cols = WorkTicketGasTest.__table__.columns
    assert "batch_id" in cols
    assert cols["instance_id"].nullable is True, "instance_id 必须改为可空以支持包级检测"


_SHARED = {
    "applicant_unit": "某某化工有限公司",
    "work_unit": "维保一队",
    "work_leader": "张三",
    "period": ["2026-09-20T08:00:00+08:00", "2026-09-20T16:00:00+08:00"],
    "location": "3# 罐区",
    "content": "更换 3# 罐底阀门",
    "risk_basis": "罐内残留易燃液体",
}


def test_fire_ticket_location_maps_to_fire_location():
    from app.services.work_ticket_batch import apply_slots

    values, meta = apply_slots(
        "DHZY",
        _SHARED,
        {
            "applicant_unit",
            "work_unit",
            "work_leader",
            "work_period",
            "fire_location",
            "work_content",
            "risk_identification",
        },
    )
    assert values["fire_location"] == "3# 罐区"
    assert values["work_period"] == _SHARED["period"]
    assert values["applicant_unit"] == "某某化工有限公司"
    assert values["risk_identification"] == "罐内残留易燃液体"
    assert meta["fire_location"] == {
        "source": "batch",
        "source_ref": {"slot": "location"},
        "edited": False,
    }


def test_confined_space_location_maps_to_space_location():
    from app.services.work_ticket_batch import apply_slots

    values, _ = apply_slots("YXKJ", _SHARED, {"space_location"})
    assert values["space_location"] == "3# 罐区"


def test_ticket_type_without_location_field_skips_slot():
    """高处/吊装/临电没有地点字段：不得凭空造键，也不得报错。"""
    from app.services.work_ticket_batch import apply_slots

    values, meta = apply_slots("GCZY", _SHARED, {"work_content", "work_height"})
    assert "work_height" not in values
    assert "work_content" in values
    assert all(item["source"] == "batch" for item in meta.values())


def test_slot_not_present_in_template_is_skipped():
    from app.services.work_ticket_batch import apply_slots

    values, _ = apply_slots("DHZY", _SHARED, {"applicant_unit"})
    assert set(values) == {"applicant_unit"}


def test_empty_shared_value_is_skipped():
    from app.services.work_ticket_batch import apply_slots

    values, _ = apply_slots("DHZY", {"applicant_unit": "", "work_unit": None}, {"applicant_unit", "work_unit"})
    assert values == {}


def test_related_map_excludes_self_and_is_stable():
    from app.services.work_ticket_batch import build_related_map

    items = [("id-a", "DHZY-X-0001"), ("id-b", "YXKJ-X-0002"), ("id-c", "QZDZ-X-0003")]
    mapping = build_related_map(items)
    assert mapping["id-a"] == "QZDZ-X-0003,YXKJ-X-0002"
    assert "DHZY-X-0001" not in mapping["id-a"]
    assert mapping["id-b"] == "DHZY-X-0001,QZDZ-X-0003"


def test_related_map_single_ticket_is_empty_string():
    from app.services.work_ticket_batch import build_related_map

    assert build_related_map([("id-a", "DHZY-X-0001")]) == {"id-a": ""}


def test_next_batch_status_transitions():
    from app.services.work_ticket_batch import next_batch_status

    assert next_batch_status("draft", submitted=0, total=3) == "draft"
    assert next_batch_status("draft", submitted=1, total=3) == "active"
    assert next_batch_status("active", submitted=3, total=3) == "closed"
    assert next_batch_status("closed", submitted=3, total=3) == "closed"


def test_batch_cancel_rejected_when_tickets_submitted():
    from app.services.work_ticket_batch import next_batch_status

    assert next_batch_status("draft", submitted=0, total=2, action="cancel") == "cancelled"
    with pytest.raises(ValueError, match="已提交"):
        next_batch_status("active", submitted=1, total=2, action="cancel")
