"""风险源权威规则与冲突留痕。"""
RULE_MARKER = "【风险数据权威规则（系统固定，任何模板不得覆盖）】"
RULE_TEXT = RULE_MARKER + """
1. 【风险源清单】是风险事实的唯一来源：风险源条目、事故类型、L/S/R、风险等级、管控措施一律以清单为准。
2. 禁止增删、改名、合并丢失或改判清单中的任何风险源；禁止以企业档案、报告摘要、常识推断为由排除清单条目。
3. 清单与【企业档案】或【风险评估报告摘要】不一致时，以清单为准；不一致项写入结构化冲突清单，正文保持干净。
4. 风险源数量、等级分布、类别分布等统计必须由清单逐条计算得出，不得自行估算。
5. 引用风险源时按系统给出的固定顺序与编号（“第N项”），不得重排。"""

VALID_CONFLICT_TYPES = {
    "count_mismatch", "level_mismatch", "category_mismatch", "coverage", "narrative",
}
_LEVELS = ("重大", "较大", "一般", "低")


def with_rule(text: str) -> str:
    """追加规则块；已包含则原样返回，避免重复注入。"""
    text = text or ""
    if RULE_MARKER in text:
        return text
    return (text.rstrip() + "\n\n" + RULE_TEXT).strip()


def _conflict(ctype: str, item: str, expected: str, actual: str, note: str, source: str) -> dict:
    return {"type": ctype, "item": item, "expected": expected,
            "actual": actual, "note": note, "source": source}


def _level_counts(risk_sources) -> dict:
    counts = {lv: 0 for lv in _LEVELS}
    for rs in risk_sources or []:
        lv = str(rs.get("risk_level") or "").strip()
        if lv in counts:
            counts[lv] += 1
    return counts


def _category_counts(risk_sources) -> dict:
    counts: dict[str, int] = {}
    for rs in risk_sources or []:
        cat = str(rs.get("categories") or "").strip()
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    return counts


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compute_conflicts(risk_sources, summary) -> list[dict]:
    summary = summary or {}
    risk_sources = risk_sources or []
    conflicts: list[dict] = []
    actual_count = summary.get("risk_source_count")
    if actual_count is None:
        conflicts.append(_conflict("coverage", "结构化摘要", "包含 risk_source_count 等字段",
                                   "缺失", "无法校验覆盖完整性", "code"))
        return conflicts
    if _as_int(actual_count) != len(risk_sources):
        conflicts.append(_conflict("count_mismatch", "风险源数量",
                                   f"{len(risk_sources)}（清单）", f"{actual_count}（报告）",
                                   "报告统计的风险源数量与清单不一致", "code"))
    expected_levels = _level_counts(risk_sources)
    actual_levels = summary.get("risk_level_distribution")
    if not isinstance(actual_levels, dict):
        conflicts.append(_conflict("coverage", "等级分布", "重大/较大/一般/低四档统计",
                                   "缺失", "报告未输出等级分布，无法校验", "code"))
    else:
        for lv, exp in expected_levels.items():
            act = _as_int(actual_levels.get(lv, 0))
            if act != exp:
                conflicts.append(_conflict("level_mismatch", f"等级分布·{lv}",
                                           f"{exp}（清单）", f"{actual_levels.get(lv)}（报告）",
                                           "报告等级分布与清单逐条统计不一致", "code"))
    expected_cats = _category_counts(risk_sources)
    actual_cats = summary.get("risk_by_category")
    if expected_cats and isinstance(actual_cats, dict):
        for cat, exp in expected_cats.items():
            act = _as_int(actual_cats.get(cat, 0))
            if act != exp:
                conflicts.append(_conflict("category_mismatch", f"类别分布·{cat}",
                                           f"{exp}（清单）", f"{actual_cats.get(cat)}（报告）",
                                           "报告类别分布与清单逐条统计不一致", "code"))
    top = summary.get("top_risks")
    if isinstance(top, list):
        by_name = {str(rs.get("name") or "").strip(): rs for rs in risk_sources}
        for tr in top:
            if not isinstance(tr, dict):
                continue
            name = str(tr.get("name") or "").strip()
            src = by_name.get(name)
            if src is None:
                conflicts.append(_conflict("coverage", name or "未命名风险源",
                                           "应来自风险源清单", "清单中不存在",
                                           "报告的 top_risks 含清单外条目", "code"))
                continue
            exp_level = str(src.get("risk_level") or "").strip()
            act_level = str(tr.get("risk_level") or "").strip()
            if exp_level and act_level and exp_level != act_level:
                conflicts.append(_conflict("level_mismatch", f"风险等级·{name}",
                                           f"{exp_level}（清单）", f"{act_level}（报告）",
                                           "报告改判了清单中的风险等级", "code"))
    return conflicts


def sanitize_model_conflicts(raw) -> list[dict]:
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        item_text = str(item.get("item") or "").strip()
        if not item_text:
            continue
        ctype = str(item.get("type") or "narrative").strip()
        if ctype not in VALID_CONFLICT_TYPES:
            ctype = "narrative"
        out.append(_conflict(ctype, item_text,
                             str(item.get("expected") or "").strip(),
                             str(item.get("actual") or "").strip(),
                             str(item.get("note") or "").strip(), "model"))
    return out


def merge_conflicts(code_conflicts, model_conflicts) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple] = set()
    for c in list(code_conflicts or []) + list(model_conflicts or []):
        key = (c.get("type"), c.get("item"), c.get("expected"), c.get("actual"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(c)
    return merged


def apply_data_conflicts(summary, risk_sources) -> dict:
    """在 summary 中写入 data_conflicts（整体替换，其它字段保留）。"""
    summary = dict(summary or {})
    model_conflicts = sanitize_model_conflicts(summary.get("data_conflicts"))
    summary["data_conflicts"] = merge_conflicts(
        compute_conflicts(risk_sources, summary), model_conflicts,
    )
    return summary
