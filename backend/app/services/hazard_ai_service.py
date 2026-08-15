"""隐患 AI 辅助服务：检查表模板 AI 生成。

参考 `risk_dual_ai_service.py` / `risk_ai_service.py` 既有惯例：
`llm_text_completion(timeout=60)` + `_parse_ai_json`；
未配置/异常/超时一律降级返回 `available: false` + 空 items（§16），
不阻塞前端流程（页面确认后再由 POST /templates 落库）。
"""

from typing import Optional

from app.services.llm_client import llm_text_completion
from app.services.risk_ai_service import _parse_ai_json


def _normalize_items(raw_items) -> list[dict]:
    """归一化 AI 返回的检查项：content 必填非空，expected_note 可空。"""
    items: list[dict] = []
    if not isinstance(raw_items, list):
        return items
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("content") or "").strip()
        if not content:
            continue
        expected_note = raw.get("expected_note")
        expected_note = str(expected_note).strip() if expected_note is not None else ""
        items.append({"content": content, "expected_note": expected_note or None})
    return items


async def generate_checklist_template(
    industry: str,
    risk_points: str,
    ai_config: Optional[object],
) -> dict:
    """AI 生成检查表模板项列表（8-15 项，覆盖 人/机/料/法/环）。

    Args:
        industry: 行业描述（可为空串，与 risk_points 二选一必填）
        risk_points: 风险点/措施文本（可为空串，与 industry 二选一必填）
        ai_config: 系统 AI 配置；None（未配置）时直接降级

    Returns:
        available=True 时含 items（[{content, expected_note}]）与 note；
        未配置/异常/超时 → {"available": False, "items": [], "note": "..."}
    """
    if ai_config is None:
        return _fallback()
    prompt = (
        "你是持证的安全与隐患排查专家。请根据行业描述与风险点/措施文本，"
        "生成一份隐患排查检查表模板。\n\n"
        f"行业描述：{industry or '（未提供）'}\n"
        f"风险点/措施文本：{risk_points or '（未提供）'}\n\n"
        "要求：\n"
        "1. 输出 8-15 个检查项，覆盖人（人员/行为）、机（设备设施）、"
        "料（物料/危化品）、法（制度/规程）、环（环境）五类要点\n"
        "2. 每项包含 content（检查内容）与 expected_note（检查标准/合格要求），"
        "均为中文，具体可执行\n"
        "3. 结合给定行业与风险点生成，避免空泛重复\n"
        '4. 只输出 JSON：{"items": [{"content": "...", "expected_note": "..."}]}'
    )
    messages = [
        {"role": "system", "content": "你是隐患排查专家，输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm_text_completion(messages, ai_config, timeout=60)
        data = _parse_ai_json(raw)
        items = _normalize_items(data.get("items"))
        if not items:
            raise ValueError("AI 未返回有效检查项")
        return {"available": True, "items": items[:15], "note": ""}
    except Exception:
        return _fallback()


def _fallback() -> dict:
    """AI 降级兜底：available=false + 空 items，不阻塞流程（§16）。"""
    return {"available": False, "items": [], "note": "AI 不可用，请手动编辑检查表模板"}
