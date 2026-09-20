"""措施"是否涉及"建议引擎（确定性、纯函数）。

设计要点：
- 只对**已建立条件映射**的措施给建议（首批为动火票 16 条，依据 GB 30871-2022
  附录A 表A.1 第 1~16 条），其余一律 unknown —— 宁可少建议，也不猜。
- 条件值三态：True / False / None。只要有任一条件为 None，就不得给出
  not_applicable，否则就是把"不知道"当成"不涉及"（安全底线）。
- 建议只影响排序与分组，**绝不自动写入 measures_meta**；落地必须人工点击。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

UNKNOWN = "unknown"
APPLICABLE = "applicable"
NOT_APPLICABLE = "not_applicable"

# 条件键 → 中文说明（用于向用户解释判定依据）
CONDITION_LABELS: dict[str, str] = {
    "internal_work": "本次动火在设备内部",
    "connected_pipeline": "动火设备连接有管线",
    "surroundings_ignition": "动火点周围有孔洞/窨井/地沟/污水井",
    "in_tank_area": "作业点在油气罐区防火堤内",
    "height_work": "本次作业涉及高处作业",
    "has_flammable_lining": "设备内有可燃物构件或防腐内衬",
    "gas_welding": "本次动火使用气焊/气割",
    "electric_welding": "本次动火使用电焊",
    "surrounding_hazardous_ops": "动火点周围有装卸/排放/喷漆等危险作业",
    "has_other_tickets": "本次作业还办理了其他特殊作业票",
}

# (票种, 措施序号) → 该措施成立所依赖的条件键。
# 语义：**任一条件为真 → 涉及**；全部为假 → 不涉及；任一为 None → 无法判定。
# 依据：GB 30871-2022 附录A 表A.1（动火安全作业票）第 1~16 条。
MEASURE_CONDITIONS: dict[tuple[str, int], tuple[str, ...]] = {
    ("DHZY", 1): ("internal_work",),
    ("DHZY", 2): ("connected_pipeline",),
    ("DHZY", 3): ("surroundings_ignition",),
    ("DHZY", 4): ("in_tank_area",),
    ("DHZY", 5): ("height_work",),
    ("DHZY", 6): ("has_flammable_lining",),
    ("DHZY", 7): ("gas_welding",),
    ("DHZY", 9): ("electric_welding",),
    ("DHZY", 10): ("surrounding_hazardous_ops",),
    ("DHZY", 11): ("surrounding_hazardous_ops",),
    ("DHZY", 12): ("has_other_tickets",),
    # 连续检测仪：电焊或气焊任一方式都要求配备
    ("DHZY", 13): ("gas_welding", "electric_welding"),
    ("DHZY", 15): ("has_other_tickets",),
}


@dataclass(frozen=True)
class MeasureContext:
    """判定上下文。conditions 里缺键等价于 None（未确定）。"""

    ticket_type: str
    conditions: Mapping[str, bool | None]


def _order_of(measure: Any) -> int:
    if isinstance(measure, Mapping):
        return int(measure["sort_order"])
    return int(measure.sort_order)


def suggest_measures(
    measures: Sequence[Any], context: MeasureContext
) -> list[dict[str, Any]]:
    """返回每条措施的建议：{sort_order, suggest, reason}。"""
    out: list[dict[str, Any]] = []
    for measure in measures:
        order = _order_of(measure)
        keys = MEASURE_CONDITIONS.get((context.ticket_type, order), ())
        if not keys:
            out.append({"sort_order": order, "suggest": UNKNOWN, "reason": None})
            continue
        values = [context.conditions.get(key) for key in keys]
        if any(value is True for value in values):
            hit = [
                CONDITION_LABELS[key]
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
                    "reason": "本票不涉及：" + "；".join(CONDITION_LABELS[k] for k in keys),
                }
            )
    return out


def conditions_from_scenario(
    *,
    ticket_type: str,
    fire_method: str | None = None,
    zone_name: str | None = None,
    other_ticket_types: Sequence[str] = (),
    scenario: Mapping[str, bool | None] | None = None,
) -> dict[str, bool | None]:
    """把"自动可推断的条件"与"用户勾选的作业情景"合并成条件表。

    自动部分（无法推断时保持 None，绝不猜）：
      - gas_welding / electric_welding：由动火方式文本推断
      - in_tank_area：由作业区域名称推断
      - has_other_tickets / height_work：由作业包内其他票种推断
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
    if ticket_type == "DHZY":
        conditions["has_other_tickets"] = len(other_ticket_types) > 0
        conditions["height_work"] = "GCZY" in other_ticket_types
    return conditions
