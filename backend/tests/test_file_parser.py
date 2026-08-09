import io

import pytest

from app.services.file_parser import parse_file_text


def test_parse_csv_text():
    text = parse_file_text("chem.csv", b"name,cas\nmethanol,67-56-1\nethanol,64-17-5\n")
    assert "methanol" in text
    assert "67-56-1" in text


def test_parse_plain_text_txt():
    text = parse_file_text("note.txt", "企业地址：杭州市XX区".encode("utf-8"))
    assert "企业地址" in text


def test_parse_unsupported_extension_raises():
    with pytest.raises(ValueError):
        parse_file_text("file.exe", b"x")


def test_parse_xlsx_bytes():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["化学品名称", "CAS号"])
    ws.append(["甲醇", "67-56-1"])
    buf = io.BytesIO()
    wb.save(buf)
    text = parse_file_text("chem.xlsx", buf.getvalue())
    assert "甲醇" in text
    assert "67-56-1" in text
