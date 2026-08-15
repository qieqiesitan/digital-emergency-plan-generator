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


# ── 隐患分级 AI 建议 + 治理方案草稿（任务 6，§9） ──

# 内置常见行业重大事故隐患判定要点（文本常量，规格 §9）。
# 来源为国家重大事故隐患判定标准要点摘要；页面须标注「参考提示，
# 以现行有效判定标准为准」，不声称完整法律效力。
JUDGMENT_POINTS = (
    "一、危化品储运：危险化学品未按分区、分类、限量储存；储罐/管道超设计参数运行；"
    "重大危险源未落实包保责任制，或安全监测监控系统缺失、失效；"
    "危化品仓库与生产、生活区安全距离不足，或未设置防爆、防雷、防静电措施。\n"
    "二、消防：疏散通道、安全出口堵塞或锁闭；消防设施（喷淋、报警、灭火器）缺失、"
    "损坏或停用；易燃易爆场所使用非防爆电气设备；违规动火作业无审批、无监护。\n"
    "三、特种设备：压力容器、压力管道、锅炉、起重机械、电梯等未定期检验或超期未检"
    "仍在使用；安全附件（安全阀、压力表、限位装置）失效；作业人员无证上岗。\n"
    "四、粉尘涉爆：粉尘爆炸危险场所未使用防爆电气；除尘系统未规范设置泄爆、隔爆、"
    "惰化装置；干式除尘系统未按规定设置锁气卸灰，或存在严重积尘。\n"
    "五、有限空间：有限空间作业未执行「先通风、再检测、后作业」；未辨识并设置警示"
    "标识；未配备气体检测仪、通风设备与应急救援装备；未落实作业审批与专人监护。\n"
    "（参考提示，以现行有效判定标准为准）"
)

# 分级建议等级码值：与 hazard_records.level 值域（规格 §5.4）一致；
# 与登记 AI 摘要 record_assist 的中文「一般/重大」是不同端点的语义，
# 本端点统一用 major/general 码值供分级确认表单直接落库。
GRADE_LEVELS = {"major", "general"}

# AI 治理方案五键（与状态机 PLAN_KEYS / hazard_records.rectification_plan 契约一致）
PLAN_KEYS = ("goal", "measures", "budget", "emergency_measures", "acceptance_criteria")


def _grade_fallback() -> dict:
    """AI 分级建议降级兜底：available=false + 空建议，不阻塞人工分级（§16）。"""
    return {
        "available": False,
        "suggested_level": "",
        "basis": "",
        "confidence": 0,
        "note": "AI 不可用，请手动判定隐患等级",
    }


def _governance_fallback() -> dict:
    """AI 治理方案降级兜底：available=false + 空 plan，不阻塞人工填写（§16）。"""
    return {
        "available": False,
        "plan": {},
        "note": "AI 不可用，请手动填写治理方案",
    }


def _normalize_plan(raw_plan) -> dict:
    """归一化 AI 治理方案草稿：五键必填且值非空，多余键丢弃，任一缺失返回空 dict。"""
    plan = {}
    if not isinstance(raw_plan, dict):
        return plan
    for key in PLAN_KEYS:
        value = str(raw_plan.get(key) or "").strip()
        if not value:
            return {}
        plan[key] = value
    return plan


async def ai_grade(
    description: str,
    ai_config: Optional[object],
    judgment_points: Optional[str] = None,
    measures_text: Optional[str] = None,
) -> dict:
    """AI 分级建议（§9）：输入隐患描述 + 判定要点 + 措施文本，输出建议等级与依据。

    Args:
        description: 隐患描述文字（必填非空，路由层已校验）
        ai_config: 系统 AI 配置；None（未配置）时直接降级
        judgment_points: 可选判定要点文本；未传时使用内置 JUDGMENT_POINTS 常量
        measures_text: 可选关联管控措施/现状说明文本

    Returns:
        available=True 时含 suggested_level（major/general 码值）、basis、confidence；
        未配置/异常/超时/返回不合法（suggested_level 非 major/general、basis 空）→
        available=False（§16），不阻塞人工分级。
    """
    if ai_config is None:
        return _grade_fallback()
    points = (judgment_points or "").strip() or JUDGMENT_POINTS
    measures = (measures_text or "").strip() or "（未提供）"
    prompt = (
        "你是持证的安全隐患排查专家。请根据隐患描述与判定要点，"
        "给出隐患等级建议及判定依据。\n\n"
        f"隐患描述：{description}\n"
        "判定要点（参考提示，以现行有效判定标准为准）：\n"
        f"{points}\n"
        f"关联管控措施/现状说明：{measures}\n\n"
        "要求：\n"
        "1. suggested_level 必须取 major（重大）或 general（一般）\n"
        "2. 重大仅限符合上述判定要点或可能引发重大事故的典型情形，不得随意拔高\n"
        "3. basis：1-3 句中文判定依据，须引用判定要点或明确说明事故后果\n"
        "4. confidence：0-100 的整数置信度\n"
        '5. 只输出 JSON：{"suggested_level": "major", "basis": "...", "confidence": 85}'
    )
    messages = [
        {"role": "system", "content": "你是隐患排查专家，输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm_text_completion(messages, ai_config, timeout=60)
        data = _parse_ai_json(raw)
        suggested_level = str(data.get("suggested_level") or "").strip()
        basis = str(data.get("basis") or "").strip()
        if suggested_level not in GRADE_LEVELS or not basis:
            raise ValueError("AI 未返回有效的分级建议")
        try:
            confidence = int(float(data.get("confidence")))
        except (TypeError, ValueError):
            confidence = 0
        confidence = max(0, min(100, confidence))
        return {
            "available": True,
            "suggested_level": suggested_level,
            "basis": basis,
            "confidence": confidence,
            "note": "",
        }
    except Exception:
        return _grade_fallback()


async def ai_governance_plan(
    description: str,
    ai_config: Optional[object],
    judgment_points: Optional[str] = None,
    measures_text: Optional[str] = None,
) -> dict:
    """AI 治理方案草稿（§9）：输出五键中文草稿，人工修改确认后由 grade 端点落库。

    Args:
        description: 隐患描述文字（必填非空，路由层已校验）
        ai_config: 系统 AI 配置；None（未配置）时直接降级
        judgment_points: 可选判定要点文本；未传时使用内置 JUDGMENT_POINTS 常量
        measures_text: 可选关联管控措施/现状说明文本

    Returns:
        available=True 时含 plan（goal/measures/budget/emergency_measures/
        acceptance_criteria 五键中文草稿）；未配置/异常/超时/五键不全 →
        available=False（§16）。本函数不落库。
    """
    if ai_config is None:
        return _governance_fallback()
    points = (judgment_points or "").strip() or JUDGMENT_POINTS
    measures = (measures_text or "").strip() or "（未提供）"
    prompt = (
        "你是持证的安全隐患排查专家。请根据隐患描述与判定要点，"
        "起草一份重大隐患治理方案。\n\n"
        f"隐患描述：{description}\n"
        "判定要点（参考提示，以现行有效判定标准为准）：\n"
        f"{points}\n"
        f"关联管控措施/现状说明：{measures}\n\n"
        "要求：\n"
        "1. 输出五键治理方案，均为具体可执行的中文：\n"
        "   - goal：治理目标\n"
        "   - measures：治理措施（工程技术/管理措施）\n"
        "   - budget：资金/资源预算\n"
        "   - emergency_measures：整改期间临时应急/防护措施\n"
        "   - acceptance_criteria：验收标准\n"
        "2. 方案应结合判定要点与现状说明，避免空泛套话\n"
        '3. 只输出 JSON：{"plan": {"goal": "...", "measures": "...", '
        '"budget": "...", "emergency_measures": "...", "acceptance_criteria": "..."}}'
    )
    messages = [
        {"role": "system", "content": "你是隐患排查专家，输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm_text_completion(messages, ai_config, timeout=60)
        data = _parse_ai_json(raw)
        plan = _normalize_plan(data.get("plan"))
        if not plan:
            raise ValueError("AI 未返回有效的治理方案")
        return {"available": True, "plan": plan, "note": ""}
    except Exception:
        return _governance_fallback()
