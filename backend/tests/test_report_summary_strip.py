"""test_report_summary_strip.py"""
from app.services.report_summary_utils import strip_trailing_json


def test_strip_json_at_end():
    text = "正文内容\n{\"internal_resource_count\":21,\"overall_assessment\":\"结论\"}"
    cleaned, parsed = strip_trailing_json(text)
    assert parsed["internal_resource_count"] == 21
    assert "正文内容" in cleaned
    assert "internal_resource_count" not in cleaned


def test_strip_json_followed_by_note():
    text = (
        "正文内容\n"
        "{\"internal_resource_count\":21,\"resource_gaps\":[{\"category\":\"消防\",\"needed\":\"x\"}]}\n"
        "注：本章数据来源于台账。"
    )
    cleaned, parsed = strip_trailing_json(text)
    assert parsed["resource_gaps"][0]["category"] == "消防"
    assert "internal_resource_count" not in cleaned
    assert "注：本章数据来源于台账" in cleaned


def test_strip_json_with_curly_quotes():
    text = "正文\n{\u201cinternal_resource_count\u201d:21}"
    cleaned, parsed = strip_trailing_json(text)
    assert parsed["internal_resource_count"] == 21
    assert "internal_resource_count" not in cleaned


def test_no_json_unchanged():
    text = "只是普通正文，没有 JSON。"
    cleaned, parsed = strip_trailing_json(text)
    assert parsed is None
    assert cleaned == text
