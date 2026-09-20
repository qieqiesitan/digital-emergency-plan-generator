"""N-39：报告导出的 chapters 形状归一（形状漂移不再裸 500）。

来源：2026-09-20 定向回归——把 summary.chapters 写成 dict 时，导出走
`for ch in chapters: ch.get(...)` → `'str' object has no attribute 'get'` → 500。
"""
from app.services.report_docx import coerce_report_chapters


def test_list_of_dicts_kept():
    raw = [{"title": "一、总则", "content": "<p>x</p>"}, {"title": "二、风险", "content": "<p>y</p>"}]
    assert coerce_report_chapters(raw) == raw


def test_dict_shape_yields_empty_and_falls_back():
    """历史/异常形状（dict）不再让导出崩，交给调用方回落正文切章。"""
    assert coerce_report_chapters({"ch1": {"title": "x"}}) == []


def test_mixed_items_drop_non_dict():
    raw = [{"title": "ok"}, "oops", None, 42, {"title": "ok2"}]
    assert coerce_report_chapters(raw) == [{"title": "ok"}, {"title": "ok2"}]


def test_non_list_inputs():
    assert coerce_report_chapters(None) == []
    assert coerce_report_chapters("just a string") == []


def test_exports_use_coercion():
    """源码守护：两个报告导出都必须先归一，并在为空时给可读错误。"""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
    for name in ("risk_assessment.py", "resource_investigation.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert "coerce_report_chapters(" in src, f"{name} 未做 chapters 归一"
        assert "报告内容为空或格式异常，无法导出" in src, f"{name} 缺少可读错误"
