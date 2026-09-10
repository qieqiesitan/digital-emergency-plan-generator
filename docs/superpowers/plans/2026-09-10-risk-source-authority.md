# 风险源清单权威性与冲突留痕 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让风险树（风险源清单）成为风险事实唯一来源，模型不得增删/改判风险源；冲突以结构化清单写入报告 summary；风险源顺序与编号稳定可复现。

**架构：** 新增纯函数模块 `report_data_authority`（规则文本 + 冲突计算/清洗/合并/写入）；`risk_context_builder` 抽出 `build_risk_sources` 并稳定排序；三处提示词构造（RA 报告、RI 报告、预案 system prompt）追加固定规则块；RA 路由在全量生成落库与 merge 时写 `summary.data_conflicts`；DB 系统提示词由迁移与 seed 同步。

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy(async) / pytest；DB 迁移为纯 SQL（幂等）。

---

## 环境与验证说明（所有任务共用）

- 后端测试在容器内运行；新增/修改测试文件先拷入容器：

```bash
docker cp backend/tests/<file>.py emergency-plan-backend:/app/tests/<file>.py
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/<file>.py
```

- SQL 迁移应用方式：`docker cp backend/db_migration_<name>.sql emergency-plan-backend:/app/` → `docker restart emergency-plan-backend`（migration_runner 启动时按 schema_migrations 幂等应用）。
- 每任务只 add 本任务文件；不 add TASKS.md、.gitignore、graph.json、scripts、backend/uploads 等他人/历史改动。

---

## 文件结构

- 新建 `backend/app/services/report_data_authority.py`：规则文本、冲突计算/清洗/合并、`apply_data_conflicts`。
- 修改 `backend/app/services/risk_context_builder.py`：抽出 `build_risk_sources(zones)` 并稳定排序；查询补 `order_by`。
- 修改 `backend/app/services/risk_assessment_service.py`：`build_chapter_prompt` 返回前 `with_rule(prompt)`。
- 修改 `backend/app/services/resource_investigation_service.py`：同上。
- 修改 `backend/app/routers/generation.py`：`_build_system_prompt` 返回值 `with_rule(...)`。
- 修改 `backend/app/routers/risk_assessment.py`：全量生成落库与 merge 后调用 `apply_data_conflicts`。
- 修改 `backend/app/services/report_system_prompts.py`：RA/RI 系统提示词常量追加规则块（seed_report_prompts.py 直接引用这两个常量）。
- 修改 `backend/seed_prompts_full.py`：4 条 emergency_system 的 system_prompt 追加规则块。
- 新建 `backend/db_migration_20260910_risk_source_authority.sql`：把规则追加到 8 条系统提示词（幂等）。
- 测试：`backend/tests/test_report_data_authority.py`、`backend/tests/test_risk_context_ordering.py`、`backend/tests/test_prompt_authority_injection.py`、`backend/tests/test_report_authority_merge.py`。

---

### 任务 1：report_data_authority 纯函数模块

**文件：**
- 创建：`backend/app/services/report_data_authority.py`
- 测试：`backend/tests/test_report_data_authority.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_report_data_authority.py"""
from app.services.report_data_authority import (
    RULE_MARKER, apply_data_conflicts, compute_conflicts,
    merge_conflicts, sanitize_model_conflicts, with_rule,
)

SOURCES = [
    {"name": "燃气灶台", "risk_level": "较大", "categories": "火灾"},
    {"name": "机柜及服务器", "risk_level": "一般", "categories": "火灾"},
    {"name": "办公电脑", "risk_level": "低", "categories": ""},
]
GOOD_SUMMARY = {
    "risk_source_count": 3,
    "risk_level_distribution": {"重大": 0, "较大": 1, "一般": 1, "低": 1},
    "risk_by_category": {"火灾": 2},
    "top_risks": [{"name": "燃气灶台", "risk_level": "较大"}],
}


def test_with_rule_appends_once():
    text = with_rule("原始提示词")
    assert RULE_MARKER in text and text.startswith("原始提示词")
    assert with_rule(text) == text


def test_compute_conflicts_clean_summary_is_empty():
    assert compute_conflicts(SOURCES, GOOD_SUMMARY) == []


def test_compute_conflicts_detects_excluded_larger_risk():
    summary = dict(GOOD_SUMMARY)
    summary["risk_source_count"] = 2
    summary["risk_level_distribution"] = {"重大": 0, "较大": 0, "一般": 1, "低": 1}
    conflicts = compute_conflicts(SOURCES, summary)
    types = {c["type"] for c in conflicts}
    assert "count_mismatch" in types
    assert "level_mismatch" in types
    assert all(c["source"] == "code" for c in conflicts)


def test_compute_conflicts_reports_missing_summary():
    conflicts = compute_conflicts(SOURCES, {})
    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "coverage"


def test_compute_conflicts_detects_top_risk_level_change():
    summary = dict(GOOD_SUMMARY)
    summary["top_risks"] = [{"name": "燃气灶台", "risk_level": "一般"}]
    conflicts = compute_conflicts(SOURCES, summary)
    assert any(c["type"] == "level_mismatch" and "燃气灶台" in c["item"] for c in conflicts)


def test_sanitize_model_conflicts_normalizes_and_drops_invalid():
    raw = [
        {"type": "narrative", "item": "厨房与企业档案描述不符", "note": "待核实"},
        {"type": "unknown", "item": "x"},
        {"item": ""},
        "not-a-dict",
    ]
    out = sanitize_model_conflicts(raw)
    assert len(out) == 2
    assert out[0]["source"] == "model"
    assert out[1]["type"] == "narrative"


def test_merge_conflicts_dedupes():
    code = [{"type": "coverage", "item": "x", "expected": "a", "actual": "b"}]
    model = [{"type": "coverage", "item": "x", "expected": "a", "actual": "b"}]
    assert len(merge_conflicts(code, model)) == 1


def test_apply_data_conflicts_keeps_other_keys():
    summary = dict(GOOD_SUMMARY)
    summary["data_conflicts"] = [{"type": "narrative", "item": "厨房与档案不符"}]
    out = apply_data_conflicts(summary, SOURCES)
    assert out["risk_source_count"] == 3
    assert out["data_conflicts"][0]["source"] == "model"
    assert "data_conflicts" in apply_data_conflicts(GOOD_SUMMARY, SOURCES)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_report_data_authority.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_report_data_authority.py`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.report_data_authority'`

- [ ] **步骤 3：编写实现**

```python
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
```

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（8 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/report_data_authority.py backend/tests/test_report_data_authority.py
git commit -m "feat(report): 风险源权威规则与冲突留痕纯函数模块"
```

---

### 任务 2：风险源稳定排序

**文件：**
- 修改：`backend/app/services/risk_context_builder.py`
- 测试：`backend/tests/test_risk_context_ordering.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_risk_context_ordering.py"""
from types import SimpleNamespace

from app.services.risk_context_builder import build_risk_sources


def _obj(name, sort=0, created="2026-01-01", oid=None):
    return SimpleNamespace(
        id=oid or name, name=name, sort_order=sort, created_at=created,
        events=[], units=[], category="", location="", description="",
        is_risk_point=False, legacy_source_id=None, responsible_unit=None,
        responsible_person=None, contact_phone=None, floor_id=None,
    )


def _event(name, sort=0, created="2026-01-01"):
    return SimpleNamespace(
        id=name, sort_order=sort, created_at=created, accident_type=name,
        description="", trigger_conditions="", consequences="",
        risk_level="低", risk_score="R=4", method_type="", method_params={},
        chemical_id=None, measures=[], inherent_risk_level=None,
        inherent_risk_score=None, control_level=None,
    )


def test_build_risk_sources_is_deterministic_regardless_of_input_order():
    e1 = _event("火灾", created="2026-01-02")
    e2 = _event("触电", created="2026-01-01")
    unit = SimpleNamespace(id="u1", name="单元", sort_order=0, created_at="2026-01-01",
                           unit_type="", description="", location="", events=[e1, e2])
    obj = _obj("对象", created="2026-01-01")
    obj.units = [unit]
    zone_a = SimpleNamespace(id="z-b", name="乙区", sort_order=0, created_at="2026-01-02",
                             description="", floor=None, objects=[obj])
    zone_b = SimpleNamespace(id="z-a", name="甲区", sort_order=0, created_at="2026-01-01",
                             description="", floor=None, objects=[])
    forward = build_risk_sources([zone_a, zone_b])
    backward = build_risk_sources([zone_b, zone_a])
    assert [r["name"] for r in forward] == [r["name"] for r in backward]
    assert forward[0]["zone"] == "甲区"
    assert forward[1]["zone"] == "乙区"
    assert [r["accident_type"] for r in forward[1:]] == ["触电", "火灾"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_risk_context_ordering.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_risk_context_ordering.py`
预期：FAIL，`ImportError: cannot import name 'build_risk_sources'`

- [ ] **步骤 3：实现**

在 `risk_context_builder.py` 增加排序键与构建函数，并替换原先的内联循环：

```python
def _sort_key(item) -> tuple:
    return (
        getattr(item, "sort_order", 0) or 0,
        str(getattr(item, "created_at", "") or ""),
        str(getattr(item, "id", "") or ""),
    )


def build_risk_sources(zones) -> list[dict]:
    """按 分区→对象→单元→事件 稳定展开风险源清单。"""
    ordered: list[dict] = []
    for zone in sorted(zones or [], key=_sort_key):
        for obj in sorted(getattr(zone, "objects", []) or [], key=_sort_key):
            for event in sorted(getattr(obj, "events", []) or [], key=_sort_key):
                ordered.append(_risk_source_item(zone, obj, None, event))
            for unit in sorted(getattr(obj, "units", []) or [], key=_sort_key):
                for event in sorted(getattr(unit, "events", []) or [], key=_sort_key):
                    ordered.append(_risk_source_item(zone, obj, unit, event))
    return ordered
```

原内联循环替换为：

```python
    risk_sources_list = build_risk_sources(zones)
```

同时给查询补稳定排序：

```python
        .order_by(RiskZone.sort_order, RiskZone.created_at, RiskZone.id)
        .options(
            selectinload(RiskZone.floor),
            selectinload(RiskZone.objects).order_by(RiskObject.sort_order, RiskObject.created_at, RiskObject.id)
            .selectinload(RiskObject.units).order_by(RiskUnit.sort_order, RiskUnit.created_at, RiskUnit.id)
            .selectinload(RiskUnit.events).order_by(RiskEvent.sort_order, RiskEvent.created_at, RiskEvent.id)
            .selectinload(RiskEvent.measures).order_by(RiskMeasure.sort_order, RiskMeasure.created_at, RiskMeasure.id)
        )
```

`total_events` 统计保持不变（改用 `build_risk_sources` 结果长度亦可：`len(risk_sources_list)`）。

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（1 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_context_builder.py backend/tests/test_risk_context_ordering.py
git commit -m "fix(risk): 风险源清单按 sort_order/created_at/id 稳定排序"
```

---

### 任务 3：三处提示词注入固定规则块

**文件：**
- 修改：`backend/app/services/risk_assessment_service.py`（`build_chapter_prompt` 末尾 `return prompt`）
- 修改：`backend/app/services/resource_investigation_service.py`（`build_chapter_prompt` 末尾 `return prompt`）
- 修改：`backend/app/routers/generation.py`（`_build_system_prompt`）
- 测试：`backend/tests/test_prompt_authority_injection.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_prompt_authority_injection.py"""
from app.services import risk_assessment_service as ra
from app.services import resource_investigation_service as ri
from app.services.report_data_authority import RULE_MARKER
from app.routers import generation as gen


def test_ra_chapter_prompt_contains_rule_once(monkeypatch):
    monkeypatch.setattr(
        ra.RegulationContextBuilder, "get_chapter_context", lambda self, **kw: ""
    )
    context = {"enterprise": {"name": "甲企业"}, "risk_sources": []}
    prompt = ra.build_chapter_prompt("ch1_hazard_id", context)
    assert prompt.count(RULE_MARKER) == 1


def test_ri_chapter_prompt_contains_rule_once():
    context = {
        "enterprise": {"name": "甲企业"},
        "internal_resources": [], "external_resources": [],
        "risk_conclusion": None, "top_risks": [], "org_members": [],
        "chemicals": [], "risk_overview": [], "top_risk_sources": [],
        "total_events": 0,
    }
    prompt = ri.build_chapter_prompt("ch1_purpose", context)
    assert prompt.count(RULE_MARKER) == 1


def test_plan_system_prompt_contains_rule_once():
    text = gen._build_system_prompt("onsite", None, None)
    assert text.count(RULE_MARKER) == 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_prompt_authority_injection.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_prompt_authority_injection.py`
预期：FAIL（3 条断言均为 `assert 0 == 1`）

- [ ] **步骤 3：实现**

`risk_assessment_service.py` 顶部加 `from app.services.report_data_authority import with_rule`，把 `build_chapter_prompt` 末尾的 `return prompt` 改为：

```python
    return with_rule(prompt)
```

`resource_investigation_service.py` 同样处理（顶部导入 + 末尾 `return with_rule(prompt)`）。

`generation.py` 顶部加 `from app.services.report_data_authority import with_rule`，把 `_build_system_prompt` 改为：

```python
def _build_system_prompt(plan_type: str = "*", style_preference: dict | None = None, advanced_overrides: dict | None = None) -> str:
    """构建系统提示词，优先风格参数，fallback 到数据库模板；固定追加风险数据权威规则。"""
    return with_rule(build_system_prompt_with_style(plan_type, style_preference, advanced_overrides))
```

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（3 passed）；再跑关键词回归：

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_report_data_authority.py tests/test_prompt_authority_injection.py tests/test_prompt_layering.py
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_assessment_service.py backend/app/services/resource_investigation_service.py backend/app/routers/generation.py backend/tests/test_prompt_authority_injection.py
git commit -m "feat(prompt): 风险评估/资源调查/预案提示词固定注入风险源权威规则"
```

---

### 任务 4：风险评估报告写入冲突清单

**文件：**
- 修改：`backend/app/routers/risk_assessment.py`（全量生成落库处、`merge_risk_assessment`）
- 测试：`backend/tests/test_report_authority_merge.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_report_authority_merge.py"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers import risk_assessment as ra


@pytest.mark.asyncio
async def test_merge_writes_data_conflicts(monkeypatch):
    ent = MagicMock(id="e1")
    report = MagicMock(id="r1", summary={}, style_preference=None, content="")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(first=lambda: report)),
    ])
    monkeypatch.setattr(
        ra, "build_risk_management_context",
        AsyncMock(return_value={"risk_sources": [
            {"name": "燃气灶台", "risk_level": "较大", "categories": "火灾"},
        ]}),
    )
    monkeypatch.setattr(ra, "_schedule_enterprise_index_rebuild", lambda *a, **k: None)
    request = MagicMock()
    request.custom_instruction = json.dumps([
        {
            "key": "ch5_conclusion", "title": "五、结论",
            "content": (
                "正文内容\n"
                '{"risk_source_count":0,"risk_level_distribution":'
                '{"重大":0,"较大":0,"一般":0,"低":0},"key_findings":[],'
                '"overall_assessment":"无较大风险"}'
            ),
        }
    ])
    await ra.merge_risk_assessment(
        "e1", request, current_user=MagicMock(id="u1"), db=db,
    )
    conflicts = report.summary["data_conflicts"]
    assert any(c["type"] == "count_mismatch" for c in conflicts)
    assert any(c["type"] == "level_mismatch" for c in conflicts)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_report_authority_merge.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_report_authority_merge.py`
预期：FAIL，`KeyError: 'data_conflicts'`

- [ ] **步骤 3：实现**

全量生成最终落库处（`bg_report.summary` 构建与结构化摘要合并之后、四色图渲染之前）追加：

```python
                    from app.services.report_data_authority import apply_data_conflicts
                    bg_report.summary = apply_data_conflicts(
                        bg_report.summary, context.get("risk_sources", []),
                    )
```

`merge_risk_assessment` 中，在 `report.summary = rebuild_chapters_summary(cleaned_chapters, ...)` 与结构化摘要 update 之后追加：

```python
    from app.services.report_data_authority import apply_data_conflicts
    ctx = await build_risk_management_context(enterprise_id, db)
    report.summary = apply_data_conflicts(report.summary, ctx.get("risk_sources", []))
```

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（1 passed）；再跑报告回归：

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_report_summary_strip.py tests/test_report_chapter_storage.py tests/test_report_generation_progress.py tests/test_report_review_service.py
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/risk_assessment.py backend/tests/test_report_authority_merge.py
git commit -m "feat(report): 风险评估报告写入 data_conflicts 冲突清单"
```

---

### 任务 5：DB 系统提示词迁移与 seed 同步

**文件：**
- 创建：`backend/db_migration_20260910_risk_source_authority.sql`
- 修改：`backend/app/services/report_system_prompts.py`
- 修改：`backend/seed_prompts_full.py`
- 测试：`backend/tests/test_prompt_seed_authority.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_prompt_seed_authority.py"""
from app.services.report_data_authority import RULE_MARKER
from app.services import report_system_prompts as rsp
from seed_prompts_full import SEEDS


def test_report_system_prompts_contain_rule():
    assert RULE_MARKER in rsp.RA_REPORT_SYSTEM_PROMPT
    assert RULE_MARKER in rsp.RI_REPORT_SYSTEM_PROMPT


def test_emergency_system_seeds_contain_rule():
    rows = [s for s in SEEDS if s.get("category") == "emergency_system"]
    assert len(rows) == 4
    assert all(RULE_MARKER in (s.get("system_prompt") or "") for s in rows)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_prompt_seed_authority.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_prompt_seed_authority.py`
预期：FAIL（断言 `RULE_MARKER in ...` 为 False）

- [ ] **步骤 3：实现 seed 同步**

`report_system_prompts.py` 末尾追加（对两个常量做幂等包裹）：

```python
from app.services.report_data_authority import with_rule as _with_rule

RA_REPORT_SYSTEM_PROMPT = _with_rule(RA_REPORT_SYSTEM_PROMPT)
RI_REPORT_SYSTEM_PROMPT = _with_rule(RI_REPORT_SYSTEM_PROMPT)
```

`seed_prompts_full.py` 顶部加 `from app.services.report_data_authority import with_rule`，把 4 条 `emergency_system_*` 条目的 `"system_prompt"` 全部改为 `with_rule("……原文本……")`。

- [ ] **步骤 4：编写迁移 SQL**

```sql
-- 20260910：把风险数据权威规则追加到系统提示词（幂等；已包含则跳过）
DO $$
DECLARE
  rule text := E'【风险数据权威规则（系统固定，任何模板不得覆盖）】\n'
    || E'1. 【风险源清单】是风险事实的唯一来源：风险源条目、事故类型、L/S/R、风险等级、管控措施一律以清单为准。\n'
    || E'2. 禁止增删、改名、合并丢失或改判清单中的任何风险源；禁止以企业档案、报告摘要、常识推断为由排除清单条目。\n'
    || E'3. 清单与【企业档案】或【风险评估报告摘要】不一致时，以清单为准；不一致项写入结构化冲突清单，正文保持干净。\n'
    || E'4. 风险源数量、等级分布、类别分布等统计必须由清单逐条计算得出，不得自行估算。\n'
    || E'5. 引用风险源时按系统给出的固定顺序与编号（“第N项”），不得重排。';
BEGIN
  UPDATE prompt_templates
     SET system_prompt = COALESCE(system_prompt, '') || E'\n\n' || rule
   WHERE template_code IN (
     'risk_assessment_system', 'risk_assessment_system_default',
     'resource_investigation_system', 'resource_investigation_system_default',
     'emergency_system_default', 'emergency_system_comprehensive_general',
     'emergency_system_onsite_general', 'emergency_system_special_general'
   )
     AND COALESCE(system_prompt, '') NOT LIKE '%【风险数据权威规则（系统固定，任何模板不得覆盖）】%';
END $$;
```

- [ ] **步骤 5：运行测试并应用迁移**

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_prompt_seed_authority.py
docker cp backend/db_migration_20260910_risk_source_authority.sql emergency-plan-backend:/app/
docker restart emergency-plan-backend
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT template_code, (system_prompt LIKE '%风险数据权威规则%') AS has_rule FROM prompt_templates WHERE template_code IN ('risk_assessment_system','risk_assessment_system_default','resource_investigation_system','resource_investigation_system_default','emergency_system_default','emergency_system_comprehensive_general','emergency_system_onsite_general','emergency_system_special_general') ORDER BY template_code;"
```

预期：测试 PASS；8 行 `has_rule = t`；`schema_migrations` 含该脚本记录。

- [ ] **步骤 6：Commit**

```bash
git add backend/db_migration_20260910_risk_source_authority.sql backend/app/services/report_system_prompts.py backend/seed_prompts_full.py backend/tests/test_prompt_seed_authority.py
git commit -m "chore(prompt): 系统提示词同步风险源权威规则（迁移+seed）"
```

---

### 任务 6：回归与真实数据只读验证

- [ ] **步骤 1：后端回归**

```bash
$files = Get-ChildItem backend/tests -File -Filter *.py | Where-Object { $_.Name -match 'authority|ordering|report|risk_assessment|resource_investigation|generation|prompt' } | Select-Object -ExpandProperty Name
foreach ($f in $files) { docker cp "backend/tests/$f" "emergency-plan-backend:/app/tests/$f" 2>$null }
$argStr = ($files | ForEach-Object { "tests/$_" }) -join ' '
docker exec emergency-plan-backend sh -c "python -m pytest -q -p no:cacheprovider $argStr"
```

预期：全部 PASS（若个别历史环境性失败文件与本次无关，记录并排除，保持与既有基线一致）。

- [ ] **步骤 2：真实数据只读验证（不调用模型、不写库）**

```python
import asyncio, json, hashlib
from sqlalchemy import select
from app.database import async_session
from app.models.enterprise import PlanProject, Enterprise, EmergencyResource, PlanSection
from app.models.hazardous_chemicals import HazardousChemical
from app.models.risk_assessment import RiskAssessmentReport
from app.services.risk_context_builder import build_risk_management_context
from app.services.report_data_authority import compute_conflicts, RULE_MARKER
from app.routers import generation as gen

PID = "9c123a28-88fd-43f1-9ce6-50c33b6e745d"

async def main():
    async with async_session() as db:
        p = (await db.execute(select(PlanProject).where(PlanProject.id == PID))).scalar_one_or_none()
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
        resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()
        ctx1 = await build_risk_management_context(p.enterprise_id, db)
        ctx2 = await build_risk_management_context(p.enterprise_id, db)
        seq1 = [r["name"] + "|" + str(r.get("unit") or "") for r in ctx1["risk_sources"]]
        seq2 = [r["name"] + "|" + str(r.get("unit") or "") for r in ctx2["risk_sources"]]
        print("order_stable:", seq1 == seq2, "sources:", len(seq1))
        print("kitchen_sources:", sum(1 for s in seq1 if "厨房" in s or "燃气" in s))
        rows = (await db.execute(select(HazardousChemical).where(HazardousChemical.enterprise_id == p.enterprise_id))).scalars().all()
        chemicals = {c.id: c for c in rows}
        org_members = await gen._load_org_members(db, p.enterprise_id)
        ent_data = gen._collect_enterprise_data(ent, ctx1, resources, chemicals, org_members=org_members)
        ent_data = await gen._enrich_with_reports(ent_data, p.enterprise_id, db)
        secs = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == PID).order_by(PlanSection.sort_order))).scalars().all()
        smap = {s.section_key: s for s in secs}
        prompt = gen._build_section_prompt(smap["sec_1"].title, ent_data, section_key="sec_1", plan_type=p.plan_type, accident_type=p.accident_type, diagram_preference="mermaid")
        print("plan_rule_count:", prompt.count(RULE_MARKER), "prompt_chars:", len(prompt))
        legacy = {"risk_source_count": 18,
                  "risk_level_distribution": {"重大": 0, "较大": 0, "一般": 2, "低": 12},
                  "top_risks": [{"name": "机柜及服务器", "risk_level": "一般"}]}
        conflicts = compute_conflicts(ctx1["risk_sources"], legacy)
        print("detected_types:", sorted({c["type"] for c in conflicts}), "count:", len(conflicts))

asyncio.run(main())
```

预期输出：

- `order_stable: True`
- `kitchen_sources: 12`（厨房相关风险源条目仍在）
- `plan_rule_count: 1`
- `detected_types` 至少包含 `count_mismatch` 与 `level_mismatch`（证明检测器能捕获本次“排除厨房、较大=0”的事故形态）

说明：本步骤只读，不触发模型调用、不修改数据库。

- [ ] **步骤 3：Commit（如有验证期修正）**

按修正涉及文件分别 commit，不混入他人改动。

---

## 自检结果

- 规格覆盖：规则文本与三处注入（任务 3+5）、DB 同步（任务 5）、冲突双轨与写入（任务 1+4）、稳定排序（任务 2）、失败只记录（任务 1 `apply_data_conflicts` 不改状态）、非目标（不重生成历史数据/不做前端展示）均有对应任务。
- 占位符：无 TODO/待定；每个代码变更步骤均含实际代码或精确插入位置说明。
- 类型一致性：`RULE_MARKER/RULE_TEXT`、`with_rule`、`compute_conflicts`、`sanitize_model_conflicts`、`merge_conflicts`、`apply_data_conflicts`、`build_risk_sources`、`_sort_key` 在任务间引用一致；`summary["data_conflicts"]` 为唯一存储位置。
