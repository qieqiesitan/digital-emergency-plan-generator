"""接入对账（纯函数，无 IO）。"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable


def compare(
    *,
    expected: int,
    actual: int,
    failed: int = 0,
    skipped: int = 0,
) -> dict:
    """比对期望条数与实际入队条数，并把差额归因。

    差额 = 实际 - 期望（负数表示少了）。
    能被 failed / skipped 解释的差额照实说明；解释不了的必须写明"原因不明"——
    含糊过去会让数据缺口永远查不出来。
    """
    diff = actual - expected
    if diff == 0:
        return {"ok": True, "diff": 0, "diff_note": None}

    explained = -(failed + skipped)
    parts: list[str] = []
    if failed:
        parts.append(f"失败 {failed} 条")
    if skipped:
        parts.append(f"跳过 {skipped} 条")

    if diff == explained and parts:
        note = "差额可由" + "、".join(parts) + "完整解释"
    else:
        note = (
            f"实际比期望{'少' if diff < 0 else '多'} {abs(diff)} 条；"
            + ("已知" + "、".join(parts) + "；" if parts else "")
            + "其余差额**原因不明**，需人工核查"
        )
    return {"ok": False, "diff": diff, "diff_note": note}


def payload_checksum(payloads: Iterable[dict]) -> str:
    """对一批载荷算稳定校验和（排序后 hash），用于跨次导入的内容一致性核对。"""
    normalized = json.dumps(
        sorted((json.dumps(p, ensure_ascii=False, sort_keys=True, default=str) for p in payloads)),
        ensure_ascii=False,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
