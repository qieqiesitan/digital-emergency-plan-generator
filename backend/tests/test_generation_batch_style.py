"""批量生成的请求级风格覆盖：解析契约 + 接线守护（2026-09-18 补）。

背景：移动端批量生成界面原本隐藏了风格选择，因为后端 batch 接口只读预案保存的
`style_preference`——用户选了也会被静默忽略。修复分两处：解析请求体（本文件上半）
与两个 batch 端点把覆盖值传给 `run_batch_generation`（下半的源码守护）。
"""

from pathlib import Path

from app.routers.generation import _parse_batch_request

ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "generation.py"


def test_parse_batch_request_passes_style_overrides():
    keys, style, advanced = _parse_batch_request(
        {
            "section_keys": ["a", "b"],
            "style_preference": {"detail_level": "concise"},
            "advanced_prompt_overrides": {"system_prompt_override": "x"},
        }
    )
    assert keys == ["a", "b"]
    assert style == {"detail_level": "concise"}
    assert advanced == {"system_prompt_override": "x"}


def test_parse_batch_request_ignores_non_dict_payload():
    assert _parse_batch_request(["not", "a", "dict"]) == (None, None, None)
    assert _parse_batch_request(None) == (None, None, None)
    assert _parse_batch_request("") == (None, None, None)


def test_parse_batch_request_ignores_dirty_style_values():
    keys, style, advanced = _parse_batch_request(
        {"section_keys": None, "style_preference": "concise", "advanced_prompt_overrides": 3}
    )
    assert keys is None
    assert style is None and advanced is None


def test_both_batch_endpoints_wire_style_override():
    """守护：两个 batch 端点都必须把请求级覆盖传给后台生成（否则前端选择再次被吞）。"""
    source = ROUTER.read_text(encoding="utf-8")
    assert source.count("style_preference=style_override or p.style_preference") == 2
    assert source.count("advanced_overrides=advanced_override or p.advanced_prompt_overrides") == 2
    assert source.count("_parse_batch_request(body)") == 2
