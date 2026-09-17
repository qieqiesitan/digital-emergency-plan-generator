"""危化品数据质量校验：CAS 校验位。

算法与 scripts/extract_gb18218_tables.py 同源（已在 82 条真实标准数据上验证），
此处验证提炼后的应用层服务行为一致。
"""

import pytest

from app.services.chemical_validation import (
    cas_checksum_ok,
    find_cas_in_text,
    is_valid_cas_format,
)


@pytest.mark.parametrize(
    "cas",
    ["7664-41-7", "75-44-5", "50-00-0", "108-88-3", "7440-23-5", "9004-70-0"],
)
def test_valid_cas_numbers_pass(cas):
    """这些值取自 GB 18218 表1 实测数据，必须通过。"""
    assert cas_checksum_ok(cas) is True


@pytest.mark.parametrize("cas", ["7664-41-8", "75-44-4", "1234-56-7"])
def test_wrong_check_digit_fails(cas):
    assert cas_checksum_ok(cas) is False


def test_empty_and_garbage_fail_checksum():
    assert cas_checksum_ok("") is False
    assert cas_checksum_ok("abc-12-3") is False
    assert cas_checksum_ok("12-3") is False  # 位数不足


def test_invalid_format_fails():
    # 注意：2 位首段是合法的（如甲醛 50-00-0），格式判断不能把 2 位首段当错误；
    # 76-41-7 形状合法、只是校验位不通过（由 cas_checksum_ok 判 False）。
    assert is_valid_cas_format("abc") is False
    assert is_valid_cas_format("7664-41") is False  # 缺校验位段
    assert is_valid_cas_format("76-4-7") is False  # 第二段必须 2 位
    assert is_valid_cas_format("76-41-7") is True
    assert is_valid_cas_format("7664-41-7") is True
    assert is_valid_cas_format("7664417") is True
    assert is_valid_cas_format("") is False
    assert is_valid_cas_format(" 7664-41-7 ") is True  # 去空白后判断


def test_find_cas_in_text_picks_candidates():
    text = "氯（CAS 7782-50-5）、光气 75-44-5，另一组 1234-56-7 是错的"
    found = find_cas_in_text(text)
    assert {f["cas"] for f in found} >= {"7782-50-5", "75-44-5"}
    assert any(f["cas"] == "1234-56-7" and f["ok"] is False for f in found)
    # 校验位正确的候选标 ok=True
    assert all(f["ok"] is True for f in found if f["cas"] == "7782-50-5")


def test_find_cas_in_text_dedupes_and_handles_empty():
    assert find_cas_in_text("") == []
    found = find_cas_in_text("氯 7782-50-5 与 7782-50-5 重复出现")
    assert [f["cas"] for f in found] == ["7782-50-5"]
