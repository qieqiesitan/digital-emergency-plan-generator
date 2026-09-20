"""作业包：共享槽位映射、票号回填、状态机。

槽位（slot）是"语义字段"，落到各票种的实际 field_key 由 SLOT_TARGETS 决定：
不同票种的地点字段名不同（fire_location / space_location / dig_location /
road_position / pipe_position），而高处（GCZY）、吊装（QZDZ）、临时用电（LSYD）
根本没有地点字段——**刻意不为它们新增票面字段**（GB 30871 附录A 票面样式不可自加行），
那些票种的地点信息由作业包作为上下文注入作业内容。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

BATCH_SOURCE = "batch"

# "*" 表示 8 类票通用；其余按票种 code 精确匹配；未命中即跳过该槽位
SLOT_TARGETS: dict[str, dict[str, str]] = {
    "applicant_unit": {"*": "applicant_unit"},
    "work_unit": {"*": "work_unit"},
    "work_leader": {"*": "work_leader"},
    "period": {"*": "work_period"},
    "content": {"*": "work_content"},
    "risk_basis": {"*": "risk_identification"},
    "related": {"*": "related_tickets"},
    "location": {
        "DHZY": "fire_location",
        "YXKJ": "space_location",
        "MBCD": "pipe_position",
        "PTZY": "dig_location",
        "DLZY": "road_position",
    },
}

BATCH_STATUSES = ("draft", "active", "closed", "cancelled")

_EMPTY = (None, "", [], {})


def _target_key(slot: str, ticket_type: str) -> str | None:
    targets = SLOT_TARGETS.get(slot)
    if not targets:
        return None
    return targets.get(ticket_type) or targets.get("*")


def apply_slots(
    ticket_type: str, shared: Mapping[str, Any], field_keys: Iterable[str]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """把作业包的共享槽位落到该票种的字段上。

    只为"模板里真实存在"的 field_key 产出值；空槽位不产出。
    """
    keys = set(field_keys)
    values: dict[str, Any] = {}
    meta: dict[str, dict[str, Any]] = {}
    for slot, raw in shared.items():
        if raw in _EMPTY:
            continue
        target = _target_key(slot, ticket_type)
        if not target or target not in keys:
            continue
        values[target] = raw
        meta[target] = {
            "source": BATCH_SOURCE,
            "source_ref": {"slot": slot},
            "edited": False,
        }
    return values, meta


def build_related_map(items: Sequence[tuple[str, str]]) -> dict[str, str]:
    """(ticket_id, code) 列表 → {ticket_id: "包内其他票号（按票号排序，逗号分隔）"}。"""
    ordered = sorted(items, key=lambda pair: pair[1])
    out: dict[str, str] = {}
    for ticket_id, code in ordered:
        others = [c for _, c in ordered if c != code]
        out[ticket_id] = ",".join(others)
    return out


def next_batch_status(
    current: str, *, submitted: int, total: int, action: str = "refresh"
) -> str:
    """包状态推进：draft → active（首张票提交）；全部终态 → closed。

    作废（cancel）在包内已有提交票时被拒绝——已进入审批的票不能失去上下文。
    """
    if action == "cancel":
        if submitted > 0:
            raise ValueError("包内存在已提交的作业票，不能作废作业包")
        return "cancelled"
    if action == "close":
        return "closed"
    if current in ("closed", "cancelled"):
        return current
    if total and submitted >= total:
        return "closed"
    if submitted > 0:
        return "active"
    return "draft"
