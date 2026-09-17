"""危化品存量文本解析：把"最大储存量 12.5吨"这类自然语言转成数值+单位。

只做能确定的解析：识别不出来一律返回 (None, None)，由人工确认——
存量数值会直接进入 R 值法计算，猜错比留空危险得多。
"""

from __future__ import annotations

import re

_UNIT_ALIASES = {
    "t": "t",
    "吨": "t",
    "kg": "t",  # 千克统一折算成吨
    "千克": "t",
    "公斤": "t",
    "m3": "m³",
    "m³": "m³",
    "立方米": "m³",
    "l": "L",
    "升": "L",
}

_PATTERN = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>m³|m3|立方米|t|吨|kg|千克|公斤|L|升)",
    re.IGNORECASE,
)


def parse_storage_text(text: str | None) -> tuple[float | None, str | None]:
    """返回 (数值, 归一化单位)；无法解析时返回 (None, None)。千克会折算成吨。"""
    if not text:
        return None, None
    match = _PATTERN.search(str(text))
    if not match:
        return None, None
    raw_unit = match.group("unit").lower()
    value = float(match.group("num"))
    unit = _UNIT_ALIASES.get(raw_unit)
    if unit is None:
        return None, None
    if unit == "t" and raw_unit in ("kg", "千克", "公斤"):
        value = value / 1000.0
    return value, unit
