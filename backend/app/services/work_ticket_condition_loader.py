"""措施条件的键工具与运行时加载。

规范化规则（锚定与查找共用同一函数，见规格 §4）：去空白、全角转半角、去尾部标点。
刻意不做模糊匹配与同义词替换——把「改了字的另一条措施」错认成同一条，
正是这套设计要避免的静默错判。
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_TAIL_PUNCT = "。；;.，,、"


def normalize_measure_text(text: str) -> str:
    """规范化措施正文：去空白 + 全角转半角 + 去尾部标点。"""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.rstrip(_TAIL_PUNCT)


def measure_ref(text: str) -> str:
    """措施正文的稳定锚点（规范化后的 sha256 前 32 位）。

    用正文而不是序号：标准修订若插入一条措施，序号整体后移，
    按序号锚定会把「不涉及」判到错误的措施上。
    """
    digest = hashlib.sha256(normalize_measure_text(text).encode("utf-8")).hexdigest()
    return digest[:32]
