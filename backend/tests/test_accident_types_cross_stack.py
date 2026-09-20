"""D-6：事故类型清单在后端（Python）与前端（TS）各有一份常量，用测试锁住一致性。

两份常量无法避免（跨栈），但可以保证**不会悄悄漂移**：任何一侧改了清单/映射而
另一侧没跟上，本文件立刻失败。这是 D-6「跨端重复常量」的可验证收口方式。
"""

import re
from pathlib import Path

from app.services.accident_types import ACCIDENT_TYPES_2025, LEGACY_TO_NEW_MAP

TS_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "accidentTypes.ts"


def _ts_source() -> str:
    return TS_FILE.read_text(encoding="utf-8")


def _parse_ts_string_array(src: str, const_name: str) -> list[str]:
    m = re.search(rf"export const {const_name}\s*=\s*\[(.*?)\]\s*as const", src, re.S)
    assert m, f"未找到 {const_name} 数组"
    return re.findall(r'"([^"]+)"', m.group(1))


def _parse_ts_string_map(src: str, const_name: str) -> dict[str, str]:
    m = re.search(rf"export const {const_name}[^=]*=\s*\{{(.*?)\n\}}", src, re.S)
    assert m, f"未找到 {const_name} 映射"
    pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', m.group(1))
    return {k: v for k, v in pairs}


def test_accident_type_list_matches_frontend():
    ts_list = _parse_ts_string_array(_ts_source(), "ACCIDENT_TYPES_2025")
    assert ts_list == ACCIDENT_TYPES_2025, (
        "事故类型清单前后端不一致："
        f"仅后端有 {set(ACCIDENT_TYPES_2025) - set(ts_list)}，仅前端有 {set(ts_list) - set(ACCIDENT_TYPES_2025)}"
    )


def test_legacy_map_matches_frontend():
    ts_map = _parse_ts_string_map(_ts_source(), "LEGACY_TO_NEW_ACCIDENT_TYPE_MAP")
    assert ts_map == LEGACY_TO_NEW_MAP, (
        "旧→新事故类型映射前后端不一致："
        f"仅后端有 {set(LEGACY_TO_NEW_MAP) - set(ts_map)}，仅前端有 {set(ts_map) - set(LEGACY_TO_NEW_MAP)}"
    )
