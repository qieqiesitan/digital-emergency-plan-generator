# 风险分级管控增强 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 补齐双重预防机制第一支柱：风险事件「固有/现有」双等级、四色分布图双模式切换、风险分级管控清单（Excel 导出）、重大风险公示（企业内打印 + 公开 token 脱敏页），并落地公共数据字典表 `data_dicts`（系统默认 + 企业覆盖）。

**架构：** 后端在现有 `risk-management` 模块上扩展：`risk_events` 加固有等级/管控层级字段；评估引擎保持纯函数并新增折算参考工具（系数来自字典）；分区/层级响应增加固有等级与颜色；新增管控清单服务与公示 token 路由。`data_dicts` 为跨模块公共字典表，读取时「企业条目 > 系统默认」合并，60s 短缓存。前端复用现有工作台/总览/告知卡组件加双模式切换与双等级展示，新增清单页、公示页、字典管理页。

**技术栈：** FastAPI + SQLAlchemy(async) + PostgreSQL、openpyxl（已有）、React 18 + Ant Design 5 + TanStack Query、Vitest、pytest。

**规格文档：** `docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md`（commit `e130075`）

---

## 文件结构

### 后端（新建 / 修改）

| 文件 | 职责 |
|------|------|
| `backend/db_migration_data_dicts.sql` | 新建：`data_dicts` 表 + 系统种子（measure_factors / control_level_map / hazard_type 等） |
| `backend/db_migration_risk_control_enhancement.sql` | 新建：risk_events 3 字段 + 回填 + enterprises.public_risk_token |
| `backend/app/models/data_dict.py` | 新建：DataDict 模型 |
| `backend/app/models/risk_management.py` | 修改：RiskEvent 加 inherent_risk_level/inherent_risk_score/control_level |
| `backend/app/models/enterprise.py` | 修改：Enterprise 加 public_risk_token |
| `backend/app/schemas/data_dict.py` | 新建：DataDict 请求/响应 |
| `backend/app/schemas/risk_management.py` | 修改：事件 Create/Update/Response 加 3 字段；Zone/Hierarchy 响应加 inherent 字段；MethodPreview 加 scenario |
| `backend/app/services/data_dict_service.py` | 新建：字典合并读取（企业 > 系统，60s 缓存） |
| `backend/app/services/risk_conversion_service.py` | 新建：自动折算参考（分值解析、系数合并、阈值映射） |
| `backend/app/services/risk_control_list_service.py` | 新建：管控清单展平/筛选/导出 |
| `backend/app/routers/data_dicts.py` | 新建：系统字典管理 + 企业字典覆盖 |
| `backend/app/routers/public_risk.py` | 新建：GET /public/risk/{token}（脱敏） |
| `backend/app/routers/risk_management.py` | 修改：control-list / export / risk-publicity / token 端点；zone/hierarchy 填双等级 |
| `backend/app/main.py` | 修改：注册 data_dicts / public_risk 路由 |
| `backend/tests/test_data_dict.py` | 新建：字典合并/覆盖/禁用/重置 |
| `backend/tests/test_risk_conversion.py` | 新建：折算算法 |
| `backend/tests/test_risk_dual_level.py` | 新建：双等级计算/校验/迁移回填 |
| `backend/tests/test_risk_control_list.py` | 新建：清单/导出/公示 |

### 前端（新建 / 修改）

| 文件 | 职责 |
|------|------|
| `frontend/src/types/riskManagement.ts` | 修改：RiskEvent/Zone/Hierarchy 类型加固有字段与管控层级 |
| `frontend/src/types/dataDict.ts` | 新建：字典类型 |
| `frontend/src/services/dataDictService.ts` | 新建：字典 API 封装 |
| `frontend/src/services/dataDictService.test.ts` | 新建：service 测试 |
| `frontend/src/services/riskManagementService.ts` | 修改：control-list / export / publicity / 折算预览 |
| `frontend/src/services/riskManagementService.test.ts` | 修改：新端点测试 |
| `frontend/src/components/enterprise/RiskEventForm.tsx` | 修改：固有参数区块 + 管控层级 + 折算参考卡片 |
| `frontend/src/pages/Enterprise/RiskControlListPage.tsx` | 新建：管控清单页 |
| `frontend/src/pages/Enterprise/RiskPublicityPage.tsx` | 新建：公示页（打印 + 链接管理） |
| `frontend/src/pages/PublicRiskPage.tsx` | 新建：公开公示页（/p/risk/:token） |
| `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx` | 修改：固有/现有切换 |
| `frontend/src/pages/Enterprise/RiskOverviewPage.tsx` | 修改：固有/现有切换 |
| `frontend/src/components/enterprise/RiskNoticeCard.tsx` | 修改：双等级展示 |
| `frontend/src/pages/Settings/DataDictManagePage.tsx` | 新建：系统字典管理 |
| `frontend/src/pages/Enterprise/EnterpriseDictConfigPage.tsx` | 新建：企业字典覆盖 |
| `frontend/src/App.tsx` | 修改：新路由 |

---

## 任务 1：`data_dicts` 表 + 迁移 + 模型

**文件：**
- 创建：`backend/db_migration_data_dicts.sql`
- 创建：`backend/app/models/data_dict.py`
- 测试：`backend/tests/test_data_dict.py`

- [ ] **步骤 1：编写失败的模型测试**

```python
# backend/tests/test_data_dict.py
from sqlalchemy import select
from app.models.data_dict import DataDict

async def test_data_dict_columns(db_session):
    row = DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                   value={"factor": 0.5}, scope="system", enterprise_id=None, is_system=True)
    db_session.add(row)
    await db_session.flush()
    got = (await db_session.execute(
        select(DataDict).where(DataDict.code == "engineering"))).scalar_one()
    assert got.dict_type == "measure_factors"
    assert got.value["factor"] == 0.5
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_data_dict.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.models.data_dict'`

- [ ] **步骤 3：创建迁移与模型**

```sql
-- backend/db_migration_data_dicts.sql
CREATE TABLE IF NOT EXISTS data_dicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dict_type VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    label VARCHAR(100) NOT NULL,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    scope VARCHAR(10) NOT NULL DEFAULT 'system',
    enterprise_id UUID NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dict_type, enterprise_id, code)
);
CREATE INDEX IF NOT EXISTS idx_data_dicts_type_scope ON data_dicts(dict_type, scope);

INSERT INTO data_dicts (dict_type, code, label, value, scope, is_system, sort_order, description) VALUES
  ('measure_factors', 'engineering', '工程技术', '{"factor":0.5}', 'system', TRUE, 1, '自动折算参考系数'),
  ('measure_factors', 'management', '管理措施', '{"factor":0.7}', 'system', TRUE, 2, '自动折算参考系数'),
  ('measure_factors', 'ppe', '个体防护', '{"factor":0.85}', 'system', TRUE, 3, '自动折算参考系数'),
  ('measure_factors', 'emergency', '应急措施', '{"factor":0.9}', 'system', TRUE, 4, '自动折算参考系数'),
  ('measure_factors', 'mode', '折算口径', '{"mode":"min"}', 'system', TRUE, 0, 'min=最小值主导，product=连乘'),
  ('control_level_map', 'major', '重大→企业', '{"level":"重大","control_level":"企业"}', 'system', TRUE, 1, '管控层级默认映射'),
  ('control_level_map', 'large', '较大→部门', '{"level":"较大","control_level":"部门"}', 'system', TRUE, 2, '管控层级默认映射'),
  ('control_level_map', 'general', '一般→班组', '{"level":"一般","control_level":"班组"}', 'system', TRUE, 3, '管控层级默认映射'),
  ('control_level_map', 'low', '低→岗位', '{"level":"低","control_level":"岗位"}', 'system', TRUE, 4, '管控层级默认映射'),
  ('hazard_type', 'equipment', '设备设施', '{}', 'system', TRUE, 1, '隐患类型（B 规格使用）'),
  ('hazard_type', 'fire', '消防', '{}', 'system', TRUE, 2, '隐患类型（B 规格使用）'),
  ('hazard_type', 'behavior', '作业行为', '{}', 'system', TRUE, 3, '隐患类型（B 规格使用）'),
  ('hazard_type', 'management', '管理缺陷', '{}', 'system', TRUE, 4, '隐患类型（B 规格使用）'),
  ('hazard_type', 'environment', '环境', '{}', 'system', TRUE, 5, '隐患类型（B 规格使用）'),
  ('hazard_type', 'other', '其他', '{}', 'system', TRUE, 6, '隐患类型（B 规格使用）');
```

```python
# backend/app/models/data_dict.py
from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Integer, Boolean, Text, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base

class DataDict(Base):
    __tablename__ = "data_dicts"
    __table_args__ = (UniqueConstraint("dict_type", "enterprise_id", "code", name="uq_data_dicts_type_ent_code"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    dict_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    scope: Mapped[str] = mapped_column(String(10), default="system", nullable=False)
    enterprise_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_data_dict.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/db_migration_data_dicts.sql backend/app/models/data_dict.py backend/tests/test_data_dict.py
git commit -m "feat(data-dict): add data_dicts table with system seed migration"
```

---

## 任务 2：字典合并服务 + 管理接口

**文件：**
- 创建：`backend/app/services/data_dict_service.py`
- 创建：`backend/app/schemas/data_dict.py`
- 创建：`backend/app/routers/data_dicts.py`
- 修改：`backend/app/main.py`（注册路由）
- 测试：`backend/tests/test_data_dict.py`（追加）

- [ ] **步骤 1：编写失败的合并测试**

```python
# backend/tests/test_data_dict.py（追加）
from app.services.data_dict_service import get_dict_map

async def test_enterprise_overrides_system(db_session):
    from app.models.data_dict import DataDict
    db_session.add_all([
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.5}, scope="system", is_system=True),
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.3}, scope="enterprise", enterprise_id="ent-1"),
    ])
    await db_session.flush()
    merged = await get_dict_map(db_session, "ent-1", "measure_factors")
    assert merged["engineering"]["factor"] == 0.3

async def test_disabled_entry_excluded(db_session):
    from app.models.data_dict import DataDict
    db_session.add(DataDict(dict_type="measure_factors", code="ppe", label="个体防护",
                            value={"factor": 0.85}, scope="system", enabled=False, is_system=True))
    await db_session.flush()
    merged = await get_dict_map(db_session, "ent-1", "measure_factors")
    assert "ppe" not in merged
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_data_dict.py -v`
预期：FAIL，`ImportError: cannot import name 'get_dict_map'`

- [ ] **步骤 3：实现合并服务**

```python
# backend/app/services/data_dict_service.py
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.data_dict import DataDict

_CACHE_TTL = 60
_cache: dict[tuple[str, str], tuple[float, dict[str, dict]]] = {}

async def get_dict_map(db: AsyncSession, enterprise_id: str | None, dict_type: str) -> dict[str, dict]:
    """合并读取：企业条目 > 系统默认；60s 进程内缓存。返回 {code: {label, value, ...}}。"""
    key = (enterprise_id or "system", dict_type)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]
    rows = (await db.execute(
        select(DataDict).where(
            DataDict.dict_type == dict_type,
            DataDict.enabled.is_(True),
            (DataDict.enterprise_id == enterprise_id) | (DataDict.enterprise_id.is_(None)),
        ).order_by(DataDict.scope, DataDict.sort_order)
    )).scalars().all()
    merged: dict[str, dict] = {}
    for r in rows:
        merged[r.code] = {"label": r.label, "value": r.value, "description": r.description}
    _cache[key] = (now, merged)
    return merged

def invalidate_dict_cache(enterprise_id: str | None = None, dict_type: str | None = None) -> None:
    for k in list(_cache):
        if (enterprise_id is None or k[0] == (enterprise_id or "system")) and (dict_type is None or k[1] == dict_type):
            _cache.pop(k, None)
```

- [ ] **步骤 4：实现 schema 与路由**

```python
# backend/app/schemas/data_dict.py
from pydantic import BaseModel

class DataDictCreate(BaseModel):
    dict_type: str
    code: str
    label: str
    value: dict = {}
    sort_order: int = 0
    enabled: bool = True
    description: str | None = None

class DataDictUpdate(BaseModel):
    label: str | None = None
    value: dict | None = None
    sort_order: int | None = None
    enabled: bool | None = None
    description: str | None = None
```

```python
# backend/app/routers/data_dicts.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.data_dict import DataDict
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.data_dict import DataDictCreate, DataDictUpdate
from app.services.data_dict_service import invalidate_dict_cache

router = APIRouter(tags=["Data Dicts"])

@router.get("/settings/data-dicts", response_model=ApiResponse[list])
async def list_system_dicts(dict_type: str | None = None, _=Depends(require_admin), db=Depends(get_db)):
    stmt = select(DataDict).where(DataDict.enterprise_id.is_(None))
    if dict_type:
        stmt = stmt.where(DataDict.dict_type == dict_type)
    rows = (await db.execute(stmt.order_by(DataDict.dict_type, DataDict.sort_order))).scalars().all()
    return ApiResponse(data=[_serialize(r) for r in rows])

@router.post("/settings/data-dicts", response_model=ApiResponse, status_code=201)
async def create_system_dict(body: DataDictCreate, _=Depends(require_admin), db=Depends(get_db)):
    exists = (await db.execute(select(DataDict.id).where(
        DataDict.dict_type == body.dict_type, DataDict.enterprise_id.is_(None), DataDict.code == body.code))).first()
    if exists:
        raise HTTPException(409, "同类型同 code 的系统条目已存在")
    db.add(DataDict(**body.model_dump(), scope="system", is_system=True, enterprise_id=None))
    await db.commit()
    invalidate_dict_cache(dict_type=body.dict_type)
    return ApiResponse(message="已创建")

@router.put("/settings/data-dicts/{dict_id}", response_model=ApiResponse)
async def update_system_dict(dict_id: str, body: DataDictUpdate, _=Depends(require_admin), db=Depends(get_db)):
    row = await db.get(DataDict, dict_id)
    if not row or row.enterprise_id is not None:
        raise HTTPException(404, "字典条目不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.commit()
    invalidate_dict_cache(dict_type=row.dict_type)
    return ApiResponse(message="已更新")

@router.get("/enterprises/{enterprise_id}/data-dicts", response_model=ApiResponse[list])
async def list_enterprise_dicts(enterprise_id: str, dict_type: str | None = None,
                                current_user: User = Depends(get_current_user), db=Depends(get_db)):
    stmt = select(DataDict).where(
        (DataDict.enterprise_id == enterprise_id) | (DataDict.enterprise_id.is_(None)))
    if dict_type:
        stmt = stmt.where(DataDict.dict_type == dict_type)
    rows = (await db.execute(stmt.order_by(DataDict.scope, DataDict.dict_type, DataDict.sort_order))).scalars().all()
    return ApiResponse(data=[_serialize(r) for r in rows])

@router.post("/enterprises/{enterprise_id}/data-dicts", response_model=ApiResponse, status_code=201)
async def create_enterprise_dict(enterprise_id: str, body: DataDictCreate,
                                 current_user: User = Depends(get_current_user), db=Depends(get_db)):
    from app.routers.risk_management import _get_ent
    await _get_ent(enterprise_id, current_user.id, db)
    exists = (await db.execute(select(DataDict.id).where(
        DataDict.dict_type == body.dict_type, DataDict.enterprise_id == enterprise_id,
        DataDict.code == body.code))).first()
    if exists:
        raise HTTPException(409, "同类型同 code 的企业条目已存在（可编辑覆盖）")
    db.add(DataDict(**body.model_dump(), scope="enterprise", enterprise_id=enterprise_id, is_system=False))
    await db.commit()
    invalidate_dict_cache(enterprise_id, body.dict_type)
    return ApiResponse(message="已创建")

@router.put("/enterprises/{enterprise_id}/data-dicts/{dict_id}", response_model=ApiResponse)
async def update_enterprise_dict(enterprise_id: str, dict_id: str, body: DataDictUpdate,
                                 current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = await db.get(DataDict, dict_id)
    if not row or row.enterprise_id != enterprise_id:
        raise HTTPException(404, "企业字典条目不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.commit()
    invalidate_dict_cache(enterprise_id, row.dict_type)
    return ApiResponse(message="已更新")

@router.delete("/enterprises/{enterprise_id}/data-dicts/{dict_id}", response_model=ApiResponse)
async def delete_enterprise_dict(enterprise_id: str, dict_id: str,
                                 current_user: User = Depends(get_current_user), db=Depends(get_db)):
    row = await db.get(DataDict, dict_id)
    if not row or row.enterprise_id != enterprise_id:
        raise HTTPException(404, "企业字典条目不存在")
    await db.delete(row)
    await db.commit()
    invalidate_dict_cache(enterprise_id, row.dict_type)
    return ApiResponse(message="已删除（恢复系统默认）")

def _serialize(r: DataDict) -> dict:
    return {"id": r.id, "dict_type": r.dict_type, "code": r.code, "label": r.label,
            "value": r.value, "scope": r.scope, "enterprise_id": r.enterprise_id,
            "sort_order": r.sort_order, "enabled": r.enabled, "is_system": r.is_system,
            "description": r.description}
```

`backend/app/main.py`：import 加 `data_dicts`，`app.include_router(data_dicts.router, prefix="/api/v1")`。

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && pytest tests/test_data_dict.py -v`
预期：PASS（新增 2 用例全绿）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/data_dict_service.py backend/app/schemas/data_dict.py backend/app/routers/data_dicts.py backend/app/main.py backend/tests/test_data_dict.py
git commit -m "feat(data-dict): merged dict service with system and enterprise override endpoints"
```

---

## 任务 3：`risk_events` 双等级字段 + 迁移 + 校验

**文件：**
- 创建：`backend/db_migration_risk_control_enhancement.sql`
- 修改：`backend/app/models/risk_management.py`（RiskEvent）
- 修改：`backend/app/models/enterprise.py`（Enterprise 加 public_risk_token）
- 修改：`backend/app/schemas/risk_management.py`（事件 Create/Update/Response）
- 测试：`backend/tests/test_risk_dual_level.py`

- [ ] **步骤 1：编写失败的校验测试**

```python
# backend/tests/test_risk_dual_level.py
import pytest
from pydantic import ValidationError
from app.schemas.risk_management import RiskEventCreate

def test_current_level_not_above_inherent():
    with pytest.raises(ValidationError, match="不应高于"):
        RiskEventCreate(accident_type="火灾", risk_level="重大", inherent_risk_level="一般")

def test_backfill_migration_present():
    sql = open("db_migration_risk_control_enhancement.sql", encoding="utf-8").read()
    assert "inherent_risk_level" in sql
    assert "public_risk_token" in sql
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_risk_dual_level.py -v`
预期：FAIL（schema 无字段/校验）

- [ ] **步骤 3：迁移 SQL 与模型字段**

```sql
-- backend/db_migration_risk_control_enhancement.sql
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS inherent_risk_level VARCHAR(20);
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS inherent_risk_score VARCHAR(50);
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS control_level VARCHAR(20);
UPDATE risk_events SET inherent_risk_level = risk_level WHERE inherent_risk_level IS NULL;
UPDATE risk_events SET inherent_risk_score = risk_score WHERE inherent_risk_score IS NULL;

ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS public_risk_token VARCHAR(64);
CREATE UNIQUE INDEX IF NOT EXISTS uq_enterprises_public_risk_token ON enterprises(public_risk_token) WHERE public_risk_token IS NOT NULL;
```

`backend/app/models/risk_management.py` RiskEvent 类追加：

```python
    # 双重预防：固有风险与管控层级
    inherent_risk_level: Mapped[Optional[str]] = mapped_column(String(20))
    inherent_risk_score: Mapped[Optional[str]] = mapped_column(String(50))
    control_level: Mapped[Optional[str]] = mapped_column(String(20))
```

`backend/app/models/enterprise.py` Enterprise 类追加：

```python
    public_risk_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
```

- [ ] **步骤 4：schema 加字段与校验**

```python
# backend/app/schemas/risk_management.py
LEVELS = {"重大", "较大", "一般", "低"}

def _validate_dual_level(risk_level: str | None, inherent_risk_level: str | None) -> None:
    if risk_level and inherent_risk_level and LEVELS.index(risk_level) < LEVELS.index(inherent_risk_level):
        raise ValueError("现有风险等级不应高于固有风险等级")
```

`RiskEventCreate` / `RiskEventUpdate` 增加：

```python
    inherent_risk_level: str | None = None
    inherent_risk_score: str | None = None
    control_level: str | None = None
```

并在类上用 `model_validator(mode="after")` 调用 `_validate_dual_level`。`RiskEventResponse` 同步加 3 字段。

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && pytest tests/test_risk_dual_level.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/db_migration_risk_control_enhancement.sql backend/app/models/risk_management.py backend/app/models/enterprise.py backend/app/schemas/risk_management.py backend/tests/test_risk_dual_level.py
git commit -m "feat(risk): add inherent risk level and control level to risk events"
```

---

## 任务 4：评估引擎扩展（双参数 + 自动折算参考）

**文件：**
- 修改：`backend/app/services/risk_method_engine.py`（抽 `level_from_score`）
- 创建：`backend/app/services/risk_conversion_service.py`
- 测试：`backend/tests/test_risk_conversion.py`

- [ ] **步骤 1：编写失败的折算测试**

```python
# backend/tests/test_risk_conversion.py
from app.services.risk_conversion_service import parse_score, combine_factor, conversion_reference

def test_parse_score_lec():
    assert parse_score("D=270") == 270

def test_combine_factor_min_default():
    factors = {"engineering": 0.5, "management": 0.7, "ppe": 0.85, "emergency": 0.9}
    assert combine_factor(factors, "min") == 0.5
    assert combine_factor(factors, "product") == pytest.approx(0.5 * 0.7 * 0.85 * 0.9)

def test_conversion_reference_level():
    thresholds = [
        {"min": 20, "max": 25, "level": "重大"},
        {"min": 15, "max": 19, "level": "较大"},
        {"min": 10, "max": 14, "level": "一般"},
        {"min": 1, "max": 9, "level": "低"},
    ]
    ref = conversion_reference("R=20", {"engineering": 0.5}, "min", thresholds)
    assert ref["reference_score"] == 10
    assert ref["reference_level"] == "一般"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_risk_conversion.py -v`
预期：FAIL（模块不存在）

- [ ] **步骤 3：实现折算服务**

```python
# backend/app/services/risk_conversion_service.py
import re
from app.services.risk_method_engine import level_from_score

def parse_score(score_str: str) -> float | None:
    m = re.search(r"(-?\d+(?:\.\d+)?)", score_str or "")
    return float(m.group(1)) if m else None

def combine_factor(factors: dict[str, float], mode: str = "min") -> float:
    present = [v for k, v in factors.items() if k != "mode" and v > 0]
    if not present:
        return 1.0
    return min(present) if mode == "min" else _prod(present)

def _prod(values: list[float]) -> float:
    out = 1.0
    for v in values:
        out *= v
    return out

def conversion_reference(inherent_score: str, factors: dict[str, float], mode: str,
                         thresholds: list[dict], method_type: str = "LS") -> dict:
    """固有分值 × 综合系数 → 参考分值/等级。DIRECT 方法由调用方短路。"""
    score = parse_score(inherent_score)
    if score is None:
        return {"factor": 1.0, "reference_score": None, "reference_level": None, "note": "无法解析固有分值"}
    factor = combine_factor(factors, mode)
    ref_score = round(score * factor, 2)
    return {"factor": factor, "reference_score": ref_score,
            "reference_level": level_from_score(method_type, ref_score, thresholds)}
```

`backend/app/services/risk_method_engine.py` 追加（把阈值匹配逻辑抽为公共函数，`compute_risk` 内部复用它）：

```python
def level_from_score(method_type: str, score: float, thresholds: list[dict]) -> str:
    for t in thresholds or []:
        if t["min"] <= score <= t["max"]:
            return t["level"]
    return "低"
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_risk_conversion.py tests/test_risk_dual_level.py -v`
预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_conversion_service.py backend/app/services/risk_method_engine.py backend/tests/test_risk_conversion.py
git commit -m "feat(risk): add risk conversion reference tool and level_from_score helper"
```

---

## 任务 5：事件表单双参数 + 折算参考（前端）

**文件：**
- 修改：`frontend/src/components/enterprise/RiskEventForm.tsx`
- 修改：`frontend/src/services/riskManagementService.ts`（预览接口加 scenario；新增折算参考调用）
- 修改：`frontend/src/types/riskManagement.ts`
- 测试：`frontend/src/services/riskManagementService.test.ts`

- [ ] **步骤 1：编写失败的 service 测试**

```typescript
// frontend/src/services/riskManagementService.test.ts（追加）
import { previewRiskMethod } from "@/services/riskManagementService";

test("previewRiskMethod passes scenario", async () => {
  const mock = vi.fn().mockResolvedValue({ data: { risk_level: "一般", risk_score: "R=10" } });
  vi.spyOn(api, "post").mockImplementation(mock);
  await previewRiskMethod("ent-1", { method_id: "m1", params: { l: 2, s: 5 }, scenario: "inherent" });
  expect(mock).toHaveBeenCalledWith("/enterprises/ent-1/risk-management/methods/preview",
    expect.objectContaining({ scenario: "inherent" }));
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd frontend && npx vitest run src/services/riskManagementService.test.ts`
预期：FAIL

- [ ] **步骤 3：service 与类型扩展**

`frontend/src/types/riskManagement.ts`：`RiskEvent` 增加 `inherent_risk_level: string | null; inherent_risk_score: string | null; control_level: string | null`；`RiskEventFormValues` 同。

`frontend/src/services/riskManagementService.ts`：`previewRiskMethod` 请求体增加 `scenario`；新增：

```typescript
export async function previewRiskConversion(enterpriseId: string, eventId: string) {
  return api.get(`/enterprises/${enterpriseId}/risk-management/events/${eventId}/conversion-reference`);
}
```

- [ ] **步骤 4：事件表单加区块**

`RiskEventForm.tsx`：评估方法为 LS/LEC/COAL_LS 时，在现有参数区上方渲染「固有风险（不考虑管控措施）」参数组（同字段名 `inherentL/inherentS` 等，按方法映射），保存时组装为 `inherent_params` 与现有 params 一并提交；DIRECT 方法渲染「固有等级」Select。下方加「管控层级」Select（选项 企业/部门/班组/岗位，placeholder「按现有等级自动映射」）与「自动折算参考」按钮：点击调 `previewRiskConversion`，展示系数说明卡（factor / reference_score / reference_level），「采用为现有风险」把参考等级/分值填入现有区块。

- [ ] **步骤 5：运行测试 + 门禁**

运行：`cd frontend && npx vitest run src/services/riskManagementService.test.ts && npx tsc -b && npx eslint src/components/enterprise/RiskEventForm.tsx src/services/riskManagementService.ts`
预期：全部通过

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/components/enterprise/RiskEventForm.tsx frontend/src/services/riskManagementService.ts frontend/src/types/riskManagement.ts frontend/src/services/riskManagementService.test.ts
git commit -m "feat(risk): dual-parameter inherent/current form with conversion reference"
```

---

## 任务 6：`max_risk_level(mode)` + 分区/层级响应双等级

**文件：**
- 修改：`backend/app/services/risk_mapping_service.py`
- 修改：`backend/app/schemas/risk_management.py`（Zone/Hierarchy 响应）
- 修改：`backend/app/routers/risk_management.py`（zone/hierarchy 组装）
- 测试：`backend/tests/test_risk_dual_level.py`（追加）

- [ ] **步骤 1：编写失败测试**

```python
async def test_max_risk_level_by_mode():
    from app.models.risk_management import RiskZone, RiskObject, RiskEvent
    zone = RiskZone(id="z1", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o1", enterprise_id="e1", zone_id="z1", name="1#储罐")
    obj.events = [RiskEvent(accident_type="火灾", risk_level="一般", inherent_risk_level="重大")]
    zone.objects = [obj]
    assert max_risk_level(zone, "current") == "一般"
    assert max_risk_level(zone, "inherent") == "重大"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_risk_dual_level.py::test_max_risk_level_by_mode -v`
预期：FAIL（max_risk_level 无 mode 参数）

- [ ] **步骤 3：改造 `max_risk_level`**

```python
def max_risk_level(zone: RiskZone, mode: str = "current") -> str:
    level = "未评估"
    for obj in zone.objects:
        for ev in obj.events:
            value = ev.inherent_risk_level if mode == "inherent" else ev.risk_level
            if value and LEVEL_ORDER.get(value, 0) > LEVEL_ORDER.get(level, 0):
                level = value
        for unit in obj.units:
            for ev in unit.events:
                value = ev.inherent_risk_level if mode == "inherent" else ev.risk_level
                if value and LEVEL_ORDER.get(value, 0) > LEVEL_ORDER.get(level, 0):
                    level = value
    return level
```

`RiskZoneResponse` / `HierarchyZoneResponse` 增加 `inherent_max_level: str | None = None` 与 `inherent_effective_color: str | None = None`；router 的 zone/hierarchy 组装处计算 `max_risk_level(zone, "inherent")` 并调用 `effective_color` 填色。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_risk_dual_level.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_mapping_service.py backend/app/schemas/risk_management.py backend/app/routers/risk_management.py backend/tests/test_risk_dual_level.py
git commit -m "feat(risk): support inherent/current mode in zone risk level and colors"
```

---

## 任务 7：四色图双模式切换（工作台 + 总览）

**文件：**
- 修改：`frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskOverviewPage.tsx`
- 修改：`frontend/src/types/riskManagement.ts`（Zone 响应字段）

- [ ] **步骤 1：类型扩展**

`HierarchyZone` / workbench zone 类型增加 `inherent_max_level?: string | null`、`inherent_effective_color?: string | null`。

- [ ] **步骤 2：工作台加切换**

`RiskMappingWorkbenchPage.tsx`：工作台顶部渲染 `Segmented`（`["现有风险图", "固有风险图"]`），state `colorMode`；区域填充色改为 `colorMode === "inherent" ? (z.inherentEffectiveColor ?? z.effectiveColor) : z.effectiveColor`，图例文案随模式切换（「区域颜色 = 该区域 现有/固有 最大风险等级」）。

- [ ] **步骤 3：总览加切换**

`RiskOverviewPage.tsx`：在现有 Segmented 旁加第二组 Segmented（固有/现有）；`RiskDistributionStage`、`RiskOverviewMatrix` 的入参增加 `mode`，取对应 max level 与 color；切换时清除高亮。

- [ ] **步骤 4：门禁**

运行：`cd frontend && npx tsc -b && npx eslint src/pages/Enterprise/RiskMappingWorkbenchPage.tsx src/pages/Enterprise/RiskOverviewPage.tsx && npx vitest run`
预期：全部通过（既有用例不回归）

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx frontend/src/pages/Enterprise/RiskOverviewPage.tsx frontend/src/types/riskManagement.ts
git commit -m "feat(risk): add inherent/current four-color map toggle in workbench and overview"
```

---

## 任务 8：管控清单 API + Excel 导出 + 公示后端

**文件：**
- 创建：`backend/app/services/risk_control_list_service.py`
- 修改：`backend/app/routers/risk_management.py`
- 创建：`backend/app/routers/public_risk.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_risk_control_list.py`

- [ ] **步骤 1：编写失败测试**

```python
# backend/tests/test_risk_control_list.py
import io
from openpyxl import load_workbook
from app.services.risk_control_list_service import flatten_rows, default_control_level, build_ledger_workbook

def test_default_control_level_from_dict():
    mapping = {"重大": "企业", "较大": "部门", "一般": "班组", "低": "岗位"}
    assert default_control_level(mapping, "重大") == "企业"

def test_build_ledger_workbook():
    rows = [{"zone": "储罐区", "object": "1#储罐", "unit": "阀门组",
             "accident": "泄漏", "inherent": "重大", "current": "一般",
             "control_level": "班组", "measures": "报警器年检", "unit_name": "生产部", "person": "李四"}]
    wb = build_ledger_workbook(rows)
    ws = wb.active
    assert ws["A1"].value == "分区"
    assert ws.max_row == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_risk_control_list.py -v`
预期：FAIL（模块不存在）

- [ ] **步骤 3：实现清单服务**

```python
# backend/app/services/risk_control_list_service.py
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

def default_control_level(mapping: dict, current_level: str | None) -> str:
    return mapping.get(current_level or "", "岗位")

def flatten_rows(zones: list, mapping: dict) -> list[dict]:
    rows = []
    for z in zones:
        for obj in z.objects or []:
            for unit in obj.units or []:
                for ev in unit.events or []:
                    rows.append(_row(z, obj, unit, ev, mapping))
            for ev in obj.events or []:
                rows.append(_row(z, obj, None, ev, mapping))
    return rows

def _row(z, obj, unit, ev, mapping) -> dict:
    measures = "；".join(
        f"{m.measure_category}:{m.description}" for m in (ev.measures or [])) or "-"
    return {
        "zone": z.name, "object": obj.name, "unit": unit.name if unit else "-",
        "accident": ev.accident_type, "inherent": ev.inherent_risk_level or ev.risk_level or "-",
        "current": ev.risk_level or "-", "control_level": ev.control_level or default_control_level(mapping, ev.risk_level),
        "measures": measures, "unit_name": obj.responsible_unit or "-",
        "person": obj.responsible_person or "-", "phone": obj.contact_phone or "-",
    }

def build_ledger_workbook(rows: list[dict]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "风险管控清单"
    headers = ["分区", "风险点", "单元", "事故类型", "固有等级", "现有等级",
               "管控层级", "管控措施", "责任单位", "责任人", "联系电话"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="EEF2F7")
    for r in rows:
        ws.append([r[h] for h in headers])
    return wb
```

- [ ] **步骤 4：实现端点**

`backend/app/routers/risk_management.py` 追加：

```python
@router.get("/control-list", response_model=ApiResponse[dict])
async def control_list(enterprise_id: str, floor_id: str | None = None, zone_id: str | None = None,
                       level: str | None = None, control_level: str | None = None,
                       keyword: str | None = None, page: int = 1, size: int = 20,
                       current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    mapping = {e["label"]: (e["value"].get("control_level") or "")
               for e in (await get_dict_map(db, enterprise_id, "control_level_map")).values()}
    # 组装 zone 树（复用现有 hierarchy 查询，含 objects/units/events/measures），按筛选过滤
    rows = flatten_rows(zones, mapping)
    if zone_id: rows = [r for r in rows if r["zone_id"] == zone_id]
    if level: rows = [r for r in rows if r["current"] == level or r["inherent"] == level]
    if control_level: rows = [r for r in rows if r["control_level"] == control_level]
    if keyword: rows = [r for r in rows if keyword in r["object"] or keyword in r["zone"]]
    total = len(rows)
    start = (page - 1) * size
    return ApiResponse(data={"items": rows[start:start+size], "total": total})

@router.get("/control-list/export")
async def control_list_export(enterprise_id: str, floor_id: str | None = None,
                              current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    mapping = ...
    rows = flatten_rows(zones, mapping)
    buf = BytesIO(); build_ledger_workbook(rows).save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=risk_control_list.xlsx"})

@router.get("/risk-publicity", response_model=ApiResponse[dict])
async def get_risk_publicity(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    if not ent.public_risk_token:
        ent.public_risk_token = secrets.token_hex(32); await db.commit()
    rows = [r for r in flatten_rows(zones, mapping) if r["current"] == "重大" or r["control_level"] == "企业"]
    return ApiResponse(data={"token": ent.public_risk_token, "enterprise_name": ent.name, "items": rows})

@router.post("/risk-publicity/token", response_model=ApiResponse[dict])
async def reset_risk_publicity_token(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    ent.public_risk_token = secrets.token_hex(32); await db.commit()
    return ApiResponse(data={"token": ent.public_risk_token})
```

`backend/app/routers/public_risk.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.enterprise import Enterprise
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/public/risk", tags=["Public Risk"])

@router.get("/{token}", response_model=ApiResponse[dict])
async def public_risk(token: str, db: AsyncSession = Depends(get_db)):
    ent = (await db.execute(select(Enterprise).where(Enterprise.public_risk_token == token))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "链接已失效")
    # 复用风险清单服务组装重大风险行，脱敏：仅 zone/object/accident/current/control_level/measures/unit_name
    items = _desensitized_major_rows(ent.id, db)
    return ApiResponse(data={"enterprise_name": ent.name, "items": items})
```

`_desensitized_major_rows` 只返回 分区/风险点/事故类型/现有等级/管控层级/管控措施/责任单位，**不含 person/phone**；`backend/app/main.py` 注册 `public_risk.router`（prefix `/api/v1`）。

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && pytest tests/test_risk_control_list.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/risk_control_list_service.py backend/app/routers/risk_management.py backend/app/routers/public_risk.py backend/app/main.py backend/tests/test_risk_control_list.py
git commit -m "feat(risk): control list with xlsx export and desensitized public risk page"
```

---

## 任务 9：管控清单页 + 公示页 + 公开页（前端）

**文件：**
- 创建：`frontend/src/pages/Enterprise/RiskControlListPage.tsx`
- 创建：`frontend/src/pages/Enterprise/RiskPublicityPage.tsx`
- 创建：`frontend/src/pages/PublicRiskPage.tsx`
- 修改：`frontend/src/services/riskManagementService.ts`、`frontend/src/App.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`（顶部「管控清单」「重大风险公示」按钮）

- [ ] **步骤 1：service 封装**

```typescript
export async function getControlList(enterpriseId: string, params: object) {
  return api.get(`/enterprises/${enterpriseId}/risk-management/control-list`, { params });
}
export async function exportControlList(enterpriseId: string) {
  return api.get(`/enterprises/${enterpriseId}/risk-management/control-list/export`, { responseType: "blob" });
}
export async function getRiskPublicity(enterpriseId: string) {
  return api.get(`/enterprises/${enterpriseId}/risk-management/risk-publicity`);
}
export async function resetRiskPublicityToken(enterpriseId: string) {
  return api.post(`/enterprises/${enterpriseId}/risk-management/risk-publicity/token`);
}
```

- [ ] **步骤 2：清单页**

`RiskControlListPage.tsx`：useQuery 拉 `getControlList`；筛选行（楼层/分区/等级/管控层级 Select + 关键字 Input）；Table 列=分区/风险点/单元/事故类型/固有等级（Tag 色）/现有等级（Tag 色）/管控层级/管控措施（ellipsis）/责任单位/责任人；分页；右上「导出 Excel」（blob 下载 + message）。

- [ ] **步骤 3：公示页与公开页**

`RiskPublicityPage.tsx`：展示四色图（现有模式，复用 `RiskDistributionStage`）+ 重大风险清单 Table + 公开链接（`location.origin + /p/risk/` + token，复制按钮）+「重置链接」（二次确认 Modal）；`@media print` 样式隐藏按钮只留公告内容。页面顶部「返回」。

`PublicRiskPage.tsx`：`useParams` 取 token → `useQuery(["public-risk", token], () => api.get('/public/risk/'+token))`；加载 Spin；错误 Result 404「链接已失效」；成功渲染企业名 + 清单表（脱敏列）。

`App.tsx` 注册路由：`/enterprises/:id/risk-control-list`、`/enterprises/:id/risk-publicity`（ProtectedRoute 内）、`/p/risk/:token`（公开，无守卫）。

- [ ] **步骤 4：门禁**

运行：`cd frontend && npx tsc -b && npx eslint src/pages/Enterprise/RiskControlListPage.tsx src/pages/Enterprise/RiskPublicityPage.tsx src/pages/PublicRiskPage.tsx src/pages/Enterprise/RiskManagementTab.tsx && npx vitest run`
预期：全部通过

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskControlListPage.tsx frontend/src/pages/Enterprise/RiskPublicityPage.tsx frontend/src/pages/PublicRiskPage.tsx frontend/src/services/riskManagementService.ts frontend/src/App.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx
git commit -m "feat(risk): control list page, publicity page and public token page"
```

---

## 任务 10：风险告知卡双等级 + 字典管理页

**文件：**
- 修改：`frontend/src/components/enterprise/RiskNoticeCard.tsx`
- 创建：`frontend/src/pages/Settings/DataDictManagePage.tsx`
- 创建：`frontend/src/pages/Enterprise/EnterpriseDictConfigPage.tsx`
- 创建：`frontend/src/services/dataDictService.ts`、`frontend/src/types/dataDict.ts`
- 修改：`frontend/src/App.tsx`、`frontend/src/layouts/AuthLayout.tsx`（系统菜单）

- [ ] **步骤 1：告知卡双等级**

`RiskNoticeCard.tsx`：卡片数据源增加 `inherent_risk_level`；等级色带区域显示「现有风险：{level}（固有 {inherent}）」小字（快照数据同样透传；`risk_notice_card` 组装处同步带上 inherent 字段，属于后端小改，随本任务一并提交）。

- [ ] **步骤 2：字典 service 与类型**

```typescript
export interface DataDictItem { id: string; dict_type: string; code: string; label: string;
  value: Record<string, unknown>; scope: "system" | "enterprise"; enterprise_id: string | null;
  sort_order: number; enabled: boolean; is_system: boolean; description?: string | null; }
```

`dataDictService.ts`：`listSystemDicts(dictType?)` / `createSystemDict(payload)` / `updateSystemDict(id, patch)` / `listEnterpriseDicts(enterpriseId, dictType?)` / `createEnterpriseDict(enterpriseId, payload)` / `updateEnterpriseDict(enterpriseId, id, patch)` / `deleteEnterpriseDict(enterpriseId, id)`。

- [ ] **步骤 3：系统字典管理页**

`DataDictManagePage.tsx`：左侧 dict_type 分组（measure_factors / control_level_map / hazard_type…），主区 Table（code/label/value JSON 展示/enabled/sort）；「新增」「编辑」Drawer 表单（dict_type、code、label、value 用 JSON 文本域 + 校验 JSON 合法性、sort_order、enabled）；关闭后 invalidate 本地 query。

- [ ] **步骤 4：企业字典覆盖页**

`EnterpriseDictConfigPage.tsx`：读取企业合并视图（系统 + 企业条目），系统条目显示「系统默认」Tag 与「覆盖」按钮（复制为 enterprise scope 后可编辑）；企业条目可编辑/删除（删除=恢复系统默认）。入口：企业详情页「风险与隐患配置」。

`AuthLayout`/菜单按现有权限模式加菜单项；`App.tsx` 加路由。

- [ ] **步骤 5：门禁**

运行：`cd frontend && npx tsc -b && npx eslint src/pages/Settings/DataDictManagePage.tsx src/pages/Enterprise/EnterpriseDictConfigPage.tsx src/components/enterprise/RiskNoticeCard.tsx && npx vitest run`
预期：全部通过

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/components/enterprise/RiskNoticeCard.tsx frontend/src/pages/Settings/DataDictManagePage.tsx frontend/src/pages/Enterprise/EnterpriseDictConfigPage.tsx frontend/src/services/dataDictService.ts frontend/src/types/dataDict.ts frontend/src/App.tsx frontend/src/layouts/AuthLayout.tsx backend/app/services/risk_notice_card_data.py
git commit -m "feat(risk): dual level on notice card and data dict management pages"
```

---

## 任务 11：回归门禁 + 手工冒烟

**文件：** 无（验证任务）

- [ ] **步骤 1：后端全量测试**

运行：`cd backend && pytest tests/ -q`
预期：全部 PASS（既有 410 左右 + 新增用例）

- [ ] **步骤 2：前端全量门禁**

运行：`cd frontend && npx tsc -b && npx vitest run && npx eslint src`
预期：exit 0 / 全部通过

- [ ] **步骤 3：`git diff --check` 与迁移复跑**

运行：`git diff --check`；对本地库执行两个新迁移 SQL（幂等验证）。
预期：干净；`IF NOT EXISTS` 可重复执行。

- [ ] **步骤 4：手工冒烟**

- 事件表单：固有/现有双参数分别预览；折算参考卡片给出系数与参考等级，一键采用；
- 四色图：工作台/总览切换固有/现有，区域颜色变化；
- 管控清单：筛选 + 导出 xlsx 打开正常；
- 公示：企业内打印样式正确；公开 token 新开无痕窗口打开正常且无责任人电话；
- 告知卡：显示「现有 X（固有 Y）」；
- 字典：系统改系数 → 企业折算参考变化；企业覆盖 → 优先于系统。

- [ ] **步骤 5：Commit（如有修复）**

```bash
git add -A && git commit -m "fix(risk): regression fixes from dual prevention A-phase smoke test"
```

---

## 自检结论

**规格覆盖度**：规格 §2 全部决策（双等级/双模式/清单/公示/告知卡/字典）均有对应任务；§5.1 字段→任务 3；§5.2 折算→任务 4；§5.4 字典→任务 1/2/10；§6 双模式→任务 6/7；§7 清单→任务 8/9；§8 公示→任务 8/9；§9 接口→任务 2/8；§10 页面→任务 5/9/10；§11 错误处理→任务 3 校验与 8 token 404；§12 测试→各任务；§13 迁移→任务 1/3；§14 验收→任务 11。

**占位符扫描**：无 TODO/待定；所有代码步骤含实际代码或精确接口签名。

**类型一致性**：`max_risk_level(zone, mode)`、`level_from_score(method_type, score, thresholds)`、`get_dict_map(db, enterprise_id, dict_type)` 在任务 4/6/2 中定义并在后续任务引用，签名一致。

**后续计划**：组织与成员管理、隐患排查治理主体为独立计划（B 规格），本计划交付后另行编写。
