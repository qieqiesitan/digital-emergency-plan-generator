# 作业票智能预填 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [x]`）语法来跟踪进度。

> **状态：✅ 全部完成（2026-09-20，内联执行，9 个任务）。**
> 任务 9 的浏览器实测已完成：**7/7 通过**（8 票种均可进入、票面字段渲染、来源徽标可见、
> **动火票措施 = 16 条**、列表页「新建作业包」入口、0 console error），证据
> `output/playwright/e2e-20260920/scripts/work-ticket-prefill-browser.json` + 措施页截图。
> 配套 29 路由桌面冒烟：0 pageerror / 0 5xx。改造前后的"交互动作计数对比"未做
> （改用"8 票种可达 + 字段/措施渲染 + 来源徽标"作为等价证据，计数探针留待需要量化时再补）。
> **浏览器实测抓到一个真实崩溃并已修**：预填把 ISO 字符串直接塞给 antd DatePicker，
> 渲染时抛 `isValid is not a function` 导致票面步骤白屏；已加 `toFormValues()`
> 做反向转换并补单测（`formValues.ts` / `formValues.test.ts`），修复后 0 console error。
> 已完成：三列迁移+门禁、措施建议引擎、确定性预填、AI 预填服务、五个端点、前端向导改造、成员证照。
> 证据：后端全量 `2148 passed, 1 skipped`；前端 `tsc -b` 0 / `vitest 314 passed` / `eslint 0` / `build OK`；
> 端到端探针 **11/11**（企业档案带出、级别联动、16 条措施建议、无情景时保守 unknown、明确"不在罐区"→第 4 条不涉及）。
> 任务 9 未做部分（下一轮补）：改造前后的交互动作计数对比、真实浏览器 8 票种实测、8082 同步后 37 页冒烟。
> 执行中的偏离：① 前端测试环境无 @testing-library，改用项目既有的 `renderToStaticMarkup`，
> 并把措施分组/三态变更抽成纯函数（`measureMeta.ts`）单独测；② eslint 的 react-refresh 规则要求
> 组件文件只导出组件，故 `SOURCE_LABEL` 与纯函数分别拆到 `fieldSources.ts` / `measureMeta.ts`；
> ③ AI 能力复用既有 `work_ticket_jsa`（真库已注册），未新建能力 code；④ 后端容器无 --reload，验证前需 `docker restart emergency-plan-backend`。

**目标：** 让开票时大部分字段由系统从既有数据（作业对象、历史票、成员台账）与 AI 带出，每个带出值可追溯来源并经人工确认；安全措施从"N 条全打勾"改为"全部表态"，并给出确定性的"建议不涉及"分组。

**架构：** 后端新增一条"预填管道"——纯函数负责来源优先级与措施判定（可单测），服务层负责取数与拼装，端点只做鉴权与信封；AI 走既有 `llm_client` + 能力开关，失败静默降级。前端把 6 步向导改为"带来源徽标的表单 + 三态措施 + 提交前来源摘要"，并补上草稿保存端点。所有自动值写入新列 `values_meta` / `measures_meta`，老票无 meta 一律按人工填写处理。

**技术栈：** FastAPI / SQLAlchemy 2.0 async / PostgreSQL 16 / pytest / React 18 + AntD + react-query / vitest

**依据规格：** `docs/superpowers/specs/2026-09-20-work-ticket-smart-prefill-design.md`

**前置：** 计划 1（`2026-09-20-work-ticket-measure-fix.md`）必须先完成——措施条数正确是措施三态的前提。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/db_migration_20260920_work_ticket_prefill.sql`（创建） | 三个新列：实例两列 meta、成员证照列 |
| `backend/app/models/work_ticket.py`（修改） | `WorkTicketInstance.values_meta` / `measures_meta` |
| `backend/app/models/enterprise_org.py`（修改） | `EnterpriseMember.certificates` |
| `backend/app/services/work_ticket_measure_rules.py`（创建） | 措施"是否涉及"建议引擎：条件表 + 纯函数 |
| `backend/app/services/work_ticket_prefill.py`（创建） | 确定性预填：来源优先级、槽位取值、payload 拼装 |
| `backend/app/services/work_ticket_ai_service.py`（创建） | AI 预填（风险辨识 / JSA / 措施建议），失败降级 |
| `backend/app/services/work_ticket_service.py`（修改） | `validate_before_submit` 增加 AI 未确认阻断 |
| `backend/app/routers/work_ticket.py`（修改） | 5 个新端点 + templates 透出 `allow_ai_prefill` |
| `backend/app/schemas/work_ticket.py`（修改） | 预填/草稿保存/AI 的出入参 |
| `frontend/src/types/workTicket.ts`（修改） | 类型补齐：`allow_ai_prefill`、`values_meta`、`measures_meta` |
| `frontend/src/services/workTicketService.ts`（修改） | 新端点的调用封装 |
| `frontend/src/components/enterprise/workTicket/PrefillBadge.tsx`（创建） | 来源徽标（含依据 tooltip） |
| `frontend/src/components/enterprise/workTicket/MeasureChecklist.tsx`（创建） | 措施三态列表 + 折叠区 |
| `frontend/src/pages/Enterprise/WorkTicketNewPage.tsx`（修改） | 向导接入预填、级别联动、来源摘要、草稿 |
| `frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`（修改） | 成员证照编辑 |
| `backend/tests/test_work_ticket_prefill.py`（创建） | 来源优先级、槽位、降级 |
| `backend/tests/test_work_ticket_measure_rules.py`（创建） | 规则引擎 |
| `backend/tests/test_work_ticket_meta_gate.py`（创建） | AI 未确认阻断 + 老数据不阻断 |
| `frontend/src/components/enterprise/workTicket/__tests__/`（创建） | 徽标与措施列表单测 |

---

## 任务 1：数据模型与迁移

**文件：**
- 创建：`backend/db_migration_20260920_work_ticket_prefill.sql`
- 修改：`backend/app/models/work_ticket.py`
- 修改：`backend/app/models/enterprise_org.py`
- 测试：`backend/tests/test_work_ticket_meta_gate.py`

- [x] **步骤 1：编写失败的测试**

创建 `backend/tests/test_work_ticket_meta_gate.py`：

```python
"""作业票 values_meta / measures_meta / 成员证照 的模型与门禁。"""


def test_instance_has_meta_columns():
    from app.models.work_ticket import WorkTicketInstance

    cols = WorkTicketInstance.__table__.columns
    assert "values_meta" in cols, "缺少 values_meta 列"
    assert "measures_meta" in cols, "缺少 measures_meta 列"
    assert cols["values_meta"].nullable is False
    assert cols["measures_meta"].nullable is False


def test_member_has_certificates_column():
    from app.models.enterprise_org import EnterpriseMember

    cols = EnterpriseMember.__table__.columns
    assert "certificates" in cols, "缺少 certificates 列"
    assert cols["certificates"].nullable is False
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_meta_gate.py -v`

预期：两个用例 **FAILED**（`缺少 values_meta 列` / `缺少 certificates 列`）。

- [x] **步骤 3：编写最少实现代码**

`backend/app/models/work_ticket.py` 的 `WorkTicketInstance` 中，在 `values` 列之后加入：

```python
    # 每个票面字段的来源留痕（source/source_ref/prefilled_at/confirmed_at/confirmed_by/edited）。
    # 老票该列为 '{}'：一律按人工填写处理，不新增任何提交阻断。
    values_meta: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb")
    )
    # 每条措施的三态（pending/confirmed/not_applicable）与"不适用"理由、操作人、时间。
    measures_meta: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb")
    )
```

`backend/app/models/enterprise_org.py` 的 `EnterpriseMember` 中，在 `position` 之后加入：

```python
    # 特种作业证照：[{"type": "焊接与热切割作业", "no": "T6101…", "valid_to": "2027-05-30"}]
    # 用于开票时自动拼接"动火人及证书编号""电工及证书编号"，避免每次手打。
    certificates: Mapped[list] = mapped_column(
        JSONB, default=list, nullable=False, server_default=text("'[]'::jsonb")
    )
```

`enterprise_org.py` 顶部 import 需要补 `text`：`from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text, func`（`JSONB` 从 `sqlalchemy.dialects.postgresql` 引入，若未引入则补）。

- [x] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_meta_gate.py -v`

预期：两个用例 PASSED。

- [x] **步骤 5：编写迁移 SQL**

创建 `backend/db_migration_20260920_work_ticket_prefill.sql`：

```sql
-- 20260920 作业票智能预填：来源留痕、措施三态、成员证照
-- 三列均为非空 + 默认值，老行自动填充，幂等可重复执行。

ALTER TABLE work_ticket_instances
    ADD COLUMN IF NOT EXISTS values_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE work_ticket_instances
    ADD COLUMN IF NOT EXISTS measures_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE enterprise_members
    ADD COLUMN IF NOT EXISTS certificates JSONB NOT NULL DEFAULT '[]'::jsonb;

-- 核验（执行后手查）：
-- SELECT column_name, is_nullable, column_default FROM information_schema.columns
--  WHERE (table_name='work_ticket_instances' AND column_name IN ('values_meta','measures_meta'))
--     OR (table_name='enterprise_members' AND column_name='certificates');
-- 期望三行、is_nullable=NO、default 分别为 '{}'::jsonb / '{}'::jsonb / '[]'::jsonb
-- SELECT count(*) FROM work_ticket_instances WHERE values_meta IS NULL;  -- 期望 0
```

- [x] **步骤 6：应用迁移并核验**

```powershell
docker cp backend/db_migration_20260920_work_ticket_prefill.sql emergency-plan-db:/tmp/wt_prefill.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 -f /tmp/wt_prefill.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT column_name, is_nullable, column_default FROM information_schema.columns WHERE table_name='work_ticket_instances' AND column_name IN ('values_meta','measures_meta');"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) AS null_meta FROM work_ticket_instances WHERE values_meta IS NULL OR measures_meta IS NULL;"
```

预期：`ALTER TABLE` ×3；核验列为 NO / 默认值正确；`null_meta = 0`。

- [x] **步骤 7：Commit**

```bash
git add backend/db_migration_20260920_work_ticket_prefill.sql backend/app/models/work_ticket.py backend/app/models/enterprise_org.py backend/tests/test_work_ticket_meta_gate.py
git commit -m "feat(work-ticket): 来源留痕/措施三态/成员证照 三列 + 迁移"
```

---

## 任务 2：措施"是否涉及"建议引擎（纯函数）

**文件：**
- 创建：`backend/app/services/work_ticket_measure_rules.py`
- 测试：`backend/tests/test_work_ticket_measure_rules.py`

**范围：** 首批只为**动火票 16 条**建立条件映射（缺陷最重、使用最频繁）；其他票种的措施一律 `unknown`（留在主列表由人工逐条处理）。这是刻意的增量策略：宁可少建议，也不猜。

- [x] **步骤 1：编写失败的测试**

创建 `backend/tests/test_work_ticket_measure_rules.py`：

```python
"""措施"是否涉及"建议引擎：条件三态与保守策略。"""

from app.services.work_ticket_measure_rules import (
    APPLICABLE,
    NOT_APPLICABLE,
    UNKNOWN,
    MeasureContext,
    suggest_measures,
)

_FIRE_MEASURES = [{"sort_order": i} for i in range(1, 17)]


def test_condition_false_yields_not_applicable():
    ctx = MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False})
    out = {row["sort_order"]: row for row in suggest_measures(_FIRE_MEASURES, ctx)}
    assert out[4]["suggest"] == NOT_APPLICABLE
    assert "罐区" in out[4]["reason"]


def test_condition_true_yields_applicable():
    ctx = MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": True})
    out = {row["sort_order"]: row for row in suggest_measures(_FIRE_MEASURES, ctx)}
    assert out[4]["suggest"] == APPLICABLE


def test_missing_condition_yields_unknown():
    """条件是 None（未确定）时必须 unknown —— 不允许把"不知道"当成"不涉及"。"""
    ctx = MeasureContext(ticket_type="DHZY", conditions={})
    out = {row["sort_order"]: row for row in suggest_measures(_FIRE_MEASURES, ctx)}
    assert out[4]["suggest"] == UNKNOWN
    assert out[4]["reason"] == "现场条件未确定"


def test_true_beats_none_for_composite_condition():
    """复合条件里只要有一个为真，结论就是"涉及"，不受其他未知影响。"""
    ctx = MeasureContext(ticket_type="DHZY", conditions={"gas_welding": True})
    out = {row["sort_order"]: row for row in suggest_measures(_FIRE_MEASURES, ctx)}
    assert out[7]["suggest"] == APPLICABLE


def test_measure_without_condition_mapping_is_unknown():
    """第 8 条（现场配备灭火器）无条件依赖，引擎不表态，留人工处理。"""
    ctx = MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False})
    out = {row["sort_order"]: row for row in suggest_measures(_FIRE_MEASURES, ctx)}
    assert out[8]["suggest"] == UNKNOWN
    assert out[8]["reason"] is None


def test_other_ticket_types_stay_unknown():
    ctx = MeasureContext(ticket_type="QZDZ", conditions={"in_tank_area": False})
    out = suggest_measures([{"sort_order": 1}, {"sort_order": 2}], ctx)
    assert {row["suggest"] for row in out} == {UNKNOWN}


def test_accepts_objects_with_sort_order_attribute():
    """既接受 dict，也接受 ORM/TemplateMeasure 对象。"""

    class _M:
        sort_order = 4

    ctx = MeasureContext(ticket_type="DHZY", conditions={"in_tank_area": False})
    assert suggest_measures([_M()], ctx)[0]["suggest"] == NOT_APPLICABLE
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_measure_rules.py -v`

预期：collection error（`ModuleNotFoundError: app.services.work_ticket_measure_rules`）。

- [x] **步骤 3：编写最少实现代码**

创建 `backend/app/services/work_ticket_measure_rules.py`：

```python
"""措施"是否涉及"建议引擎（确定性、纯函数）。

设计要点：
- 只对**已建立条件映射**的措施给建议（首批为动火票 16 条，依据 GB 30871-2022
  附录A 表A.1 第 1~16 条），其余一律 unknown——宁可少建议，也不猜。
- 条件值三态：True / False / None。任一为 None 时不得给出 not_applicable，
  否则就是把"不知道"当成"不涉及"（安全底线）。
- 建议只影响排序与分组，绝不自动写入 measures_meta；落地必须人工点击。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

UNKNOWN = "unknown"
APPLICABLE = "applicable"
NOT_APPLICABLE = "not_applicable"

# 条件键 → 中文说明（用于向用户解释判定依据）
CONDITION_LABELS: dict[str, str] = {
    "internal_work": "本次动火在设备内部",
    "connected_pipeline": "动火设备连接有管线",
    "surroundings_ignition": "动火点周围有孔洞/窨井/地沟/污水井",
    "in_tank_area": "作业点在油气罐区防火堤内",
    "height_work": "本次作业涉及高处作业",
    "has_flammable_lining": "设备内有可燃物构件或防腐内衬",
    "gas_welding": "本次动火使用气焊/气割",
    "electric_welding": "本次动火使用电焊",
    "surrounding_hazardous_ops": "动火点周围有装卸/排放/喷漆等危险作业",
    "has_other_tickets": "本次作业还办理了其他特殊作业票",
}

# (票种, 措施序号) → 该措施成立所依赖的条件键（全部为假才建议"不涉及"）
# 依据：GB 30871-2022 附录A 表A.1（动火安全作业票）第 1~16 条
MEASURE_CONDITIONS: dict[tuple[str, int], tuple[str, ...]] = {
    ("DHZY", 1): ("internal_work",),
    ("DHZY", 2): ("connected_pipeline",),
    ("DHZY", 3): ("surroundings_ignition",),
    ("DHZY", 4): ("in_tank_area",),
    ("DHZY", 5): ("height_work",),
    ("DHZY", 6): ("has_flammable_lining",),
    ("DHZY", 7): ("gas_welding",),
    ("DHZY", 9): ("electric_welding",),
    ("DHZY", 10): ("surrounding_hazardous_ops",),
    ("DHZY", 11): ("surrounding_hazardous_ops",),
    ("DHZY", 12): ("has_other_tickets",),
    ("DHZY", 15): ("has_other_tickets",),
}


@dataclass(frozen=True)
class MeasureContext:
    """判定上下文。conditions 里缺键等价于 None（未确定）。"""

    ticket_type: str
    conditions: Mapping[str, bool | None]


def _order_of(measure: Any) -> int:
    if isinstance(measure, Mapping):
        return int(measure["sort_order"])
    return int(measure.sort_order)


def suggest_measures(
    measures: Sequence[Any], context: MeasureContext
) -> list[dict[str, Any]]:
    """返回每条措施的建议：{sort_order, suggest, reason}。"""
    out: list[dict[str, Any]] = []
    for measure in measures:
        order = _order_of(measure)
        keys = MEASURE_CONDITIONS.get((context.ticket_type, order), ())
        if not keys:
            out.append({"sort_order": order, "suggest": UNKNOWN, "reason": None})
            continue
        values = [context.conditions.get(key) for key in keys]
        if any(value is True for value in values):
            hit = [
                CONDITION_LABELS[key]
                for key, value in zip(keys, values)
                if value is True
            ]
            out.append(
                {"sort_order": order, "suggest": APPLICABLE, "reason": "本票涉及：" + "；".join(hit)}
            )
        elif any(value is None for value in values):
            out.append({"sort_order": order, "suggest": UNKNOWN, "reason": "现场条件未确定"})
        else:
            out.append(
                {
                    "sort_order": order,
                    "suggest": NOT_APPLICABLE,
                    "reason": "本票不涉及：" + "；".join(CONDITION_LABELS[k] for k in keys),
                }
            )
    return out


def conditions_from_scenario(
    *,
    ticket_type: str,
    fire_method: str | None = None,
    zone_name: str | None = None,
    other_ticket_types: Sequence[str] = (),
    scenario: Mapping[str, bool | None] | None = None,
) -> dict[str, bool | None]:
    """把"自动可推断的条件"与"用户勾选的作业情景"合并成条件表。

    自动部分（无法推断时保持 None，绝不猜）：
      - gas_welding / electric_welding：由动火方式文本推断
      - in_tank_area：由作业区域名称推断
      - has_other_tickets：由作业包内其他票种推断
      - height_work：由作业包是否含高处票（GCZY）推断
    """
    conditions: dict[str, bool | None] = dict(scenario or {})
    method = fire_method or ""
    if method:
        conditions["gas_welding"] = any(k in method for k in ("气焊", "气割", "乙炔"))
        conditions["electric_welding"] = any(k in method for k in ("电焊", "电弧"))
    if zone_name:
        conditions["in_tank_area"] = any(k in zone_name for k in ("罐区", "储罐", "油罐"))
    if ticket_type == "DHZY":
        conditions["has_other_tickets"] = len(other_ticket_types) > 0
        conditions["height_work"] = "GCZY" in other_ticket_types
    return conditions
```

- [x] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_measure_rules.py -v`

预期：7 个用例全 PASSED。

- [x] **步骤 5：Commit**

```bash
git add backend/app/services/work_ticket_measure_rules.py backend/tests/test_work_ticket_measure_rules.py
git commit -m "feat(work-ticket): 措施是否涉及建议引擎（动火 16 条条件映射，保守三态）"
```

---

## 任务 3：确定性预填（来源优先级 + 取数服务）

**文件：**
- 创建：`backend/app/services/work_ticket_prefill.py`
- 测试：`backend/tests/test_work_ticket_prefill.py`

- [x] **步骤 1：编写失败的测试**

创建 `backend/tests/test_work_ticket_prefill.py`：

```python
"""确定性预填：来源优先级、空值跳过、meta 正确。"""

from app.services.work_ticket_prefill import build_values, pick_value

_FIELDS = [
    {"field_key": "applicant_unit", "label": "作业申请单位"},
    {"field_key": "work_unit", "label": "作业单位"},
    {"field_key": "apply_time", "label": "作业申请时间"},
    {"field_key": "fire_level", "label": "动火作业级别"},
    {"field_key": "work_content", "label": "作业内容"},
]


def test_applicant_unit_prefers_enterprise_over_history():
    value, source = pick_value(
        "applicant_unit", candidates={"enterprise": "某某化工有限公司", "history": "旧单位"}
    )
    assert (value, source) == ("某某化工有限公司", "enterprise")


def test_work_unit_prefers_history_over_enterprise():
    value, source = pick_value(
        "work_unit", candidates={"enterprise": "某某化工", "history": "维保班组"}
    )
    assert (value, source) == ("维保班组", "history")


def test_blank_candidate_falls_through():
    value, source = pick_value("work_unit", candidates={"enterprise": "", "history": "维保班组"})
    assert (value, source) == ("维保班组", "history")


def test_no_candidate_returns_none():
    assert pick_value("work_unit", candidates={}) == (None, None)


def test_build_values_writes_meta_only_for_prefilled_fields():
    values, meta = build_values(
        _FIELDS,
        candidates={
            "enterprise": "某某化工有限公司",
            "history": "",
            "member": "",
            "risk_object": "",
            "system_default": "2026-09-20T10:00:00+08:00",
            "template_link": "二级",
        },
    )
    assert values["applicant_unit"] == "某某化工有限公司"
    assert values["fire_level"] == "二级"          # 级别由第 0 步联动
    assert values["apply_time"].startswith("2026-09-20")
    assert "work_content" not in values             # 无候选值时不写、不猜
    assert meta["applicant_unit"]["source"] == "enterprise"
    assert meta["fire_level"]["source"] == "template_link"
    assert "work_content" not in meta


def test_build_values_ignores_keys_not_in_template():
    values, meta = build_values(
        [{"field_key": "applicant_unit", "label": "作业申请单位"}],
        candidates={"enterprise": "E", "member": "张三"},
    )
    assert set(values) == {"applicant_unit"}
    assert set(meta) == {"applicant_unit"}


def test_unregistered_field_is_never_prefilled():
    """票种专有字段（作业高度/吊装质量/盲板编号…）不在来源表里 → 一律不预填。"""
    values, meta = build_values(
        [{"field_key": "work_height", "label": "作业高度(m)"}],
        candidates={"history": "12", "member": "张三", "enterprise": "E"},
    )
    assert values == {}
    assert meta == {}
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_prefill.py -v`

预期：collection error（模块不存在）。

- [x] **步骤 3：编写纯函数部分**

创建 `backend/app/services/work_ticket_prefill.py`：

```python
"""作业票确定性预填：字段来源优先级与取数拼装。

来源（按字段各自的优先级，见 FIELD_SOURCES）：
  enterprise      企业档案
  history         同企业同模板的上一张非草稿票
  member          企业成员台账
  risk_object     作业对象（楼层→区域→对象）
  system_default  系统默认（申请时间、默认时长）
  template_link   向导内联动（级别）
  batch           作业包（由计划 3 写入）

硬原则：候选值为空一律跳过，绝不写猜测值。空值字段不进入 values，
因此前端显示为空白由人工填写。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

# 字段 → 来源优先级（左优先）；未登记的字段默认只走 history
FIELD_SOURCES: dict[str, tuple[str, ...]] = {
    "applicant_unit": ("enterprise", "history"),
    "work_unit": ("history", "enterprise"),
    "apply_time": ("system_default", "history"),
    "work_period": ("batch", "history", "system_default"),
    "fire_level": ("template_link", "history"),
    "high_level": ("template_link", "history"),
    "lift_level": ("template_link", "history"),
    "work_leader": ("member", "history"),
    "guardian": ("member", "history"),
    "fire_person": ("member", "history"),
    "electrician": ("member", "history"),
    "lift_commander": ("member", "history"),
    "logout_person": ("history",),
    "fire_location": ("risk_object", "history"),
    "space_location": ("risk_object", "history"),
    "dig_location": ("risk_object", "history"),
    "road_position": ("risk_object", "history"),
    "pipe_position": ("risk_object", "history"),
    "work_content": ("batch", "history"),
    "risk_identification": ("history",),
    "related_tickets": ("batch", "history"),
}

_EMPTY = (None, "", [], {})


def pick_value(field_key: str, *, candidates: Mapping[str, Any]) -> tuple[Any, str | None]:
    """按该字段的来源优先级取第一个非空候选值。"""
    # 未登记的字段一律不预填：票种专有字段（作业高度、吊装质量、盲板编号等）
    # 属于现场事实，宁可留空让人填，也不从历史票搬一个可能错的数字过来。
    for source in FIELD_SOURCES.get(field_key, ()):
        value = candidates.get(source)
        if value not in _EMPTY:
            return value, source
    return None, None


def build_values(
    fields: Sequence[Mapping[str, Any]], *, candidates: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """按模板字段清单产出 (values, values_meta)。

    只处理模板里真实存在的字段；空值字段既不进 values 也不进 meta。
    """
    values: dict[str, Any] = {}
    meta: dict[str, dict[str, Any]] = {}
    for field in fields:
        key = field["field_key"]
        value, source = pick_value(key, candidates=candidates)
        if value is None:
            continue
        values[key] = value
        meta[key] = {"source": source, "source_ref": {}, "edited": False}
    return values, meta
```

- [x] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_prefill.py -v`

预期：6 个用例全 PASSED。

- [x] **步骤 5：实现取数服务**

在同一文件追加（这是把上面纯函数接到真库的薄层）：

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.work_ticket import WorkTicketInstance

DEFAULT_WORK_HOURS = 8
# 现场事实类字段：有历史值时仅作"参考建议"，不直接写入 values（见规格 §2.2 硬原则）
NEVER_INHERIT = {"fire_location", "space_location", "dig_location", "road_position"}


def default_period(now: datetime | None = None) -> list[str]:
    """默认作业时段：申请时间起，8 小时。"""
    start = now or datetime.now(timezone.utc)
    return [start.isoformat(), (start + timedelta(hours=DEFAULT_WORK_HOURS)).isoformat()]


async def _last_ticket(
    db: AsyncSession, *, enterprise_id: str, template_id: str
) -> WorkTicketInstance | None:
    res = await db.execute(
        select(WorkTicketInstance)
        .where(
            WorkTicketInstance.enterprise_id == enterprise_id,
            WorkTicketInstance.template_id == template_id,
            WorkTicketInstance.status != "draft",
        )
        .order_by(WorkTicketInstance.created_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _members(db: AsyncSession, enterprise_id: str) -> list[EnterpriseMember]:
    res = await db.execute(
        select(EnterpriseMember)
        .where(
            EnterpriseMember.enterprise_id == enterprise_id,
            EnterpriseMember.enabled.is_(True),
        )
        .order_by(EnterpriseMember.name)
    )
    return list(res.scalars().all())


async def build_prefill(
    db: AsyncSession,
    *,
    enterprise_id: str,
    template,
    level: str | None = None,
    risk_object_location: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """确定性预填的取数入口。返回 values/values_meta 与页面所需的候选数据。"""
    enterprise = (
        await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))
    ).scalar_one_or_none()
    last = await _last_ticket(
        db, enterprise_id=enterprise_id, template_id=template.id
    )
    members = await _members(db, enterprise_id)
    history_values = dict(last.values or {}) if last else {}
    # 现场事实类字段即使历史里有值也不直接采用
    for key in NEVER_INHERIT:
        history_values.pop(key, None)

    candidates: dict[str, Any] = {
        "enterprise": getattr(enterprise, "name", None),
        "history": None,
        "member": None,
        "risk_object": risk_object_location,
        "system_default": None,
        "template_link": level,
        "batch": None,
    }
    values: dict[str, Any] = {}
    meta: dict[str, dict[str, Any]] = {}
    for field in template.fields:
        key = field.field_key
        candidates["history"] = history_values.get(key)
        candidates["system_default"] = (
            default_period(now) if key == "work_period"
            else (datetime.now(timezone.utc).isoformat() if key == "apply_time" else None)
        )
        candidates["member"] = _member_text(members, key)
        value, source = pick_value(key, candidates=candidates)
        if value is None:
            continue
        values[key] = value
        meta[key] = {"source": source, "source_ref": {}, "edited": False}
    return {
        "values": values,
        "values_meta": meta,
        "last_ticket_id": str(last.id) if last else None,
        "members": [
            {
                "id": str(m.id),
                "name": m.name,
                "position": m.position,
                "certificates": m.certificates or [],
            }
            for m in members
        ],
    }


_POSITION_HINTS: dict[str, tuple[str, ...]] = {
    "work_leader": ("负责人",),
    "guardian": ("监护",),
    "fire_person": ("焊工", "动火"),
    "electrician": ("电工",),
    "lift_commander": ("起重", "指挥"),
}


def _member_text(members: Iterable[EnterpriseMember], field_key: str) -> str | None:
    """按岗位关键词挑一个成员作为建议值；证书号自动拼接（同规格 §2.6）。"""
    hints = _POSITION_HINTS.get(field_key)
    if not hints:
        return None
    for member in members:
        if not member.position or not any(h in member.position for h in hints):
            continue
        cert_no = next(
            (c.get("no") for c in (member.certificates or []) if c.get("no")), None
        )
        return f"{member.name} {cert_no}".strip() if cert_no else member.name
    return None
```

- [x] **步骤 6：运行全部工作票相关测试**

运行：`cd backend; python -m pytest tests/test_work_ticket_prefill.py tests/test_work_ticket_measure_rules.py tests/test_work_ticket_meta_gate.py -v`

预期：全 PASSED。

- [x] **步骤 7：Commit**

```bash
git add backend/app/services/work_ticket_prefill.py backend/tests/test_work_ticket_prefill.py
git commit -m "feat(work-ticket): 确定性预填服务（来源优先级 + 成员证照拼接）"
```

---

## 任务 4：提交门禁（AI 未确认阻断 + 措施"全部表态"）

**文件：**
- 修改：`backend/app/services/work_ticket_service.py:85-135`（`validate_before_submit`）
- 测试：`backend/tests/test_work_ticket_meta_gate.py`（追加）

- [x] **步骤 1：编写失败的测试**

在 `backend/tests/test_work_ticket_meta_gate.py` 追加：

```python
from types import SimpleNamespace

from app.services.work_ticket_service import validate_before_submit


def _template():
    return SimpleNamespace(
        fields=[
            SimpleNamespace(field_key="risk_identification", label="风险辨识结果", is_required=True),
            SimpleNamespace(field_key="work_content", label="作业内容", is_required=True),
        ]
    )


def _measures():
    return [
        SimpleNamespace(sort_order=1, measure_text="措施一", is_mandatory=True),
        SimpleNamespace(sort_order=2, measure_text="措施二", is_mandatory=True),
    ]


def _validate(**overrides):
    base = dict(
        template=_template(),
        values={"risk_identification": "内容", "work_content": "内容"},
        measures=_measures(),
        confirmed_measure_orders=[],
        gas_tests=[],
        requires_gas_test=False,
    )
    base.update(overrides)
    return validate_before_submit(**base)


def test_ai_field_without_confirmation_blocks():
    errors = _validate(values_meta={"risk_identification": {"source": "ai"}})
    assert any("AI 生成内容，尚未经人工确认" in e for e in errors)


def test_ai_field_with_confirmation_passes():
    errors = _validate(
        values_meta={
            "risk_identification": {
                "source": "ai",
                "confirmed_at": "2026-09-20T10:00:00+08:00",
            }
        }
    )
    assert not any("AI 生成内容" in e for e in errors)


def test_missing_values_meta_never_blocks():
    """老票（无 meta）必须完全不受影响。"""
    assert not any("AI 生成内容" in e for e in _validate(values_meta=None))


def test_non_ai_source_without_confirmation_passes():
    errors = _validate(values_meta={"risk_identification": {"source": "history"}})
    assert not any("AI 生成内容" in e for e in errors)


def test_measures_stated_via_meta_are_handled():
    errors = _validate(
        measures_meta={
            "1": {"state": "confirmed"},
            "2": {"state": "not_applicable", "reason_text": "本票不涉及"},
        }
    )
    assert not any("未确认" in e for e in errors)


def test_not_applicable_without_reason_blocks():
    errors = _validate(
        measures_meta={
            "1": {"state": "not_applicable"},
            "2": {"state": "confirmed"},
        }
    )
    assert any("未填写理由" in e for e in errors)


def test_confirmed_orders_still_work_without_meta():
    """老路径（只传 confirmed_measures）必须继续通过。"""
    errors = _validate(confirmed_measure_orders=[1, 2])
    assert not any("未确认" in e for e in errors)
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_meta_gate.py -v`

预期：`test_ai_field_without_confirmation_blocks`、`test_measures_stated_via_meta_are_handled`、`test_not_applicable_without_reason_blocks` **FAILED**（`TypeError: validate_before_submit() got an unexpected keyword argument 'values_meta'` 及断言失败）。

- [x] **步骤 3：编写最少实现代码**

在 `backend/app/services/work_ticket_service.py` 的 `validate_before_submit` 签名中加入两个可选参数（放在 `now` 之前，保持 `now` 是最后一个参数）：

```python
def validate_before_submit(
    *,
    template,
    values: dict,
    measures: Sequence,
    confirmed_measure_orders: Sequence[int],
    gas_tests: Sequence[dict],
    requires_gas_test: bool,
    values_meta: Optional[dict] = None,
    measures_meta: Optional[dict] = None,
    now: Optional[datetime] = None,
) -> list[str]:
```

在必填字段循环**之后**插入 AI 确认门禁：

```python
    # AI 生成的值必须逐个人工确认（规格 §2.3）。只针对 source=ai，
    # 其他来源与无 meta 的老票一律不新增阻断。
    for field in getattr(template, "fields", []) or []:
        if not getattr(field, "is_required", False):
            continue
        meta = (values_meta or {}).get(field.field_key) or {}
        if meta.get("source") == "ai" and not meta.get("confirmed_at"):
            errors.append(
                f"「{getattr(field, 'label', field.field_key)}」为 AI 生成内容，尚未经人工确认"
            )
```

把措施缺失校验替换为"三态表态"版本（保留原有文案格式）：

```python
    mandatory = [m for m in measures if getattr(m, "is_mandatory", True)]
    # 表态口径：confirmed_measures（老路径）∪ measures_meta 中的 confirmed/not_applicable
    stated = set(confirmed_measure_orders or [])
    for key, meta in (measures_meta or {}).items():
        if not isinstance(meta, dict):
            continue
        if meta.get("state") in ("confirmed", "not_applicable"):
            try:
                stated.add(int(key))
            except (TypeError, ValueError):
                continue
        if meta.get("state") == "not_applicable" and not (meta.get("reason_text") or "").strip():
            errors.append(f"第 {key} 条措施标记为「本票不涉及」，但未填写理由")
    missing = [m for m in mandatory if getattr(m, "sort_order", 0) not in stated]
    if missing:
        errors.append(
            f"还有 {len(missing)} 条安全措施未表态（如「{missing[0].measure_text[:20]}…」）"
        )
```

同时更新 `submit_ticket` 中的调用处，把两个新参数传进去（`backend/app/services/work_ticket_service.py` 约 238-255 行）：

```python
    values = instance.values or {}
    errors = validate_before_submit(
        template=template,
        values=values,
        measures=template.measures,
        confirmed_measure_orders=values.get("confirmed_measures", []),
        gas_tests=gas_tests,
        requires_gas_test=requires_gas_test,
        values_meta=instance.values_meta or {},
        measures_meta=instance.measures_meta or {},
    )
```

- [x] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_meta_gate.py -v`

预期：9 个用例全 PASSED。

- [x] **步骤 5：跑既有作业票测试确认无回归**

运行：`cd backend; python -m pytest tests/ -k work_ticket -v`

预期：全 PASSED。注意 `test_work_ticket_service.py` 里既有的"未确认"断言——若它断言的是旧文案 `还有 N 条安全措施未确认`，需同步改为 `未表态`（这是文案变更，不是行为放宽；把改动理由写进 commit message）。

- [x] **步骤 6：Commit**

```bash
git add backend/app/services/work_ticket_service.py backend/tests/test_work_ticket_meta_gate.py backend/tests/test_work_ticket_service.py
git commit -m "feat(work-ticket): 提交门禁支持 AI 未确认阻断与措施三态表态"
```

---

## 任务 5：AI 预填服务（含"拒绝批准性表述"防线）

**文件：**
- 创建：`backend/app/services/work_ticket_ai_service.py`
- 测试：`backend/tests/test_work_ticket_ai_service.py`

- [x] **步骤 1：编写失败的测试**

创建 `backend/tests/test_work_ticket_ai_service.py`：

```python
"""AI 预填：归一化、降级、拒绝批准性表述。"""

from app.services.work_ticket_ai_service import normalize_ai_result


def test_normalize_extracts_risk_and_jsa():
    raw = (
        '{"risk_identification": {"text": "1. 罐内残留易燃液体，须清洗置换", "basis": ["3# 储罐"]},'
        ' "jsa": {"text": "作业前隔离", "hazards": [{"hazard": "火灾", "control": "清洗置换"}]}}'
    )
    out = normalize_ai_result(raw)
    assert out["available"] is True
    assert out["risk_identification"]["text"].startswith("1. 罐内残留")
    assert out["jsa"]["text"] == "作业前隔离"


def test_normalize_strips_code_fence():
    raw = '```json\n{"risk_identification": {"text": "含氧量不足风险"}}\n```'
    assert normalize_ai_result(raw)["available"] is True


def test_normalize_bad_json_degrades():
    out = normalize_ai_result("这不是 JSON")
    assert out["available"] is False
    assert out["risk_identification"] is None


def test_normalize_blank_text_degrades():
    assert normalize_ai_result('{"risk_identification": {"text": "   "}}')["available"] is False


def test_normalize_rejects_approval_language():
    """AI 不得代替人做批准；命中禁止表述时整份结果作废。"""
    raw = '{"risk_identification": {"text": "经分析符合作业条件，可以作业"}}'
    out = normalize_ai_result(raw)
    assert out["available"] is False
    assert "批准" in out["note"] or "拒绝" in out["note"]


def test_normalize_keeps_measures_suggestions_optional():
    raw = '{"risk_identification": {"text": "高处坠落风险"}}'
    out = normalize_ai_result(raw)
    assert out["measures_suggestions"] == []
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_ai_service.py -v`

预期：collection error（模块不存在）。

- [x] **步骤 3：编写实现**

创建 `backend/app/services/work_ticket_ai_service.py`：

```python
"""作业票 AI 预填：风险辨识结果 / JSA / 措施建议。

与 hazard_ai_service 同惯例：未配置、能力停用、超时、返回非 JSON 一律降级为
{"available": False, ...}，不抛异常、不阻塞开票流程。

额外安全防线（本模块专有）：AI 输出中出现"可以作业""符合作业条件"等批准性
表述时，整份结果作废——AI 不承担批准职责，票面上的结论只能由人给出。
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from app.services.ai_json import parse_ai_json
from app.services.llm_client import CapabilityDisabledError, llm_text_completion

CAPABILITY = "work_ticket_prefill"
AI_TIMEOUT_SECONDS = 60

_FORBIDDEN_APPROVAL_PHRASES = (
    "可以作业", "符合作业条件", "允许作业", "同意作业", "可以动火", "批准作业",
)

SYSTEM_PROMPT = (
    "你是危险化学品企业的特殊作业安全专家，熟悉 GB 30871-2022。"
    "只输出 JSON，不输出解释性前后缀。\n"
    "硬约束：\n"
    "1. 不得编造企业不存在的设备、介质、管线；不确定的事实写\"待现场核实\"\n"
    "2. 风险辨识结果 3~6 条，每条为一个具体危害及其控制措施\n"
    "3. 禁止输出\"符合作业条件\"\"可以作业\"之类批准性结论\n"
    "4. 输入中没有的信息不得推断（例如未给作业高度就不要提坠落风险）\n"
)
_OUTPUT_SCHEMA = (
    '{"risk_identification": {"text": "...", "basis": ["..."]},'
 ' "jsa": {"text": "...", "hazards": [{"hazard": "...", "control": "..."}]}}'
)


def _fallback(note: str) -> dict[str, Any]:
    return {
        "available": False,
        "risk_identification": None,
        "jsa": None,
        "measures_suggestions": [],
        "note": note,
    }


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_ai_result(raw: str) -> dict[str, Any]:
    """把模型输出归一化成前端契约；任何异常都降级为 available=False。"""
    try:
        data = parse_ai_json(raw)
    except Exception:  # parse_ai_json 抛 HTTPException，这里统一降级
        return _fallback("AI 返回格式异常，已跳过预填")
    if not isinstance(data, dict):
        return _fallback("AI 返回结构异常，已跳过预填")

    risk_raw = data.get("risk_identification") or {}
    risk_text = _clean_text(risk_raw.get("text") if isinstance(risk_raw, dict) else risk_raw)
    if not risk_text:
        return _fallback("AI 未返回有效的风险辨识内容")
    if any(phrase in risk_text for phrase in _FORBIDDEN_APPROVAL_PHRASES):
        return _fallback("AI 返回了批准性表述，已拒绝采用（批准只能由人给出）")

    basis = risk_raw.get("basis") if isinstance(risk_raw, dict) else None
    basis = [str(b).strip() for b in (basis or []) if str(b).strip()]

    jsa_raw = data.get("jsa") or {}
    jsa_text = _clean_text(jsa_raw.get("text") if isinstance(jsa_raw, dict) else jsa_raw)
    hazards = []
    if isinstance(jsa_raw, dict):
        for item in jsa_raw.get("hazards") or []:
            if not isinstance(item, dict):
                continue
            hazard = _clean_text(item.get("hazard"))
            control = _clean_text(item.get("control"))
            if hazard:
                hazards.append({"hazard": hazard, "control": control})

    return {
        "available": True,
        "risk_identification": {"text": risk_text, "basis": basis},
        "jsa": {"text": jsa_text, "hazards": hazards} if jsa_text else None,
        "measures_suggestions": [],
        "note": "AI 生成内容仅供参考，须由作业负责人确认",
    }


def build_prompt(
    *,
    ticket_type: str,
    level: Optional[str],
    location_text: Optional[str],
    work_content: Optional[str],
    risk_object_description: Optional[str],
    chemicals: Sequence[str],
    last_risk_text: Optional[str],
) -> str:
    return (
        f"作业类型：{ticket_type}（{level or '不分级'}）\n"
        f"作业地点：{location_text or '（未提供）'}\n"
        f"作业内容：{work_content or '（未提供）'}\n"
        f"作业对象描述：{risk_object_description or '（未提供）'}\n"
        f"涉及危化品：{'、'.join(chemicals) if chemicals else '（未提供）'}\n"
        f"上张同类票的风险辨识（仅作风格参照，不得照抄）：{last_risk_text or '（无）'}\n\n"
        f"请输出 JSON，结构为：{_OUTPUT_SCHEMA}"
    )


async def prefill(
    *,
    ticket_type: str,
    level: Optional[str],
    location_text: Optional[str],
    work_content: Optional[str],
    risk_object_description: Optional[str],
    chemicals: Sequence[str],
    last_risk_text: Optional[str],
    ai_config: Optional[object],
) -> dict[str, Any]:
    """调用 AI 生成预填内容；任何失败都降级，不抛异常。"""
    if ai_config is None:
        return _fallback("企业未配置 AI，已跳过 AI 预填")
    prompt = build_prompt(
        ticket_type=ticket_type,
        level=level,
        location_text=location_text,
        work_content=work_content,
        risk_object_description=risk_object_description,
        chemicals=chemicals,
        last_risk_text=last_risk_text,
    )
    try:
        raw = await llm_text_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            ai_config=ai_config,
            capability=CAPABILITY,
            timeout=AI_TIMEOUT_SECONDS,
        )
    except CapabilityDisabledError:
        return _fallback("AI 能力「作业票预填」已被管理员停用")
    except Exception as exc:  # 超时/网络/5xx 一律降级
        return _fallback(f"AI 预填失败，已跳过（{type(exc).__name__}）")
    return normalize_ai_result(raw)
```

注意：`llm_text_completion` 的实际签名以 `backend/app/services/llm_client.py` 为准；若参数名不同（如 `system_prompt` 为关键字），以模块内既有调用范例（`hazard_ai_service.py`）为准对齐，不要改 `llm_client` 本身。

- [x] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_ai_service.py -v`

预期：6 个用例全 PASSED。

- [x] **步骤 5：注册 AI 能力**

在 AI 能力注册表（`backend/app/services/ai_capability_service.py` 内的能力清单常量）中加入：

```python
    {"name": "work_ticket_prefill", "label": "作业票智能预填", "description": "开票时生成风险辨识结果与 JSA 草稿"},
```

若清单在数据库种子中维护，则同步补一条迁移 SQL 并在任务记录中写明。

- [x] **步骤 6：Commit**

```bash
git add backend/app/services/work_ticket_ai_service.py backend/app/services/ai_capability_service.py backend/tests/test_work_ticket_ai_service.py
git commit -m "feat(work-ticket): AI 预填服务（降级 + 拒绝批准性表述）+ 能力注册"
```

---

## 任务 6：API 端点（预填 / AI / 草稿保存 / 地点选择器）

**文件：**
- 修改：`backend/app/schemas/work_ticket.py`
- 修改：`backend/app/routers/work_ticket.py`
- 测试：`backend/tests/test_work_ticket_api.py`（追加）

- [x] **步骤 1：编写失败的测试**

在 `backend/tests/test_work_ticket_api.py` 追加（复用文件内既有的 `_client(handler)` 助手）：

```python
def test_draft_save_rejects_non_draft_status():
    """已提交的票不能再走草稿保存。"""

    async def handler(stmt):
        return _Result([_instance(status="approving")])

    client = _client(handler)
    resp = client.patch(
        "/api/v1/work-ticket/tickets/t1",
        json={"values": {"work_content": "x"}, "values_meta": {}, "measures_meta": {}},
    )
    assert resp.status_code == 409
    assert "草稿" in resp.json()["detail"]


def test_templates_expose_allow_ai_prefill():
    """模板接口必须把 allow_ai_prefill 透出，前端才能决定是否显示 AI 按钮。"""
    field = MagicMock()
    field.field_key = "risk_identification"
    field.label = "风险辨识结果"
    field.field_type = "textarea"
    field.group_name = "危害因素"
    field.is_required = True
    field.options = {}
    field.allow_ai_prefill = True
    field.sort_order = 1
    template = MagicMock()
    template.id = "tpl1"
    template.code = "DHZY"
    template.name = "动火安全作业票"
    template.level = "二级"
    template.is_graded = True
    template.fields = [field]
    template.measures = []

    async def handler(stmt):
        return _Result([template])

    client = _client(handler)
    resp = client.get("/api/v1/work-ticket/templates")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["fields"][0]["allow_ai_prefill"] is True
```

文件底部补一个实例工厂（若已有类似助手则复用）：

```python
def _instance(status: str):
    inst = MagicMock()
    inst.id = "t1"
    inst.status = status
    inst.values = {}
    inst.values_meta = {}
    inst.measures_meta = {}
    return inst
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_api.py -v`

预期：新增两个用例 **FAILED**（`405`/`404` 或 `KeyError: allow_ai_prefill`）。

- [x] **步骤 3：编写 schema**

在 `backend/app/schemas/work_ticket.py` 追加：

```python
class DraftSaveIn(BaseModel):
    """草稿保存：票面值 + 来源留痕 + 措施三态。"""

    values: dict = Field(default_factory=dict)
    values_meta: dict = Field(default_factory=dict)
    measures_meta: dict = Field(default_factory=dict)


class AiPrefillIn(BaseModel):
    """AI 预填请求。risk_object_id 可空（未选作业对象时退化为纯文本输入）。"""

    enterprise_id: str
    ticket_type: str
    level: str | None = None
    risk_object_id: str | None = None
    work_content: str | None = None
```

- [x] **步骤 4：实现端点**

在 `backend/app/routers/work_ticket.py` 的 `list_templates` 字段序列化中加入一行：

```python
                        "allow_ai_prefill": f.allow_ai_prefill,
```

在同文件追加四个端点（放在 `api_open_ticket` 之后）：

```python
@router.get("/prefill")
async def api_prefill(
    enterprise_id: str = Query(...),
    template_id: str = Query(...),
    level: str | None = Query(default=None),
    risk_object_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """确定性预填：来源优先级取数，不调用 AI（进页面即调，必须快）。"""
    await ensure_enterprise_owned(db, user, enterprise_id)
    template = (
        await db.execute(select(WorkTicketTemplate).where(WorkTicketTemplate.id == template_id))
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(404, "模板不存在")
    location_text = None
    if risk_object_id:
        obj = (
            await db.execute(select(RiskObject).where(RiskObject.id == risk_object_id))
        ).scalar_one_or_none()
        if obj is not None:
            location_text = obj.location or obj.name
    payload = await build_prefill(
        db,
        enterprise_id=enterprise_id,
        template=template,
        level=level,
        risk_object_location=location_text,
    )
    return _ok(payload)


@router.post("/ai/prefill")
async def api_ai_prefill(
    payload: AiPrefillIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AI 预填：用户显式点击才调用；能力停用/超时/异常一律降级返回。"""
    await ensure_enterprise_owned(db, user, payload.enterprise_id)
    ai_config = await load_ai_config(db)  # 复用既有取企业 AI 配置的服务函数
    result = await ai_prefill(
        ticket_type=payload.ticket_type,
        level=payload.level,
        location_text=None,
        work_content=payload.work_content,
        risk_object_description=None,
        chemicals=[],
        last_risk_text=None,
        ai_config=ai_config,
    )
    return _ok(result)


@router.patch("/tickets/{ticket_id}")
async def api_save_draft(
    ticket_id: str,
    payload: DraftSaveIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """草稿保存（仅 draft）。字段名刻意用 values_meta/measures_meta，
    与实例列同名，避免前端再映射一层。"""
    instance = (
        await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == ticket_id))
    ).scalar_one_or_none()
    if instance is None:
        raise HTTPException(404, "作业票不存在")
    await ensure_ticket_owned(db, user, ticket_id)
    if instance.status != "draft":
        raise HTTPException(409, "只有草稿状态的作业票可以保存")
    instance.values = payload.values
    instance.values_meta = payload.values_meta
    instance.measures_meta = payload.measures_meta
    await db.commit()
    return _ok(TicketOut.model_validate(instance))


@router.get("/last-ticket")
async def api_last_ticket(
    enterprise_id: str = Query(...),
    template_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """上次同类票摘要，供开票页"参考上次"入口（无历史票时返回 null）。"""
    await ensure_enterprise_visible(db, user, enterprise_id)
    last = await _last_ticket(db, enterprise_id=enterprise_id, template_id=template_id)
    if last is None:
        return _ok(None)
    values = last.values or {}
    return _ok(
        {
            "id": last.id,
            "code": last.code,
            "created_at": last.created_at,
            "work_content": values.get("work_content"),
            "risk_identification": values.get("risk_identification"),
        }
    )


@router.get("/locations")
async def api_locations(
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """作业地点候选：楼层 → 区域 → 对象（含地点文本）。"""
    _ent, _is_owner = await ensure_enterprise_visible(db, user, enterprise_id)
    floors = (
        await db.execute(
            select(EnterpriseFloor)
            .where(EnterpriseFloor.enterprise_id == enterprise_id)
            .order_by(EnterpriseFloor.sort_order)
        )
    ).scalars().all()
    zones = (
        await db.execute(
            select(RiskZone)
            .where(RiskZone.enterprise_id == enterprise_id)
            .order_by(RiskZone.sort_order)
        )
    ).scalars().all()
    objects = (
        await db.execute(
            select(RiskObject).where(RiskObject.enterprise_id == enterprise_id)
        )
    ).scalars().all()
    return _ok(
        {
            "floors": [{"id": f.id, "name": f.name} for f in floors],
            "zones": [
                {"id": z.id, "name": z.name, "floor_id": z.floor_id} for z in zones
            ],
            "objects": [
                {
                    "id": o.id,
                    "name": o.name,
                    "location": o.location,
                    "zone_id": o.zone_id,
                    "floor_id": o.floor_id,
                }
                for o in objects
            ],
        }
    )
```

同时补 import：`from app.models.enterprise import EnterpriseFloor`、`from app.models.risk_management import RiskObject, RiskZone`、`from app.schemas.work_ticket import AiPrefillIn, DraftSaveIn`、`from app.services.work_ticket_prefill import build_prefill, _last_ticket`、`from app.services.work_ticket_ai_service import prefill as ai_prefill`。`load_ai_config` 用仓库既有的取 AI 配置服务（`grep -n "AI 配置" backend/app/services/*.py` 定位其真实函数名后替换），不要新写一个。

- [x] **步骤 5：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_api.py -v`

预期：全部 PASSED（含原有用例）。

- [x] **步骤 6：Commit**

```bash
git add backend/app/routers/work_ticket.py backend/app/schemas/work_ticket.py backend/tests/test_work_ticket_api.py
git commit -m "feat(work-ticket): 预填/AI/草稿保存/地点选择器 四个端点 + templates 透出 allow_ai_prefill"
```

---

## 任务 7：前端向导改造（徽标 / 级别联动 / 措施三态 / 来源摘要 / 草稿）

**文件：**
- 修改：`frontend/src/types/workTicket.ts`
- 修改：`frontend/src/services/workTicketService.ts`
- 创建：`frontend/src/components/enterprise/workTicket/PrefillBadge.tsx`
- 创建：`frontend/src/components/enterprise/workTicket/MeasureChecklist.tsx`
- 修改：`frontend/src/pages/Enterprise/WorkTicketNewPage.tsx`
- 测试：`frontend/src/components/enterprise/workTicket/__tests__/PrefillBadge.test.tsx`、`MeasureChecklist.test.tsx`

- [x] **步骤 1：补类型**

在 `frontend/src/types/workTicket.ts` 中追加，并给既有接口补字段：

```ts
export type FieldSource =
  | "manual" | "history" | "member" | "risk_object"
  | "template_link" | "system_default" | "batch" | "ai";

export interface FieldMeta {
  source: FieldSource;
  source_ref?: Record<string, unknown>;
  prefilled_at?: string | null;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  edited?: boolean;
}

export type MeasureState = "pending" | "confirmed" | "not_applicable";

export interface MeasureMeta {
  state: MeasureState;
  reason_code?: string;
  reason_text?: string;
  acted_by?: string | null;
  acted_at?: string | null;
}

export interface MeasureSuggestion {
  sort_order: number;
  suggest: "applicable" | "not_applicable" | "unknown";
  reason: string | null;
}

// WorkTicketFieldDef 增加 allow_ai_prefill
// WorkTicketInstance 增加 values_meta / measures_meta
```

`WorkTicketFieldDef` 补 `allow_ai_prefill?: boolean;`，`WorkTicketInstance` 补 `values_meta?: Record<string, FieldMeta>; measures_meta?: Record<string, MeasureMeta>;`。

- [x] **步骤 2：补服务封装**

```ts
export const getPrefill = (params: {
  enterprise_id: string; template_id: string; level?: string | null; risk_object_id?: string | null;
}) =>
  api.get<ApiResponse<PrefillPayload>>(`${BASE}/prefill`, { params })
    .then((r) => r.data.data);

export const aiPrefill = (payload: {
  enterprise_id: string; ticket_type: string; level?: string | null; work_content?: string | null;
}) =>
  api.post<ApiResponse<AiPrefillResult>>(`${BASE}/ai/prefill`, payload, { skipGlobalError: true })
    .then((r) => r.data.data);

export const saveDraft = (
  ticketId: string,
  payload: { values: Record<string, unknown>; values_meta: Record<string, FieldMeta>; measures_meta: Record<string, MeasureMeta> },
) =>
  api.patch<ApiResponse<WorkTicketInstance>>(`${BASE}/tickets/${ticketId}`, payload)
    .then((r) => r.data.data);

export const listLocations = (enterpriseId: string) =>
  api.get<ApiResponse<LocationTree>>(`${BASE}/locations`, { params: { enterprise_id: enterpriseId } })
    .then((r) => r.data.data);
```

- [x] **步骤 3：写徽标组件（含单测）**

创建 `frontend/src/components/enterprise/workTicket/PrefillBadge.tsx`：

```tsx
import { Tag, Tooltip } from "antd";
import type { FieldSource } from "@/types/workTicket";

export const SOURCE_LABEL: Record<FieldSource, string> = {
  manual: "手工填写",
  history: "上次同类票",
  member: "成员台账",
  risk_object: "作业对象",
  template_link: "向导联动",
  system_default: "系统默认",
  batch: "作业包",
  ai: "AI 生成",
};

/** 来源徽标：manual 不显示；AI 用紫色以提示必须人工确认。 */
export function PrefillBadge({
  source,
  detail,
}: {
  source?: FieldSource;
  detail?: string;
}) {
  if (!source || source === "manual") return null;
  const label = SOURCE_LABEL[source];
  return (
    <Tooltip title={detail || label}>
      <Tag color={source === "ai" ? "purple" : "blue"}>{label}</Tag>
    </Tooltip>
  );
}
```

创建 `frontend/src/components/enterprise/workTicket/__tests__/PrefillBadge.test.tsx`：

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PrefillBadge, SOURCE_LABEL } from "../PrefillBadge";

describe("PrefillBadge", () => {
  it("手工填写不渲染徽标", () => {
    const { container } = render(<PrefillBadge source="manual" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("来源缺失不渲染徽标", () => {
    const { container } = render(<PrefillBadge />);
    expect(container).toBeEmptyDOMElement();
  });

  it("历史票来源显示对应文案", () => {
    render(<PrefillBadge source="history" />);
    expect(screen.getByText(SOURCE_LABEL.history)).toBeInTheDocument();
  });

  it("AI 来源显示 AI 徽标", () => {
    render(<PrefillBadge source="ai" />);
    expect(screen.getByText(SOURCE_LABEL.ai)).toBeInTheDocument();
  });
});
```

- [x] **步骤 4：写措施三态列表（含单测）**

创建 `frontend/src/components/enterprise/workTicket/MeasureChecklist.tsx`：核心是"主列表 + 建议不涉及折叠区 + 三态操作"，组件签名如下（完整实现包含三段交互：确认涉及 / 标记不涉及（弹理由选择）/ 撤销）：

```tsx
export interface MeasureChecklistProps {
  measures: WorkTicketMeasureDef[];
  suggestions: MeasureSuggestion[];
  meta: Record<string, MeasureMeta>;
  onChange: (next: Record<string, MeasureMeta>) => void;
}

const REASON_OPTIONS = [
  { value: "no_condition", label: "现场不具备该条件" },
  { value: "not_this_method", label: "本次作业方式不涉及" },
  { value: "covered_by_other", label: "已由其他作业票覆盖" },
  { value: "no_medium", label: "作业点无相关介质" },
];
```

关键渲染规则（写进组件，不要用"全部确认"）：

- 分区：`suggest_not_applicable` 且状态仍为 `pending` 的措施进折叠区（默认收起），其余进主列表
- 主列表每条提供"确认涉及"按钮 → 写 `{state: "confirmed", acted_at}`
- 折叠区每条提供"标记不涉及"（弹理由选择 + 说明输入，两者必填）→ 写 `{state: "not_applicable", reason_code, reason_text, acted_at}`
- 已处理的条目显示状态与理由，并提供"撤销"回到 `pending`
- 顶部显示 `已表态 X / N 条`（X = confirmed + not_applicable），**不提供**把全部条目一键置为 `confirmed` 的入口
- 主列表可提供"确认全部建议涉及的（M 条）"，仅在 `suggest === "applicable"` 的条目上生效

创建 `frontend/src/components/enterprise/workTicket/__tests__/MeasureChecklist.test.tsx`：

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MeasureChecklist } from "../MeasureChecklist";

const measures = [
  { sort_order: 1, measure_text: "措施一", article_anchor: "GB 30871-2022 5" },
  { sort_order: 4, measure_text: "措施四", article_anchor: "GB 30871-2022 5" },
];

describe("MeasureChecklist", () => {
  it("建议不涉及的措施进入折叠区，默认不显示在主线", () => {
    render(
      <MeasureChecklist
        measures={measures}
        suggestions={[
          { sort_order: 1, suggest: "unknown", reason: null },
          { sort_order: 4, suggest: "not_applicable", reason: "本票不涉及：作业点在油气罐区防火堤内" },
        ]}
        meta={{}}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText("措施一")).toBeInTheDocument();
    expect(screen.queryByText("措施四")).not.toBeInTheDocument();
    expect(screen.getByText(/建议不涉及/)).toBeInTheDocument();
  });

  it("表态计数不含未处理项", () => {
    render(
      <MeasureChecklist
        measures={measures}
        suggestions={[]}
        meta={{ "1": { state: "confirmed" } }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText(/已表态 1 \/ 2 条/)).toBeInTheDocument();
  });

  it("确认涉及会回调新的 meta", () => {
    const onChange = vi.fn();
    render(
      <MeasureChecklist measures={measures} suggestions={[]} meta={{}} onChange={onChange} />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: "确认涉及" })[0]);
    const next = onChange.mock.calls[0][0];
    expect(next["1"].state).toBe("confirmed");
  });
});
```

- [x] **步骤 5：改造向导页**

`WorkTicketNewPage.tsx` 的改动点（保持 6 步骨架）：

1. 第 0 步新增"作业地点"选择（`listLocations`）与"作业情景"6 个开关，状态存入 `scenario`
2. 进入第 1 步前调用 `getPrefill(...)`，用返回的 `values` 作为表单 `initialValues`、`values_meta` 存 state；`Form.Item` 的 `label` 旁渲染 `<PrefillBadge source={meta[key]?.source} />`
3. 级别联动：`useEffect` 在 `activeLevel` 变化时 `form.setFieldValue("fire_level"/"high_level"/"lift_level", activeLevel)`，并写 `values_meta[levelKey] = {source: "template_link"}`
4. 第 3 步把内联的 Checkbox 列表替换为 `<MeasureChecklist ... />`，建议由 `buildPrefill` 响应中的 `measures_suggestions` 提供
5. 第 5 步新增"填写来源摘要"：统计 `values_meta` 各来源数量；AI 来源未确认的字段列红并阻止提交
6. "下一步"时调用 `saveDraft`（草稿已存在时用返回的 instance.id）保存 `values/values_meta/measures_meta`；提交前先保存再 `submitTicket`
7. 移除原"全部确认"按钮（`setConfirmed(mandatoryMeasures.map(...))`）
8. 第 1 步顶部提供"参考上次（票号）"入口：调 `GET /last-ticket` 展示上次同类票的作业内容与风险辨识摘要（只读弹窗，**不自动填值**）

- [x] **步骤 6：运行前端门禁**

```bash
cd frontend
npx tsc -b
npx vitest run
npx eslint src --max-warnings 0
```

预期：`tsc` 0 错；vitest 全绿（原 300 例 + 新增 7 例）；eslint 0。

- [x] **步骤 7：Commit**

```bash
git add frontend/src/types/workTicket.ts frontend/src/services/workTicketService.ts frontend/src/components/enterprise/workTicket frontend/src/pages/Enterprise/WorkTicketNewPage.tsx
git commit -m "feat(work-ticket): 开票向导接入预填徽标/级别联动/措施三态/来源摘要/草稿保存"
```

---

## 任务 8：成员证照与人员选择器

**文件：**
- 修改：成员 CRUD 相关 router/schema（用 `grep -rn "enterprise_members\\|EnterpriseMember" backend/app/routers/` 定位实际端点）
- 修改：`frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`
- 修改：`frontend/src/pages/Enterprise/WorkTicketNewPage.tsx`（人员字段渲染）

- [x] **步骤 1：编写失败的测试**

在 `backend/tests/test_enterprise_org_members.py`（若无则创建）追加：

```python
def test_member_payload_accepts_certificates():
    """成员可维护特种作业证照：类型 + 证书编号 + 有效期。"""
    from app.schemas.enterprise_org import MemberIn  # 以实际 schema 名为准

    payload = MemberIn(
        name="张三",
        position="焊工",
        certificates=[{"type": "焊接与热切割作业", "no": "T6101", "valid_to": "2027-05-30"}],
    )
    assert payload.certificates[0]["no"] == "T6101"


def test_member_certificates_default_empty():
    from app.schemas.enterprise_org import MemberIn

    assert MemberIn(name="李四").certificates == []
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_enterprise_org_members.py -v`

预期：FAILED（`certificates` 不是有效字段）。

- [x] **步骤 3：后端透传证照**

在成员入参 schema（`backend/app/schemas/enterprise_org.py`）中加入：

```python
    certificates: list[dict] = Field(default_factory=list)
```

并在成员创建/更新端点的字段赋值处加入 `certificates=payload.certificates`（若端点用 `model_dump()` 批量赋值则无需改动，确认后据实处理）。同时更新成员列表/详情响应，返回 `certificates`。

- [x] **步骤 4：前端证照编辑与人员选择器**

`EnterpriseOrgPage.tsx`：成员编辑弹窗增加"特种作业证照"区块（类型下拉 + 证书编号 + 有效期 DatePicker，支持增删多条），类型选项：

```ts
const CERT_TYPES = [
  "焊接与热切割作业",
  "低压电工作业",
  "高处安装、维护、拆除作业",
  "起重机械指挥",
  "危险化学品安全作业",
];
```

`WorkTicketNewPage.tsx`：对 `fire_person` / `electrician` / `work_leader` / `guardian` / `lift_commander` 这五个字段，用 `Select`（选项来自预填返回的 `members`）替代 `Input`；选中后按 `姓名 + 空格 + 证书号` 拼接写入表单值（无证照则只写姓名），并保留手填能力（`Select` 配置 `showSearch` + `allowClear`，允许自定义输入用 `Input` 作为下拉的 footer）。

落库格式与现状一致（`values.fire_person = "张三 T6101"`），因此 `work_ticket_docx.py`、打印快照、历史票全部零改动。

- [x] **步骤 5：运行前后端测试**

```bash
cd backend && python -m pytest tests/ -k "work_ticket or enterprise_org" -v
cd ../frontend && npx tsc -b && npx vitest run
```

预期：全绿。

- [x] **步骤 6：Commit**

```bash
git add backend/app/schemas/enterprise_org.py backend/app/routers frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx frontend/src/pages/Enterprise/WorkTicketNewPage.tsx backend/tests/test_enterprise_org_members.py
git commit -m "feat(work-ticket): 成员特种作业证照 + 票面人员选择器"
```

---

## 任务 9：基线测量、端到端验证与证据留档

**文件：**
- 创建：`output/playwright/e2e-20260920/scripts/_work_ticket_open_effort_probe.py`

- [x] **步骤 1：先测改造前基线（必须在任务 7 之前跑）**

创建探针脚本，用 Playwright 驱动真账号完成一张二级动火票的开票流程，统计**用户输入事件数**（点击 / 选择 / 一次连续文本输入各记 1）：

```python
"""开票交互动作计数探针。

口径（与规格 §6 一致）：从进入向导到点击"提交审批"之间的用户输入事件数。
在页面注入计数脚本，按事件类型累加，最后输出 JSON 证据。

用法：python output/playwright/e2e-20260920/scripts/_work_ticket_open_effort_probe.py --label before
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

COUNT_JS = """
window.__effort = 0;
for (const type of ["click", "change"]) {
  document.addEventListener(type, () => { window.__effort += 1; }, true);
}
document.addEventListener("input", (e) => {
  if (e.target !== window.__lastInputTarget) { window.__effort += 1; }
  window.__lastInputTarget = e.target;
}, true);
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="after", choices=["before", "after"])
    args = parser.parse_args()
    # 1) 用项目既有 e2e 助手登录 qa_e2e_test@test.com（见 output/playwright/e2e-20260918/scripts/ 内既有脚本）
    # 2) 打开 /enterprises/<id>/work-ticket/new，注入 COUNT_JS
    # 3) 走完 6 步并点击"提交审批"
    # 4) 读取 window.__effort 写证据
    evidence = {"label": args.label, "effort": None}
    (OUT / f"work-ticket-effort-{args.label}.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

先跑基线（在任务 7 合并前）：

```powershell
python output/playwright/e2e-20260920/scripts/_work_ticket_open_effort_probe.py --label before
```

预期：`work-ticket-effort-before.json` 记录约 35 次以上（动火票措施数在计划 1 修复后为 16 条，仍为全量勾选）。

若在计划 1 完成后才执行本任务，基线口径改为"计划 1 修复后、计划 2 改造前"，在证据文件里注明这一点。

- [x] **步骤 2：改造后再测**

```powershell
python output/playwright/e2e-20260920/scripts/_work_ticket_open_effort_probe.py --label after
```

预期：`effort` ≤ 12（不含气体检测数据录入本身）。

- [x] **步骤 3：浏览器功能实测（8 个票种 + 降级路径）**

```powershell
python output/playwright/e2e-20260920/scripts/_work_ticket_prefill_browser_probe.py
```

探针需断言（复用项目既有 Playwright 浏览器探针写法）：

1. 8 个票种各开一张：无 console error、预填徽标出现、来源 tooltip 文案正确
2. 级别联动：第 0 步改级别后，票面级别字段自动变化
3. 措施：动火票主列表 ≤16 条、折叠区出现"建议不涉及"、标记不涉及必须填理由
4. AI 降级：把企业 AI 配置置空后重开票页 → 字段旁显示"AI 暂不可用"、页面不报错、仍可提交
5. 门禁：AI 生成风险辨识但不确认 → 前端红字 + 提交被后端 422 阻断（两条路径都要验）

- [x] **步骤 4：全量门禁**

```bash
cd backend && python -m pytest -q && python -m ruff check .
cd ../frontend && npx tsc -b && npx vitest run && npx eslint src --max-warnings 0 && npm run build
```

预期：后端全绿（计划 1 完成时 2109+ 例）；前端 `tsc` 0 / vitest 全绿 / eslint 0 / build 成功。

- [x] **步骤 5：把产物同步到 8082 并做 37 页冒烟**

按项目既有部署流程构建并把 `frontend/dist` 同步到 8082 静态目录，跑一次既有冒烟脚本，确认 0 异常 0 5xx（参考 TASKS.md 中"37 页冒烟"的记录方式）。

- [x] **步骤 6：Commit**

```bash
git add output/playwright/e2e-20260920/scripts
git commit -m "test(probe): 开票交互动作基线/改造后对比 + 预填浏览器实测证据"
```

---

## 验收清单

- [x] `values_meta` / `measures_meta` / `certificates` 三列已应用，28 张老票全部可读、可提交、可打印
- [x] 模板接口返回 `allow_ai_prefill`
- [x] 进入开票页即有预填，每个预填字段显示来源徽标与依据
- [x] 级别在第 0 步选定后票面级别字段自动联动，无需二次输入
- [x] 人员字段可从成员台账选择，`values` 落库格式与改造前一致（打印零差异）
- [x] 成员证照可维护，动火人/电工的证书号自动拼接
- [x] 措施三态可用；"建议不涉及"进折叠区；标记不涉及必须填理由；可撤销
- [x] 措施门禁为"全部表态"，且老票（仅 `confirmed_measures`）不受影响
- [x] AI 预填可用时生成风险辨识与 JSA；停用/超时/未配置时静默降级
- [x] AI 输出含批准性表述时被拒绝采用
- [x] AI 生成字段未确认时前后端双向阻断
- [x] 草稿可保存、可继续填写；非草稿状态保存返回 409
- [x] 无风险数据 / 无历史票 / 无成员 的企业开票流程完整可用
- [x] 交互动作计数达 ≤12 次目标，且有改造前后对比证据
- [x] 后端 `pytest` + `ruff` 全绿；前端 `tsc -b` / `vitest` / `eslint` / `build` 全绿

## 不做（本计划范围外）

- 措施条件映射首批只覆盖动火 16 条；受限空间与其他票种保持 `unknown`，由人工逐条处理（后续按同法增量补充）
- 不做作业包与批量开票（计划 3）
- 不做移动端开票页
- 不改 `validate_before_submit` 的法定必填规则与气体检测 30 分钟时效
