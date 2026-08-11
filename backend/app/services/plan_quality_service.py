"""预案内容质量校验：导出前检查占位符残留、档案一致性、章节完整性、疑似推断。"""
import re

from app.services.mermaid_renderer import _extract_mermaid_code


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


def _role_matches(member: dict, role: str) -> bool:
    """判断成员是否承担某角色：职务名直接匹配，或总经理→总指挥/副总经理→副总指挥。"""
    pos = (member.get("position") or "") + (member.get("role") or "")
    if role in pos:
        return True
    if role == "总指挥" and "总经理" in pos:
        return True
    if role == "副总指挥" and "副总经理" in pos:
        return True
    return False


def check_plan(plan, enterprise, sections, required_sections: list | None = None, resources: list | None = None, has_risk: bool = False) -> dict:
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
        (r"(?<!副)总指挥\s*[：:为是（(]\s*([\u4e00-\u9fa5]{2,4})(?=[，。；;、\s）)]|$)", "总指挥"),
        (r"副总指挥\s*[：:为是（(]\s*([\u4e00-\u9fa5]{2,4})(?=[，。；;、\s）)]|$)", "副总指挥"),
        (r"安全负责人\s*[：:为是（(]\s*([\u4e00-\u9fa5]{2,4})(?=[，。；;、\s）)]|$)", "安全负责人"),
    ]

    _NAME_STOPWORDS = {
        "下令", "负责", "组织", "指挥", "安排", "协调", "执行", "开展", "启动", "部署",
        "报告", "通知", "上报", "汇报", "配合",
        "不在岗时", "职责", "负责制", "指令后", "接报后", "组织讲评", "下达", "代行", "命令",
    }

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
            if _role_matches(m, role)
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
    has_chinese = bool(re.search(
        r"(?<!设置)(?<!分为)(?<!划分)一(?:级|类)(?:应急)?响应"
        r"|(?<!设置)(?<!分为)(?<!划分)二(?:级|类)(?:应急)?响应"
        r"|(?<!设置)(?<!分为)(?<!划分)三(?:级|类)(?:应急)?响应",
        full_text,
    ))
    if has_roman and has_chinese:
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": "响应分级表述不统一（III级/II级/I级 与 一级/二级/三级 混用）",
        })
    # 时限混用检查已移除（2026-08-11）：纯正则无法判断分钟/小时数值是否属于同一场景，
    # 「持续观察 30 分钟」（普通火灾）与「观察时间延长至 2 小时」（锂电池）等独立场景会被误报，价值小于误报成本。

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

    # ── L2 法规引用真实性 —— 暂缓（2026-08-11 用户确认方案 A）──
    # 法规库 graph.json 含大量 article 节点与测试节点、法规名写法不统一，
    # 纯规则无法可靠判定「引用是否存在」；仅保留 _extract_regulation_refs 供治理后启用。

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

    # ── E1：组织架构联系电话完整性（正文电话格式检查已收敛移除：
    #    正文数字语义判断纯正则不可靠，易误报身份证/证件号）──
    for g in (getattr(enterprise, "org_structure", None) or []):
        for m in g.get("members", []):
            if m.get("name") and not m.get("phone"):
                warnings.append({
                    "section_key": "",
                    "section_title": "",
                    "warning": f"企业组织架构中{m.get('name')}（{m.get('position','') or m.get('role','') or ''}）无联系电话",
                })

    # ── E2：关键岗位覆盖 ──
    org_roles = {
        role
        for g in (getattr(enterprise, "org_structure", None) or [])
        for m in g.get("members", [])
        for role in ("总指挥", "副总指挥")
        if _role_matches(m, role)
    }
    has_commander = "总指挥" in org_roles
    has_deputy = "副总指挥" in org_roles
    if not has_commander or not has_deputy:
        # 规则 1：档案缺岗位
        missing = []
        if not has_commander:
            missing.append("总指挥")
        if not has_deputy:
            missing.append("副总指挥")
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": f"企业组织架构缺少{'、'.join(missing)}",
        })
        # 规则 2：正文提及指挥机构但档案缺总指挥（仅当规则 1 已报且缺总指挥时补充）
        if not has_commander:
            for s in sections:
                text = _strip_html(s.content)
                if ("应急指挥" in text or "指挥机构" in text) and text.strip():
                    warnings.append({
                        "section_key": s.section_key,
                        "section_title": s.title,
                        "warning": "正文提及应急指挥机构，但企业组织架构未设置总指挥",
                    })

    # ── E3：应急资源充分性 ──
    resources = resources or []
    cats = {getattr(r, "category", "") or r.get("category", "") for r in resources}
    if not any("消防" in c or "灭火" in c for c in cats):
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": "企业未登记消防/灭火类应急资源",
        })
    if not any("急救" in c or "医疗" in c for c in cats):
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": "企业未登记急救/医疗类应急资源",
        })
    # E3 第 3 条：类别下所有资源数量均为 0 才提示（需企业有风险点才有意义；
    # 类别下任一资源有正数即视为该类可用，不再按单条资源误报整类为 0）
    if has_risk:
        cat_quantities: dict[str, list] = {}
        for r in resources:
            cat = getattr(r, "category", "") or r.get("category", "")
            qty = getattr(r, "quantity", None) if hasattr(r, "quantity") else r.get("quantity")
            cat_quantities.setdefault(cat, []).append(qty)
        for cat, qs in cat_quantities.items():
            # None 视为未知不参与：类别下须存在已知数量，且全部为 0、无正数才提示
            if (cat and qs and any(q is not None for q in qs)
                    and all(q == 0 for q in qs if q is not None)
                    and not any(q is not None and q > 0 for q in qs)):
                warnings.append({
                    "section_key": "",
                    "section_title": "",
                    "warning": f"{cat}应急资源数量均为 0",
                })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }
