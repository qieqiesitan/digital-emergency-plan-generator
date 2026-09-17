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

---

## 任务 3：单元在平面图上的落点

**文件：**

- 修改：`backend/app/routers/major_hazard.py`
- 修改：`frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx`
- 新增组件：`frontend/src/components/enterprise/majorHazard/UnitPolygonEditor.tsx`

**做法：复用四色图工作台的既有机制。** 单元的 `floor_id` + `polygon` 与 `RiskZone.floor_plan_polygon` 同结构，因此**几何计算直接复用 `frontend/src/utils/riskMappingGeometry.ts` 与 `riskMappingMarquee.ts` 的纯函数**，本任务只做"选楼层 + 画/改多边形 + 保存"的薄封装。

**不要重写多边形编辑逻辑**——四色图工作台那套已经过框选、整体变换、批量写回的多轮打磨（含 `dragWritebackRef` 防重复写回这类坑），重写等于把踩过的坑再踩一遍。

- [ ] **步骤 1：后端加落点写入端点**

在 `backend/app/routers/major_hazard.py` 追加：

```python
class UnitPolygonIn(BaseModel):
    floor_id: Optional[str] = None
    polygon: Optional[dict] = None


@router.put("/units/{unit_id}/polygon")
async def api_set_unit_polygon(
    unit_id: str, payload: UnitPolygonIn, db: AsyncSession = Depends(get_db)
):
    """设置单元在平面图上的落点。polygon 结构与 RiskZone.floor_plan_polygon 一致。

    floor_id 与 polygon 必须同时给或同时清空——只改一个会让单元落到错误的楼层上。
    """
    if (payload.floor_id is None) != (payload.polygon is None):
        raise HTTPException(422, "floor_id 与 polygon 必须同时提供或同时清空")

    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise HTTPException(404, "重大危险源单元不存在")

    unit.floor_id = payload.floor_id
    unit.polygon = payload.polygon
    await db.commit()
    return _ok({"unit_id": unit_id, "floor_id": payload.floor_id})
```

- [ ] **步骤 2：编写接口测试**

追加到 `backend/tests/test_major_hazard_linkage.py`：

```python
def test_polygon_endpoint_rejects_partial_payload():
    """只给 floor_id 不给 polygon（或反之）必须被拒。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.dependencies import get_current_user
    from app.routers import major_hazard

    app = FastAPI()
    app.include_router(major_hazard.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(return_value=_Result([MagicMock()]))
        db.commit = AsyncMock()
        yield db

    async def _user():
        return MagicMock(id="u1")

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app)

    resp = client.put("/api/v1/major-hazard/units/u1/polygon", json={"floor_id": "f1"})
    assert resp.status_code == 422
    assert "同时" in resp.json()["detail"]
```

- [ ] **步骤 3：前端落点编辑器**

`UnitPolygonEditor.tsx` 要点：

1. 楼层下拉（复用 `riskManagementService` 的 `listFloors`）
2. 画布：加载楼层底图；若单元已有 `polygon` 则渲染为可拖顶点
3. 交互：拖动顶点改形；`Esc` 取消当前编辑；「保存落点」调 `PUT /units/{id}/polygon`
4. **复用几何工具**：顶点变换、命中判定从 `utils/riskMappingGeometry.ts` 引入，不在本组件里另写一套
5. 未选楼层时画布禁用并提示"请先选择楼层"

- [ ] **步骤 4：接入单元详情页**

在 `MajorHazardUnitPage` 的「基本信息」Tab 底部加「平面图落点」区块挂载该编辑器；保存成功后 `invalidateQueries(["major-hazard-units"])`。

- [ ] **步骤 5：验证**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_linkage.py -v
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
```

预期：后端 `9 passed`；`tsc` exit 0；vitest 全绿

- [ ] **步骤 6：真实浏览器冒烟**

1. 选楼层 → 在图上框出单元范围 → 保存
2. **刷新后多边形仍在**（验证持久化）
3. 打开四色图工作台确认该楼层显示正常，**不因新增单元多边形而串位**
4. 清空落点（传 `{floor_id: null, polygon: null}`）后再刷新，多边形消失

- [ ] **步骤 7：Commit**

```bash
git add backend/app/routers/major_hazard.py backend/tests/test_major_hazard_linkage.py frontend/src/components/enterprise/majorHazard/UnitPolygonEditor.tsx frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx
git commit -m "feat(linkage): 单元平面图落点（复用四色图几何工具，落点与楼层必须成对）（任务 3/5）"
```

---

## 任务 4：隐患可关联重大危险源单元

**文件：**

- 创建：`backend/db_migration_20260917_hazard_unit_link.sql`
- 修改：`backend/app/models/hazard_management.py`
- 修改：`backend/app/routers/hazard_management.py`
- 修改：`frontend/src/pages/Enterprise/HazardRecordDetailPage.tsx`
- 测试：`backend/tests/test_hazard_linkage_api.py`（新建）

**字段可空是刻意的。** 多数隐患与重大危险源单元无关（比如配电箱门缺失），强制关联会逼用户乱选。只有确实发生在重大危险源所在区域的隐患才需要挂上去——这样"重大危险源区域隐患数"才是可信指标。

- [ ] **步骤 1：加字段与迁移**

在 `backend/app/models/hazard_management.py` 的 `HazardRecord` 类中追加：

```python
    # 隐患来源可追溯到重大危险源单元（可空：多数隐患与单元无关）
    major_hazard_unit_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("major_hazard_units.id", ondelete="SET NULL")
    )
```

`backend/db_migration_20260917_hazard_unit_link.sql`：

```sql
-- 20260917 隐患可关联重大危险源单元。
-- 可空是刻意的：多数隐患与重大危险源单元无关，强制关联会逼用户乱选。
ALTER TABLE hazard_records
    ADD COLUMN IF NOT EXISTS major_hazard_unit_id UUID
    REFERENCES major_hazard_units(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_hazard_records_mh_unit
    ON hazard_records (major_hazard_unit_id);
```

- [ ] **步骤 2：编写失败的测试**

```python
"""隐患关联重大危险源单元：写入与筛选。"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import hazard_management


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


def _model_has_field():
    from app.models.hazard_management import HazardRecord

    return "major_hazard_unit_id" in HazardRecord.__table__.columns


def test_hazard_record_has_unit_field():
    assert _model_has_field()


def test_migration_declares_column():
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1]
        / "db_migration_20260917_hazard_unit_link.sql"
    ).read_text(encoding="utf-8")
    assert "major_hazard_unit_id" in sql
    assert "ADD COLUMN IF NOT EXISTS" in sql
    assert "ON DELETE SET NULL" in sql, "单元删除不应连带删除隐患"
```

- [ ] **步骤 3：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_hazard_linkage_api.py -q
```

预期：FAIL（字段不存在 / SQL 文件不存在）

- [ ] **步骤 4：列表支持按单元筛选**

在 `hazard_management.py` 的隐患列表端点加可选 query 参数：

```python
@router.get("/records")
async def list_records(
    # ... 既有参数
    major_hazard_unit_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    # ... 既有 where 条件之后
    if major_hazard_unit_id:
        stmt = stmt.where(HazardRecord.major_hazard_unit_id == major_hazard_unit_id)
```

并在隐患详情返回体里带上单元名称（联表取一次，避免前端二次请求）：

```python
    # 详情组装处
    unit_name = None
    if record.major_hazard_unit_id:
        from app.models.major_hazard import MajorHazardUnit

        unit_res = await db.execute(
            select(MajorHazardUnit.name).where(
                MajorHazardUnit.id == record.major_hazard_unit_id
            )
        )
        unit_name = unit_res.scalar_one_or_none()
    payload["major_hazard_unit_name"] = unit_name
```

- [ ] **步骤 5：前端加选择器**

隐患登记/编辑表单加可空的「关联重大危险源单元」下拉（数据源 `GET /major-hazard/units?enterprise_id=`）；详情页若已关联则显示单元名称与跳转链接。

- [ ] **步骤 6：验证**

运行：

```bash
cd backend && python -m pytest tests/ -q -k "hazard"
docker exec -w /app emergency-plan-frontend npx tsc -b
```

预期：hazard 相关全绿；`tsc` exit 0

- [ ] **步骤 7：Commit**

```bash
git add backend/db_migration_20260917_hazard_unit_link.sql backend/app/models/hazard_management.py backend/app/routers/hazard_management.py backend/tests/test_hazard_linkage_api.py frontend/src/pages/Enterprise/HazardRecordDetailPage.tsx
git commit -m "feat(linkage): 隐患可关联重大危险源单元并支持筛选（任务 4/5）"
```

---

## 任务 5：预案生成时引用重大危险源清单

**文件：**

- 创建：`backend/app/services/major_hazard_context.py`
- 修改：`backend/app/services/risk_context_builder.py`
- 测试：`backend/tests/test_major_hazard_context.py`

**为什么这条重要：** 重大危险源辨识结果是应急预案编制的法定输入（编制导则要求预案基于风险评估与重大危险源辨识结论）。没有这条，用户得手工把清单抄进提示词。

- [ ] **步骤 1：编写失败的测试**

```python
"""预案上下文应包含重大危险源摘要。"""

from unittest.mock import MagicMock

import pytest

from app.services.major_hazard_context import build_major_hazard_brief


def _db(units, latest):
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        text = str(stmt)
        if "major_hazard_units" in text:
            res.scalars.return_value.all.return_value = units
        else:
            res.scalar_one_or_none.return_value = latest
        return res

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_brief_lists_units_with_level():
    unit = MagicMock()
    unit.id = "u1"
    unit.name = "罐区A"
    unit.unit_type = "storage"
    latest = MagicMock()
    latest.level = "二级"
    latest.is_major_hazard = True
    latest.r_value = 62.5
    latest.seq = 3

    brief = await build_major_hazard_brief(_db([unit], latest), enterprise_id="e1")
    assert "罐区A" in brief["text"]
    assert "二级" in brief["text"]
    assert brief["units"][0]["level"] == "二级"


@pytest.mark.asyncio
async def test_brief_marks_unidentified_units():
    """没有计算快照的单元必须标「尚未辨识」，不能默认成「不构成」。"""
    unit = MagicMock()
    unit.id = "u1"
    unit.name = "锅炉房"
    unit.unit_type = "production"
    brief = await build_major_hazard_brief(_db([unit], None), enterprise_id="e1")
    assert "尚未辨识" in brief["text"]
    assert "不构成" not in brief["text"]
    assert brief["units"][0]["level"] is None


@pytest.mark.asyncio
async def test_brief_empty_when_no_units():
    brief = await build_major_hazard_brief(_db([], None), enterprise_id="e1")
    assert brief["units"] == []
    assert brief["text"] == ""
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_context.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""预案生成上下文：重大危险源摘要。

预案编制必须基于重大危险源辨识结果，这里把清单与最近一次结论提供给生成链路。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.major_hazard import MajorHazardCalculation, MajorHazardUnit

UNIT_TYPE_LABEL = {"production": "生产单元", "storage": "储存单元"}


async def build_major_hazard_brief(db: AsyncSession, *, enterprise_id: str) -> dict:
    """返回 {units: [...], text: 供提示词注入的纯文本}。没有单元时 text 为空串。"""
    res = await db.execute(
        select(MajorHazardUnit).where(MajorHazardUnit.enterprise_id == enterprise_id)
    )
    units = list(res.scalars().all())
    if not units:
        return {"units": [], "text": ""}

    rows: list[dict] = []
    for u in units:
        calc_res = await db.execute(
            select(MajorHazardCalculation)
            .where(MajorHazardCalculation.unit_id == u.id)
            .order_by(MajorHazardCalculation.seq.desc())
            .limit(1)
        )
        latest = calc_res.scalar_one_or_none()
        if latest is None:
            conclusion, level = "尚未辨识", None
        elif latest.is_major_hazard:
            conclusion, level = "构成重大危险源", latest.level
        else:
            conclusion, level = "不构成重大危险源", None
        rows.append(
            {
                "id": u.id,
                "name": u.name,
                "unit_type": UNIT_TYPE_LABEL.get(u.unit_type, u.unit_type),
                "level": level,
                "conclusion": conclusion,
                "r_value": (
                    float(latest.r_value) if latest is not None and latest.is_major_hazard else None
                ),
            }
        )

    lines = ["【重大危险源清单】"]
    for r in rows:
        level_part = f"，{r['level']}" if r["level"] else ""
        lines.append(f"- {r['name']}（{r['unit_type']}）：{r['conclusion']}{level_part}")
    lines.append(
        "说明：清单中标注「尚未辨识」的单元不得在预案中作出构成或不构成的判断。"
    )
    return {"units": rows, "text": "\n".join(lines)}
```

- [ ] **步骤 4：接线到上下文构建器**

在 `app/services/risk_context_builder.py` 的上下文拼装处追加：

```python
from app.services.major_hazard_context import build_major_hazard_brief

# ... 既有上下文片段拼装完成后
_mh = await build_major_hazard_brief(db, enterprise_id=enterprise_id)
if _mh["text"]:
    context_parts.append(_mh["text"])
```

> 变量名以该文件实际写法为准；关键是**只在 `text` 非空时追加**，
> 否则会给没有重大危险源的企业塞一个空标题进提示词。

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_context.py tests/test_risk_context_builder.py tests/test_risk_context_ordering.py -v
```

预期：全绿

- [ ] **步骤 6：跑后端全量**

运行：

```bash
cd backend && python -m pytest tests/ -q
```

预期：失败数不高于 4 个既有失败

- [ ] **步骤 7：Commit**

```bash
git add backend/app/services/major_hazard_context.py backend/app/services/risk_context_builder.py backend/tests/test_major_hazard_context.py
git commit -m "feat(linkage): 预案上下文注入重大危险源清单（未辨识不做判断）（任务 5/5）"
```

---

## 验收清单

- [ ] `cd backend && python -m pytest tests/ -q` 失败数不高于 4 个既有失败
- [ ] `docker exec -w /app emergency-plan-frontend npx tsc -b` exit 0，vitest 全绿
- [ ] **同企业校验**：跨企业关联风险点 / 台账条目均被拒（422 + 可读原因）
- [ ] **设计最大量只给建议**：接口返回 `requires_confirmation: true` 与口径提示，且**接口自身不写库**
- [ ] **落点成对**：只传 `floor_id` 或只传 `polygon` 被拒（422）
- [ ] 单元落点保存后刷新仍在，四色图工作台显示不受影响
- [ ] 隐患可关联单元、可按单元筛选；**未关联的隐患仍能正常保存**（字段可空是刻意的）
- [ ] 预案生成上下文包含重大危险源清单
- [ ] **「尚未辨识」不被误判**：无快照的单元在上下文与界面上都显示"尚未辨识"，**不出现"不构成"字样**

## 未纳入本计划

- **风险点反向显示所属单元**（在风险点详情显示"属于重大危险源罐区A"）：价值明确但优先级低
- **单元与应急资源的关联**：弱关联，暂无明确需求
- **单元变更时自动通知关联隐患/预案更新**：属工作流通知范畴
- **单元落点的四色图等级着色**：本计划只做几何落点，不参与四色分区渲染
