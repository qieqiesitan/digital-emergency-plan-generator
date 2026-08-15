"""隐患 AI 辅助服务：检查表模板 AI 生成 + 隐患登记 AI 摘要/分类 +
排查计划一键生成/排程建议/清单补全/智能引导（任务 12）。

参考 `risk_dual_ai_service.py` / `risk_ai_service.py` 既有惯例：
`llm_text_completion(timeout=60)` + `_parse_ai_json`；
未配置/异常/超时一律降级返回 `available: false` + 空 items（§16），
不阻塞前端流程（页面确认后再由 POST /templates 落库）。

`record_assist`（§8 #6）：输入登记描述文字（仅文本，不读照片），返回
title 摘要 + hazard_type 码值 + 分级建议；任何失败/未配置 → available:false
降级（§16），人工确认后填入登记表单。

任务 12（§3.7 #2/#7、§6、§16）：`build_inspection_plans`（排查计划一键生成，
2-6 套建议）、`suggest_schedule`（排程建议）、`suggest_checklist_items`（清单
补全）、`run_setup_wizard`（智能引导，复用 `suggest_org_tree` / plan-builder /
checklist-template 三个既有函数）。全部为文本通道、失败降级不落库。
"""

from typing import Optional

from app.services.llm_client import llm_text_completion
from app.services.enterprise_org_service import suggest_org_tree
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


# ── AI 排查计划一键生成 / 排程建议 / 清单补全 / 智能引导（任务 12） ──

# 与路由层 PLAN_CATEGORIES / PLAN_FREQUENCIES（规格 §5.1 值域）保持一致；
# 服务层自包含定义，避免依赖路由层常量。
PLAN_CATEGORY_CODES = {"daily", "comprehensive", "special", "holiday"}
FREQUENCY_CODES = {"daily", "weekly", "monthly", "custom"}


def _plan_builder_fallback() -> dict:
    """AI 计划一键生成降级兜底：available=false + 空 plans，不阻塞手动建计划（§16）。"""
    return {"available": False, "plans": [], "note": "AI 不可用，请手动创建排查计划"}


def _schedule_fallback() -> dict:
    """AI 排程建议降级兜底：available=false + 空建议，不阻塞计划创建（§16）。"""
    return {
        "available": False,
        "suggested_frequency": "",
        "suggested_responsible_user_id": None,
        "reason": "",
        "note": "AI 不可用，请手动设置排程",
    }


def _checklist_fallback() -> dict:
    """AI 清单补全降级兜底：available=false + 空 items，不阻塞任务执行（§16）。"""
    return {"available": False, "items": [], "note": "AI 不可用，请使用既有检查项"}


def _normalize_plan_suggestion(raw) -> dict:
    """归一化 AI 返回的单套排查计划：name/category/frequency 必填且码值合法。

    可选字段 weekdays（int 数组）、responsible_user_name（责任人建议姓名文本）、
    zone_names（覆盖分区名称文本）类型非法时置空——本服务不落库、不解析 id，
    页面确认后由前端/落库路径把姓名与名称映射为企业成员 id 与分区 id。
    """
    if not isinstance(raw, dict):
        return {}
    name = str(raw.get("name") or "").strip()
    category = str(raw.get("category") or "").strip()
    frequency = str(raw.get("frequency") or "").strip()
    if not name or category not in PLAN_CATEGORY_CODES or frequency not in FREQUENCY_CODES:
        return {}
    weekdays = raw.get("weekdays")
    if isinstance(weekdays, list):
        weekdays = [int(w) for w in weekdays if isinstance(w, int) and not isinstance(w, bool)] or None
    else:
        weekdays = None
    responsible = raw.get("responsible_user_name")
    responsible = str(responsible).strip() if responsible is not None else ""
    zones = raw.get("zone_names")
    if isinstance(zones, list):
        zones = [str(z).strip() for z in zones if str(z).strip()] or None
    else:
        zones = None
    return {
        "name": name,
        "category": category,
        "frequency": frequency,
        "weekdays": weekdays,
        "responsible_user_name": responsible or None,
        "zone_names": zones,
    }


async def build_inspection_plans(
    areas: str,
    frequency_preference: str,
    ai_config: Optional[object],
) -> dict:
    """AI 一键生成排查计划（§3.7 #2/§6）：区域清单 + 频次偏好 → 2-6 套计划建议。

    Args:
        areas: 区域清单文本（必填非空，路由层已校验）
        frequency_preference: 频次偏好文本（必填非空，路由层已校验）
        ai_config: 系统 AI 配置；None（未配置）时直接降级

    Returns:
        available=True 时含 plans（2-6 套，元素 {name, category, frequency,
        weekdays?, responsible_user_name?, zone_names?}）。responsible_user_name /
        zone_names 为建议责任人姓名与分区名称文本——页面整批确认或逐条调整后
        映射为企业成员 id 与分区 id 再经 POST /plans 落库（本服务不落库）。
        未配置/异常/超时/返回不合法（不足 2 套有效计划、码值非法）→
        available=False（§16），不阻塞手动创建。
    """
    if ai_config is None:
        return _plan_builder_fallback()
    pref = (frequency_preference or "").strip() or "（未特别要求，请结合区域合理推荐）"
    prompt = (
        "你是持证的安全隐患排查专家。请根据区域清单与频次偏好，"
        "生成整套排查计划建议。\n\n"
        f"区域清单：{areas}\n"
        f"频次偏好：{pref}\n\n"
        "要求：\n"
        "1. 输出 2-6 套计划，尽可能覆盖 日常(daily)/综合(comprehensive)/"
        "专项(special)/节假日(holiday) 四类\n"
        "2. 每套计划包含：\n"
        "   - name：计划名称（中文，具体到区域/主题）\n"
        "   - category：daily/comprehensive/special/holiday 之一\n"
        "   - frequency：daily/weekly/monthly/custom 之一\n"
        "   - weekdays（可选）：weekly/custom 时的星期集合 [1-7]（周一=1）\n"
        "   - responsible_user_name（可选）：建议责任人姓名（仅姓名文本，不编造账号）\n"
        "   - zone_names（可选）：覆盖分区名称列表（使用用户提供的区域名称）\n"
        "3. 计划应结合区域特点，避免空泛重复\n"
        '4. 只输出 JSON：{"plans": [{"name": "...", "category": "daily", '
        '"frequency": "weekly", "weekdays": [1, 3], "responsible_user_name": "张三", '
        '"zone_names": ["生产车间"]}]}'
    )
    messages = [
        {"role": "system", "content": "你是隐患排查专家，输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm_text_completion(messages, ai_config, timeout=60)
        data = _parse_ai_json(raw)
        raw_plans = data.get("plans")
        if not isinstance(raw_plans, list):
            raise ValueError("AI 未返回计划列表")
        plans = [p for p in (_normalize_plan_suggestion(x) for x in raw_plans) if p]
        if len(plans) < 2:
            raise ValueError("AI 返回的有效计划不足 2 套")
        return {"available": True, "plans": plans[:6], "note": ""}
    except Exception:
        return _plan_builder_fallback()


async def suggest_schedule(
    plan_draft: str,
    ai_config: Optional[object],
    zone_risk_hints: Optional[str] = None,
    history_hints: Optional[str] = None,
) -> dict:
    """AI 排程建议（§6）：输入计划草稿 + 可选分区风险/历史隐患提示。

    Args:
        plan_draft: 计划草稿文本（必填非空，路由层已校验）
        ai_config: 系统 AI 配置；None（未配置）时直接降级
        zone_risk_hints: 可选分区风险等级提示文本
        history_hints: 可选历史隐患频次提示文本

    Returns:
        available=True 时含 suggested_frequency（daily/weekly/monthly/custom 码值）、
        suggested_responsible_user_id（建议用户 id——服务不校验存在性，页面确认后
        落库前再校验；AI 无法给出时 null + reason 说明）、reason（依据说明）。
        未配置/异常/超时/返回不合法（频次非码值、reason 缺失）→ available=False
        （§16），不阻塞计划创建。
    """
    if ai_config is None:
        return _schedule_fallback()
    zone_text = (zone_risk_hints or "").strip() or "（未提供）"
    history_text = (history_hints or "").strip() or "（未提供）"
    prompt = (
        "你是持证的安全隐患排查专家。请根据计划草稿与分区风险/历史隐患提示，"
        "给出排查排程建议。\n\n"
        f"计划草稿：{plan_draft}\n"
        f"分区风险等级提示：{zone_text}\n"
        f"历史隐患频次提示：{history_text}\n\n"
        "要求：\n"
        "1. suggested_frequency 必须取 daily/weekly/monthly/custom 之一\n"
        "2. suggested_responsible_user_id：如能从草稿或提示中确定建议责任人，"
        "给出其用户 id（字符串）；无法确定时输出 null，并在 reason 中说明\n"
        "3. reason：1-2 句中文说明频次与责任人依据\n"
        '4. 只输出 JSON：{"suggested_frequency": "weekly", '
        '"suggested_responsible_user_id": "u-001", "reason": "..."}'
    )
    messages = [
        {"role": "system", "content": "你是隐患排查专家，输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm_text_completion(messages, ai_config, timeout=60)
        data = _parse_ai_json(raw)
        frequency = str(data.get("suggested_frequency") or "").strip()
        responsible = data.get("suggested_responsible_user_id")
        if responsible is not None:
            responsible = str(responsible).strip() or None
        reason = str(data.get("reason") or "").strip()
        if frequency not in FREQUENCY_CODES or not reason:
            raise ValueError("AI 未返回有效的排程建议")
        return {
            "available": True,
            "suggested_frequency": frequency,
            "suggested_responsible_user_id": responsible,
            "reason": reason,
            "note": "",
        }
    except Exception:
        return _schedule_fallback()


async def suggest_checklist_items(
    task_context: str,
    ai_config: Optional[object],
) -> dict:
    """AI 清单补全（§6）：输入任务上下文，返回 8 项以内建议新增项。

    Args:
        task_context: 任务上下文文本（任务标题/分区/既有清单项等，必填非空）
        ai_config: 系统 AI 配置；None（未配置）时直接降级

    Returns:
        available=True 时含 items（[{content, expected_note}]，≤8 项，页面勾选后
        与既有清单项合并去重）；未配置/异常/超时/返回不合法 → available=False
        （§16），任务仍可执行。
    """
    if ai_config is None:
        return _checklist_fallback()
    prompt = (
        "你是持证的安全隐患排查专家。请根据任务上下文，补充建议排查清单项。\n\n"
        f"任务上下文：{task_context}\n\n"
        "要求：\n"
        "1. 输出不超过 8 项建议新增的排查项（不要重复既有清单内容）\n"
        "2. 每项包含 content（检查内容）与 expected_note（期望状态/合格标准），"
        "均为中文、具体可执行\n"
        "3. 结合任务上下文中的区域/设备/既有项，避免空泛\n"
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
            raise ValueError("AI 未返回有效清单项")
        return {"available": True, "items": items[:8], "note": ""}
    except Exception:
        return _checklist_fallback()


def _wizard_fallback() -> dict:
    """智能引导降级兜底：available=false + 三块空建议，不阻塞手动初始配置（§16）。"""
    return {
        "available": False,
        "org_suggestion": {"available": False, "note": "AI 不可用，请手动维护组织架构"},
        "plans_suggestion": _plan_builder_fallback(),
        "checklist_suggestion": _checklist_fallback(),
        "note": "AI 不可用，请手动完成初始配置",
    }


async def run_setup_wizard(
    industry: str,
    areas: str,
    employee_count: Optional[str],
    frequency_preference: Optional[str],
    ai_config: Optional[object],
) -> dict:
    """智能引导向导（§3.8/#7）：一次性预填 组织树 → 排查计划 → 检查表，分步确认。

    复用既有服务函数避免重复实现：org_suggestion 直接调用
    `enterprise_org_service.suggest_org_tree`（同型建树）、plans_suggestion 直接
    调用本文件的 `build_inspection_plans`、checklist_suggestion 直接调用
    `generate_checklist_template`；三块各自内部兜底 available:false，本函数仅当
    三块全失败时整体降级（任一可用即 available=True，前端分块显示）。

    Args:
        industry: 行业描述（必填非空，路由层已校验）
        areas: 主要区域文本（必填非空，路由层已校验）
        employee_count: 大致人数（可空）
        frequency_preference: 希望排查频次偏好（可空）
        ai_config: 系统 AI 配置；None（未配置）时直接降级且不调用 LLM

    Returns:
        available=True 时含 org_suggestion / plans_suggestion / checklist_suggestion
        三块（各自结构同 suggest_org_tree / plan-builder / checklist-template）与
        note；未配置/三块全失败 → available=False（§16）。本函数不落库——分步
        确认后由组织/计划/模板落库端点写库。
    """
    if ai_config is None:
        return _wizard_fallback()
    try:
        org_result = await suggest_org_tree(
            {"industry": industry, "employee_count": employee_count},
            ai_config,
        )
    except Exception:
        org_result = {"available": False, "note": "AI 不可用，请手动维护组织架构"}
    try:
        plans_result = await build_inspection_plans(areas, frequency_preference or "", ai_config)
    except Exception:
        plans_result = _plan_builder_fallback()
    try:
        checklist_result = await generate_checklist_template(industry, areas, ai_config)
    except Exception:
        checklist_result = _checklist_fallback()
    blocks = (org_result, plans_result, checklist_result)
    if not any(isinstance(b, dict) and b.get("available") is True for b in blocks):
        return _wizard_fallback()
    return {
        "available": True,
        "org_suggestion": org_result,
        "plans_suggestion": plans_result,
        "checklist_suggestion": checklist_result,
        "note": "",
    }
