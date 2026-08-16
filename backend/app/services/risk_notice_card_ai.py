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


async def review_signs(
    db: AsyncSession,
    user_id: str,
    enterprise_name: str,
    object_name: str,
    category: str | None,
    location: str | None,
    events: list[dict],
    current_signs: list[dict],
    catalog: list[dict],
) -> dict:
    """AI 审查安全标志：返回 {remove, add, reasons} 差异建议。"""
    ai_config = await _get_ai_config(user_id, db)
    events_text = "\n".join(
        f"- 事故类型：{e.get('accident_type', '') or ''}；触发条件：{e.get('trigger_conditions', '') or ''}；"
        f"可能后果：{e.get('consequences', '') or ''}"
        for e in events
    )
    current_text = "、".join(f"{s.get('name', '')}({s.get('svg_name', '')})" for s in current_signs) or "（无）"
    catalog_text = "；".join(f"{s.get('name', '')}({s.get('svg_name', '')})" for s in catalog)
    prompt = (
        "你是安全生产专家，熟悉 GB 2894-2025《安全色和安全标志》与 GB 6441-1986 事故分类。"
        "请审查以下风险点告知卡的安全标志是否合理，输出严格 JSON："
        '{"remove": ["svg_name 列表（仅限当前标志中不合理的）"], "add": ["svg_name 列表（仅限候选库中应补充的）"], '
        '"reasons": [{"sign_name": "标志中文名", "reason": "具体理由"}]}。'
        f"企业：{enterprise_name}；风险点：{object_name}；类别：{category or '未知'}；位置：{location or '未知'}。\n"
        f"风险事件：\n{events_text or '（无）'}\n"
        f"当前标志：{current_text}\n"
        f"候选标志库（只能从这里选，不得发明）：{catalog_text}\n"
        "要求：remove 必须来自当前标志；add 必须来自候选库且不在当前标志；"
        "每类（警告/禁止/指令/提示）最多 2 个、总数不超过 8；理由结合具体场景；中文输出。"
    )
    messages = [
        {"role": "system", "content": "你是安全生产专家。"},
        {"role": "user", "content": prompt},
    ]
    raw = await llm_text_completion(messages, ai_config, timeout=60)
    try:
        data = _parse_optimized_json(raw)
    except json.JSONDecodeError:
        logger.warning("AI 审查标志 JSON 解析失败: raw=%s", raw[:200])
        raise HTTPException(502, "AI 返回格式异常，无法解析 JSON")
    if not isinstance(data, dict):
        raise HTTPException(502, "AI 返回格式异常，无法解析 JSON")
    remove = data.get("remove", []) if isinstance(data.get("remove"), list) else []
    add = data.get("add", []) if isinstance(data.get("add"), list) else []
    reasons = data.get("reasons", []) if isinstance(data.get("reasons"), list) else []
    return {"remove": remove, "add": add, "reasons": reasons}
