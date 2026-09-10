"""报告章节尾部 JSON 摘要提取——必须支持嵌套大括号。

根因：原实现用「{ 到末尾且不含嵌套 }」的正则，无法跨嵌套层，ch5/ch6
要求的 top_risks 数组、risk_level_distribution 对象等摘要永远解析失败，
导致资源调查/预案拿不到风险评估结论。
"""

import json

from app.services.report_summary_utils import extract_trailing_json


def test_plain_nested_json_object():
    text = '正文内容\n\n{"a": 1, "b": {"c": [1, 2]}}'
    assert extract_trailing_json(text) == {"a": 1, "b": {"c": [1, 2]}}


def test_top_risks_array_json():
    payload = {
        "risk_source_count": 34,
        "top_risks": [
            {
                "name": "燃气灶台",
                "category": "火灾",
                "risk_level": "较大",
                "location": "厨房",
            }
        ],
        "risk_level_distribution": {"重大": 0, "较大": 1, "一般": 8, "低": 25},
    }
    text = "结论正文。\n\n" + json.dumps(payload, ensure_ascii=False)
    assert extract_trailing_json(text) == payload


def test_trailing_whitespace_after_json():
    text = '前言\n\n{"key": "value", "nested": {"x": 1}}\n\n'
    assert extract_trailing_json(text) == {"key": "value", "nested": {"x": 1}}


def test_no_trailing_json_returns_none():
    assert extract_trailing_json("没有 JSON 的正文内容") is None
    assert extract_trailing_json("") is None


def test_json_without_dict_type_returns_none():
    assert extract_trailing_json('正文 [1, 2, 3]') is None


def test_malformed_json_returns_none():
    assert extract_trailing_json('正文 {"a": 1, "b": }') is None
