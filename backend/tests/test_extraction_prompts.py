"""抽取提示词与输出结构校验。"""

import pytest

from app.services.extraction_prompts import (
    ENTITY_SCHEMAS,
    ExtractionSchemaError,
    build_messages,
    validate_payload,
)


def test_entity_schemas_cover_two_targets():
    assert set(ENTITY_SCHEMAS) >= {"major_hazard_unit", "major_hazard_unit_chemical"}


def test_build_messages_includes_required_fields_and_source_hint():
    msgs = build_messages(
        target_entity="major_hazard_unit_chemical",
        text="罐区A 储存甲醇 79 吨",
        source_hint="安全评价报告.pdf",
    )
    joined = " ".join(m["content"] for m in msgs)
    assert "chemical_name" in joined
    assert "q_design_max" in joined
    assert "安全评价报告.pdf" in joined, "必须把来源文件名喂给模型，便于产出 source_locator"
    assert "JSON" in joined


def test_validate_payload_accepts_good_row():
    ok = validate_payload(
        "major_hazard_unit_chemical",
        {
            "chemical_name": "甲醇",
            "q_design_max": 79,
            "physical_state": "液态",
            "source_locator": "报告.pdf 段12",
            "confidence": "medium",
        },
    )
    assert ok["chemical_name"] == "甲醇"
    assert ok["q_design_max"] == 79.0


def test_validate_payload_rejects_missing_required():
    with pytest.raises(ExtractionSchemaError) as ei:
        validate_payload(
            "major_hazard_unit_chemical",
            {"chemical_name": "甲醇", "source_locator": "x", "confidence": "high"},
        )
    assert "q_design_max" in str(ei.value)


def test_validate_payload_rejects_bad_unit_type():
    with pytest.raises(ExtractionSchemaError):
        validate_payload(
            "major_hazard_unit",
            {"name": "罐区A", "unit_type": "storage_area", "source_locator": "x", "confidence": "high"},
        )


def test_validate_payload_rejects_unknown_confidence():
    with pytest.raises(ExtractionSchemaError):
        validate_payload(
            "major_hazard_unit",
            {"name": "罐区A", "unit_type": "storage", "source_locator": "x", "confidence": "sure"},
        )


def test_validate_payload_requires_source_locator():
    """没有来源定位的抽取结果不可追溯，必须拒绝。"""
    with pytest.raises(ExtractionSchemaError) as ei:
        validate_payload(
            "major_hazard_unit",
            {"name": "罐区A", "unit_type": "storage", "confidence": "high"},
        )
    assert "source_locator" in str(ei.value)


def test_validate_payload_coerces_numeric_strings():
    """模型常把数值输出成字符串，这里做受控转换。"""
    ok = validate_payload(
        "major_hazard_unit_chemical",
        {
            "chemical_name": "氯",
            "q_design_max": "5.0",
            "source_locator": "x",
            "confidence": "high",
        },
    )
    assert ok["q_design_max"] == 5.0
