"""预案内容质量校验：导出前检查占位符残留、档案一致性、章节完整性、疑似推断。"""
import re

from app.services.mermaid_renderer import _extract_mermaid_code


_reg_index_cache = None
_reg_index_loaded = False

_REG_NODE_TYPES = ("law", "policy", "standard", "article")


def _load_regulation_index() -> dict | None:
    """加载法规库 graph.json：{full_name: status}；失败返回 None（静默跳过）。"""
    global _reg_index_cache, _reg_index_loaded
    if _reg_index_loaded:
        return _reg_index_cache
    _reg_index_loaded = True
    try:
        import json as _json
        from pathlib import Path
        p = Path(__file__).parent.parent / "regulations" / "data" / "graph.json"
        data = _json.loads(p.read_text(encoding="utf-8"))
        index = {}
        for n in data.get("nodes", []):
            full = n.get("full_name", "")
            if not full or n.get("node_type") not in _REG_NODE_TYPES:
                continue
            status = n.get("status", "effective")
            if full not in index or status == "effective":
                index[full] = status
        _reg_index_cache = index
    except Exception:
        _reg_index_cache = None
    return _reg_index_cache


def _extract_regulation_refs(text: str) -> list:
    """提取法规引用：书名号 / 标准号 / 令号。"""
    refs = []
    refs += re.findall(r"《([^》]{2,60})》", text)
    refs += re.findall(r"(?:GB/T?|GB)\s*\d+[-—]\d{4}", text)
    refs += re.findall(r"[（(][^）)]{0,20}?第?\s*\d{1,4}\s*号[）)]", text)
    return [r.strip() for r in refs if r.strip()]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def _normalize(text: str) -> str:
    """去除所有空白字符并归一化全半角，用于档案字段模糊匹配。"""
    result = re.sub(r"\s+", "", text or "")
    result = result.translate(str.maketrans(
        "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    ))
    return result


def _suspected_address(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fa5]{2,8}(?:省|市|区|县).{0,8}(?:路|街|大道)", text))


MUST_HAVE_SECTION = {"comprehensive": "sec_2", "special": "sec_1", "onsite": "sec_1"}


def _must_have_section_key(plan_type: str) -> str | None:
    return MUST_HAVE_SECTION.get(plan_type)


def _extract_address_fragments(address: str) -> list:
    """从档案地址提取关键片段：区县/路街/门牌级别，用于模糊匹配。"""
    if not address:
        return []
    frags = []
    # 区县/开发区级别片段
    m = re.search(r"[\u4e00-\u9fa5]{2,10}(?:区|县|开发区|新区)", address)
    if m:
        frags.append(m.group(0))
    # 路街/门牌级别片段：从最后一个区划后缀之后提取，避免前缀过长（如带上区县名）导致正文匹配失败
    tail = re.split(r"(?:省|市|区|县|开发区|新区)", address)[-1]
    m = re.search(r"[\u4e00-\u9fa5]{2,6}(?:路|街|大道)[0-9０-９]*号?", tail)
    if m:
        frags.append(m.group(0))
    return frags


def check_plan(plan, enterprise, sections, required_sections: list | None = None) -> dict:
    issues = []
    warnings = []

    for s in sections:
        if not s.content or not s.content.strip():
            issues.append({
                "section_key": s.section_key,
                "section_title": s.title,
                "issue": "章节内容为空",
            })
            continue
        text = _strip_html(s.content)
        if "（待补充）" in text:
            warnings.append({
                "section_key": s.section_key,
                "section_title": s.title,
                "warning": "存在待补充占位符，请人工补全",
            })

        # Mermaid 代码块缺少图表类型声明（规则 5）
        codes = _extract_mermaid_code(s.content or "")
        for code in codes:
            if not code.strip().startswith((
                "flowchart", "graph", "sequenceDiagram", "classDiagram",
                "stateDiagram", "erDiagram", "gantt", "pie",
                "gitGraph", "mindmap", "timeline", "journey",
            )):
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": "Mermaid 代码块缺少图表类型声明",
                })

        # 占位附图
        for key, meta in (s.diagram_svgs or {}).items():
            if isinstance(meta, dict) and meta.get("placeholder"):
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": f"存在未生成的附图占位：{key}（{meta.get('reason', '')}）",
                })

        # C0：档案字段未体现 —— 仅必含章节检查，地址用关键片段匹配
        must_key = _must_have_section_key(getattr(plan, "plan_type", ""))
        if s.section_key == must_key:
            norm_text = _normalize(text)
            for field, label, use_frag in [
                (getattr(enterprise, "address", None), "地址", True),
                (getattr(enterprise, "legal_representative", None), "法定代表人", False),
                (getattr(enterprise, "safety_officer", None), "安全负责人", False),
            ]:
                if not field or field in ("（待补充）",):
                    continue
                if use_frag:
                    frags = _extract_address_fragments(field)
                    matched = any(_normalize(f) in norm_text for f in frags) if frags else _normalize(field) in norm_text
                else:
                    matched = _normalize(field) in norm_text
                if not matched:
                    warnings.append({
                        "section_key": s.section_key,
                        "section_title": s.title,
                        "warning": f"正文未体现企业档案{label}：{field}",
                    })

        # 档案缺失时正文出现疑似地址 → 可能是推断
        if getattr(enterprise, "address", None) in (None, "", "（待补充）") and _suspected_address(text):
            warnings.append({
                "section_key": s.section_key,
                "section_title": s.title,
                "warning": "疑似推断地址，请核实",
            })

    # ── C1：跨章节人物一致性 ──
    role_map: dict[str, list[tuple[str, str]]] = {}  # role -> [(section_title, name)]
    ROLE_PATTERNS = [
        (r"(?<!副)总指挥\s*[：:为是]?\s*([\u4e00-\u9fa5]{2,4})(?=[，。；;、\s]|$)", "总指挥"),
        (r"副总指挥\s*[：:为是]?\s*([\u4e00-\u9fa5]{2,4})(?=[，。；;、\s]|$)", "副总指挥"),
        (r"安全负责人\s*[：:为是]?\s*([\u4e00-\u9fa5]{2,4})(?=[，。；;、\s]|$)", "安全负责人"),
        (r"(?<!副)组长\s*[：:为是]?\s*([\u4e00-\u9fa5]{2,4})(?=[，。；;、\s]|$)", "组长"),
    ]

    _NAME_STOPWORDS = {"下令", "负责", "组织", "指挥", "安排", "协调", "执行", "开展", "启动", "部署", "报告", "通知", "上报", "汇报", "配合"}

    def _is_plausible_name(name: str) -> bool:
        return name not in _NAME_STOPWORDS

    for s in sections:
        text = _strip_html(s.content)
        for pat, role in ROLE_PATTERNS:
            for m in re.finditer(pat, text):
                name = m.group(1)
                if _is_plausible_name(name):
                    role_map.setdefault(role, []).append((s.title, name))
    for role, entries in role_map.items():
        names = {n for _, n in entries}
        if len(names) > 1:
            detail = "、".join(f"「{t}」{n}" for t, n in entries)
            warnings.append({
                "section_key": "",
                "section_title": "",
                "warning": f"跨章节{role}姓名不一致：{detail}",
            })
        org_names = {
            m.get("name") for g in (getattr(enterprise, "org_structure", None) or [])
            for m in g.get("members", [])
            if role in (m.get("position") or "") or role in (m.get("role") or "")
        }
        if org_names and not ({n for _, n in entries} <= org_names):
            warnings.append({
                "section_key": "",
                "section_title": entries[0][0],
                "warning": f"正文{role}与企业组织架构不符",
            })

    # ── C2：地址/法人冲突（仅必含章节）──
    must_key = _must_have_section_key(getattr(plan, "plan_type", ""))
    addr = getattr(enterprise, "address", None)
    for s in sections:
        if s.section_key != must_key:
            continue
        text = _strip_html(s.content)
        if addr and addr not in ("（待补充）",):
            frags = _extract_address_fragments(addr)
            archive_present = any(_normalize(f) in _normalize(text) for f in frags) if frags else _normalize(addr) in _normalize(text)
            if not archive_present and _suspected_address(text):
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": "疑似地址与档案不一致",
                })
        for field, label in [
            (getattr(enterprise, "legal_representative", None), "法定代表人"),
            (getattr(enterprise, "safety_officer", None), "安全负责人"),
        ]:
            if field and field not in ("（待补充）",):
                pat = f"{label}(?:：|为|是)?\\s*([\\u4e00-\\u9fa5]{{2,4}})"
                for m in re.finditer(pat, text):
                    if m.group(1) != field:
                        warnings.append({
                            "section_key": s.section_key,
                            "section_title": s.title,
                            "warning": f"疑似{label}与档案不一致（档案：{field}，正文：{m.group(1)}）",
                        })

    # ── C3：响应分级表述混用 ──
    full_text = "".join(_strip_html(s.content) for s in sections)
    has_roman = bool(re.search(r"III级|II级|I级", full_text))
    has_chinese = bool(re.search(r"一(?:级|类)(?:应急)?响应|二(?:级|类)(?:应急)?响应|三(?:级|类)(?:应急)?响应", full_text))
    if has_roman and has_chinese:
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": "响应分级表述不统一（III级/II级/I级 与 一级/二级/三级 混用）",
        })

    # 时限混用：仅当分钟与小时并存且数值不对应（如 30分钟 与 2小时）时报告
    # 先剔除复合时长（如 1小时30分钟），避免拆分成小时+分钟误报
    time_text = re.sub(r"\d+(?:\.\d+)?\s*小时\s*\d+(?:\.\d+)?\s*分钟", "", full_text)
    min_vals = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*分钟", time_text)]
    hr_vals = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*小时", time_text)]
    if min_vals and hr_vals:
        equivalent = any(any(abs(m - h * 60) < 1 for h in hr_vals) for m in min_vals)
        if not equivalent:
            warnings.append({
                "section_key": "",
                "section_title": "",
                "warning": "时限表述不统一（分钟与小时数值不对应）",
            })

    # ── L1：必含章节结构合规 ──
    if required_sections:
        existing_keys = {s.section_key for s in sections}
        for key in required_sections:
            if key not in existing_keys:
                issues.append({
                    "section_key": key,
                    "section_title": key,
                    "issue": "缺少必含章节",
                })

    # ── L2：法规引用真实性 ──
    reg_index = _load_regulation_index()
    for s in sections:
        text = _strip_html(s.content)
        for ref in _extract_regulation_refs(text):
            norm_ref = _normalize(ref)
            matched_status = None
            if reg_index:
                for full, status in reg_index.items():
                    full_norm = _normalize(full)
                    if not full_norm:
                        continue
                    if norm_ref in full_norm or full_norm in norm_ref:
                        matched_status = status
                        break
            if reg_index and matched_status is None:
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": f"疑似引用不存在的法规：《{ref}》",
                })
            elif matched_status == "abolished":
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": f"《{ref}》已废止，请核实",
                })

    # ── L3：术语统一 ──
    TERM_PAIRS = [
        ("应急救援指挥部", "应急指挥部"),
        ("应急救援小组", "应急小组"),
        ("抢险救援组", "抢险组"),
        ("通讯联络组", "通信联络组"),
        ("疏散引导组", "疏散组"),
    ]
    for a, b in TERM_PAIRS:
        has_a = any(a in _strip_html(s.content) for s in sections)
        has_b = any(b in _strip_html(s.content) for s in sections)
        if has_a and has_b:
            warnings.append({
                "section_key": "",
                "section_title": "",
                "warning": f"术语表述不统一：{a} 与 {b} 混用",
            })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }
