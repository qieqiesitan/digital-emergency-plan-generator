"""对账：期望 vs 实际，差异要能说清原因。"""

from app.services.ingest_reconcile import compare, payload_checksum


def test_compare_matches():
    out = compare(expected=100, actual=100)
    assert out["ok"] is True
    assert out["diff"] == 0


def test_compare_reports_shortfall_with_reason():
    out = compare(expected=100, actual=97, failed=2, skipped=1)
    assert out["ok"] is False
    assert out["diff"] == -3
    assert "失败 2" in out["diff_note"]
    assert "跳过 1" in out["diff_note"]


def test_compare_flags_unexplained_shortfall():
    """差额无法被失败/跳过解释时，必须显式说明"原因不明"，不能含糊过去。"""
    out = compare(expected=100, actual=95, failed=0, skipped=0)
    assert out["ok"] is False
    assert "原因不明" in out["diff_note"]


def test_compare_surplus_is_not_ok():
    """实际比期望多也要报——多出来的行同样要查清来源。"""
    out = compare(expected=10, actual=12)
    assert out["ok"] is False
    assert out["diff"] == 2


def test_payload_checksum_is_order_insensitive():
    a = payload_checksum([{"x": 1}, {"y": 2}])
    b = payload_checksum([{"y": 2}, {"x": 1}])
    assert a == b


def test_payload_checksum_changes_on_content():
    a = payload_checksum([{"x": 1}])
    b = payload_checksum([{"x": 2}])
    assert a != b
