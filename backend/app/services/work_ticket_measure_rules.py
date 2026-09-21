"""措施"是否涉及"建议引擎（确定性、纯函数）。

设计要点：
- 映射不写在本模块里：由 `work_ticket_condition_loader` 从
  `work_ticket_measure_conditions` 表加载后注入（表由 YAML + 生成器产出，见规格）。
  本模块只保留判定逻辑——纯函数、可单测。
- **锚定键是措施正文**（`measure_ref(measure_text)`），不是序号：标准修订插入条文时不会错判。
- 条件值三态：True / False / None。任一条件未确定时不得给出 not_applicable，
  否则就是把"不知道"当成"不涉及"（安全底线）。
- 建议只影响排序与分组，**绝不自动写入 measures_meta**；落地必须人工点击。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.services.work_ticket_condition_loader import measure_ref

UNKNOWN = "unknown"
APPLICABLE = "applicable"
NOT_APPLICABLE = "not_applicable"

# 判定语义：**任一条件为真 → 涉及**；全部为假 → 不涉及；任一为 None → 无法判定。
ConditionsMap = Mapping[tuple[str, str], Sequence[str]]
ConditionLabels = Mapping[str, str]


@dataclass(frozen=True)
class MeasureContext:
    """判定上下文。conditions 里缺键等价于 None（未确定）。"""

    ticket_type: str
    conditions: Mapping[str, bool | None]


def _order_of(measure: Any) -> int:
    if isinstance(measure, Mapping):
        return int(measure["sort_order"])
    return int(measure.sort_order)


def _text_of(measure: Any) -> str:
    if isinstance(measure, Mapping):
        return str(measure.get("measure_text") or "")
    return str(getattr(measure, "measure_text", "") or "")


def _keys_for(
    measure: Any, context: MeasureContext, conditions_map: ConditionsMap | None
) -> tuple[str, ...]:
    """按措施正文锚点查该票种的条件键；无映射（含未传表）时返回空 → 落 unknown。"""
    if not conditions_map:
        return ()
    return tuple(conditions_map.get((context.ticket_type, measure_ref(_text_of(measure))), ()))


def suggest_measures(
    measures: Sequence[Any],
    context: MeasureContext,
    *,
    conditions_map: ConditionsMap | None = None,
    labels: ConditionLabels | None = None,
) -> list[dict[str, Any]]:
    """返回每条措施的建议：{sort_order, suggest, reason}。

    `conditions_map` 缺省（或为空）时，所有措施落 `unknown`——这是安全默认：
    宁可让人逐条确认，也不在缺少映射时给出"不涉及"。
    """
    label_of = dict(labels or {})
    out: list[dict[str, Any]] = []
    for measure in measures:
        order = _order_of(measure)
        keys = _keys_for(measure, context, conditions_map)
        if not keys:
            out.append({"sort_order": order, "suggest": UNKNOWN, "reason": None})
            continue
        values = [context.conditions.get(key) for key in keys]
        if any(value is True for value in values):
            hit = [
                label_of.get(key, key)
                for key, value in zip(keys, values, strict=True)
                if value is True
            ]
            out.append(
                {
                    "sort_order": order,
                    "suggest": APPLICABLE,
                    "reason": "本票涉及：" + "；".join(hit),
                }
            )
        elif any(value is None for value in values):
            out.append(
                {"sort_order": order, "suggest": UNKNOWN, "reason": "现场条件未确定"}
            )
        else:
            out.append(
                {
                    "sort_order": order,
                    "suggest": NOT_APPLICABLE,
                    "reason": "本票不涉及：" + "；".join(label_of.get(k, k) for k in keys),
                }
            )
    return out


def conditions_from_scenario(
    *,
    ticket_type: str,
    fire_method: str | None = None,
    zone_name: str | None = None,
    work_period: Sequence[str] | None = None,
    field_values: Mapping[str, Any] | None = None,
    level: str | None = None,
    other_ticket_types: Sequence[str] = (),
    scenario: Mapping[str, bool | None] | None = None,
) -> dict[str, bool | None]:
    """把"自动可推断的条件"与"用户勾选的作业情景"合并成条件表。

    自动部分（无法推断时保持 None，绝不猜）：
      - gas_welding / electric_welding：由动火方式文本推断
      - in_tank_area：由作业区域名称推断
      - has_other_tickets / height_work：由作业包内其他票种推断
      - night_work：由作业时段推断（任一端落在 20:00~06:00）
      - above_30m：由 `work_height` 字段推断
      - deep_excavation：由 `dig_depth` 字段推断
      - level_1_or_2：由吊装级别推断
    其余现场条件（是否进入设备内部、是否连接管线、周围有无窨井等）
    只能由用户在第 0 步的"作业情景"里勾选，勾了才有 True/False，否则为 None。
    """
    conditions: dict[str, bool | None] = dict(scenario or {})
    method = fire_method or ""
    if method:
        conditions["gas_welding"] = any(k in method for k in ("气焊", "气割", "乙炔"))
        conditions["electric_welding"] = any(k in method for k in ("电焊", "电弧"))
    if zone_name:
        conditions["in_tank_area"] = any(k in zone_name for k in ("罐区", "储罐", "油罐"))
    if work_period:
        night = _period_hits_night(work_period)
        if night is not None:
            conditions["night_work"] = night
    values = dict(field_values or {})
    height = _as_float(values.get("work_height"))
    if height is not None:
        conditions["above_30m"] = height >= 30
    depth = _as_float(values.get("dig_depth"))
    if depth is not None:
        conditions["deep_excavation"] = depth > 1.2
    if ticket_type == "QZDZ" and level:
        conditions["level_1_or_2"] = level in ("一级", "二级")
    # 「是否还办了其他特殊作业票」对所有票种都成立（8 张票里 7 张有这条措施）
    conditions["has_other_tickets"] = len(other_ticket_types) > 0
    if ticket_type == "DHZY":
        conditions["height_work"] = "GCZY" in other_ticket_types
    return conditions


def _as_float(value: Any) -> float | None:
    """把字段值转成数字；空值/非数字返回 None（宁可不判定，也不猜）。"""
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _period_hits_night(period: Sequence[str]) -> bool | None:
    """作业时段是否涉及夜间（20:00~06:00）；时段不可解析时返回 None。"""
    from datetime import datetime

    if not period or len(period) != 2:
        return None
    for endpoint in period:
        try:
            hour = datetime.fromisoformat(str(endpoint).replace("Z", "+00:00")).hour
        except (TypeError, ValueError):
            return None
        if hour >= 20 or hour < 6:
            return True
    return False
