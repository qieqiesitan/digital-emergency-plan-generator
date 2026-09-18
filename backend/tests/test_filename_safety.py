"""文件名安全化（防目录穿越 / 路径归一）——2026-09-18 审计。"""

import pytest

from app.services.filename_safety import safe_filename


@pytest.mark.parametrize(
    "raw",
    [
        "../../evil.docx",
        "..\\..\\evil.docx",
        "/etc/passwd",
        "C:\\Windows\\evil.txt",
        "....//x",
        "..",
        "   ",
        "",
        None,
    ],
)
def test_unsafe_names_never_escape(raw):
    out = safe_filename(raw, fallback="fallback.docx")
    assert "/" not in out and "\\" not in out
    assert not out.startswith(".")
    assert out  # 空输入回落 fallback


def test_keeps_unicode_and_extension():
    assert safe_filename("西安宝岳 应急资源.docx") == "西安宝岳_应急资源.docx"


def test_length_limited():
    out = safe_filename("a" * 500 + ".docx", max_len=20)
    assert len(out) == 20


def test_plain_name_unchanged():
    assert safe_filename("report-2026.docx") == "report-2026.docx"
