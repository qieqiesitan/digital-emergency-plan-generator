"""作业票轻量审批引擎。

三次设计决策（见 spec §7.4）：
1. **不引入 BPMN 引擎**——8 类票的流程本质是固定骨架 + 少量条件分支，
   且标准附录B 表B.1 已给定审批人；Flowable/Camunda 是 Java 服务，
   与 Python 栈不匹配且 AI 难介入解释；
2. **条件表达式受限**——只支持字段比较，不引入通用表达式引擎。
   安全是次要的，主要理由是"人一眼能看懂这条分支为什么这么走"；
3. **法定环节不可删**——`is_statutory=True` 的节点拒绝删除，
   与"法定必填项一律阻断"同属一条原则：平台不提供绕过合规的开关。
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence


class FlowError(ValueError):
    """流程配置或流转非法。"""


# 状态机。与 app/services/hazard_state_machine.py 同构，保持项目内一致性。
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submit", "cancel"},
    "submitted": {"start_review", "cancel"},
    "approving": {"approve", "reject", "cancel"},
    "rejected": {"submit", "cancel"},
    "approved": {"start", "cancel", "expire"},
    "working": {"finish"},
    "finished": {"close"},
    "closed": set(),
    "cancelled": set(),
    "expired": set(),  # 已过期只能重新开票，不能恢复
}


def can_transition(status: str, action: str) -> bool:
    return action in TRANSITIONS.get(status, set())


# 生命周期动作 → 目标状态（`approved → working → finished → closed`；cancel 可从多个状态触发）。
# 与 TRANSITIONS 配套：TRANSITIONS 决定「能不能做」，这里决定「做完到哪」。
LIFECYCLE_ACTIONS: dict[str, str] = {
    "start": "working",
    "finish": "finished",
    "close": "closed",
    "cancel": "cancelled",
}

LIFECYCLE_LABELS: dict[str, str] = {
    "start": "开始作业",
    "finish": "完工",
    "close": "归档",
    "cancel": "作废",
}


def lifecycle_target(action: str) -> str:
    """生命周期动作对应的目标状态；未知动作抛 FlowError。"""
    if action not in LIFECYCLE_ACTIONS:
        raise FlowError(f"未知生命周期动作：{action!r}，可选 {sorted(LIFECYCLE_ACTIONS)}")
    return LIFECYCLE_ACTIONS[action]


# --- 条件表达式（受限） ---------------------------------------------------

_EQ = re.compile(r"^(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)\s*==\s*(?P<value>.+)$")
_IN = re.compile(r"^(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+\[(?P<items>[^\]]*)\]$")


def _norm(value: Any) -> str:
    """统一比较口径：布尔转小写字符串，其余去空白转字符串。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def evaluate_condition(expr: Optional[str], ctx: dict) -> bool:
    """求值受限条件表达式。空表达式恒为真；字段缺失返回 False。"""
    if not expr or not expr.strip():
        return True
    text = expr.strip()

    m = _EQ.match(text)
    if m:
        field, expected = m.group("field"), m.group("value").strip()
        if field not in ctx:
            return False
        return _norm(ctx[field]) == _norm(expected)

    m = _IN.match(text)
    if m:
        field = m.group("field")
        if field not in ctx:
            return False
        items = [i.strip() for i in m.group("items").split(",") if i.strip()]
        return _norm(ctx[field]) in {_norm(i) for i in items}

    raise FlowError(
        f"不支持的条件表达式：{expr!r}。只允许 `字段 == 值` 或 `字段 in [值1, 值2]` 两种形式"
    )


def is_node_active(node, ctx: dict) -> bool:
    """该节点在当前作业票数据下是否需要走（条件分支命中与否）。"""
    return evaluate_condition(getattr(node, "condition_expr", None), ctx)


# --- 会签 -----------------------------------------------------------------


def sign_requirement_met(node, *, signed_users: Sequence[str], eligible_users: Sequence[str]) -> bool:
    """判断节点签署是否已完成。

    - `any`：有一人签即可；
    - `all`：所有有资格的人都要签。**没配有资格的人时判定为未完成**——
      否则一个空节点会被当成"已通过"，审批被静默跳过。
    """
    policy = getattr(node, "sign_policy", "any")
    signed = {u for u in signed_users if u}
    if policy == "any":
        return bool(signed)
    if policy == "all":
        eligible = {u for u in eligible_users if u}
        if not eligible:
            return False
        return eligible <= signed
    raise FlowError(f"未知会签策略：{policy!r}，只允许 any / all")


# --- 节点推进 -------------------------------------------------------------


def next_node(nodes: Sequence, *, current_order: int, ctx: dict):
    """返回 current_order 之后第一个「条件命中」的节点；没有则返回 None（流程结束）。"""
    ordered = sorted(nodes, key=lambda n: n.sort_order)
    for node in ordered:
        if node.sort_order <= current_order:
            continue
        if is_node_active(node, ctx):
            return node
    return None


def validate_node_deletion(node) -> None:
    """删除节点前的校验。法定环节一律拒绝。"""
    if getattr(node, "is_statutory", False):
        raise FlowError(
            f"节点「{getattr(node, 'name', '')}」是 GB 30871 附录B 规定的法定审批环节，"
            "不允许删除；如需调整可改绑定的角色或在其前后插入自有节点"
        )
