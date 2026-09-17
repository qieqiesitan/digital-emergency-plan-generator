# AI 抽取链路（资料 → 待确认队列）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 用户上传《安全评价报告》《重大危险源评估报告》或危化品台账 Excel，系统抽出结构化的单元、品种、设计最大量候选，**带来源定位与置信度**进入 DataHub 待确认队列，人工确认后落入重大危险源台账。

**架构：** 抽取走计划 2 的 AI 网关（统一异常语义 + 调用留痕）；产出统一落进计划 5 的 `ingest_items`（`pending`）。本计划**只新增"从文本到候选"与"候选到目标表"两段**，不重复实现解析、幂等、确认链路。

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x / openpyxl / APScheduler / pytest。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §6.4、§8.4

**依赖：**

- **计划 2（AI 网关）必需**——抽取依赖调用留痕与截断语义
- **计划 5（DataHub）必需**——`create_item` / `confirm_items` / `TARGET_WRITERS` 全部复用
- 计划 1（已完成）——目标表 `major_hazard_units` / `major_hazard_unit_chemicals`

**贯穿全程的硬门槛（spec §1.4）：** AI 抽取的数据必须带来源与置信度，**未经人工确认不得入库**。本计划的代码结构就是为这条服务的——抽取函数**没有写业务表的权限**，只能 `create_item`。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/app/services/extraction_prompts.py`（新建） | 抽取提示词模板与输出结构校验 |
| `backend/app/services/extraction_service.py`（新建） | 调 AI 抽候选、校验结构、常量表复核、落 `ingest_items` |
| `backend/app/services/ingest_writers.py`（新建） | 目标实体写入器：把确认后的载荷写进正式表 |
| `backend/app/services/schema_matching.py`（新建） | 表格列 → 目标字段的 AI 建议 |
| `backend/app/schemas/extraction.py`（新建） | 出入参 |
| `backend/app/routers/extraction.py`（新建） | 上传解析、触发抽取、映射建议 |
| `backend/app/main.py`（修改） | 注册路由 |
| `backend/tests/test_extraction_prompts.py`（新建） | 提示词与结构校验 |
| `backend/tests/test_extraction_service.py`（新建） | 抽取 + 常量复核 + 落队列 |
| `backend/tests/test_ingest_writers.py`（新建） | 写入器（确认后落正式表） |
| `backend/tests/test_schema_matching.py`（新建） | 列映射建议 |
| `backend/tests/test_extraction_api.py`（新建） | 端点测试 |
| `frontend/src/services/extractionService.ts`（新建） | API 封装 |
| `frontend/src/pages/Settings/DataHubImportPage.tsx`（新建） | 上传 + 映射确认 + 触发抽取 |

**既有约定**

- 复用 `app/services/file_parser.py` 的 `parse_file_text(filename, data) -> str`（csv/xlsx/docx/pdf）
- 复用 `app/services/ingest_service.py` 的 `create_item` / `register_target_writer`
- 复用 `app/services/onboarding_service.py` 的 `_get_ai_config_or_400`
- AI 调用统一走 `app/services/llm_client.py`（异常语义以计划 2 修正后为准）

---

## 抽取契约（先定数据结构，再写代码）

| `target_entity` | 抽取字段 | 必填 |
|---|---|---|
| `major_hazard_unit` | `name`、`unit_type`(production/storage)、`boundary_desc`、`address` | `name`、`unit_type` |
| `major_hazard_unit_chemical` | `unit_name`、`chemical_name`、`q_design_max`、`physical_state` | `chemical_name`、`q_design_max` |

每条候选必须携带 `source_locator`（如 `安全评价报告.pdf P12 §3.2`）、`confidence`（high/medium/low）、`payload`、可选 `review_note`。

**置信度判定：** 原文明确写出数值与单位且字段齐全 → `high`；数值由其他信息推算（如"有效容积 100m³"→ 79t）或字段有缺 → `medium`；描述模糊、单位缺失、无法确定归属 → `low`。

> **服务层兜底（关键）：** 模型返回的 `critical_quantity_t` 与 `beta` **一律不采信**，
> 落队列前用 `critical_quantities` / `hazard_beta_factors` 常量表复核；
> 查不到就置空、降级为 `low` 并写明"临界量待人工指定"。
> 理由：Q 与 β 是 **GB 18218 的法定查表值**，让模型"读"出来等于把查表权威交给它。

---

## 任务 1：抽取提示词与结构校验

**文件：**

- 创建：`backend/app/services/extraction_prompts.py`
- 测试：`backend/tests/test_extraction_prompts.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""抽取提示词与输出结构校验。"""

import pytest

from app.services.extraction_prompts import (
    ENTITY_SCHEMAS,
    ExtractionSchemaError,
    build_messages,
    validate_payload,
)


def test_entity_schemas_cover_two_targets():
    assert set(ENTITY_SCHEMAS) >= {"major_hazard_unit", "major_hazard_unit_chemical"}


def test_build_messages_includes_required_fields_and_source_hint():
    msgs = build_messages(
        target_entity="major_hazard_unit_chemical",
        text="罐区A 储存甲醇 79 吨",
        source_hint="安全评价报告.pdf",
    )
    joined = " ".join(m["content"] for m in msgs)
    assert "chemical_name" in joined
    assert "q_design_max" in joined
    assert "安全评价报告.pdf" in joined, "必须把来源文件名喂给模型，便于产出 source_locator"
    assert "JSON" in joined


def test_validate_payload_accepts_good_row():
    ok = validate_payload(
        "major_hazard_unit_chemical",
        {
            "chemical_name": "甲醇",
            "q_design_max": 79,
            "physical_state": "液态",
            "source_locator": "报告.pdf 段12",
            "confidence": "medium",
        },
    )
    assert ok["chemical_name"] == "甲醇"
    assert ok["q_design_max"] == 79.0


def test_validate_payload_rejects_missing_required():
    with pytest.raises(ExtractionSchemaError) as ei:
        validate_payload(
            "major_hazard_unit_chemical",
            {"chemical_name": "甲醇", "source_locator": "x", "confidence": "high"},
        )
    assert "q_design_max" in str(ei.value)


def test_validate_payload_rejects_bad_unit_type():
    with pytest.raises(ExtractionSchemaError):
        validate_payload(
            "major_hazard_unit",
            {"name": "罐区A", "unit_type": "storage_area", "source_locator": "x", "confidence": "high"},
        )


def test_validate_payload_rejects_unknown_confidence():
    with pytest.raises(ExtractionSchemaError):
        validate_payload(
            "major_hazard_unit",
            {"name": "罐区A", "unit_type": "storage", "source_locator": "x", "confidence": "sure"},
        )


def test_validate_payload_requires_source_locator():
    """没有来源定位的抽取结果不可追溯，必须拒绝。"""
    with pytest.raises(ExtractionSchemaError) as ei:
        validate_payload(
            "major_hazard_unit",
            {"name": "罐区A", "unit_type": "storage", "confidence": "high"},
        )
    assert "source_locator" in str(ei.value)


def test_validate_payload_coerces_numeric_strings():
    """模型常把数值输出成字符串，这里做受控转换。"""
    ok = validate_payload(
        "major_hazard_unit_chemical",
        {
            "chemical_name": "氯",
            "q_design_max": "5.0",
            "source_locator": "x",
            "confidence": "high",
        },
    )
    assert ok["q_design_max"] == 5.0
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_extraction_prompts.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""抽取提示词模板与输出结构校验。

设计原则：**抽字段，不抽标准值**。临界量 Q 与校正系数 β 是 GB 18218 的法定查表值，
必须由系统按名称/类别查表得出，不能让模型"读"出来——那等于把查表权威交给模型。
"""

from __future__ import annotations

from typing import Any


class ExtractionSchemaError(ValueError):
    """模型输出不满足目标实体结构要求。"""


ENTITY_SCHEMAS: dict[str, dict] = {
    "major_hazard_unit": {
        "title": "重大危险源单元",
        "fields": {
            "name": {"type": "str", "required": True, "desc": "单元名称，如「罐区A」「锅炉房」"},
            "unit_type": {
                "type": "enum",
                "values": ["production", "storage"],
                "required": True,
                "desc": "生产单元填 production，储存单元（储罐区/仓库）填 storage",
            },
            "boundary_desc": {"type": "str", "required": False, "desc": "边界描述，如「以罐区防火堤为界」"},
            "address": {"type": "str", "required": False, "desc": "所在位置"},
        },
    },
    "major_hazard_unit_chemical": {
        "title": "单元内危险化学品存量",
        "fields": {
            "unit_name": {"type": "str", "required": False, "desc": "归属单元名称，用于人工确认时对应"},
            "chemical_name": {"type": "str", "required": True, "desc": "危险化学品名称"},
            "q_design_max": {
                "type": "float",
                "required": True,
                "desc": "设计最大量，单位吨。注意：是设计最大量（按设备设计容积/额定充装量），"
                "不是日常储存量。原文给容积时按密度换算并在 review_note 说明。",
            },
            "physical_state": {"type": "str", "required": False, "desc": "物理状态"},
        },
    },
}


def build_messages(*, target_entity: str, text: str, source_hint: str) -> list[dict]:
    """构造抽取用对话消息。"""
    schema = ENTITY_SCHEMAS.get(target_entity)
    if schema is None:
        raise ExtractionSchemaError(f"未知目标实体：{target_entity}")

    field_lines = []
    for name, spec in schema["fields"].items():
        req = "必填" if spec.get("required") else "可选"
        extra = ""
        if spec.get("type") == "enum":
            extra = f"，取值只能是 {spec['values']}"
        field_lines.append(f"- {name}（{req}{extra}）：{spec['desc']}")

    system = (
        "你是危险化学品安全技术资料的结构化抽取助手。"
        "你的任务是把给定的资料原文抽取成结构化数据，**不得虚构原文没有的信息**。"
        "只输出 JSON 数组，不要输出解释、Markdown 代码围栏或任何其他文字。"
    )
    user = "\n".join(
        [
            f"资料文件名：{source_hint}",
            f"需要抽取的实体：{schema['title']}（{target_entity}）",
            "",
            "字段要求：",
            *field_lines,
            "",
            "输出格式：JSON 数组，每个元素包含：",
            '- "payload"：上述字段组成的对象',
            f'- "source_locator"：该条信息在资料中的位置，格式为「{source_hint} 段N」或「{source_hint} PN」',
            '- "confidence"：high / medium / low',
            '- "review_note"：低置信度时说明原因，可选',
            "",
            "置信度判定：",
            "- high：原文明确写出数值与单位，且必需字段齐全",
            "- medium：数值由其他信息换算得出（如由容积×密度推算），或部分字段缺失",
            "- low：原文描述模糊、单位缺失、无法确定归属",
            "",
            "资料原文：",
            text,
        ]
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _to_float(value: Any, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        try:
            return float(cleaned)
        except ValueError as exc:
            raise ExtractionSchemaError(f"字段 {field} 无法转为数值：{value!r}") from exc
    raise ExtractionSchemaError(f"字段 {field} 类型不支持：{type(value).__name__}")


def validate_payload(target_entity: str, row: dict) -> dict:
    """校验并规范化一条抽取结果。不合格直接抛错，不做"尽力而为"的修补。"""
    schema = ENTITY_SCHEMAS.get(target_entity)
    if schema is None:
        raise ExtractionSchemaError(f"未知目标实体：{target_entity}")
    if not isinstance(row, dict):
        raise ExtractionSchemaError("抽取结果必须是对象")

    payload = row.get("payload") if isinstance(row.get("payload"), dict) else row

    if not row.get("source_locator"):
        raise ExtractionSchemaError("缺少 source_locator：抽取结果必须可追溯到原文位置")
    confidence = row.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        raise ExtractionSchemaError(f"confidence 取值非法：{confidence}")

    out: dict = {}
    for name, spec in schema["fields"].items():
        value = payload.get(name)
        if value in ("", "null"):
            value = None
        if value is None:
            if spec.get("required"):
                raise ExtractionSchemaError(f"缺少必填字段 {name}")
            out[name] = None
            continue
        if spec["type"] == "float":
            out[name] = _to_float(value, name)
        elif spec["type"] == "enum":
            if value not in spec["values"]:
                raise ExtractionSchemaError(
                    f"字段 {name} 取值 {value!r} 不在允许范围 {spec['values']}"
                )
            out[name] = value
        else:
            out[name] = str(value).strip()

    out["source_locator"] = str(row["source_locator"])
    out["confidence"] = confidence
    out["review_note"] = row.get("review_note")
    return out
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_extraction_prompts.py -v
```

预期：`8 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/extraction_prompts.py backend/tests/test_extraction_prompts.py
git commit -m "feat(extraction): 抽取提示词与结构校验（必带来源定位，Q/beta 不采信模型值）（任务 1/6）"
```

---

## 任务 2：抽取服务（调 AI → 校验 → 常量复核 → 落队列）

**文件：**

- 创建：`backend/app/services/extraction_service.py`
- 测试：`backend/tests/test_extraction_service.py`

**本任务的代码结构本身就是一条约束：** 它没有任何写业务表的路径，只能 `create_item` 产出 `pending` 条目。"未经人工确认不得入库"是靠结构保证的，不靠自觉。

- [ ] **步骤 1：编写失败的测试**

```python
"""抽取服务：解析模型输出、常量表复核、落队列。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.extraction_service import (
    extract_candidates,
    parse_model_json,
    reconcile_with_constants,
)


def test_parse_model_json_tolerates_code_fence():
    raw = '```json\n[{"payload": {"name": "罐区A"}, "confidence": "high"}]\n```'
    rows = parse_model_json(raw)
    assert rows[0]["payload"]["name"] == "罐区A"


def test_parse_model_json_handles_single_object():
    rows = parse_model_json('{"payload": {"name": "X"}, "confidence": "high"}')
    assert len(rows) == 1


def test_parse_model_json_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_model_json("模型今天不想干活")


def _cq(name, q):
    c = MagicMock()
    c.chemical_name = name
    c.critical_t = q
    return c


def _beta(name=None, beta="4.0", table="3"):
    b = MagicMock()
    b.chemical_name = name
    b.beta = beta
    b.source_table = table
    return b


def test_reconcile_fills_q_and_beta_from_constants():
    """模型给的 Q/beta 一律不采信；能查表就填表值。"""
    row = {
        "chemical_name": "氯",
        "q_design_max": 5.0,
        "critical_quantity_t": 999.0,
        "beta": 1.0,
        "source_locator": "报告.pdf 段1",
        "confidence": "high",
    }
    out = reconcile_with_constants(
        row, critical_rows=[_cq("氯", 5)], beta_rows=[_beta(name="氯", beta="4.0")]
    )
    assert out["critical_quantity_t"] == 5
    assert out["beta"] == 4.0
    assert out["confidence"] == "high"


def test_reconcile_downgrades_when_not_found():
    row = {
        "chemical_name": "某种混合物",
        "q_design_max": 3.0,
        "critical_quantity_t": 1.0,
        "beta": 2.0,
        "source_locator": "报告.pdf 段9",
        "confidence": "high",
    }
    out = reconcile_with_constants(row, critical_rows=[], beta_rows=[])
    assert out["critical_quantity_t"] is None
    assert out["beta"] is None
    assert out["confidence"] == "low", "查不到法定值时必须降级"
    assert "临界量" in out["review_note"]


def _empty_db():
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_extract_candidates_writes_pending_items():
    ai_json = json.dumps(
        [
            {
                "payload": {"chemical_name": "氯", "q_design_max": 5},
                "source_locator": "报告.pdf 段1",
                "confidence": "high",
            }
        ],
        ensure_ascii=False,
    )
    created: list = []

    async def fake_create(db, **kwargs):
        created.append(kwargs)
        return {"created": True, "item_id": "i1"}

    with patch(
        "app.services.extraction_service.llm_text_completion",
        new=AsyncMock(return_value=ai_json),
    ), patch("app.services.extraction_service.create_item", side_effect=fake_create):
        out = await extract_candidates(
            _empty_db(),
            job_id="j1",
            source_id="s1",
            target_entity="major_hazard_unit_chemical",
            text="罐区A 储存氯 5 吨",
            filename="报告.pdf",
            ai_config=MagicMock(),
        )

    assert out["queued"] == 1
    assert created[0]["target_entity"] == "major_hazard_unit_chemical"
    assert created[0]["source_locator"] == "报告.pdf 段1"


@pytest.mark.asyncio
async def test_extract_candidates_skips_invalid_rows():
    """单条结构不合法只跳过该条，不让整批抽取失败。"""
    ai_json = json.dumps(
        [
            {"payload": {"chemical_name": "氯", "q_design_max": 5}, "source_locator": "a", "confidence": "high"},
            {"payload": {"chemical_name": "缺数量"}, "source_locator": "b", "confidence": "high"},
        ],
        ensure_ascii=False,
    )
    calls: list = []

    async def fake_create(db, **kwargs):
        calls.append(kwargs)
        return {"created": True, "item_id": "i"}

    with patch(
        "app.services.extraction_service.llm_text_completion",
        new=AsyncMock(return_value=ai_json),
    ), patch("app.services.extraction_service.create_item", side_effect=fake_create):
        out = await extract_candidates(
            _empty_db(),
            job_id="j1",
            source_id="s1",
            target_entity="major_hazard_unit_chemical",
            text="x",
            filename="报告.pdf",
            ai_config=MagicMock(),
        )

    assert out["queued"] == 1
    assert out["invalid"] == 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_extraction_service.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""AI 抽取服务：把资料文本抽成结构化候选，落进 DataHub 待确认队列。

**本模块没有任何写业务表的路径**——只调 create_item 产出 pending 条目。
这是"未经人工确认不得入库"在代码结构上的保证。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.standard_constants import CriticalQuantity, HazardBetaFactor
from app.services.extraction_prompts import (
    ExtractionSchemaError,
    build_messages,
    validate_payload,
)
from app.services.ingest_service import build_idempotency_key, create_item
from app.services.llm_client import llm_text_completion

logger = logging.getLogger("extraction_service")

STANDARD = "GB18218-2018"
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def parse_model_json(raw: str) -> list[dict]:
    """解析模型输出。容忍代码围栏、单个对象、前后噪声。"""
    if not raw or not raw.strip():
        raise ValueError("模型返回为空")
    text = _FENCE.sub("", raw).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
        end = max(text.rfind("]"), text.rfind("}"))
        if start < 0 or end <= start:
            raise ValueError("模型输出不是合法 JSON") from None
        data = json.loads(text[start : end + 1])
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    raise ValueError("模型输出既不是对象也不是数组")


def reconcile_with_constants(
    row: dict,
    *,
    critical_rows: Sequence[CriticalQuantity],
    beta_rows: Sequence[HazardBetaFactor],
) -> dict:
    """用常量表复核 Q 与 β。

    **模型给的 Q/β 一律不采信。** Q 与 β 是 GB 18218 的法定查表值；
    查得到用表值，查不到留空并降级为 low，交人工指定危险性类别。
    """
    name = row.get("chemical_name")
    out = dict(row)

    q = None
    for c in critical_rows:
        if c.chemical_name == name and c.critical_t is not None:
            q = float(c.critical_t)
            break
    out["critical_quantity_t"] = q

    beta = None
    for b in beta_rows:
        if b.source_table == "3" and b.chemical_name == name:
            beta = float(b.beta)
            break
    out["beta"] = beta

    if q is None or beta is None:
        missing = []
        if q is None:
            missing.append("临界量")
        if beta is None:
            missing.append("校正系数 β")
        out["confidence"] = "low"
        out["review_note"] = (
            "、".join(missing) + "未能按标准查表得出，需人工指定危险性类别后补齐"
        )
    return out


async def _load_constants(db: AsyncSession, name: str):
    q_res = await db.execute(
        select(CriticalQuantity).where(
            CriticalQuantity.standard == STANDARD,
            CriticalQuantity.chemical_name == name,
        )
    )
    b_res = await db.execute(
        select(HazardBetaFactor).where(HazardBetaFactor.standard == STANDARD)
    )
    return list(q_res.scalars().all()), list(b_res.scalars().all())


async def extract_candidates(
    db: AsyncSession,
    *,
    job_id: str,
    source_id: str,
    target_entity: str,
    text: str,
    filename: str,
    ai_config,
    timeout: int = 120,
) -> dict:
    """抽取并落队列。返回 {queued, skipped, invalid}。"""
    messages = build_messages(target_entity=target_entity, text=text, source_hint=filename)
    raw = await llm_text_completion(messages, ai_config, timeout=timeout)
    try:
        rows = parse_model_json(raw)
    except ValueError as exc:
        raise ExtractionSchemaError(f"模型输出无法解析为 JSON：{exc}") from exc

    queued = skipped = invalid = 0
    for row in rows:
        try:
            valid = validate_payload(target_entity, row)
        except ExtractionSchemaError as exc:
            logger.warning("抽取结果结构不合法，已跳过：%s", exc)
            invalid += 1
            continue

        if target_entity == "major_hazard_unit_chemical":
            critical_rows, beta_rows = await _load_constants(db, valid.get("chemical_name"))
            valid = reconcile_with_constants(
                valid, critical_rows=critical_rows, beta_rows=beta_rows
            )

        key = build_idempotency_key(
            source_id=source_id,
            target=target_entity,
            external_id=valid.get("source_locator"),
            payload={k: v for k, v in valid.items() if k != "source_locator"},
        )
        out = await create_item(
            db,
            job_id=job_id,
            idempotency_key=key,
            raw_payload=valid,
            target_entity=target_entity,
            source_locator=valid.get("source_locator"),
            confidence=valid.get("confidence", "medium"),
        )
        if out["created"]:
            queued += 1
        else:
            skipped += 1
    return {"queued": queued, "skipped": skipped, "invalid": invalid}
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_extraction_service.py -v
```

预期：`7 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/extraction_service.py backend/tests/test_extraction_service.py
git commit -m "feat(extraction): 抽取服务（Q/beta 常量表复核，查不到即降级 low）（任务 2/6）"
```

---

## 任务 3：目标实体写入器（确认后落正式表）

**文件：**

- 创建：`backend/app/services/ingest_writers.py`
- 测试：`backend/tests/test_ingest_writers.py`

**这是抽取数据进入正式表的唯一通路**，由计划 5 的 `confirm_items` 调用。注册在应用启动时完成。

- [ ] **步骤 1：编写失败的测试**

```python
"""目标实体写入器：把确认后的载荷写进正式表。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ingest_service import TARGET_WRITERS, confirm_items
from app.services.ingest_writers import register_default_writers


def test_register_default_writers_registers_two_targets():
    register_default_writers()
    assert "major_hazard_unit" in TARGET_WRITERS
    assert "major_hazard_unit_chemical" in TARGET_WRITERS


@pytest.mark.asyncio
async def test_unit_writer_requires_enterprise_id():
    """缺 enterprise_id 时明确报错——单元必须挂在企业下。"""
    register_default_writers()
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    with pytest.raises(Exception) as ei:
        await TARGET_WRITERS["major_hazard_unit"](db, {"name": "罐区A", "unit_type": "storage"}, MagicMock())
    assert "enterprise" in str(ei.value).lower()


@pytest.mark.asyncio
async def test_unit_chemical_writer_requires_existing_unit():
    """按 unit_name 找单元；找不到明确报错，不静默丢弃。"""
    register_default_writers()
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        return res

    db.execute = execute
    with pytest.raises(Exception) as ei:
        await TARGET_WRITERS["major_hazard_unit_chemical"](
            db,
            {"unit_name": "不存在的单元", "chemical_name": "氯", "q_design_max": 5},
            MagicMock(),
        )
    assert "单元" in str(ei.value)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_writers.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""DataHub 目标实体写入器。

这些函数是**唯一**会把确认后的数据写进正式业务表的代码。
由确认流程调用，因此必须做完整的入参校验——走到这里的数据已经过人工确认，
失败意味着数据本身有问题或映射配错了，要显式报错而不是静默跳过。
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.major_hazard import MajorHazardUnit, MajorHazardUnitChemical
from app.services.ingest_service import register_target_writer

logger = logging.getLogger("ingest_writers")


class WriterPayloadError(ValueError):
    """确认后的载荷缺少写库所需字段。"""


async def write_major_hazard_unit(db: AsyncSession, payload: dict, item) -> str:
    enterprise_id = payload.get("enterprise_id")
    if not enterprise_id:
        raise WriterPayloadError("写入重大危险源单元需要 enterprise_id")
    name = payload.get("name")
    if not name:
        raise WriterPayloadError("写入重大危险源单元需要 name")
    unit_type = payload.get("unit_type")
    if unit_type not in ("production", "storage"):
        raise WriterPayloadError(f"unit_type 取值非法：{unit_type!r}")

    unit = MajorHazardUnit(
        enterprise_id=enterprise_id,
        name=name,
        unit_type=unit_type,
        boundary_desc=payload.get("boundary_desc"),
        address=payload.get("address"),
    )
    db.add(unit)
    await db.flush()
    return unit.id


async def write_major_hazard_unit_chemical(db: AsyncSession, payload: dict, item) -> str:
    unit_name = payload.get("unit_name")
    if not unit_name:
        raise WriterPayloadError("写入单元品种需要 unit_name 以确定归属单元")
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.name == unit_name))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise WriterPayloadError(f"未找到名称为「{unit_name}」的重大危险源单元")

    if payload.get("critical_quantity_t") is None:
        raise WriterPayloadError(
            f"「{payload.get('chemical_name')}」的临界量未确定，请先指定危险性类别"
        )
    if payload.get("beta") is None:
        raise WriterPayloadError(
            f"「{payload.get('chemical_name')}」的校正系数 β 未确定，请先指定危险性类别"
        )
    q = payload.get("q_design_max")
    if q is None:
        raise WriterPayloadError("缺少设计最大量 q_design_max")

    row = MajorHazardUnitChemical(
        unit_id=unit.id,
        chemical_name=payload["chemical_name"],
        physical_state=payload.get("physical_state"),
        q_design_max=Decimal(str(q)),
        critical_quantity_t=Decimal(str(payload["critical_quantity_t"])),
        beta=Decimal(str(payload["beta"])),
        beta_source=payload.get("beta_source") or "table3",
    )
    db.add(row)
    await db.flush()
    return row.id


_REGISTERED = False


def register_default_writers() -> None:
    """注册内置写入器。应用启动时调用一次即可，重复调用无害。"""
    global _REGISTERED
    register_target_writer("major_hazard_unit", write_major_hazard_unit)
    register_target_writer("major_hazard_unit_chemical", write_major_hazard_unit_chemical)
    _REGISTERED = True
    logger.info("DataHub 目标写入器已注册：major_hazard_unit / major_hazard_unit_chemical")
```

- [ ] **步骤 4：在应用启动时注册**

在 `backend/app/main.py` 的 lifespan/startup 段（与 `migration_runner` 调用同处）追加：

```python
from app.services.ingest_writers import register_default_writers
register_default_writers()
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_writers.py -v
```

预期：`3 passed`

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/ingest_writers.py backend/app/main.py backend/tests/test_ingest_writers.py
git commit -m "feat(extraction): 目标实体写入器（确认后落正式表，唯一通路）（任务 3/6）"
```

---

## 任务 4：表格列映射建议（schema matching）

**文件：**

- 创建：`backend/app/services/schema_matching.py`
- 测试：`backend/tests/test_schema_matching.py`

**目的：** 客户上传的 Excel 列名千奇百怪（"品名/物料名称/危险化学品"都指同一个字段）。让 AI 建议列到字段的映射，人工确认后存进 `field_mappings` 复用。

- [ ] **步骤 1：编写失败的测试**

```python
"""列映射建议：AI 建议 + 白名单过滤 + 兜底精确匹配。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.schema_matching import suggest_mapping, validate_mapping


def test_validate_mapping_drops_unknown_targets():
    """只保留目标实体允许的字段——防止把任意字段写进业务表。"""
    out = validate_mapping(
        "major_hazard_unit_chemical",
        {"品名": "chemical_name", "数量": "q_design_max", "胡写": "evil_field"},
    )
    assert out == {"品名": "chemical_name", "数量": "q_design_max"}


def test_validate_mapping_drops_duplicate_targets():
    """两个源列映射到同一目标字段时，保留第一个，避免歧义。"""
    out = validate_mapping(
        "major_hazard_unit_chemical",
        {"品名": "chemical_name", "名称": "chemical_name"},
    )
    assert out == {"品名": "chemical_name"}


@pytest.mark.asyncio
async def test_suggest_mapping_falls_back_to_exact_match_on_ai_failure():
    """AI 不可用时退回精确匹配，不能整体失败——映射本来就是人工确认的。"""
    with patch(
        "app.services.schema_matching.llm_text_completion",
        new=AsyncMock(side_effect=RuntimeError("AI 挂了")),
    ):
        out = await suggest_mapping(
            headers=["chemical_name", "q_design_max", "备注"],
            target_entity="major_hazard_unit_chemical",
            ai_config=None,
        )
    assert out["mapping"]["chemical_name"] == "chemical_name"
    assert out["mapping"]["q_design_max"] == "q_design_max"
    assert out["source"] == "exact"


@pytest.mark.asyncio
async def test_suggest_mapping_returns_ai_result_when_available():
    import json

    ai = json.dumps({"品名": "chemical_name", "设计最大量": "q_design_max"}, ensure_ascii=False)
    with patch(
        "app.services.schema_matching.llm_text_completion",
        new=AsyncMock(return_value=ai),
    ):
        out = await suggest_mapping(
            headers=["品名", "设计最大量"],
            target_entity="major_hazard_unit_chemical",
            ai_config=object(),
        )
    assert out["source"] == "ai"
    assert out["mapping"]["品名"] == "chemical_name"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_schema_matching.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""表格列 → 目标字段的映射建议。

AI 只是"建议"，产出必须经 validate_mapping 过滤后再由人工确认。
AI 不可用时退回精确匹配——映射本来就是人工确认的环节，不值得为它硬失败。
"""

from __future__ import annotations

import json
import logging

from app.services.extraction_prompts import ENTITY_SCHEMAS
from app.services.llm_client import llm_text_completion

logger = logging.getLogger("schema_matching")


def allowed_targets(target_entity: str) -> list[str]:
    schema = ENTITY_SCHEMAS.get(target_entity)
    if schema is None:
        return []
    return list(schema["fields"].keys())


def validate_mapping(target_entity: str, mapping: dict) -> dict:
    """只保留合法目标字段，并去重（同一目标字段只接受第一个源列）。"""
    allowed = set(allowed_targets(target_entity))
    out: dict = {}
    used: set[str] = set()
    for src, target in (mapping or {}).items():
        if target not in allowed or target in used:
            continue
        out[src] = target
        used.add(target)
    return out


def _exact_match(headers: list[str], target_entity: str) -> dict:
    """列名与目标字段同名时直接匹配（英文表头或已规范化的中文表）。"""
    allowed = set(allowed_targets(target_entity))
    return {h: h for h in headers if h in allowed}


async def suggest_mapping(
    *,
    headers: list[str],
    target_entity: str,
    ai_config,
    timeout: int = 60,
) -> dict:
    """返回 {mapping, source}，source ∈ {ai, exact}。"""
    allowed = allowed_targets(target_entity)
    if not allowed:
        return {"mapping": {}, "source": "exact"}

    if ai_config is not None:
        prompt = "\n".join(
            [
                f"目标字段（只能从这里选）：{allowed}",
                f"表格列名：{headers}",
                "",
                "请给出列名到目标字段的映射，只输出 JSON 对象，键为列名、值为目标字段；",
                "无法对应的列不要出现在结果里。不要输出任何其他文字。",
            ]
        )
        try:
            raw = await llm_text_completion(
                [
                    {"role": "system", "content": "你是数据表结构对齐助手，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                ai_config,
                timeout=timeout,
            )
            text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            proposed = json.loads(text)
            if isinstance(proposed, dict):
                mapping = validate_mapping(target_entity, proposed)
                if mapping:
                    return {"mapping": mapping, "source": "ai"}
        except Exception:
            logger.warning("AI 列映射建议失败，退回精确匹配", exc_info=True)

    return {"mapping": _exact_match(headers, target_entity), "source": "exact"}
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_schema_matching.py -v
```

预期：`4 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/schema_matching.py backend/tests/test_schema_matching.py
git commit -m "feat(extraction): 表格列映射建议（白名单过滤 + AI 不可用退回精确匹配）（任务 4/6）"
```

---

## 任务 5：API 与路由

**文件：**

- 创建：`backend/app/schemas/extraction.py`
- 创建：`backend/app/routers/extraction.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_extraction_api.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""抽取相关端点测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import extraction


def _client(handler):
    app = FastAPI()
    app.include_router(extraction.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        db.add = MagicMock()
        yield db

    async def _user():
        u = MagicMock()
        u.id = "user1"
        return u

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_suggest_mapping_endpoint():
    async def handler(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        return res

    client = _client(handler)
    with patch(
        "app.routers.extraction.suggest_mapping",
        new=AsyncMock(return_value={"mapping": {"品名": "chemical_name"}, "source": "ai"}),
    ):
        resp = client.post(
            "/api/v1/extraction/suggest-mapping",
            json={"headers": ["品名"], "target_entity": "major_hazard_unit_chemical"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["mapping"]["品名"] == "chemical_name"


def test_extract_endpoint_rejects_unknown_target():
    async def handler(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        return res

    client = _client(handler)
    resp = client.post(
        "/api/v1/extraction/run",
        json={"job_id": "j1", "source_id": "s1", "target_entity": "no_such", "text": "x", "filename": "f.pdf"},
    )
    assert resp.status_code == 422


def test_extract_endpoint_returns_queued_counts():
    async def handler(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = MagicMock()  # 有 AI 配置
        return res

    client = _client(handler)
    with patch(
        "app.routers.extraction.extract_candidates",
        new=AsyncMock(return_value={"queued": 5, "skipped": 1, "invalid": 0}),
    ):
        resp = client.post(
            "/api/v1/extraction/run",
            json={
                "job_id": "j1",
                "source_id": "s1",
                "target_entity": "major_hazard_unit",
                "text": "罐区A",
                "filename": "报告.pdf",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["queued"] == 5
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_extraction_api.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写 schemas 与路由**

```python
"""抽取相关出入参。"""

from typing import Optional

from pydantic import BaseModel, Field


class SuggestMappingIn(BaseModel):
    headers: list[str] = Field(min_length=1)
    target_entity: str = Field(min_length=1, max_length=60)


class RunExtractionIn(BaseModel):
    job_id: str
    source_id: str
    target_entity: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=1)
    filename: str = Field(min_length=1, max_length=300)
```

```python
"""抽取 API：列映射建议、触发抽取、上传解析。"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.extraction import RunExtractionIn, SuggestMappingIn
from app.services.ai_config_service import get_system_ai_config
from app.services.extraction_prompts import ENTITY_SCHEMAS, ExtractionSchemaError
from app.services.extraction_service import extract_candidates
from app.services.file_parser import parse_file_text
from app.services.schema_matching import suggest_mapping

router = APIRouter(prefix="/extraction", tags=["Extraction"])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.post("/suggest-mapping")
async def api_suggest_mapping(payload: SuggestMappingIn, db: AsyncSession = Depends(get_db)):
    """给出「表格列 → 目标字段」的映射建议。AI 不可用时退回精确匹配。"""
    ai_config = await get_system_ai_config(db)
    out = await suggest_mapping(
        headers=payload.headers, target_entity=payload.target_entity, ai_config=ai_config
    )
    return _ok(out)


@router.post("/run")
async def api_run_extraction(payload: RunExtractionIn, db: AsyncSession = Depends(get_db)):
    """对已解析的文本执行抽取，结果落 DataHub 待确认队列。"""
    if payload.target_entity not in ENTITY_SCHEMAS:
        raise HTTPException(422, f"未知目标实体：{payload.target_entity}")
    ai_config = await get_system_ai_config(db)
    if ai_config is None:
        raise HTTPException(400, "尚未配置系统级 AI 模型，请先在系统设置中配置")
    try:
        out = await extract_candidates(
            db,
            job_id=payload.job_id,
            source_id=payload.source_id,
            target_entity=payload.target_entity,
            text=payload.text,
            filename=payload.filename,
            ai_config=ai_config,
        )
    except ExtractionSchemaError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)


@router.post("/parse-file")
async def api_parse_file(file: UploadFile = File(...)):
    """上传文件并转成文本，返回文本供前端预览后再触发抽取。"""
    data = await file.read()
    if not data:
        raise HTTPException(422, "文件为空")
    try:
        text = parse_file_text(file.filename or "upload", data)
    except Exception as exc:
        raise HTTPException(422, f"文件解析失败：{exc}") from exc
    return _ok({"filename": file.filename, "chars": len(text), "text": text})
```

- [ ] **步骤 4：注册路由**

`backend/app/main.py` 第 14 行 import 列表末尾加 `, extraction`；在 `app.include_router(ingest.router, prefix="/api/v1")` 之后加：

```python
app.include_router(extraction.router, prefix="/api/v1")
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_extraction_api.py tests/test_extraction_service.py tests/test_extraction_prompts.py tests/test_schema_matching.py tests/test_ingest_writers.py -q
```

预期：`25 passed`

- [ ] **步骤 6：跑后端全量**

运行：

```bash
cd backend && python -m pytest tests/ -q
```

预期：失败数不高于 4 个既有失败

- [ ] **步骤 7：Commit**

```bash
git add backend/app/schemas/extraction.py backend/app/routers/extraction.py backend/app/main.py backend/tests/test_extraction_api.py
git commit -m "feat(extraction): 抽取 API（映射建议/触发抽取/文件解析）（任务 5/6）"
```

---

## 任务 6：前端导入页

**文件：**

- 创建：`frontend/src/services/extractionService.ts`
- 创建：`frontend/src/pages/Settings/DataHubImportPage.tsx`
- 修改：`frontend/src/routes/index.tsx`

- [ ] **步骤 1：service 层**

```ts
// frontend/src/services/extractionService.ts
import api from "./api";
import type { ApiResponse } from "@/types/common";

const BASE = "/extraction";

export const parseFile = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return api
    .post<ApiResponse<{ filename: string; chars: number; text: string }>>(
      `${BASE}/parse-file`,
      fd,
    )
    .then((r) => r.data.data);
};

export const suggestMapping = (headers: string[], targetEntity: string) =>
  api
    .post<ApiResponse<{ mapping: Record<string, string>; source: "ai" | "exact" }>>(
      `${BASE}/suggest-mapping`,
      { headers, target_entity: targetEntity },
    )
    .then((r) => r.data.data);

export const runExtraction = (payload: {
  job_id: string;
  source_id: string;
  target_entity: string;
  text: string;
  filename: string;
}) =>
  api
    .post<ApiResponse<{ queued: number; skipped: number; invalid: number }>>(
      `${BASE}/run`,
      payload,
    )
    .then((r) => r.data.data);
```

- [ ] **步骤 2：实现导入页**

四步式向导（`Steps` 组件）：

1. **选目标实体**：`major_hazard_unit`（抽单元）/ `major_hazard_unit_chemical`（抽品种存量）
2. **上传文件**：`Upload.Dragger`，接受 `.pdf/.docx/.xlsx/.csv`；上传后调 `parseFile`，展示字符数与文本前 500 字预览
3. **确认映射**（仅表格类文件显示）：调 `suggestMapping(表头, target_entity)`，展示建议来源（`ai` / `exact`）+ 可编辑的列→字段映射表；**必填字段未映射时禁止下一步**
4. **触发抽取**：调 `runExtraction`，完成后展示 `已入队 N 条 / 跳过 M 条 / 结构不合法 K 条`，并给「去待确认队列」按钮跳到 `/settings/data-hub/:jobId/review`

> 表格类文件的目标实体若为 `major_hazard_unit_chemical`，`unit_name` 字段无对应源列是正常的
> （单元归属靠人工在队列页确认），不要因此阻断流程。

- [ ] **步骤 3：注册路由**

`frontend/src/routes/index.tsx` 追加 `/settings/data-hub/import → DataHubImportPage`。
并在 `DataHubPage` 顶部加「导入资料」按钮指向该页。

- [ ] **步骤 4：验证**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
```

预期：`tsc` exit 0；vitest 全绿

- [ ] **步骤 5：真实浏览器端到端（需配置可用的 AI 模型）**

1. 上传一份含「罐区A / 甲醇 / 79 吨」的 PDF 或 DOCX
2. 选目标实体 `major_hazard_unit_chemical`，走完 4 步
3. 确认入队条数 > 0，点「去待确认队列」能看到条目，且**每条都有来源定位**
4. **降级验证**：把 AI 配置清空后再走一次 → 应提示"尚未配置系统级 AI 模型"，而不是 500
5. **确定性验证**：同一份文件再导一次 → `跳过` 数 = 上次的 `入队` 数（幂等生效）

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/services/extractionService.ts frontend/src/pages/Settings/DataHubImportPage.tsx frontend/src/routes/index.tsx
git commit -m "feat(extraction): 资料导入向导（上传→映射→抽取→去确认）（任务 6/6）"
```

---

## 验收清单

- [ ] `cd backend && python -m pytest tests/ -q` 失败数不高于 4 个既有失败
- [ ] `docker exec -w /app emergency-plan-frontend npx tsc -b` exit 0，vitest 全绿
- [ ] **抽取函数无写业务表能力**：代码审查确认 `extraction_service.py` 只 import `create_item`，不 import 任何业务模型
- [ ] **Q 与 β 来自查表**：模型故意返回错误的 Q/β 时，入库值必须是常量表的值
- [ ] **查不到即降级**：表1/表3 都查不到的物质，条目 `confidence='low'` 且 `review_note` 说明需人工指定类别
- [ ] **写入器是唯一通路**：确认后数据才出现在 `major_hazard_units` / `major_hazard_unit_chemicals`
- [ ] **缺临界量拒绝写入**：确认一条 `critical_quantity_t=None` 的品种，应返回明确错误而不是写入 NULL
- [ ] **映射白名单**：AI 建议里混入不存在的目标字段时，`validate_mapping` 会剔掉
- [ ] **端到端**：上传 → 抽取 → 队列显示来源定位与置信度 → 确认 → 台账可见
- [ ] **幂等**：同文件重复导入，队列不新增重复条目

## 未纳入本计划

- **定时拉取（api_pull）调度器**：`ingest_sources.source_type` 已预留该类型，但调度接入留到有真实外部系统对接需求时再做（YAGNI）
- **图片型 PDF 的 OCR 抽取**：现有 `vision_helpers.py` 有 RapidOCR 能力，但本计划只处理文本层可解析的资料
- **单元与危化品台账的自动关联**：抽取出的品种写入 `major_hazard_unit_chemicals` 时暂不填 `chemical_id`；台账关联属计划 7
- **抽取质量看板**（各来源的入队/入库/失败率）：属计划 10
