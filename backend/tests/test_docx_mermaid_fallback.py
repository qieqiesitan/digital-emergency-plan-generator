"""DOCX 导出：内容里有 Mermaid 但无预渲染缓存时，必须就地渲染（2026-09-18 修）。

生成期会把 AI 产出的 Mermaid 预渲染成 SVG 存进 `PlanSection.mermaid_svgs`；
但用户手工编辑/粘贴的 mermaid 块没有任何缓存，原实现只把它的 hash 记成"已覆盖"，
既不用内联 SVG 也不用代码渲染 → **图被静默丢弃**，导出文档少了流程图。
"""

from app.services.docx_template import missing_mermaid_codes
from app.services.mermaid_renderer import _mermaid_hash
from pathlib import Path


def test_code_without_cache_or_inline_needs_render():
    code = "graph TD; A-->B;"
    assert missing_mermaid_codes([code], {}, set()) == [code]


def test_code_covered_by_cache_is_skipped():
    code = "graph TD; A-->B;"
    assert missing_mermaid_codes([code], {_mermaid_hash(code): "<svg/>"}, set()) == []


def test_code_covered_by_inline_svg_is_skipped():
    code = "graph TD; A-->B;"
    assert missing_mermaid_codes([code], {}, {_mermaid_hash(code)}) == []


def test_duplicate_codes_render_once_and_order_preserved():
    a, b = "graph TD; A-->B;", "graph LR; C-->D;"
    assert missing_mermaid_codes([a, b, a], {}, set()) == [a, b]


def test_no_codes_returns_empty():
    assert missing_mermaid_codes([], {"x": "<svg/>"}, set()) == []


def test_call_site_uses_covered_set_not_seen_set():
    """守护调用点：兜底必须按「真正拿到 SVG」的集合判定。

    踩过的坑：来源1 会把所有 code 的 hash 记进 `rendered_hashes`（只是"见过"），
    若把那个集合传给兜底，`missing_mermaid_codes` 永远返回空 → 手工写的图仍然丢。
    """
    src = (Path(__file__).resolve().parents[1] / "app" / "services" / "docx_template.py").read_text(
        encoding="utf-8"
    )
    assert "missing_mermaid_codes(codes, mermaid_svgs, covered_hashes)" in src
    assert "covered_hashes.add(_h)" in src and "covered_hashes.add(h)" in src
