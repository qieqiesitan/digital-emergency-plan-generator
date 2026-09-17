"""表格列 → 目标字段的映射建议。

AI 只是"建议"，产出必须经 validate_mapping 过滤后再由人工确认。
AI 不可用时退回精确匹配——映射本来就是人工确认的环节，不值得为它硬失败。
"""

from __future__ import annotations

import json
import logging

from app.services.extraction_prompts import ENTITY_SCHEMAS
from app.services.llm_client import llm_text_completion

logger = logging.getLogger("schema_matching")


def allowed_targets(target_entity: str) -> list[str]:
    schema = ENTITY_SCHEMAS.get(target_entity)
    if schema is None:
        return []
    return list(schema["fields"].keys())


def validate_mapping(target_entity: str, mapping: dict) -> dict:
    """只保留合法目标字段，并去重（同一目标字段只接受第一个源列）。"""
    allowed = set(allowed_targets(target_entity))
    out: dict = {}
    used: set[str] = set()
    for src, target in (mapping or {}).items():
        if target not in allowed or target in used:
            continue
        out[src] = target
        used.add(target)
    return out


def _exact_match(headers: list[str], target_entity: str) -> dict:
    """列名与目标字段同名时直接匹配（英文表头或已规范化的中文表）。"""
    allowed = set(allowed_targets(target_entity))
    return {h: h for h in headers if h in allowed}


async def suggest_mapping(
    *,
    headers: list[str],
    target_entity: str,
    ai_config,
    timeout: int = 60,
) -> dict:
    """返回 {mapping, source}，source ∈ {ai, exact}。"""
    allowed = allowed_targets(target_entity)
    if not allowed:
        return {"mapping": {}, "source": "exact"}

    if ai_config is not None:
        prompt = "\n".join(
            [
                f"目标字段（只能从这里选）：{allowed}",
                f"表格列名：{headers}",
                "",
                "请给出列名到目标字段的映射，只输出 JSON 对象，键为列名、值为目标字段；",
                "无法对应的列不要出现在结果里。不要输出任何其他文字。",
            ]
        )
        try:
            raw = await llm_text_completion(
                [
                    {"role": "system", "content": "你是数据表结构对齐助手，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                ai_config,
                timeout=timeout,
            )
            text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            proposed = json.loads(text)
            if isinstance(proposed, dict):
                mapping = validate_mapping(target_entity, proposed)
                if mapping:
                    return {"mapping": mapping, "source": "ai"}
        except Exception:
            logger.warning("AI 列映射建议失败，退回精确匹配", exc_info=True)

    return {"mapping": _exact_match(headers, target_entity), "source": "exact"}
