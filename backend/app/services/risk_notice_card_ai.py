"""风险告知卡 AI 优化（可选路径，规则生成失败不影响）。"""
import json
import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.risk_ai_service import _get_ai_config
from app.services.llm_client import llm_text_completion
from app.schemas.risk_notice_card import RightColumn

logger = logging.getLogger(__name__)


def _parse_optimized_json(raw: str) -> dict:
    """剥离 markdown 代码块后解析 AI 返回的 JSON（等价于 risk_ai_service._parse_ai_json）。"""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:]) if lines[0].startswith("```") else raw
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    return json.loads(raw)


async def optimize_right_column(
    db: AsyncSession,
    user_id: str,
    enterprise_name: str,
    object_name: str,
    original: RightColumn,
) -> RightColumn:
    ai_config = await _get_ai_config(user_id, db)
    prompt = (
        "请优化风险告知卡右栏文案，输出严格 JSON："
        '{"hazard_description": "主要危险因素描述", "control_measures": ["① ...", "② ..."], "emergency_measures": ["① ...", "② ..."]}。'
        f"企业：{enterprise_name}；风险点：{object_name}；原版：{original.model_dump_json()}。"
        "要求：措施用①②③编号开头；事故类型不得改动；中文输出。"
    )
    messages = [
        {"role": "system", "content": "你是安全生产专家。"},
        {"role": "user", "content": prompt},
    ]
    raw = await llm_text_completion(messages, ai_config, timeout=60)
    try:
        data = _parse_optimized_json(raw)
    except json.JSONDecodeError:
        logger.warning("风险告知卡 AI JSON 解析失败: raw=%s", raw[:200])
        raise HTTPException(502, "AI 返回格式异常，无法解析 JSON")
    control_measures = data.get("control_measures", original.control_measures)
    if not isinstance(control_measures, list):
        control_measures = original.control_measures
    emergency_measures = data.get("emergency_measures", original.emergency_measures)
    if not isinstance(emergency_measures, list):
        emergency_measures = original.emergency_measures
    hazard_description = data.get("hazard_description", original.hazard_description)
    if not isinstance(hazard_description, str):
        hazard_description = original.hazard_description
    return RightColumn(
        hazard_description=hazard_description,
        accident_types=original.accident_types,
        control_measures=control_measures,
        emergency_measures=emergency_measures,
    )
