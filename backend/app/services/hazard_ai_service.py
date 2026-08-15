"""隐患 AI 辅助服务：检查表模板 AI 生成 + 隐患登记 AI 摘要/分类。

参考 `risk_dual_ai_service.py` / `risk_ai_service.py` 既有惯例：
`llm_text_completion(timeout=60)` + `_parse_ai_json`；
未配置/异常/超时一律降级返回 `available: false` + 空 items（§16），
不阻塞前端流程（页面确认后再由 POST /templates 落库）。

`record_assist`（§8 #6）：输入登记描述文字（仅文本，不读照片），返回
title 摘要 + hazard_type 码值 + 分级建议；任何失败/未配置 → available:false
降级（§16），人工确认后填入登记表单。
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


# ── 隐患登记 AI 摘要/分类（任务 5，§8 #6） ──

# 与数据字典 hazard_type 系统种子码值一致（equipment/fire/behavior/management/
# environment/other，见 db_migration_data_dicts.sql）；服务层用固定集合校验 AI
# 返回，路由层登记校验仍走企业数据字典（企业覆盖 > 系统默认）。
HAZARD_TYPE_CODES = {"equipment", "fire", "behavior", "management", "environment", "other"}
# 分级建议取中文「一般/重大」，与 hazard_records.level 值域（规格 §5.4）一致
RECORD_LEVELS = {"一般", "重大"}


def _record_assist_fallback() -> dict:
    """AI 摘要/分类降级兜底：available=false + 空建议，不阻塞登记（§16）。"""
    return {
        "available": False,
        "title": "",
        "hazard_type": "",
        "suggested_level": "",
        "reason": "",
        "note": "AI 不可用，请手动填写隐患摘要与分类",
    }


async def record_assist(
    description: str,
    ai_config: Optional[object],
    object_id: Optional[str] = None,
    measure_id: Optional[str] = None,
) -> dict:
    """AI 摘要/分类（§8 #6）：输入登记描述，输出 title/hazard_type/suggested_level。

    Args:
        description: 隐患登记描述文字（必填非空，路由层已校验）
        ai_config: 系统 AI 配置；None（未配置）时直接降级
        object_id: 可选关联风险点 id（作为上下文提示 AI，不落库）
        measure_id: 可选关联管控措施 id（作为上下文提示 AI，不落库）

    Returns:
        available=True 时含 title（≤255 中文摘要）、hazard_type（字典码值之一）、
        suggested_level（一般/重大）、reason；未配置/异常/超时/返回不合法 →
        available=False 空建议（§16）。
    """
    if ai_config is None:
        return _record_assist_fallback()
    context = "（未提供）"
    parts = []
    if object_id:
        parts.append(f"关联风险点 ID：{object_id}")
    if measure_id:
        parts.append(f"关联管控措施 ID：{measure_id}")
    if parts:
        context = "；".join(parts)
    prompt = (
        "你是持证的安全隐患排查专家。请根据隐患登记描述，生成隐患摘要与分类建议。\n\n"
        f"隐患描述：{description}\n"
        f"上下文：{context}\n\n"
        "要求：\n"
        "1. title：不超过 255 字的中文隐患摘要，具体可执行，不得照抄全文\n"
        "2. hazard_type：必须取以下码值之一：equipment（设备设施）、fire（消防）、"
        "behavior（作业行为）、management（管理缺陷）、environment（环境）、other（其他）\n"
        "3. suggested_level：取 一般 或 重大（重大仅限可能引发重大事故的典型情形，"
        "不得随意拔高）\n"
        "4. reason：用一句中文说明分类与分级依据\n"
        '5. 只输出 JSON：{"title": "...", "hazard_type": "...", '
        '"suggested_level": "一般", "reason": "..."}'
    )
    messages = [
        {"role": "system", "content": "你是隐患排查专家，输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm_text_completion(messages, ai_config, timeout=60)
        data = _parse_ai_json(raw)
        title = str(data.get("title") or "").strip()[:255]
        hazard_type = str(data.get("hazard_type") or "").strip()
        suggested_level = str(data.get("suggested_level") or "").strip()
        reason = str(data.get("reason") or "").strip()
        if not title or hazard_type not in HAZARD_TYPE_CODES or suggested_level not in RECORD_LEVELS:
            raise ValueError("AI 未返回有效的摘要/分类结果")
        return {
            "available": True,
            "title": title[:255],
            "hazard_type": hazard_type,
            "suggested_level": suggested_level,
            "reason": reason,
            "note": "",
        }
    except Exception:
        return _record_assist_fallback()
