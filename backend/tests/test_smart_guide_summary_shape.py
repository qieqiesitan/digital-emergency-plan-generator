"""smart-guide 的 summary 归一：模型返回非 dict 时不得变成裸 500。

来源：2026-09-19 mock 供应商实测——summary 返回字符串 "" 时，
SmartGuideResponse 抛 Pydantic 校验错，接口返回没有任何提示的 500。
"""
import pytest

from app.services.risk_ai_service import normalize_smart_guide_summary


@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"zones": 3}, {"zones": 3}),          # 正常 dict 原样透传
        ("已生成 3 个分区", {"text": "已生成 3 个分区"}),  # 自然语言包成 text
        ("   ", {}),                            # 空白串退化为空
        ("", {}),
        (None, {}),
        (123, {}),                              # 数字无法展示
        (["a"], {}),                            # 列表不是 dict
    ],
)
def test_normalize_smart_guide_summary(raw, expected):
    assert normalize_smart_guide_summary(raw) == expected


def test_router_uses_normalizer_and_guards_shape():
    """源码守护：不得再出现 `summary=result.get("summary",{})` 这种直接透传。"""
    import pathlib
    import re

    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "risk_management.py").read_text(
        encoding="utf-8"
    )
    assert "normalize_smart_guide_summary(result.get" in src
    assert not re.search(r'SmartGuideResponse\(hierarchy=result\.get\("zones"', src)
