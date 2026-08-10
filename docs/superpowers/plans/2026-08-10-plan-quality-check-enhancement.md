# 预案质量检查增强（一致性/合规性/可执行性）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 `plan_quality_service.check_plan` 中新增 9 条规则（C1-C3/L1-L3/E1-E3）并修正现有粒度问题（C0），全部纯规则、零 LLM 成本。

**架构：** 保持 `check_plan(plan, enterprise, sections)` 纯函数签名；新增可选参数 `required_sections: list[str] | None`（L1 用，由调用方从 PlanTemplate 传入，不传则跳过 L1）；法规引用比对读取 `regulations/data/graph.json`（加载失败静默跳过）。新增规则全部返回统一 warning/issue 结构。

**技术栈：** Python 3.12 + re 正则；pytest；JSON 法规库。

**规格：** `docs/superpowers/specs/2026-08-10-plan-quality-check-enhancement-design.md`

---

## 文件结构

**后端：**
- 修改 `backend/app/services/plan_quality_service.py` — 新增 C0/C1-C3/L1-L3/E1-E3
- 修改 `backend/app/routers/export.py` — validate 调用传 `required_sections`
- 修改 `backend/tests/test_plan_quality.py` — 新增各规则测试
- 新增 `backend/tests/test_plan_quality_compliance.py` — 法规引用比对测试

**前端：**
- 无改动（复用现有展示）

---

### 任务 1：C0 基础修正（必含章节粒度 + 地址片段匹配）

**文件：**
- 修改：`backend/app/services/plan_quality_service.py`
- 修改：`backend/tests/test_plan_quality.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_quality.py 追加
from app.services.plan_quality_service import (
    check_plan, _extract_address_fragments, _must_have_section_key,
)


def test_must_have_section_keys():
    assert _must_have_section_key("comprehensive") == "sec_2"
    assert _must_have_section_key("special") == "sec_1"
    assert _must_have_section_key("onsite") == "sec_1"
    assert _must_have_section_key("unknown") is None


def test_extract_address_fragments():
    frags = _extract_address_fragments("陕西省西安市经济技术开发区民经一路726号2幢12402室")
    assert any("民经一路726号" in f for f in frags)
    assert any("经济技术开发区" in f for f in frags)


def test_non_must_have_section_no_archive_warning():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号2幢12402室",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    # sec_3 处置程序非必含章节：即使不含地址也不该报「未体现」
    result = check_plan(plan, enterprise, [_section("sec_3", "处置程序与措施", "<p>内容</p>")])
    assert not any("未体现" in w["warning"] for w in result["warnings"])


def test_must_have_section_address_fragment_match_no_warning():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号2幢12402室",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    # 必含章节 sec_1：正文含关键片段「民经一路726号」即视为已体现
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>公司位于民经一路726号，法定代表人为刘昕野，安全负责人刘昕野。</p>")
    ])
    assert not any("未体现" in w["warning"] for w in result["warnings"])
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v`
预期：FAIL，`ImportError: cannot import name '_must_have_section_key'`

- [ ] **步骤 3：实现 C0**

```python
# backend/app/services/plan_quality_service.py  模块级新增：
MUST_HAVE_SECTION = {"comprehensive": "sec_2", "special": "sec_1", "onsite": "sec_1"}


def _must_have_section_key(plan_type: str) -> str | None:
    return MUST_HAVE_SECTION.get(plan_type)


def _extract_address_fragments(address: str) -> list:
    """从档案地址提取关键片段：区县/路街/门牌级别，用于模糊匹配。"""
    if not address:
        return []
    frags = []
    # 路/街/道 + 门牌（如 民经一路726号）
    m = re.search(r"[\u4e00-\u9fa5]{2,12}(?:路|街|大道)[0-9０-９]*号?", address)
    if m:
        frags.append(m.group(0))
    # 区/县/开发区级（如 经济技术开发区）
    m = re.search(r"[\u4e00-\u9fa5]{2,10}(?:区|县|开发区|新区)", address)
    if m:
        frags.append(m.group(0))
    return frags
```

`check_plan` 内「档案字段未体现」逻辑改为：

```python
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
```

删除原「逐章节 for field」块。

- [ ] **步骤 4：运行测试验证通过**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_quality_service.py backend/tests/test_plan_quality.py
git commit -m "fix(plan): check archive fields only in must-have section with fragment matching (quality C0)"
```

---

### 任务 2：C1-C3 一致性检查

**文件：**
- 修改：`backend/app/services/plan_quality_service.py`
- 修改：`backend/tests/test_plan_quality.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_quality.py 追加
def test_c1_cross_section_person_conflict():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "13800000000", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>总指挥：刘昕野</p>"),
        _section("sec_3", "处置程序", "<p>总指挥：王五</p>"),
    ])
    assert any("总指挥" in w["warning"] and "不一致" in w["warning"] for w in result["warnings"])


def test_c2_address_conflict():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>公司位于湖北省武汉市某街道。</p>"),
    ])
    assert any("地址" in w["warning"] and "不一致" in w["warning"] for w in result["warnings"])


def test_c3_level_notation_mixed():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>启动III级响应，执行一级响应程序。</p>"),
    ])
    assert any("响应分级" in w["warning"] for w in result["warnings"])
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v`
预期：FAIL（3 个新测试失败：无相应 warning）

- [ ] **步骤 3：实现 C1-C3**

在 `check_plan` 的章节循环之后新增全文级规则：

```python
    # ── C1：跨章节人物一致性 ──
    role_map: dict[str, list[tuple[str, str]]] = {}  # role -> [(section_title, name)]
    ROLE_PATTERNS = [
        (r"总指挥（?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "总指挥"),
        (r"副总指挥（?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "副总指挥"),
        (r"安全负责人（?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "安全负责人"),
    ]
    for s in sections:
        text = _strip_html(s.content)
        for pat, role in ROLE_PATTERNS:
            for m in re.finditer(pat, text):
                role_map.setdefault(role, []).append((s.title, m.group(1)))
    for role, entries in role_map.items():
        names = {n for _, n in entries}
        if len(names) > 1:
            warnings.append({
                "section_key": "",
                "section_title": entries[0][0],
                "warning": f"跨章节{role}姓名不一致：{'、'.join(sorted(names))}",
            })
        # 与档案比对
        org_names = {
            m.get("name") for g in (getattr(enterprise, "org_structure", None) or [])
            for m in g.get("members", []) if role in (m.get("position") or "")
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
                pat = f"{label}（?:：|为|是)?\\s*([\\u4e00-\\u9fa5]{{2,4}})"
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
```

- [ ] **步骤 4：运行测试验证通过 + 全量回归**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v`
预期：PASS

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_quality_service.py backend/tests/test_plan_quality.py
git commit -m "feat(plan): add consistency checks C1-C3 (quality)"
```

---

### 任务 3：L1-L3 合规性检查

**文件：**
- 修改：`backend/app/services/plan_quality_service.py`
- 修改：`backend/app/routers/export.py`（传 required_sections）
- 新增：`backend/tests/test_plan_quality_compliance.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_quality_compliance.py
from unittest.mock import MagicMock, patch
from app.services.plan_quality_service import check_plan, _extract_regulation_refs, _regulation_exists


def _section(key, title, content):
    s = MagicMock()
    s.section_key = key
    s.title = title
    s.content = content
    s.diagram_svgs = {}
    return s


def test_extract_regulation_refs():
    text = "依据《安全生产法》和GB/T 29639-2020，以及（应急管理部令第2号）要求"
    refs = _extract_regulation_refs(text)
    assert any("安全生产法" in r for r in refs)
    assert any("29639" in r for r in refs)


def test_l1_missing_required_section_is_issue():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    # required_sections=["sec_1","sec_2","sec_3","sec_4"]，只给了 sec_1 → 缺 sec_2 等
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>x</p>"),
    ], required_sections=["sec_1", "sec_2", "sec_3", "sec_4"])
    assert any("必含章节" in i["issue"] for i in result["issues"])
    assert result["valid"] is False


def test_l2_regulation_ref_not_in_library_warning():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    with patch("app.services.plan_quality_service._load_regulation_index") as mock_load:
        mock_load.return_value = ["安全生产法"]
        result = check_plan(plan, enterprise, [
            _section("sec_1", "事故风险分析", "<p>依据《不存在的法规X》要求。</p>"),
        ])
    assert any("不存在" in w["warning"] for w in result["warnings"])


def test_l3_terminology_mixed():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_2", "应急指挥", "<p>应急救援指挥部负责，应急指挥部协调。</p>"),
    ])
    assert any("术语" in w["warning"] for w in result["warnings"])
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality_compliance.py -v`
预期：FAIL（函数不存在或规则未实现）

- [ ] **步骤 3：实现 L1-L3**

```python
# backend/app/services/plan_quality_service.py  模块级新增：
_reg_index_cache = None
_reg_index_loaded = False


def _load_regulation_index() -> list | None:
    """加载法规库 graph.json 的 full_name 列表；失败返回 None（静默跳过）。"""
    global _reg_index_cache, _reg_index_loaded
    if _reg_index_loaded:
        return _reg_index_cache
    _reg_index_loaded = True
    try:
        import json as _json
        from pathlib import Path
        p = Path(__file__).parent.parent / "regulations" / "data" / "graph.json"
        data = _json.loads(p.read_text(encoding="utf-8"))
        _reg_index_cache = [n.get("full_name", "") for n in data.get("nodes", [])]
    except Exception:
        _reg_index_cache = None
    return _reg_index_cache


def _extract_regulation_refs(text: str) -> list:
    """提取法规引用：书名号 / 标准号 / 令号。"""
    refs = []
    refs += re.findall(r"《([^》]{2,60})》", text)
    refs += re.findall(r"(?:GB/T?|GB)\s*\d+[-—]\d{4}", text)
    refs += re.findall(r"（[^）]{0,20}?第?\s*\d{3,4}\s*号）", text)
    return [r.strip() for r in refs if r.strip()]


def _regulation_exists(ref: str, index: list | None) -> bool:
    if not index:
        return True  # 库不可用时不误报
    norm = re.sub(r"\s+", "", ref)
    return any(norm in re.sub(r"\s+", "", full) or re.sub(r"\s+", "", full) in norm for full in index)
```

`check_plan` 签名改为 `def check_plan(plan, enterprise, sections, required_sections: list | None = None) -> dict:`

循环后新增：

```python
    # ── L1：必含章节结构合规 ──
    if required_sections:
        present = {s.section_key for s in sections if s.content and s.content.strip()}
        for key in required_sections:
            if key not in present:
                issues.append({
                    "section_key": key,
                    "section_title": key,
                    "issue": "缺少必含章节（章节缺失或内容为空）",
                })

    # ── L2：法规引用真实性 ──
    reg_index = _load_regulation_index()
    for s in sections:
        text = _strip_html(s.content)
        for ref in _extract_regulation_refs(text):
            if not _regulation_exists(ref, reg_index):
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": f"疑似引用不存在的法规：《{ref}》",
                })

    # ── L3：术语统一 ──
    TERM_PAIRS = [("应急救援指挥部", "应急指挥部"), ("应急救援小组", "应急小组")]
    for a, b in TERM_PAIRS:
        has_a = any(a in _strip_html(s.content) for s in sections)
        has_b = any(b in _strip_html(s.content) for s in sections)
        if has_a and has_b:
            warnings.append({
                "section_key": "",
                "section_title": "",
                "warning": f"术语表述不统一：{a} 与 {b} 混用",
            })
```

`export.py::validate_plan_export` 传 required_sections：

```python
    # 从模板读必含章节（顶层 required=True）
    required = []
    tpl = (await db.execute(
        select(PlanTemplate).where(
            PlanTemplate.plan_type == plan.plan_type, PlanTemplate.is_active == True
        ).order_by(PlanTemplate.version.desc()).limit(1)
    )).scalar_one_or_none()
    if tpl and tpl.structure:
        required = [item.get("key") for item in tpl.structure if item.get("required")]
    result = check_plan(plan, enterprise, sections, required_sections=required or None)
```

（`PlanTemplate` 需在 export.py 顶部导入；`select` 已导入。）

- [ ] **步骤 4：运行测试验证通过 + 全量回归**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality_compliance.py -v`
预期：PASS

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_quality_service.py backend/app/routers/export.py backend/tests/test_plan_quality_compliance.py
git commit -m "feat(plan): add compliance checks L1-L3 (quality)"
```

---

### 任务 4：E1-E3 可执行性检查

**文件：**
- 修改：`backend/app/services/plan_quality_service.py`
- 修改：`backend/tests/test_plan_quality.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_quality.py 追加
def test_e1_invalid_phone_format():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "12345", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>联系电话：12345</p>"),
    ])
    assert any("电话" in w["warning"] for w in result["warnings"])


def test_e2_missing_commander():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "抢险组", "members": [
            {"name": "李四", "position": "组长", "phone": "13800000000", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ])
    assert any("总指挥" in w["warning"] for w in result["warnings"])


def test_e3_missing_fire_resource():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ], resources=[])
    assert any("消防" in w["warning"] for w in result["warnings"])
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v`
预期：FAIL（3 个新测试失败）

- [ ] **步骤 3：实现 E1-E3**

`check_plan` 签名增加可选参数：`def check_plan(plan, enterprise, sections, required_sections: list | None = None, resources: list | None = None) -> dict:`

循环后新增：

```python
    # ── E1：联系电话格式 ──
    for s in sections:
        text = _strip_html(s.content)
        for num in re.findall(r"\d{5,}", text):
            if not re.fullmatch(r"1[3-9]\d{9}", num) and not re.fullmatch(r"0\d{2,3}-?\d{7,8}", num):
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": f"疑似联系电话格式错误：{num}",
                })
    for g in (getattr(enterprise, "org_structure", None) or []):
        for m in g.get("members", []):
            if m.get("name") and not m.get("phone"):
                warnings.append({
                    "section_key": "",
                    "section_title": "",
                    "warning": f"企业组织架构中{m.get('name')}（{m.get('position','')}）无联系电话",
                })

    # ── E2：关键岗位覆盖 ──
    org_names = {
        m.get("position", "") for g in (getattr(enterprise, "org_structure", None) or [])
        for m in g.get("members", [])
    }
    if "总指挥" not in org_names or "副总指挥" not in org_names:
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": "企业组织架构缺少总指挥或副总指挥",
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
```

`export.py::validate_plan_export` 传入 resources：

```python
    resources = (await db.execute(
        select(EmergencyResource).where(EmergencyResource.enterprise_id == plan.enterprise_id)
    )).scalars().all()
    result = check_plan(plan, enterprise, sections, required_sections=required or None, resources=resources)
```

（`EmergencyResource` 需导入。）

- [ ] **步骤 4：运行测试验证通过 + 全量回归**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v`
预期：PASS

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_quality_service.py backend/app/routers/export.py backend/tests/test_plan_quality.py
git commit -m "feat(plan): add executability checks E1-E3 (quality)"
```

---

### 任务 5：收尾验证

- [ ] **步骤 1：后端全量回归**

运行：`docker run --rm -v "${PWD}/backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 2：前端无改动确认**

运行：`cd frontend && npx tsc -b`
预期：PASS（确认无前端回归）

- [ ] **步骤 3：规格对照自检**

- [x] C0 必含章节/片段匹配 → 任务 1
- [x] C1-C3 → 任务 2
- [x] L1-L3 → 任务 3
- [x] E1-E3 → 任务 4
- [x] 输出结构不变 → 各任务

- [ ] **步骤 4：Commit（如收尾有额外改动）**

```bash
git add -A
git commit -m "chore(plan): quality check enhancement final verification"
```
