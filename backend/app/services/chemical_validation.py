"""危化品数据质量校验。

CAS 校验位算法移植自 scripts/extract_gb18218_tables.py（已在 82 条真实标准数据上
验证通过），此处作为应用层服务供 DataHub 导入校验复用——不是重新实现。
"""

from __future__ import annotations

import re

_CAS_PATTERN = re.compile(r"\b(\d{2,7})-(\d{2})-(\d)\b")
_CAS_BARE = re.compile(r"^\d{5,10}$")


def is_valid_cas_format(cas: str) -> bool:
    """形如 2~7 位-2 位-1 位；也接受无连字符的纯数字串。"""
    if not cas:
        return False
    text = cas.strip()
    if _CAS_PATTERN.fullmatch(text):
        return True
    return bool(_CAS_BARE.fullmatch(text))


def cas_checksum_ok(cas: str) -> bool:
    """CAS 校验位验证：末位 = 前面各位从右向左依次×1,2,3… 之和 mod 10。

    注意：本函数只回答"校验位对不对"，不回答"格式像不像 CAS"——格式判断
    由 `is_valid_cas_format` 负责。所以这里对分隔符宽容（去掉所有非数字）。
    """
    if not cas:
        return False
    digits = re.sub(r"\D", "", cas)
    if len(digits) < 5:
        return False
    # 纯字母串去掉非数字后可能缩成短数字，视为不合法
    if not cas.strip().replace("-", "").replace(" ", "").isdigit():
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    return total % 10 == check


def find_cas_in_text(text: str) -> list[dict]:
    """从自由文本里挑出形似 CAS 的串并附校验结果（去重，保持出现顺序）。"""
    if not text:
        return []
    seen: set[str] = set()
    out: list[dict] = []
    for m in _CAS_PATTERN.finditer(text):
        cas = m.group(0)
        if cas in seen:
            continue
        seen.add(cas)
        out.append({"cas": cas, "ok": cas_checksum_ok(cas)})
    return out
