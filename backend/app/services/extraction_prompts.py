"""抽取提示词模板与输出结构校验。

设计原则：**抽字段，不抽标准值**。临界量 Q 与校正系数 beta 是 GB 18218 的法定查表值，
必须由系统按名称/类别查表得出，不能让模型"读"出来——那等于把查表权威交给模型。
"""

from __future__ import annotations

from typing import Any


class ExtractionSchemaError(ValueError):
    """模型输出不满足目标实体结构要求。"""


ENTITY_SCHEMAS: dict[str, dict] = {
    "major_hazard_unit": {
        "title": "重大危险源单元",
        "fields": {
            "name": {"type": "str", "required": True, "desc": "单元名称，如「罐区A」「锅炉房」"},
            "unit_type": {
                "type": "enum",
                "values": ["production", "storage"],
                "required": True,
                "desc": "生产单元填 production，储存单元（储罐区/仓库）填 storage",
            },
            "boundary_desc": {"type": "str", "required": False, "desc": "边界描述，如「以罐区防火堤为界」"},
            "address": {"type": "str", "required": False, "desc": "所在位置"},
        },
    },
    "major_hazard_unit_chemical": {
        "title": "单元内危险化学品存量",
        "fields": {
            "unit_name": {"type": "str", "required": False, "desc": "归属单元名称，用于人工确认时对应"},
            "chemical_name": {"type": "str", "required": True, "desc": "危险化学品名称"},
            "q_design_max": {
                "type": "float",
                "required": True,
                "desc": "设计最大量，单位吨。注意：是设计最大量（按设备设计容积/额定充装量），"
                "不是日常储存量。原文给容积时按密度换算并在 review_note 说明。",
            },
            "physical_state": {"type": "str", "required": False, "desc": "物理状态"},
        },
    },
}


def build_messages(*, target_entity: str, text: str, source_hint: str) -> list[dict]:
    """构造抽取用对话消息。"""
    schema = ENTITY_SCHEMAS.get(target_entity)
    if schema is None:
        raise ExtractionSchemaError(f"未知目标实体：{target_entity}")

    field_lines = []
    for name, spec in schema["fields"].items():
        req = "必填" if spec.get("required") else "可选"
        extra = ""
        if spec.get("type") == "enum":
            extra = f"，取值只能是 {spec['values']}"
        field_lines.append(f"- {name}（{req}{extra}）：{spec['desc']}")

    system = (
        "你是危险化学品安全技术资料的结构化抽取助手。"
        "你的任务是把给定的资料原文抽取成结构化数据，**不得虚构原文没有的信息**。"
        "只输出 JSON 数组，不要输出解释、Markdown 代码围栏或任何其他文字。"
    )
    user = "\n".join(
        [
            f"资料文件名：{source_hint}",
            f"需要抽取的实体：{schema['title']}（{target_entity}）",
            "",
            "字段要求：",
            *field_lines,
            "",
            "输出格式：JSON 数组，每个元素包含：",
            '- "payload"：上述字段组成的对象',
            f'- "source_locator"：该条信息在资料中的位置，格式为「{source_hint} 段N」或「{source_hint} PN」',
            '- "confidence"：high / medium / low',
            '- "review_note"：低置信度时说明原因，可选',
            "",
            "置信度判定：",
            "- high：原文明确写出数值与单位，且必需字段齐全",
            "- medium：数值由其他信息换算得出（如由容积×密度推算），或部分字段缺失",
            "- low：原文描述模糊、单位缺失、无法确定归属",
            "",
            "资料原文：",
            text,
        ]
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _to_float(value: Any, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        try:
            return float(cleaned)
        except ValueError as exc:
            raise ExtractionSchemaError(f"字段 {field} 无法转为数值：{value!r}") from exc
    raise ExtractionSchemaError(f"字段 {field} 类型不支持：{type(value).__name__}")


def validate_payload(target_entity: str, row: dict) -> dict:
    """校验并规范化一条抽取结果。不合格直接抛错，不做"尽力而为"的修补。"""
    schema = ENTITY_SCHEMAS.get(target_entity)
    if schema is None:
        raise ExtractionSchemaError(f"未知目标实体：{target_entity}")
    if not isinstance(row, dict):
        raise ExtractionSchemaError("抽取结果必须是对象")

    payload = row.get("payload") if isinstance(row.get("payload"), dict) else row

    if not row.get("source_locator"):
        raise ExtractionSchemaError("缺少 source_locator：抽取结果必须可追溯到原文位置")
    confidence = row.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        raise ExtractionSchemaError(f"confidence 取值非法：{confidence}")

    out: dict = {}
    for name, spec in schema["fields"].items():
        value = payload.get(name)
        if value in ("", "null"):
            value = None
        if value is None:
            if spec.get("required"):
                raise ExtractionSchemaError(f"缺少必填字段 {name}")
            out[name] = None
            continue
        if spec["type"] == "float":
            out[name] = _to_float(value, name)
        elif spec["type"] == "enum":
            if value not in spec["values"]:
                raise ExtractionSchemaError(
                    f"字段 {name} 取值 {value!r} 不在允许范围 {spec['values']}"
                )
            out[name] = value
        else:
            out[name] = str(value).strip()

    out["source_locator"] = str(row["source_locator"])
    out["confidence"] = confidence
    out["review_note"] = row.get("review_note")
    return out
