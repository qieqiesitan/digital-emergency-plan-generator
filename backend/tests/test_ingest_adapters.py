"""来源适配：文件 / 表格 / 对接，统一产出 pending 条目。"""

import pytest

from app.services.ingest_adapters import (
    AdapterError,
    rows_from_file_text,
    rows_from_sheet,
)


def test_rows_from_file_text_keeps_source_locator():
    """每条抽出的行都要带来源定位——可疑时能翻回原文。"""
    text = "一、罐区A\n罐区A 储存甲醇 79 吨，甲苯 12 吨。\n二、库房B\n库房B 存放丙酮。"
    rows = rows_from_file_text(text, "安全评价报告.pdf")
    assert rows, "应至少抽出一行"
    for r in rows:
        assert r["source_locator"].startswith("安全评价报告.pdf")
        assert r["raw_payload"]["text"]


def test_rows_from_file_text_empty_input():
    assert rows_from_file_text("", "x.pdf") == []
    assert rows_from_file_text(None, "x.pdf") == []


def test_rows_from_sheet_maps_columns_and_reports_required_missing():
    """表头映射 + 必填校验：缺必填列直接报错，不要把脏数据塞进队列。"""
    raw = [
        ["品种名称", "设计最大量(t)", "临界量(t)"],
        ["氯", "5", "5"],
        ["氨", "5", "10"],
    ]
    mapping = {
        "品种名称": "chemical_name",
        "设计最大量(t)": "q_design_max",
        "临界量(t)": "critical_quantity_t",
    }
    rows = rows_from_sheet(raw, mapping, required=["chemical_name", "q_design_max"])
    assert len(rows) == 2
    assert rows[0]["raw_payload"]["chemical_name"] == "氯"
    assert rows[0]["raw_payload"]["q_design_max"] == "5"
    assert rows[0]["source_locator"] == "第 2 行"


def test_rows_from_sheet_raises_on_missing_required_column():
    raw = [["品种名称"], ["氯"]]
    mapping = {"品种名称": "chemical_name"}
    with pytest.raises(AdapterError) as ei:
        rows_from_sheet(raw, mapping, required=["chemical_name", "q_design_max"])
    assert "q_design_max" in str(ei.value)


def test_rows_from_sheet_raises_on_unmapped_required_field():
    """映射表里没覆盖的必填字段也要报错——否则每行都会缺字段。"""
    raw = [["品名", "数量"], ["氯", "5"]]
    mapping = {"品名": "chemical_name"}  # 缺 q_design_max 的源列
    with pytest.raises(AdapterError):
        rows_from_sheet(raw, mapping, required=["chemical_name", "q_design_max"])


def test_rows_from_sheet_skips_blank_rows():
    raw = [["品名"], ["氯"], [""], ["  "], ["氨"]]
    rows = rows_from_sheet(raw, {"品名": "chemical_name"}, required=["chemical_name"])
    assert len(rows) == 2


def test_rows_from_sheet_empty_input():
    assert rows_from_sheet([], {"a": "b"}, required=[]) == []
