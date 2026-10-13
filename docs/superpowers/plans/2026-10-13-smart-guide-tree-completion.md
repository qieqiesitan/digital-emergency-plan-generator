# 智能导引「补全现有风险树」实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 「🚀 智能导引」生成依据企业档案完整字段＋现有风险树结构＋用户补充描述，对现有树查漏补缺（补对象/单元/事件/措施），预览标记「新增/并入」，导入沿用现有同名合并逻辑。

**架构：** 后端在 `risk_ai_service.py` 新增 3 个纯函数（`build_smart_guide_enterprise_info` / `build_existing_tree_dict` / `serialize_existing_tree`），`smart_guide()` prompt 改为三段输入＋查漏补缺规则；路由 `ai_smart_guide` 读取完整层级树并接线；`SmartGuideRequest.description` 允许空串。前端 `smartGuideImport.ts` 新增 `buildMergeBadges` 预判节点去向；`RiskSmartGuideModal` 并行拉取现有树、渲染「新增/并入」标签、描述可选。

**技术栈：** FastAPI + SQLAlchemy(async) + pytest（`cd backend; python -m pytest`）；React + antd + @tanstack/react-query + vitest；playwright 浏览器实测。

**规格：** `docs/superpowers/specs/2026-10-13-smart-guide-tree-completion-design.md`

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/risk_ai_service.py` | 3 个新纯函数 + `smart_guide` prompt 重写 | 修改 |
| `backend/app/routers/risk_management.py` | `ai_smart_guide` 端点接线（读全树、新签名传参） | 修改 |
| `backend/app/schemas/risk_management.py` | `SmartGuideRequest.description` 默认空串 | 修改 |
| `backend/tests/test_smart_guide_import.py` | 3 个纯函数与 prompt 的单测 | 修改 |
| `backend/tests/test_smart_guide_summary_shape.py` | 路由接线源码守护测试 | 修改 |
| `frontend/src/utils/smartGuideImport.ts` | `buildMergeBadges` 纯函数 | 修改 |
| `frontend/src/utils/smartGuideImport.test.ts` | `buildMergeBadges` 单测 | 修改 |
| `frontend/src/components/enterprise/RiskSmartGuideModal.tsx` | 描述可选、并行拉树、标签、文案 | 修改 |

**不要碰**（另一会话正在改，见 TASKS.md 协作警示）：`RiskManagementTab.tsx`、`RiskHierarchyTree.tsx`、`RiskTreeFourColorMap.tsx`、`frontend/e2e/risk-hierarchy-tree.spec.ts`。

**提交纪律：** 一律按路径精确提交（`git commit -m "..." -- <files>`），不要依赖暂存区状态。

---

## 任务 1：后端 · 现有树序列化（`serialize_existing_tree`）

**文件：**
- 修改：`backend/app/services/risk_ai_service.py`
- 测试：`backend/tests/test_smart_guide_import.py`

- [ ] **步骤 1：编写失败的测试**

把 `backend/tests/test_smart_guide_import.py` 顶部导入替换为（只引入本任务已实现/将实现的符号；`build_smart_guide_enterprise_info` 在任务 2 再追加，避免任务 1 阶段整个文件 collection error）：

```python
from app.services.risk_ai_service import (
    _normalize_smart_guide_hierarchy,
    build_existing_tree_dict,
    serialize_existing_tree,
    smart_guide,
)
```

并添加：

```python
def _sample_tree():
    return [{
        "name": "储罐区",
        "objects": [{
            "name": "1号储罐",
            "category": "储罐",
            "units": [{
                "name": "罐体",
                "unit_type": "设备",
                "events": [{
                    "accident_type": "泄漏",
                    "measures": [{"measure_category": "engineering",
                                  "description": "设置液位监控报警"}],
                }],
            }],
            "events": [],
        }],
    }]


def test_serialize_existing_tree_keeps_measure_description_when_small():
    text, truncated = serialize_existing_tree(_sample_tree())
    assert truncated is False
    for token in ("储罐区", "1号储罐", "罐体", "泄漏", "设置液位监控报警"):
        assert token in text


def test_serialize_existing_tree_empty_returns_brackets():
    text, truncated = serialize_existing_tree([])
    assert text == "[]"
    assert truncated is False


def test_serialize_existing_tree_degrades_measures_when_too_long():
    long_desc = "措" * 60
    tree = [{
        "name": "储罐区",
        "objects": [{
            "name": "1号储罐",
            "category": None,
            "units": [],
            "events": [{
                "accident_type": "火灾",
                "measures": [{"measure_category": "engineering",
                              "description": long_desc} for _ in range(10)],
            }],
        }],
    }]
    text, truncated = serialize_existing_tree(tree, max_chars=600)
    assert truncated is False
    assert long_desc not in text          # 降级为数量
    assert '"measures":10' in text        # 紧凑分隔符，无空格


def test_serialize_existing_tree_truncated_when_even_skeleton_too_long():
    tree = [{"name": f"分区{i:03d}", "objects": []} for i in range(300)]
    text, truncated = serialize_existing_tree(tree, max_chars=300)
    assert truncated is True
    assert len(text) <= 300
    assert "分区000" in text
    assert "分区299" not in text
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_smart_guide_import.py -v -k serialize`
预期：collection error / FAIL（`serialize_existing_tree` 等不存在）

- [ ] **步骤 3：编写最少实现代码**

在 `backend/app/services/risk_ai_service.py` 的 `normalize_smart_guide_summary` 之后添加：

```python
SMART_GUIDE_TREE_MAX_CHARS = 20000


def build_existing_tree_dict(zones) -> list[dict]:
    """把现有风险分区（ORM 对象）转为紧凑树 dict，供 AI 提示词使用。

    只保留名称/类型/事件/措施描述，不含画布坐标与长描述——现有树是提示词上下文，
    体量必须可控（超大树的裁剪交给 serialize_existing_tree）。
    """
    def _event(ev) -> dict:
        return {
            "accident_type": ev.accident_type,
            "measures": [
                {"measure_category": m.measure_category, "description": m.description}
                for m in (ev.measures or [])
            ],
        }

    def _object(o) -> dict:
        return {
            "name": o.name,
            "category": o.category,
            "units": [
                {
                    "name": u.name,
                    "unit_type": u.unit_type,
                    "events": [_event(e) for e in (u.events or [])],
                }
                for u in (o.units or [])
            ],
            "events": [_event(e) for e in (o.events or [])],
        }

    return [{"name": z.name, "objects": [_object(o) for o in (z.objects or [])]}
            for z in zones]


def _compact_event(ev: dict, level: int) -> dict:
    out: dict = {"accident_type": ev.get("accident_type") or ""}
    measures = ev.get("measures") or []
    if level == 1:
        out["measures"] = [
            {"measure_category": m.get("measure_category") or "",
             "description": (m.get("description") or "")[:60]}
            for m in measures
        ]
    elif level == 2:
        out["measures"] = len(measures)
    return out


def _compact_unit(u: dict, level: int) -> dict:
    out: dict = {"name": u.get("name") or ""}
    if level <= 2 and u.get("unit_type"):
        out["unit_type"] = u["unit_type"]
    events = u.get("events") or []
    if level <= 2 or events:
        out["events"] = [_compact_event(e, level) for e in events]
    return out


def _compact_object(o: dict, level: int) -> dict:
    out: dict = {"name": o.get("name") or ""}
    if level <= 2 and o.get("category"):
        out["category"] = o["category"]
    out["units"] = [_compact_unit(u, level) for u in (o.get("units") or [])]
    out["events"] = [_compact_event(e, level) for e in (o.get("events") or [])]
    return out


def _compact_zone(z: dict, level: int) -> dict:
    return {
        "name": z.get("name") or "",
        "objects": [_compact_object(o, level) for o in (z.get("objects") or [])],
    }


def _dumps_tree(tree) -> str:
    return json.dumps(tree, ensure_ascii=False, separators=(",", ":"))


def serialize_existing_tree(
    zones: list[dict], max_chars: int = SMART_GUIDE_TREE_MAX_CHARS
) -> tuple[str, bool]:
    """把现有风险树序列化为紧凑 JSON 文本；超长时逐级降级，仍超则截断分区。

    逐级降级：L1 措施带描述（截 60 字）→ L2 措施只留数量 → L3 仅结构骨架。
    返回 (text, truncated)：truncated=True 表示未包含全部分区。
    """
    for level in (1, 2, 3):
        text = _dumps_tree([_compact_zone(z, level) for z in zones])
        if len(text) <= max_chars:
            return text, False
    kept: list[dict] = []
    for z in zones:
        trial = kept + [_compact_zone(z, 3)]
        if len(_dumps_tree(trial)) > max_chars:
            break
        kept = trial
    return _dumps_tree(kept), True
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_smart_guide_import.py -v -k serialize`
预期：4 passed

- [ ] **步骤 5：Commit**

```bash
git commit -m "feat(risk): 智能导引现有树紧凑序列化（逐级降级+超长截断）" -- backend/app/services/risk_ai_service.py backend/tests/test_smart_guide_import.py
```

---

## 任务 2：后端 · 企业信息构造（`build_smart_guide_enterprise_info`）

**文件：**
- 修改：`backend/app/services/risk_ai_service.py`
- 测试：`backend/tests/test_smart_guide_import.py`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_smart_guide_import.py` 追加：

```python
def test_build_smart_guide_enterprise_info_filters_empty_and_merges_ledger():
    from types import SimpleNamespace

    ent = SimpleNamespace(
        name="测试企业", industry="加油站", business_scope=None, address="XX路1号",
        employee_count=None, building_overview="", main_products="汽油、柴油",
        annual_capacity=None, hazardous_chemicals="汽油", special_equipment=None,
        special_equipment_detail=None, main_equipment_list="1号储罐、2号储罐",
        natural_conditions=None, fire_protection_summary="消防栓8个",
        surrounding_info={"nearby_units": [], "sensitive_targets": [],
                          "traffic_info": "东侧国道"},
    )
    info = build_smart_guide_enterprise_info(
        ent, [{"name": "汽油", "cas_no": "86290-81-5", "location": "罐区"}]
    )
    assert info["name"] == "测试企业"
    assert info["address"] == "XX路1号"
    assert info["main_products"] == "汽油、柴油"
    assert info["main_equipment_list"] == "1号储罐、2号储罐"
    assert info["fire_protection_summary"] == "消防栓8个"
    assert info["surrounding_info"]["traffic_info"] == "东侧国道"
    assert info["chemicals_ledger"][0]["name"] == "汽油"
    for empty_key in ("business_scope", "employee_count", "annual_capacity",
                      "building_overview", "hazardous_chemicals", "special_equipment",
                      "special_equipment_detail", "natural_conditions"):
        assert empty_key not in info


def test_build_smart_guide_enterprise_info_without_ledger_skips_key():
    from types import SimpleNamespace

    ent = SimpleNamespace(
        name="乙", industry=None, business_scope=None, address=None,
        employee_count=None, building_overview=None, main_products=None,
        annual_capacity=None, hazardous_chemicals=None, special_equipment=None,
        special_equipment_detail=None, main_equipment_list=None,
        natural_conditions=None, fire_protection_summary=None, surrounding_info=None,
    )
    info = build_smart_guide_enterprise_info(ent, [])
    assert info == {"name": "乙"}
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_smart_guide_import.py -v -k enterprise_info`
预期：FAIL（`build_smart_guide_enterprise_info` 未定义）

- [ ] **步骤 3：编写最少实现代码**

在 `backend/app/services/risk_ai_service.py` 添加（`SMART_GUIDE_TREE_MAX_CHARS` 之前）：

（先把测试文件的导入行补上 `build_smart_guide_enterprise_info`：）

```python
from app.services.risk_ai_service import (
    _normalize_smart_guide_hierarchy,
    build_smart_guide_enterprise_info,
    build_existing_tree_dict,
    serialize_existing_tree,
    smart_guide,
)
```

```python
def build_smart_guide_enterprise_info(ent, ledger_rows: list[dict]) -> dict:
    """构造智能导引的企业信息 dict（空值剔除；危化品台账合并为 chemicals_ledger）。

    字段对应 Enterprise 模型：让 AI 结合企业实际情况查漏补缺；
    未填写的一律不注入，避免提示词噪声。
    """
    raw = {
        "name": ent.name,
        "industry": ent.industry,
        "business_scope": ent.business_scope,
        "address": ent.address,
        "employee_count": ent.employee_count,
        "building_overview": ent.building_overview,
        "main_products": ent.main_products,
        "annual_capacity": ent.annual_capacity,
        "hazardous_chemicals": ent.hazardous_chemicals,
        "special_equipment": ent.special_equipment,
        "special_equipment_detail": ent.special_equipment_detail,
        "main_equipment_list": ent.main_equipment_list,
        "natural_conditions": ent.natural_conditions,
        "fire_protection_summary": ent.fire_protection_summary,
        "surrounding_info": ent.surrounding_info,
    }
    info = {k: v for k, v in raw.items() if v not in (None, "", [], {})}
    if ledger_rows:
        info["chemicals_ledger"] = ledger_rows
    return info
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_smart_guide_import.py -v -k enterprise_info`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git commit -m "feat(risk): 智能导引企业信息扩展（设备清单/特种设备/周边/自然条件等，空值剔除）" -- backend/app/services/risk_ai_service.py backend/tests/test_smart_guide_import.py
```

---

## 任务 3：后端 · `smart_guide` prompt 改为查漏补缺

**文件：**
- 修改：`backend/app/services/risk_ai_service.py`（`smart_guide` 函数，约 L294 起）
- 测试：`backend/tests/test_smart_guide_import.py`

- [ ] **步骤 1：改写失败的测试**

把现有 `test_smart_guide_prompt_includes_existing_names` **整体替换**为：

```python
@pytest.mark.asyncio
async def test_smart_guide_prompt_includes_existing_tree():
    captured = {}

    async def fake_llm(messages, ai_config, timeout=120, **kwargs):
        captured["messages"] = messages
        return '{"zones": [], "summary": {}}'

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.risk_ai_service.llm_text_completion",
            fake_llm,
        )
        await smart_guide(
            "储罐区要补充泄漏事件",
            {"name": "测试企业"},
            ai_config=object(),
            existing_tree_text='[{"name":"储罐区","objects":[{"name":"1号储罐","units":[]}]}]',
        )

    prompt = captured["messages"][-1]["content"]
    assert "储罐区" in prompt
    assert "1号储罐" in prompt
    assert "查漏补缺" in prompt
    assert "不得生成与现有分区" not in prompt


@pytest.mark.asyncio
async def test_smart_guide_prompt_handles_empty_description_and_extended_fields():
    captured = {}

    async def fake_llm(messages, ai_config, timeout=120, **kwargs):
        captured["messages"] = messages
        return '{"zones": [], "summary": {}}'

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.risk_ai_service.llm_text_completion",
            fake_llm,
        )
        await smart_guide(
            "",
            {"name": "甲", "main_equipment_list": "1号储罐、2号储罐",
             "surrounding_info": {"traffic_info": "东侧国道"}},
            ai_config=object(),
        )

    prompt = captured["messages"][-1]["content"]
    assert "未填写补充说明" in prompt
    assert "1号储罐、2号储罐" in prompt
    assert "东侧国道" in prompt
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_smart_guide_import.py -v -k "existing_tree or empty_description"`
预期：FAIL（`smart_guide() got an unexpected keyword argument 'existing_tree_text'`）

- [ ] **步骤 3：改写实现**

重写 `backend/app/services/risk_ai_service.py` 中的 `smart_guide`（**整函数替换**）：

```python
async def smart_guide(
    description: str,
    enterprise_info: dict,
    ai_config: AIConfig,
    existing_tree_text: str = "",
    tree_truncated: bool = False,
) -> dict:
    """一键智能导引：企业档案 + 现有树 + 用户补充 → 查漏补缺的完整层级结构。

    Args:
        description: 用户自然语言补充说明（可为空；为空时仅依据档案与现有树分析）
        enterprise_info: 企业基本信息（见 build_smart_guide_enterprise_info）
        ai_config: AI 配置
        existing_tree_text: serialize_existing_tree 输出的紧凑 JSON（空串=尚未建树）
        tree_truncated: 现有树文本是否因过大被截断

    Returns:
        dict 含 zones 和 summary 字段；zones 中同名节点在导入时自动并入现有树。
    """
    description_text = (description or "").strip() or (
        "（用户未填写补充说明，请仅依据企业档案与现有风险树分析）"
    )
    tree_text = existing_tree_text or "[]"
    tree_note = ""
    if tree_truncated:
        tree_note = "\n（注意：现有树过大，以上仅展示部分内容；未展示部分不要臆断其缺失或存在。）"
    prompt = (
        f"请对企业风险分级管控层级结构进行「查漏补缺」，并补充用户新提到的内容。\n\n"
        f"用户补充说明：\n{description_text}\n\n"
        f"企业基本情况：\n{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}\n\n"
        f"企业现有风险分级管控树（JSON，供你查漏补缺）：\n{tree_text}{tree_note}\n\n"
        "要求：\n"
        "1. 你的输出将与现有树合并：同名分区/对象/单元自动并入现有节点，只在其下补充缺失内容；"
        "输出路径中的已有节点名称必须与现有树完全一致（用于合并匹配）\n"
        "2. 对照现有树查漏补缺：已有分区缺分析对象的补对象；已有对象缺单元/风险事件的补单元/事件；"
        "已有单元缺事件的补事件；已有事件缺管控措施的补措施（措施按类别与描述去重）\n"
        "3. 不得重复已有事件（同一父节点下相同事故类型）与已有措施\n"
        "4. 用户补充说明中提到的新内容，正常生成新分区/对象\n"
        "5. 不要改写已有节点的描述与等级（合并时只取你的补充部分）\n"
        "6. 每个事件使用 LS 矩阵法评估（L: 1-5, S: 1-5），含 risk_level 和 risk_score\n"
        "7. 每事件至少 2 条管控措施\n"
        "8. 最多覆盖 8 个分区；对象（含作为路径的已有对象）合计不超过 80 个，"
        "优先覆盖最重要的缺口\n"
        "9. 同一区域内多个同类设备用编号区分命名（如「1号储罐」「2号储罐」），避免对象名重复\n"
        "10. 所有对象 is_risk_point 一律输出 false（风险点由用户在画布上手动标记）\n\n"
        '输出 JSON 格式（完整层级）：\n'
        '{"zones": [{"name": "...", "description": "...", '
        '"objects": [{"name": "...", "category": "...", '
        '"is_risk_point": false, "units": [{"name": "...", '
        '"unit_type": "...", "events": [{"accident_type": "...", '
        '"risk_level": "重大|较大|一般|低", "risk_score": "R=XX", '
        '"method_type": "LS", "method_params": {"l": X, "s": X}, '
        '"measures": [{"measure_category": "engineering|management|ppe|emergency", '
        '"description": "...", '
        '"check_items": [{"name": "...", "standard": "...", "frequency": "..."}]}]}]}]}]}]}\n'
        "只输出 JSON，不要任何解释。"
    )

    messages = [
        {
            "role": "system",
            "content": "你是注册安全工程师，精通风险分级管控和 GB/T 29639 标准。输出严格 JSON。",
        },
        {"role": "user", "content": prompt},
    ]

    raw = await llm_text_completion(messages, ai_config, timeout=60, module="risk")
    data = _parse_ai_json(raw)
    return _normalize_smart_guide_hierarchy(data)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_smart_guide_import.py tests/test_smart_guide_summary_shape.py -v`
预期：全通过（含旧 normalize 用例）

- [ ] **步骤 5：Commit**

```bash
git commit -m "feat(risk): smart-guide prompt 改查漏补缺（企业档案+现有树+补充说明三段输入）" -- backend/app/services/risk_ai_service.py backend/tests/test_smart_guide_import.py
```

---

## 任务 4：后端 · 路由接线 + schema 默认空串

**文件：**
- 修改：`backend/app/routers/risk_management.py`（`ai_smart_guide` 端点，约 L1291-1330）
- 修改：`backend/app/schemas/risk_management.py`（`SmartGuideRequest`，L345）
- 测试：`backend/tests/test_smart_guide_import.py`、`backend/tests/test_smart_guide_summary_shape.py`

- [ ] **步骤 1：编写失败的测试**

`backend/tests/test_smart_guide_import.py` 追加（`build_existing_tree_dict` 已随任务 1 导入）：

```python
def test_build_existing_tree_dict_compact_shape():
    from types import SimpleNamespace as NS

    zones = [NS(name="储罐区", objects=[NS(
        name="1号储罐", category="储罐",
        units=[NS(name="罐体", unit_type="设备", events=[NS(
            accident_type="泄漏",
            measures=[NS(measure_category="engineering", description="设置液位监控报警")],
        )])],
        events=[],
    )])]
    assert build_existing_tree_dict(zones) == [{
        "name": "储罐区",
        "objects": [{
            "name": "1号储罐",
            "category": "储罐",
            "units": [{
                "name": "罐体",
                "unit_type": "设备",
                "events": [{
                    "accident_type": "泄漏",
                    "measures": [{"measure_category": "engineering",
                                  "description": "设置液位监控报警"}],
                }],
            }],
            "events": [],
        }],
    }]
```

`backend/tests/test_smart_guide_summary_shape.py` 追加：

```python
def test_smart_guide_route_wires_completion_inputs():
    """源码守护：smart-guide 路由必须接线「完整树序列化 + 企业信息构造」。"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "risk_management.py").read_text(
        encoding="utf-8"
    )
    assert "existing_tree = build_existing_tree_dict(" in src
    assert "tree_text, tree_truncated = serialize_existing_tree(" in src
    assert "build_smart_guide_enterprise_info(" in src
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_smart_guide_import.py tests/test_smart_guide_summary_shape.py -v -k "compact_shape or wires_completion"`
预期：FAIL（守护测试断言路由未接线）

- [ ] **步骤 3：修改实现**

3a. `backend/app/schemas/risk_management.py` L345：

```python
class SmartGuideRequest(BaseModel): description: str = ""
```

3b. `backend/app/routers/risk_management.py` 顶部导入行（L18）追加三个符号：

```python
from app.services.risk_ai_service import (_get_ai_config, suggest_objects, suggest_events, suggest_measures, smart_guide, analyze_floor_plan, migrate_preview, build_smart_guide_enterprise_info, serialize_existing_tree, build_existing_tree_dict)
```

3c. `ai_smart_guide` 端点（L1291 起）**整段替换**为：

```python
@router.post("/ai/smart-guide", response_model=ApiResponse[SmartGuideResponse])
async def ai_smart_guide(body: SmartGuideRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    # 危化品交叉校验（D-2）：档案文本是台账的派生摘要，但历史数据可能不同步，
    # 这里把台账品种一并喂给 AI，避免"风险 AI 只看文本、台账 AI 只看台账"。
    ledger_rows = (await db.execute(
        select(HazardousChemical.name, HazardousChemical.cas_no, HazardousChemical.location)
        .where(HazardousChemical.enterprise_id == enterprise_id)
        .order_by(HazardousChemical.name)
    )).all()
    info = build_smart_guide_enterprise_info(
        ent,
        [{"name": r[0], "cas_no": r[1], "location": r[2]} for r in ledger_rows],
    )
    # 现有树完整层级（与 get_hierarchy 相同加载链）：供 AI 查漏补缺。
    # 超长时 serialize_existing_tree 逐级降级/截断，避免撑爆提示词。
    zone_models = (await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == enterprise_id)
        .options(
            selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures),
            selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures),
        )
        .order_by(RiskZone.sort_order)
    )).scalars().all()
    existing_tree = build_existing_tree_dict(zone_models)
    tree_text, tree_truncated = serialize_existing_tree(existing_tree)
    await release_request_connection(db)  # 长耗时 AI 调用前把连接还池，避免 idle in transaction 占满池（压测 N-32）
    result = await smart_guide(body.description, info, ai_config,
                               existing_tree_text=tree_text, tree_truncated=tree_truncated)
    # 容错：模型把 summary 写成自然语言或数字都很常见，原样塞进 SmartGuideResponse 会抛
    # Pydantic 校验错 → 没有任何提示的 500（2026-09-19 mock 实测命中），交给归一函数处理。
    from app.services.risk_ai_service import normalize_smart_guide_summary

    summary = normalize_smart_guide_summary(result.get("summary"))
    zones = result.get("zones")
    if not isinstance(zones, list):
        logger.warning("smart-guide 返回的 zones 不是列表（%s），按空处理", type(zones).__name__)
        zones = []
    try:
        data = SmartGuideResponse(hierarchy=zones, summary=summary)
    except Exception:
        logger.exception("smart-guide 返回结构无法映射为 SmartGuideResponse")
        raise HTTPException(500, "AI 返回格式异常，请稍后重试")
    return ApiResponse(data=data)
```

注意：原实现里 `await _get_ent(...)` 被调用两次（一次丢弃结果、一次赋值 `ent`），替换后只调用一次；`RiskZone/RiskObject/RiskUnit/RiskEvent` 已在本文件导入（`get_hierarchy` 在用），无需新增。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_smart_guide_import.py tests/test_smart_guide_summary_shape.py -v`
预期：全通过

- [ ] **步骤 5：Commit**

```bash
git commit -m "feat(risk): smart-guide 路由接线——完整现有树+扩展档案注入，description 允许空" -- backend/app/routers/risk_management.py backend/app/schemas/risk_management.py backend/tests/test_smart_guide_import.py backend/tests/test_smart_guide_summary_shape.py
```

---

## 任务 5：前端 · `buildMergeBadges`

**文件：**
- 修改：`frontend/src/utils/smartGuideImport.ts`
- 测试：`frontend/src/utils/smartGuideImport.test.ts`

- [ ] **步骤 1：编写失败的测试**

`frontend/src/utils/smartGuideImport.test.ts` 的 import 行改为：

```ts
import { buildExistingIndex, buildImportPlan, buildMergeBadges } from "./smartGuideImport";
```

并在文件末尾追加：

```ts
const existingForBadges: HierarchyZone[] = [
  {
    id: "z1", name: "储罐区", description: null,
    objects: [
      {
        id: "o1", name: "1号储罐", category: null, is_risk_point: false,
        units: [
          {
            id: "u1", name: "罐体", unit_type: null,
            events: [
              {
                id: "ev1", accident_type: "泄漏", description: null, risk_level: null,
                risk_score: null, method_type: "LS", chemical_id: null,
                method_params: {}, measures: [],
              },
            ],
          },
        ],
        events: [],
      },
    ],
  },
];

describe("buildMergeBadges", () => {
  it("已有节点标 merge、新节点标 new（含补单元/补事件/新增对象）", () => {
    const index = buildExistingIndex(existingForBadges);
    const hierarchy: SmartGuideZone[] = [
      {
        name: "储罐区",
        objects: [
          {
            name: "1号储罐",
            units: [
              { name: "罐体", events: [{ accident_type: "泄漏" }, { accident_type: "中毒" }] },
              { name: "阀门组", events: [] },
            ],
          },
          { name: "2号储罐", units: [{ name: "罐体", events: [] }] },
        ],
      },
    ];
    const badges = buildMergeBadges(index, hierarchy, {});
    expect(badges.get("z-0")).toBe("merge");
    expect(badges.get("z-0-o-0")).toBe("merge");
    expect(badges.get("z-0-o-0-u-0")).toBe("merge");
    expect(badges.get("z-0-o-0-u-0-ev-0")).toBe("merge");
    expect(badges.get("z-0-o-0-u-0-ev-1")).toBe("new");
    expect(badges.get("z-0-o-0-u-1")).toBe("new");
    expect(badges.get("z-0-o-1")).toBe("new");
    expect(badges.get("z-0-o-1-u-0")).toBe("new");
  });

  it("对象级事件按父对象判定；改名 override 参与匹配", () => {
    const index = buildExistingIndex(existingForBadges);
    const hierarchy: SmartGuideZone[] = [
      { name: "储罐区", objects: [{ name: "1号罐", events: [{ accident_type: "泄漏" }] }] },
    ];
    const renamed = buildMergeBadges(index, hierarchy, { "z-0": "储罐区", "z-0-o-0": "1号储罐" });
    expect(renamed.get("z-0")).toBe("merge");
    expect(renamed.get("z-0-o-0")).toBe("merge");
    expect(renamed.get("z-0-o-0-ev-0")).toBe("merge");

    const withoutOverride = buildMergeBadges(index, hierarchy, {});
    expect(withoutOverride.get("z-0")).toBe("new");
  });

  it("全新分区其下全部为 new", () => {
    const index = buildExistingIndex(existingForBadges);
    const hierarchy: SmartGuideZone[] = [
      { name: "锅炉房", objects: [{ name: "1号锅炉", units: [{ name: "炉体", events: [{ accident_type: "爆炸" }] }] }] },
    ];
    const badges = buildMergeBadges(index, hierarchy, {});
    expect(badges.get("z-0")).toBe("new");
    expect(badges.get("z-0-o-0")).toBe("new");
    expect(badges.get("z-0-o-0-u-0")).toBe("new");
    expect(badges.get("z-0-o-0-u-0-ev-0")).toBe("new");
  });
});
```

（第二例说明：现有树无对象级事件，「1号罐」经 override 命中现有「1号储罐」→ 对象级事件「泄漏」在 o1 下不存在但 o1 无对象级事件，判为 new。）

- [ ] **步骤 2：运行测试验证失败**

运行：`cd frontend; npx vitest run src/utils/smartGuideImport.test.ts`
预期：FAIL（`buildMergeBadges is not a function / not exported`）

- [ ] **步骤 3：编写最少实现代码**

在 `frontend/src/utils/smartGuideImport.ts` 末尾追加：

```ts
export type MergeBadge = "new" | "merge";

/**
 * 预判 AI 生成树各节点导入时是「并入现有」还是「新增」。
 * key 体系与预览树一致（z-{zi} / {parent}-o-{oi} / {parent}-u-{ui} / {parent}-ev-{ei}）；
 * 判定与 RiskSmartGuideModal.importMut 的合并逻辑一一对应；父节点新增时子节点必为 new。
 */
export function buildMergeBadges(
  index: ExistingIndex,
  hierarchy: SmartGuideZone[],
  nameOverrides: Record<string, string> = {},
): Map<string, MergeBadge> {
  const badges = new Map<string, MergeBadge>();
  hierarchy.forEach((zone, zi) => {
    const zoneKey = `z-${zi}`;
    const zoneName = nameOverrides[zoneKey] ?? zone.name;
    const zoneId = index.zones.get(zoneName);
    badges.set(zoneKey, zoneId ? "merge" : "new");

    (zone.objects || []).forEach((obj, oi) => {
      const objKey = `${zoneKey}-o-${oi}`;
      const objName = nameOverrides[objKey] ?? obj.name;
      const objId = zoneId ? index.objects.get(zoneName)?.get(objName) : undefined;
      badges.set(objKey, objId ? "merge" : "new");

      (obj.units || []).forEach((unit, ui) => {
        const unitKey = `${objKey}-u-${ui}`;
        const unitName = nameOverrides[unitKey] ?? unit.name;
        const unitId = objId ? index.units.get(objId)?.get(unitName) : undefined;
        badges.set(unitKey, unitId ? "merge" : "new");

        (unit.events || []).forEach((ev, ei) => {
          const evKey = `${unitKey}-ev-${ei}`;
          const evName = nameOverrides[evKey] ?? ev.accident_type;
          const merged = unitId ? index.eventIds.get(unitId)?.has(evName) ?? false : false;
          badges.set(evKey, merged ? "merge" : "new");
        });
      });

      (obj.events || []).forEach((ev, ei) => {
        const evKey = `${objKey}-ev-${ei}`;
        const evName = nameOverrides[evKey] ?? ev.accident_type;
        const merged = objId ? index.eventIds.get(objId)?.has(evName) ?? false : false;
        badges.set(evKey, merged ? "merge" : "new");
      });
    });
  });
  return badges;
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd frontend; npx vitest run src/utils/smartGuideImport.test.ts`
预期：全部 passed（含旧用例）

- [ ] **步骤 5：Commit**

```bash
git commit -m "feat(risk): 智能导引预览合并预判 buildMergeBadges（新增/并入判定，与导入逻辑一致）" -- frontend/src/utils/smartGuideImport.ts frontend/src/utils/smartGuideImport.test.ts
```

---

## 任务 6：前端 · `RiskSmartGuideModal` 接线

**文件：**
- 修改：`frontend/src/components/enterprise/RiskSmartGuideModal.tsx`

- [ ] **步骤 1：导入与 state**

原 `import { buildExistingIndex } from "@/utils/smartGuideImport";` 替换为：

```ts
import { buildExistingIndex, buildMergeBadges } from "@/utils/smartGuideImport";
import type { ExistingIndex, MergeBadge } from "@/utils/smartGuideImport";
```

antd 导入行补上 `Tag`（原行为 `import { App as AntApp, Modal, Input, Button, Tree, Alert, Spin } from "antd";`）：

```ts
import { App as AntApp, Modal, Input, Button, Tree, Alert, Spin, Tag } from "antd";
```

组件内 state 区（`nameOverrides` 之后）追加：

```ts
const [existingIndex, setExistingIndex] = useState<ExistingIndex | null>(null);
```

打开重置块（`if (open) { ... }`）追加：`setExistingIndex(null);`

- [ ] **步骤 2：guideMut 并行拉取现有树、描述可选**

替换 `guideMut` 为：

```ts
const guideMut = useMutation({
  mutationFn: async () => {
    const [guideRes, treeRes] = await Promise.allSettled([
      aiSmartGuide(enterpriseId, description),
      getFullHierarchy(enterpriseId),
    ]);
    if (guideRes.status === "rejected") throw guideRes.reason;
    return {
      data: guideRes.value,
      index: treeRes.status === "fulfilled" ? buildExistingIndex(treeRes.value) : null,
    };
  },
  onSuccess: ({ data, index }) => {
    setHierarchy(data.hierarchy);
    setExistingIndex(index);
    const allKeys = collectAllKeys(data.hierarchy);
    setCheckedKeys(allKeys);
    setExpandedKeys(allKeys.filter((k) => String(k).startsWith("z-") && String(k).split("-").length === 2));
    setStep("preview");
  },
  onError: (e: Error) => {
    antMessage.error("AI 分析失败: " + (e?.message || "请重试"));
    setStep("input");
  },
});
```

替换 `handleStartAnalysis`（去掉必填拦截）：

```ts
const handleStartAnalysis = () => {
  setStep("loading");
  guideMut.mutate();
};
```

- [ ] **步骤 3：badges 与汇总统计**

在 `const counts = useMemo(...)` 之前追加：

```ts
const badges = useMemo<Map<string, MergeBadge>>(
  () =>
    existingIndex
      ? buildMergeBadges(existingIndex, hierarchy, nameOverrides)
      : new Map<string, MergeBadge>(),
  [existingIndex, hierarchy, nameOverrides],
);

const badgeSummary = useMemo(() => {
  const keySet = new Set(checkedKeys.map(String));
  let fresh = 0;
  let merge = 0;
  badges.forEach((badge, key) => {
    if (!keySet.has(key)) return;
    if (badge === "merge") merge++;
    else fresh++;
  });
  return { fresh, merge };
}, [badges, checkedKeys]);
```

- [ ] **步骤 4：titleRender 显示标签**

`titleRender` 中显示名字的 `<span>`（`{displayName}</span>`）之后插入：

```tsx
{badges.get(key) === "new" && (
  <Tag color="green" style={{ margin: 0, fontSize: 11, lineHeight: "16px", flexShrink: 0 }}>
    {"新增"}
  </Tag>
)}
{badges.get(key) === "merge" && (
  <Tag color="blue" style={{ margin: 0, fontSize: 11, lineHeight: "16px", flexShrink: 0 }}>
    {"并入"}
  </Tag>
)}
```

`titleRender` 的 useCallback 依赖数组追加 `badges`。

- [ ] **步骤 5：文案更新**

输入步骤标题与提示替换为：

```tsx
<div style={{ marginBottom: 8, fontWeight: 500 }}>
  {"请描述需要 AI 分析的区域情况（可选）"}
</div>
```

```tsx
<span>
  {"可不填：留空时 AI 将依据企业档案与现有风险树自动查漏补缺；填写设备、工艺、物料、周边等补充说明可让结果更准确。支持中文自然语言输入。"}
</span>
```

预览 Alert 替换为：

```tsx
<Alert
  type="warning"
  showIcon
  title="AI 已按企业档案与现有风险树查漏补缺；同名节点并入现有树（只补充缺失内容，不改写已有描述/等级），新增节点单独创建。请核实后确认导入"
  style={{ marginBottom: 12 }}
/>
```

loading 文案替换为：`{"AI 正在结合企业档案与现有风险树查漏补缺…"}`

底部汇总行（`选中汇总：` span 之后）追加：

```tsx
<span style={{ marginLeft: 12 }}>
  {`将新增 ${badgeSummary.fresh} · 并入 ${badgeSummary.merge}`}
</span>
```

- [ ] **步骤 6：验证**

运行：`cd frontend; npx tsc -b --force`
预期：0 错误

运行：`cd frontend; npx vitest run src/utils/smartGuideImport.test.ts`
预期：全通过

运行：`cd frontend; npx eslint src/components/enterprise/RiskSmartGuideModal.tsx src/utils/smartGuideImport.ts`
预期：0 警告 0 错误

- [ ] **步骤 7：Commit**

```bash
git commit -m "feat(risk): 智能导引弹窗接线——描述可选、并行拉现有树、新增/并入标签与汇总" -- frontend/src/components/enterprise/RiskSmartGuideModal.tsx frontend/src/utils/smartGuideImport.ts frontend/src/utils/smartGuideImport.test.ts
```

---

## 任务 7：全量门禁

- [ ] **步骤 1：后端全量测试**

运行：`cd backend; python -m pytest -q`
预期：≥2205 passed / 1 skipped（基线），无 failed。

- [ ] **步骤 2：前端全量测试与构建**

运行：`cd frontend; npx tsc -b --force; npx vitest run; npx eslint src; npm run build`
预期：全部通过（若失败先甄别是否另一会话的半成品改动导致：`RiskManagementTab.tsx` / `RiskHierarchyTree.tsx` / `RiskTreeFourColorMap.tsx`；本任务范围内的问题才修）。

- [ ] **步骤 3：同步图谱**

```bash
codegraph sync .
graphify update .
```

（`python graphify-out/_finalize_graph.py` 本机不存在（见 TASKS.md）；若本机无 graphify 命令则记录后跳过。）

---

## 任务 8：浏览器实测（8082）

- [ ] **步骤 1：部署候选构建**

前端：`cd frontend; npm run build` 后按既有流程同步 `dist` 到 `shuzihuayuan:/app/dist`（先备份旧版 `/app/dist.bak.<日期>`）；后端为 bind mount，重启容器加载新代码。

- [ ] **步骤 2：编写探针脚本**

新建 `output/playwright/e2e-20261013/scripts/_smart_guide_completion_probe.py`（参照 `_major_hazard_ledger_prefill_probe.py` 的
`E2E_API=http://localhost:8000/api/v1`、`E2E_BASE=http://localhost:8082`、qa 账号模式）：

1. 造企业：通过 API 创建分区「储罐区」+ 对象「1号储罐」（无单元/事件）→ 制造"缺下级"缺口；
2. UI 打开智能导引：
   - 场景 A：描述留空 → 点分析 → 断言生成结果中出现「储罐区」路径与补全的事件/措施；
   - 场景 B：填描述"储罐区有 2 个汽油储罐" → 再次分析 → 断言描述内容被利用；
3. 断言预览出现「新增/并入」标签、汇总行含"将新增/并入"文案；
4. 导入后 API 回读：已有对象下出现事件/措施，且原分区/对象描述与 ID 未变；
5. 输出 `smart-guide-completion.json`（含各断言与响应快照）与 2 张截图；断言"0 console error"。

若 8082 环境未配置可用 AI 供应商（探针返回"系统未配置 AI 模型"），先在系统设置配置 mock/真实供应商再跑；
把实际操作路径记录到 JSON 证据里。

- [ ] **步骤 3：运行探针**

运行：`python output/playwright/e2e-20261013/scripts/_smart_guide_completion_probe.py`
预期：全部断言通过；证据落盘同目录。

- [ ] **步骤 4：Commit 证据**

```bash
git commit -m "test(probe): 智能导引补全现有树浏览器实测证据" -- output/playwright/e2e-20261013
```

---

## 任务 9：收尾

- [ ] **步骤 1：更新 TASKS.md 快照**（本次任务状态、commit 列表、证据路径、下一步）
- [ ] **步骤 2：确认提交分组**（按路径精确提交；工作区内其它会话文件（`RiskManagementTab` 等）不得混入本任务提交）
- [ ] **步骤 3：推送决策**（推送与否由用户拍板，与其它未推送提交的压缩策略一并说明）
