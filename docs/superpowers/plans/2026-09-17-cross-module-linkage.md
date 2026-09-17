# 跨模块关联打通实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把重大危险源接到已有模块上，形成「风险 → 重大危险源 → 隐患 → 预案」的证据链：单元关联风险点与平面图落点、单元品种关联危化品台账（含设计最大量初值带出）、隐患可关联单元、预案生成时引用重大危险源清单。

**架构：** 不新建模块，只在既有关系上加"最后一根线"。多数关联字段（`major_hazard_units.risk_object_id` / `floor_id` / `polygon`、`major_hazard_unit_chemicals.chemical_id`）在计划 1 建表时已预留，本计划做的是**让它们在界面上可操作、在数据上自动流转**。

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x / React 18 / antd 5 / Konva（四色图工作台既有）。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §6.5、§9

**依赖：** 计划 1（已完成）、计划 3（前端，本计划在其页面上加关联交互）。

**视觉走查确认的第 4 条约束（本计划落地）：** `q_design_max` 从危化品台账 `max_storage` 带出初值 + **强制人工确认**，界面标注"设计最大量口径，通常 ≥ 台账最大储存量"。计划 3 里只做了提示与手填，本计划接上台账后实现真正的带出。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/app/services/major_hazard_linkage.py`（新建） | 关联读写：风险点、台账条目 |
| `backend/app/services/major_hazard_context.py`（新建） | 预案上下文：重大危险源摘要 |
| `backend/app/routers/major_hazard.py`（修改） | 新增关联相关端点 |
| `backend/db_migration_20260917_hazard_unit_link.sql`（新建） | `hazard_records` 增加来源单元字段 |
| `backend/app/models/hazard_management.py`（修改） | `HazardRecord` 增加 `major_hazard_unit_id` |
| `backend/app/services/risk_context_builder.py`（修改） | 预案生成上下文注入重大危险源摘要 |
| `backend/tests/test_major_hazard_linkage.py`（新建） | 关联服务测试 |
| `backend/tests/test_major_hazard_context.py`（新建） | 上下文摘要测试 |
| `frontend/src/components/enterprise/majorHazard/RiskObjectPicker.tsx`（新建） | 风险点选择器 |
| `frontend/src/components/enterprise/majorHazard/ChemicalLibraryPicker.tsx`（新建） | 台账条目选择器 + 初值带出 |
| `frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx`（修改） | 接入两个选择器 + 平面图落点 |

**既有约定**

- 四色图多边形结构见 `app/models/risk_management.py` 的 `RiskZone.floor_plan_polygon` 与 `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
- 风险点即 `RiskObject`（`is_risk_point=True`），数据在 `risk_objects`
- 危化品台账 `HazardousChemical` 已有 `storage_amount` / `storage_unit`（计划 1 任务 8 加的），`max_storage` 为原始文本
- 预案生成上下文由 `app/services/risk_context_builder.py` 组装

---

## 任务 1：单元 ↔ 风险点关联

**文件：**

- 创建：`backend/app/services/major_hazard_linkage.py`
- 修改：`backend/app/routers/major_hazard.py`
- 测试：`backend/tests/test_major_hazard_linkage.py`

**为什么必须做同企业校验：** 关联一旦跨企业，A 企业用户就能通过界面看到 B 企业的风险点名称；在多企业部署下这是数据越界，属于安全事故级别的 bug，不是"边界情况"。

- [ ] **步骤 1：编写失败的测试**

```python
"""跨模块关联：风险点、台账条目。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.major_hazard_linkage import (
    LinkageError,
    link_risk_object,
    list_linkable_risk_objects,
)


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


def _db(unit=None, objects=None):
    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit] if unit else [])
        if "risk_objects" in text:
            return _Result(objects or [])
        return _Result([])

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_link_risk_object_sets_field():
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    unit.risk_object_id = None
    obj = MagicMock()
    obj.id = "o1"
    obj.enterprise_id = "e1"
    db = _db(unit=unit, objects=[obj])

    await link_risk_object(db, unit_id="u1", risk_object_id="o1")
    assert unit.risk_object_id == "o1"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_link_risk_object_rejects_cross_enterprise():
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    obj = MagicMock()
    obj.id = "o2"
    obj.enterprise_id = "e2"
    db = _db(unit=unit, objects=[obj])
    with pytest.raises(LinkageError) as ei:
        await link_risk_object(db, unit_id="u1", risk_object_id="o2")
    assert "企业" in str(ei.value)


@pytest.mark.asyncio
async def test_link_risk_object_allows_clearing():
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    unit.risk_object_id = "o1"
    db = _db(unit=unit, objects=[])
    await link_risk_object(db, unit_id="u1", risk_object_id=None)
    assert unit.risk_object_id is None


@pytest.mark.asyncio
async def test_list_linkable_objects_filters_by_enterprise():
    obj = MagicMock()
    obj.id = "o1"
    obj.name = "罐区A风险点"
    obj.zone_id = "z1"
    obj.floor_id = "f1"
    db = _db(objects=[obj])
    out = await list_linkable_risk_objects(db, enterprise_id="e1")
    assert out[0]["id"] == "o1"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_linkage.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.major_hazard_linkage'`

- [ ] **步骤 3：编写实现**

```python
"""重大危险源与既有模块的关联读写。

关联必须做**同企业校验**——跨企业关联会造成数据越界，
在多企业部署下是安全事故级别的 bug。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.major_hazard import MajorHazardUnit, MajorHazardUnitChemical
from app.models.risk_management import RiskObject


class LinkageError(ValueError):
    """关联操作非法（跨企业、目标不存在等）。"""


async def link_risk_object(
    db: AsyncSession,
    *,
    unit_id: str,
    risk_object_id: Optional[str],
) -> dict:
    """把单元关联到风险点；传 None 表示解除关联。"""
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise LinkageError("重大危险源单元不存在")

    if risk_object_id is None:
        unit.risk_object_id = None
        await db.commit()
        return {"unit_id": unit_id, "risk_object_id": None}

    obj_res = await db.execute(select(RiskObject).where(RiskObject.id == risk_object_id))
    obj = obj_res.scalar_one_or_none()
    if obj is None:
        raise LinkageError("风险点不存在")
    if getattr(obj, "enterprise_id", None) != unit.enterprise_id:
        raise LinkageError("风险点与单元不属于同一企业，禁止关联")
    unit.risk_object_id = risk_object_id
    await db.commit()
    return {"unit_id": unit_id, "risk_object_id": risk_object_id}


async def list_linkable_risk_objects(db: AsyncSession, *, enterprise_id: str) -> list[dict]:
    """列出可关联的风险点（本企业、标记为风险点的对象）。"""
    res = await db.execute(
        select(RiskObject).where(
            RiskObject.enterprise_id == enterprise_id,
            RiskObject.is_risk_point.is_(True),
        )
    )
    return [
        {
            "id": o.id,
            "name": o.name,
            "zone_id": getattr(o, "zone_id", None),
            "floor_id": getattr(o, "floor_id", None),
        }
        for o in res.scalars().all()
    ]
```

- [ ] **步骤 4：加端点**

在 `backend/app/routers/major_hazard.py` 顶部补 import，并追加：

```python
from pydantic import BaseModel

from app.services.major_hazard_linkage import (
    LinkageError,
    link_risk_object,
    list_linkable_risk_objects,
)


class LinkRiskObjectIn(BaseModel):
    risk_object_id: Optional[str] = None


@router.get("/linkable/risk-objects")
async def api_list_linkable_risk_objects(
    enterprise_id: str = Query(...), db: AsyncSession = Depends(get_db)
):
    return _ok(await list_linkable_risk_objects(db, enterprise_id=enterprise_id))


@router.put("/units/{unit_id}/risk-object")
async def api_link_risk_object(
    unit_id: str, payload: LinkRiskObjectIn, db: AsyncSession = Depends(get_db)
):
    try:
        out = await link_risk_object(db, unit_id=unit_id, risk_object_id=payload.risk_object_id)
    except LinkageError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_linkage.py -v
```

预期：`4 passed`

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/major_hazard_linkage.py backend/app/routers/major_hazard.py backend/tests/test_major_hazard_linkage.py
git commit -m "feat(linkage): 单元关联风险点（含同企业校验）（任务 1/5）"
```

---

## 任务 2：单元品种 ↔ 危化品台账（含设计最大量初值带出）

**文件：**

- 修改：`backend/app/services/major_hazard_linkage.py`
- 修改：`backend/app/routers/major_hazard.py`
- 测试：`backend/tests/test_major_hazard_linkage.py`（追加）

**这是视觉走查第 4 条约束的落地。** 注意服务层的措辞：它返回的是 **suggested_q（建议初值）+ requires_confirmation=true**，**自身不写库**。真正落库要等用户在界面上确认后调品种保存接口。这条设计的理由是设计最大量与台账最大储存量在原标准里是两个口径，直接采用会算小导致漏判。

- [ ] **步骤 1：编写失败的测试（追加到 `test_major_hazard_linkage.py`，顶部补 `from decimal import Decimal`）**

```python
from decimal import Decimal

from app.services.major_hazard_linkage import (
    link_unit_chemical_to_ledger,
    suggest_design_max_from_ledger,
)


def _db_chem(chem):
    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        return _Result([chem])

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_suggest_design_max_uses_structured_amount_first():
    chem = MagicMock()
    chem.id = "c1"
    chem.enterprise_id = "e1"
    chem.name = "甲醇"
    chem.storage_amount = Decimal("40")
    chem.storage_unit = "t"
    chem.max_storage = "最大储存量 40 吨"
    db = _db_chem(chem)

    out = await suggest_design_max_from_ledger(db, chemical_id="c1", enterprise_id="e1")
    assert out["suggested_q"] == 40.0
    assert out["ledger_text"] == "最大储存量 40 吨"
    assert "设计最大量" in out["hint"]
    assert out["requires_confirmation"] is True
    assert out["source"] == "structured"


@pytest.mark.asyncio
async def test_suggest_design_max_parses_text_when_structured_missing():
    chem = MagicMock()
    chem.id = "c2"
    chem.enterprise_id = "e1"
    chem.name = "氯"
    chem.storage_amount = None
    chem.storage_unit = None
    chem.max_storage = "5t"
    db = _db_chem(chem)
    out = await suggest_design_max_from_ledger(db, chemical_id="c2", enterprise_id="e1")
    assert out["suggested_q"] == 5.0
    assert out["source"] == "text"


@pytest.mark.asyncio
async def test_suggest_design_max_returns_none_when_unparseable():
    """解析不出来就返回 None，不猜测。"""
    chem = MagicMock()
    chem.id = "c3"
    chem.enterprise_id = "e1"
    chem.name = "某物"
    chem.storage_amount = None
    chem.storage_unit = None
    chem.max_storage = "见台账"
    db = _db_chem(chem)
    out = await suggest_design_max_from_ledger(db, chemical_id="c3", enterprise_id="e1")
    assert out["suggested_q"] is None
    assert out["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_suggest_design_max_rejects_cross_enterprise():
    chem = MagicMock()
    chem.id = "c4"
    chem.enterprise_id = "e2"
    db = _db_chem(chem)
    with pytest.raises(LinkageError):
        await suggest_design_max_from_ledger(db, chemical_id="c4", enterprise_id="e1")
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_linkage.py -q
```

预期：`ImportError: cannot import name 'suggest_design_max_from_ledger'`

- [ ] **步骤 3：编写实现（追加到 `major_hazard_linkage.py`）**

```python
from decimal import Decimal

from app.models.hazardous_chemicals import HazardousChemical
from app.services.chemical_storage_parser import parse_storage_text

DESIGN_MAX_HINT = (
    "设计最大量按 GB 18218-2018 4.2.2 确定：储罐及其他容器、设备或仓储区的"
    "实际存在量按设计最大量计，通常 ≥ 台账登记的最大储存量。请核对后确认。"
)


async def suggest_design_max_from_ledger(
    db: AsyncSession,
    *,
    chemical_id: str,
    enterprise_id: str,
) -> dict:
    """从危化品台账给设计最大量一个**建议初值**，由界面人工确认。

    本函数不写库。设计最大量与台账最大储存量在标准里是两个口径
    （前者按设备设计容积/额定充装量），直接采用会算小导致漏判。
    """
    res = await db.execute(select(HazardousChemical).where(HazardousChemical.id == chemical_id))
    chem = res.scalar_one_or_none()
    if chem is None:
        raise LinkageError("危化品台账条目不存在")
    if getattr(chem, "enterprise_id", None) != enterprise_id:
        raise LinkageError("危化品台账条目与单元不属于同一企业，禁止关联")

    if getattr(chem, "storage_amount", None) is not None:
        suggested = float(chem.storage_amount)
        source = "structured"
    else:
        value, _unit = parse_storage_text(getattr(chem, "max_storage", None))
        suggested = value
        source = "text"

    return {
        "chemical_id": chemical_id,
        "chemical_name": chem.name,
        "suggested_q": suggested,
        "ledger_text": getattr(chem, "max_storage", None),
        "source": source,
        "hint": DESIGN_MAX_HINT,
        "requires_confirmation": True,
    }


async def link_unit_chemical_to_ledger(
    db: AsyncSession,
    *,
    unit_chemical_id: str,
    chemical_id: Optional[str],
) -> dict:
    """把单元品种行关联到危化品台账条目（只写引用，**不改数量**）。"""
    res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.id == unit_chemical_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise LinkageError("单元品种行不存在")
    row.chemical_id = chemical_id
    await db.commit()
    return {"unit_chemical_id": unit_chemical_id, "chemical_id": chemical_id}
```

- [ ] **步骤 4：加端点**

在 `backend/app/routers/major_hazard.py` 追加：

```python
class LinkChemicalIn(BaseModel):
    chemical_id: Optional[str] = None


@router.get("/ledger/chemicals")
async def api_list_ledger_chemicals(
    enterprise_id: str = Query(...), db: AsyncSession = Depends(get_db)
):
    """列出本企业危化品台账条目，供单元品种关联选择。"""
    from app.models.hazardous_chemicals import HazardousChemical

    res = await db.execute(
        select(HazardousChemical)
        .where(HazardousChemical.enterprise_id == enterprise_id)
        .order_by(HazardousChemical.name)
    )
    return _ok(
        [
            {
                "id": c.id,
                "name": c.name,
                "cas_no": c.cas_no,
                "max_storage": c.max_storage,
                "storage_amount": (
                    float(c.storage_amount)
                    if getattr(c, "storage_amount", None) is not None
                    else None
                ),
                "storage_unit": c.storage_unit,
            }
            for c in res.scalars().all()
        ]
    )


@router.get("/ledger/chemicals/{chemical_id}/suggest-design-max")
async def api_suggest_design_max(
    chemical_id: str,
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """返回设计最大量的建议初值 + 口径提示（需人工确认后才写入）。"""
    try:
        out = await suggest_design_max_from_ledger(
            db, chemical_id=chemical_id, enterprise_id=enterprise_id
        )
    except LinkageError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)


@router.put("/unit-chemicals/{unit_chemical_id}/ledger-link")
async def api_link_unit_chemical(
    unit_chemical_id: str,
    payload: LinkChemicalIn,
    db: AsyncSession = Depends(get_db),
):
    try:
        out = await link_unit_chemical_to_ledger(
            db, unit_chemical_id=unit_chemical_id, chemical_id=payload.chemical_id
        )
    except LinkageError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)
```

同时在该文件顶部 import 区补：

```python
from app.services.major_hazard_linkage import (
    link_unit_chemical_to_ledger,
    suggest_design_max_from_ledger,
)
```

- [ ] **步骤 5：前端接入选择器**

新建 `ChemicalLibraryPicker.tsx`：下拉选择本企业台账条目；选中后调 `/ledger/chemicals/{id}/suggest-design-max`，把 `suggested_q` 填进设计最大量输入框，并在下方常驻显示 `hint` 文案与 `ledger_text` 原文。**用户不改也能保存**（尊重人工确认的语义），但字段提示必须可见。

在 `UnitChemicalTable` 的品种名称列加"从台账选择"按钮打开该选择器。

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_linkage.py -v
docker exec -w /app emergency-plan-frontend npx tsc -b
```

预期：`8 passed`；`tsc` exit 0

- [ ] **步骤 7：Commit**

```bash
git add backend/app/services/major_hazard_linkage.py backend/app/routers/major_hazard.py backend/tests/test_major_hazard_linkage.py frontend/src/components/enterprise/majorHazard/ChemicalLibraryPicker.tsx frontend/src/components/enterprise/majorHazard/UnitChemicalTable.tsx
git commit -m "feat(linkage): 单元品种关联台账 + 设计最大量建议初值（需人工确认）（任务 2/5）"
```
