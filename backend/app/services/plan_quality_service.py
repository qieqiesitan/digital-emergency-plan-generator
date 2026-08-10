"""预案内容质量校验：导出前检查占位符残留、档案一致性、章节完整性、疑似推断。"""
import re

from app.services.mermaid_renderer import _extract_mermaid_code


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def _normalize(text: str) -> str:
    """去除所有空白字符，用于档案字段模糊匹配。"""
    return re.sub(r"\s+", "", text or "")


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


def check_plan(plan, enterprise, sections) -> dict:
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
        (r"(?<!副)总指挥(?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "总指挥"),
        (r"副总指挥(?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "副总指挥"),
        (r"安全负责人(?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "安全负责人"),
        (r"(?<!副)组长(?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "组长"),
    ]
    for s in sections:
        text = _strip_html(s.content)
        for pat, role in ROLE_PATTERNS:
            for m in re.finditer(pat, text):
                role_map.setdefault(role, []).append((s.title, m.group(1)))
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
            for f in frags:
                if _normalize(f) not in _normalize(text) and _suspected_address(text):
                    warnings.append({
                        "section_key": s.section_key,
                        "section_title": s.title,
                        "warning": f"疑似地址与档案不一致（档案含：{f}）",
                    })
                    break
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
    has_chinese = bool(re.search(r"一(?:级|类)响应|二级响应|三级响应", full_text))
    if has_roman and has_chinese:
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": "响应分级表述不统一（III级/II级/I级 与 一级/二级/三级 混用）",
        })

    # 时限混用：30分钟 与 0.5小时 并存
    has_min = bool(re.search(r"\d+\s*分钟", full_text))
    has_hr = bool(re.search(r"\d+(?:\.\d+)?\s*小时", full_text))
    if has_min and has_hr:
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": "时限表述不统一（分钟与小时混用）",
        })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }
