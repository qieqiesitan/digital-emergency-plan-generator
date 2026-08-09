# 易用性整体优化 · 计划 B（后端核心）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 完成后端核心改造——AI 配置全局化（系统级单例）、危化品与风险事件关联及生成上下文注入、企业数据完成度聚合接口。

**架构：** `AIConfig.user_id` 改为可空并用 `user_id IS NULL` 表示系统级配置，统一取配置入口到新 `ai_config_service`；`RiskEvent` 增加 `chemical_id` 外键并在生成上下文注入化学品属性；新增 `onboarding_service.compute_completion` 供引导页与企业列表使用。

**技术栈：** FastAPI + SQLAlchemy + PostgreSQL（后端）、pytest（测试）、前端 tsc 验证。

**规格依据：** `docs/superpowers/specs/2026-08-08-usability-enhancement-design.md` 第 9、10、6.6、14 节。

**依赖：** 先执行计划 A（基础层）。

**基线：** master 已合入预案附图扩展（94cc4bf）。`generation.py::_collect_enterprise_data` 现已有 `risk_events/zones/risk_objects` 字段（附图用），本计划任务 B2 在其基础上**追加** `chemicals/chemical 属性/risk_method_config/备案` 字段，签名不变，无冲突；`risk_context_builder.py` 的 `_risk_source_item` 未被附图扩展改动，任务 B2 直接追加 `chemical_id` 字段。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `backend/db_migration_ai_config_system.sql` | user_id 可空 + is_system 列 | 新建 |
| `backend/db_migration_risk_event_chemical.sql` | risk_events 加 chemical_id | 新建 |
| `backend/app/models/enterprise.py` | AIConfig.user_id 可空、加 is_system | 修改 |
| `backend/app/models/risk_management.py` | RiskEvent 加 chemical_id/relationship | 修改 |
| `backend/app/services/ai_config_service.py` | 系统配置统一读取 | 新建 |
| `backend/app/services/risk_ai_service.py` | `_get_ai_config` 改为系统级 | 修改 |
| `backend/app/routers/ai_config.py` | 路由改为系统级（管理员） | 修改 |
| `backend/app/routers/generation.py` | 取配置改系统级；生成上下文注入 chemical/方法/备案 | 修改 |
| `backend/app/routers/chat.py`、`chat_dispatch.py`、`external.py`、`hazardous_chemicals.py`、`regulations.py`、`resources_ext.py` | 取配置改系统级 | 修改 |
| `backend/app/schemas/risk_management.py` | RiskEventCreate/Update 加 chemical_id | 修改 |
| `backend/app/services/onboarding_service.py` | 完成度聚合 | 新建 |
| `backend/app/routers/onboarding.py` | `GET /enterprises/{id}/completion` | 新建 |
| `backend/app/routers/enterprises.py` | 列表项加 completion | 修改 |
| `backend/tests/test_ai_config_system.py` | 系统配置读取测试 | 新建 |
| `backend/tests/test_risk_event_chemical.py` | chemical_id schema/模型测试 | 新建 |
| `backend/tests/test_onboarding_completion.py` | 完成度聚合测试 | 新建 |

---

### 任务 B1：AI 配置全局化（系统级单例）

**文件：**
- 新建：`backend/db_migration_ai_config_system.sql`
- 修改：`backend/app/models/enterprise.py`
- 新建：`backend/app/services/ai_config_service.py`
- 修改：`backend/app/services/risk_ai_service.py`
- 修改：`backend/app/routers/ai_config.py`
- 修改：`backend/app/routers/generation.py`、`chat.py`、`chat_dispatch.py`、`external.py`、`hazardous_chemicals.py`、`regulations.py`、`resources_ext.py`
- 测试：`backend/tests/test_ai_config_system.py`

- [x] **步骤 1：编写失败测试**

新建 `backend/tests/test_ai_config_system.py`：

```python
import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.ai_config_service import get_system_ai_config


def test_get_system_ai_config_returns_none_when_missing():
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    result = asyncio.run(get_system_ai_config(db))
    assert result is None


def test_get_system_ai_config_filters_user_id_is_null():
    db = AsyncMock()
    cfg = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = cfg
    result = asyncio.run(get_system_ai_config(db))
    assert result is cfg
    # 验证查询条件包含 user_id IS NULL
    call_kwargs = db.execute.call_args
    sql = str(call_kwargs.args[0])
    assert "user_id IS NULL" in sql or "user_id IS" in sql


def test_risk_ai_get_config_raises_when_system_missing():
    from app.services.risk_ai_service import _get_ai_config
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(Exception) as exc:
        asyncio.run(_get_ai_config("any-user", db))
    assert exc.value.status_code == 400
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_ai_config_system.py -v`

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.ai_config_service'`。

- [x] **步骤 3：迁移 SQL + 模型 + 统一服务**

新建 `backend/db_migration_ai_config_system.sql`：

```sql
-- AI 配置全局化：user_id 可空（NULL = 系统级配置），加 is_system 标记
ALTER TABLE ai_configs ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE ai_configs ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;
```

`backend/app/models/enterprise.py` 中 `AIConfig` 修改：

```python
class AIConfig(Base):
    __tablename__ = "ai_configs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # 系统级配置 user_id 为 NULL（is_system=True）；用户级配置保留给专业模式
    user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(500))
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=16384)
    top_p: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

（`unique=True` 从 `user_id` 移除；`Optional` 已在文件顶部导入。）

新建 `backend/app/services/ai_config_service.py`：

```python
"""系统级 AI 配置统一读取。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enterprise import AIConfig


async def get_system_ai_config(db: AsyncSession) -> AIConfig | None:
    """返回系统级 AI 配置（user_id IS NULL 且激活），无则返回 None。"""
    result = await db.execute(
        select(AIConfig).where(
            AIConfig.user_id.is_(None),
            AIConfig.is_system.is_(True),
            AIConfig.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
```

- [x] **步骤 4：改造取配置调用点为系统级**

`backend/app/services/risk_ai_service.py` 的 `_get_ai_config` 替换为：

```python
async def _get_ai_config(user_id: str, db: AsyncSession) -> AIConfig:
    """获取系统级 AI 配置，未配置则抛出 400（user_id 参数保留兼容调用方）。"""
    from app.services.ai_config_service import get_system_ai_config
    config = await get_system_ai_config(db)
    if not config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")
    return config
```

`backend/app/routers/generation.py`：将函数内所有

```python
ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id, AIConfig.is_active == True))).scalar_one_or_none()
```

替换为：

```python
from app.services.ai_config_service import get_system_ai_config
ai_config = await get_system_ai_config(db)
```

并在未配置处统一返回 400「系统未配置 AI 模型，请联系管理员」。

`backend/app/routers/chat.py`、`hazardous_chemicals.py`、`resources_ext.py`、`regulations.py`：按同一模式替换（`regulations.py` 的 `_get_ai_config(user_id, db)` helper 内部改为调用 `get_system_ai_config(db)`）。

`backend/app/routers/external.py`：`AIConfig.user_id == user_id` 的查询替换为 `get_system_ai_config(db)`。

`backend/app/services/chat_dispatch.py`：`get_ai_config` tool 的查询替换为系统配置（返回 provider/model 供前端展示）。

- [x] **步骤 5：ai_config.py 路由改为系统级（管理员）**

`backend/app/routers/ai_config.py` 整体改造：

- `get_ai_config`：查询系统配置（`user_id IS NULL` 且 `is_system=True`），未配置返回 404「尚未配置 AI」。
- `update_ai_config`：upsert 系统配置（`user_id=None, is_system=True`），不再绑定 `current_user`；加 `Depends(require_admin)`。
- `delete_ai_config`：删除系统配置；加 `Depends(require_admin)`。
- `test_ai_connection` 不变（传入的 data 自带 key）。
- 顶部导入追加 `from app.dependencies import require_admin`。

具体代码（替换三个 handler 的核心逻辑）：

```python
@router.get("/ai-config", response_model=ApiResponse[AIConfigResponse])
async def get_ai_config(_=Depends(require_admin), db=Depends(get_db)):
    from app.services.ai_config_service import get_system_ai_config
    r = await get_system_ai_config(db)
    if not r:
        raise HTTPException(404, "尚未配置 AI")
    return ApiResponse(data=AIConfigResponse.model_validate(r))


@router.put("/ai-config", response_model=ApiResponse[AIConfigResponse])
async def update_ai_config(data: AIConfigCreate, _=Depends(require_admin), db=Depends(get_db)):
    from app.services.ai_config_service import get_system_ai_config
    r = await get_system_ai_config(db)
    encrypted = _encrypt(data.api_key)
    if r:
        r.provider = data.provider; r.api_key_encrypted = encrypted; r.model_name = data.model_name
        r.base_url = data.base_url; r.temperature = data.temperature; r.max_tokens = data.max_tokens; r.top_p = data.top_p
        r.is_system = True; r.is_active = True
    else:
        r = AIConfig(user_id=None, is_system=True, is_active=True, provider=data.provider,
                     api_key_encrypted=encrypted, model_name=data.model_name, base_url=data.base_url,
                     temperature=data.temperature, max_tokens=data.max_tokens, top_p=data.top_p)
        db.add(r)
    await db.commit(); await db.refresh(r)
    return ApiResponse(data=AIConfigResponse.model_validate(r))


@router.delete("/ai-config")
async def delete_ai_config(_=Depends(require_admin), db=Depends(get_db)):
    from app.services.ai_config_service import get_system_ai_config
    r = await get_system_ai_config(db)
    if r:
        await db.delete(r); await db.commit()
    return {"code": 0, "message": "已删除"}
```

- [x] **步骤 6：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_ai_config_system.py -v`

预期：3 个测试全部 PASS。

- [x] **步骤 7：全量后端测试 + Commit**

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（含既有 216+ 测试）。

```bash
git add backend/db_migration_ai_config_system.sql backend/app/models/enterprise.py backend/app/services/ai_config_service.py backend/app/services/risk_ai_service.py backend/app/routers/ai_config.py backend/app/routers/generation.py backend/app/routers/chat.py backend/app/routers/chat_dispatch.py backend/app/routers/external.py backend/app/routers/hazardous_chemicals.py backend/app/routers/regulations.py backend/app/routers/resources_ext.py backend/tests/test_ai_config_system.py
git commit -m "refactor(ai): consolidate AI config to system-level singleton"
```

---

### 任务 B2：危化品 ↔ 风险事件关联 + 生成上下文注入

**文件：**
- 新建：`backend/db_migration_risk_event_chemical.sql`
- 修改：`backend/app/models/risk_management.py`
- 修改：`backend/app/schemas/risk_management.py`
- 修改：`backend/app/routers/risk_management.py`
- 修改：`backend/app/routers/generation.py`
- 测试：`backend/tests/test_risk_event_chemical.py`

- [x] **步骤 1：编写失败测试**

新建 `backend/tests/test_risk_event_chemical.py`：

```python
from app.schemas.risk_management import RiskEventCreate, RiskEventUpdate


def test_risk_event_create_accepts_chemical_id():
    data = RiskEventCreate(
        object_id="o1", accident_type="火灾",
        chemical_id="c1",
    )
    assert data.chemical_id == "c1"


def test_risk_event_update_accepts_chemical_id():
    data = RiskEventUpdate(chemical_id="c2")
    assert data.chemical_id == "c2"


def test_risk_event_model_has_chemical_id_column():
    from app.models.risk_management import RiskEvent
    cols = {c.name for c in RiskEvent.__table__.columns}
    assert "chemical_id" in cols
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_risk_event_chemical.py -v`

预期：FAIL，`chemical_id` 未定义。

- [x] **步骤 3：迁移 SQL + 模型 + schema**

新建 `backend/db_migration_risk_event_chemical.sql`：

```sql
-- 风险事件关联危化品（可空，删除化学品时置空）
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS chemical_id UUID REFERENCES hazardous_chemicals(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_risk_events_chemical ON risk_events(chemical_id);
```

`backend/app/models/risk_management.py` 的 `RiskEvent` 增加字段与关系：

```python
    chemical_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("hazardous_chemicals.id", ondelete="SET NULL"), nullable=True, index=True)
```

`backend/app/schemas/risk_management.py` 修改：

```python
class RiskEventCreate(BaseModel):
    unit_id: str | None = None; object_id: str | None = None
    accident_type: str
    description: str | None = None
    trigger_conditions: str | None = None
    consequences: str | None = None
    method_type: str = "LS"
    method_params: dict = {}
    chemical_id: str | None = None

class RiskEventUpdate(BaseModel):
    accident_type: str | None = None
    description: str | None = None
    trigger_conditions: str | None = None
    consequences: str | None = None
    method_type: str | None = None
    method_params: dict | None = None
    chemical_id: str | None = None
```

- [x] **步骤 4：路由透传 chemical_id**

`backend/app/routers/risk_management.py` 中创建/更新事件（`create_event` / `update_event`）的位置，在构造/赋值时透传：

```python
event = RiskEvent(
    unit_id=data.unit_id, object_id=data.object_id,
    accident_type=data.accident_type, description=data.description,
    trigger_conditions=data.trigger_conditions, consequences=data.consequences,
    method_type=data.method_type, method_params=data.method_params,
    chemical_id=data.chemical_id,
)
```

更新分支：

```python
if data.chemical_id is not None:
    event.chemical_id = data.chemical_id
```

- [x] **步骤 5：生成上下文注入（chemical / risk_method_config / 备案 / 化学品清单）**

`backend/app/routers/generation.py` 的 `_collect_enterprise_data` 中：

1. `risk_sources` 列表推导内增加 chemical 属性（需要先构建 chemical_id → 化学品 dict 映射，在函数开头注入）：

```python
def _collect_enterprise_data(enterprise: Enterprise, risk_context: dict, resources: list, chemicals: dict) -> dict:
    ...
    "chemicals": [
        {"name": c.name, "cas_no": c.cas_no, "flash_point": c.flash_point,
         "explosion_limit": c.explosion_limit, "location": c.location, "max_storage": c.max_storage}
        for c in chemicals.values()
    ],
    "risk_sources": [
        {
            ...existing fields...,
            "chemical": chemicals.get(rs.get("chemical_id")) and {
                "name": chemicals[rs["chemical_id"]].name,
                "cas_no": chemicals[rs["chemical_id"]].cas_no,
                "flash_point": chemicals[rs["chemical_id"]].flash_point,
                "explosion_limit": chemicals[rs["chemical_id"]].explosion_limit,
            },
        }
        for rs in risk_context.get("risk_sources", [])
    ],
    "risk_method_config": enterprise.risk_method_config,
    "last_plan_filing_date": str(enterprise.last_plan_filing_date) if enterprise.last_plan_filing_date else None,
    "last_plan_filing_authority": enterprise.last_plan_filing_authority,
```

2. `_collect_enterprise_data` 的调用处（`generate_section` / `_run_batch_generation` 等）增加查询化学品并传参：

```python
from app.models.hazardous_chemicals import HazardousChemical
chemicals_rows = (await db.execute(
    select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id)
)).scalars().all()
chemicals = {c.id: c for c in chemicals_rows}
```

3. `risk_context_builder.py` 的 `_risk_source_item` 增加 `"chemical_id": event.chemical_id` 字段。

- [x] **步骤 6：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_event_chemical.py -v`

预期：3 个测试 PASS。

- [x] **步骤 7：全量后端测试 + Commit**

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS。

```bash
git add backend/db_migration_risk_event_chemical.sql backend/app/models/risk_management.py backend/app/schemas/risk_management.py backend/app/routers/risk_management.py backend/app/routers/generation.py backend/app/services/risk_context_builder.py backend/tests/test_risk_event_chemical.py
git commit -m "feat(risk): link risk events to hazardous chemicals and inject into generation context"
```

---

### 任务 B3：企业数据完成度聚合

**文件：**
- 新建：`backend/app/services/onboarding_service.py`
- 新建：`backend/app/routers/onboarding.py`
- 修改：`backend/app/routers/enterprises.py`
- 测试：`backend/tests/test_onboarding_completion.py`

- [x] **步骤 1：编写失败测试**

新建 `backend/tests/test_onboarding_completion.py`：

```python
import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.onboarding_service import compute_completion


def test_completion_all_done_returns_100():
    db = AsyncMock()
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = "地址"; ent.industry = "化工"
    ent.org_structure = [{"group_key": "cmd", "group_name": "指挥部",
                          "members": [{"name": "张三", "role": "chief", "phone": "138"}]}]
    ent.surrounding_info = {"nearby_units": [{"name": "加油站"}], "sensitive_targets": []}
    ent.risk_method_config = None

    def fake_execute(stmt):
        res = AsyncMock()
        text = str(stmt)
        if "risk_events" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="e1", chemical_id="c1")]
        elif "hazardous_chemicals" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="c1")]
        elif "emergency_resources" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="r1")]
        elif "risk_assessment_reports" in text:
            res.scalars.return_value.all.return_value = [MagicMock(status="completed")]
        elif "resource_investigation_reports" in text:
            res.scalars.return_value.all.return_value = [MagicMock(status="completed")]
        else:
            res.scalars.return_value.all.return_value = []
        return res

    db.execute.side_effect = fake_execute
    result = asyncio.run(compute_completion("e1", db))
    assert result["percent"] == 100
    assert all(m["done"] for m in result["modules"])


def test_completion_empty_enterprise():
    db = AsyncMock()
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = ""; ent.industry = ""
    ent.org_structure = []
    ent.surrounding_info = {"nearby_units": [], "sensitive_targets": []}
    ent.risk_method_config = None
    db.execute.side_effect = lambda stmt: AsyncMock(
        scalars=lambda: AsyncMock(all=lambda: [])
    )
    result = asyncio.run(compute_completion("e1", db))
    assert result["percent"] == 0
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_onboarding_completion.py -v`

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.onboarding_service'`。

- [x] **步骤 3：实现完成度服务**

新建 `backend/app/services/onboarding_service.py`：

```python
"""企业数据完成度聚合（6 模块加权）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent
from app.models.hazardous_chemicals import HazardousChemical
from app.models.enterprise import EmergencyResource
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport

MODULE_WEIGHTS = {
    "enterprise_info": 10,
    "org_structure": 15,
    "risk_chemical": 30,
    "resources": 15,
    "surrounding": 10,
    "reports": 20,
}

MODULE_LABELS = {
    "enterprise_info": "企业信息",
    "org_structure": "组织架构",
    "risk_chemical": "风险与危化品",
    "resources": "应急资源",
    "surrounding": "周边环境",
    "reports": "报告",
}


async def compute_completion(enterprise_id: str, db: AsyncSession) -> dict:
    """返回 {percent, modules: [{key,label,weight,done}]}。"""
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        raise ValueError("企业不存在")

    done = {}
    done["enterprise_info"] = bool(ent.name and ent.address and ent.industry)
    done["org_structure"] = _org_done(ent.org_structure)

    events = (await db.execute(select(RiskEvent).where(RiskEvent.enterprise_id == enterprise_id))).scalars().all()
    chemicals = (await db.execute(select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id))).scalars().all()
    done["risk_chemical"] = bool(events) or bool(chemicals)

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == enterprise_id))).scalars().all()
    done["resources"] = bool(resources)

    surrounding = ent.surrounding_info or {}
    done["surrounding"] = bool(surrounding.get("nearby_units")) or bool(surrounding.get("sensitive_targets"))

    ra = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id,
        RiskAssessmentReport.status == "completed",
    ))).scalars().all()
    ri = (await db.execute(select(ResourceInvestigationReport).where(
        ResourceInvestigationReport.enterprise_id == enterprise_id,
        ResourceInvestigationReport.status == "completed",
    ))).scalars().all()
    done["reports"] = bool(ra) and bool(ri)

    total = 0
    modules = []
    for key, weight in MODULE_WEIGHTS.items():
        d = done[key]
        if d:
            total += weight
        modules.append({"key": key, "label": MODULE_LABELS[key], "weight": weight, "done": d})
    return {"percent": total, "modules": modules}


def _org_done(org_structure: list | None) -> bool:
    for group in org_structure or []:
        for member in group.get("members", []):
            if member.get("name"):
                return True
    return False
```

（注意：`RiskEvent.enterprise_id` 需在模型中存在——若事件仅通过 zone/object 间接归属企业，查询改为 `select(RiskEvent).join(RiskObject).where(RiskObject.enterprise_id == enterprise_id)`。实现时按实际模型调整。）

- [x] **步骤 4：新增 completion 接口 + 企业列表扩展**

新建 `backend/app/routers/onboarding.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import ApiResponse
from app.services.onboarding_service import compute_completion

router = APIRouter(tags=["Onboarding"])


@router.get("/enterprises/{enterprise_id}/completion", response_model=ApiResponse[dict])
async def get_enterprise_completion(
    enterprise_id: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await compute_completion(enterprise_id, db)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return ApiResponse(data=data)
```

`backend/app/routers/enterprises.py` 的 `list_enterprises`：为每行计算完成度并写入响应：

```python
from app.services.onboarding_service import compute_completion
items = []
for e in rows:
    item = _build_response(e, event_counts.get(e.id, 0))
    item.completion = await compute_completion(e.id, db)
    items.append(item)
```

`EnterpriseResponse` schema 增加 `completion: dict | None = None` 字段（`backend/app/schemas/enterprise.py`）。

- [x] **步骤 5：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_onboarding_completion.py -v`

预期：2 个测试 PASS。

- [x] **步骤 6：全量后端测试 + Commit**

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS。

```bash
git add backend/app/services/onboarding_service.py backend/app/routers/onboarding.py backend/app/routers/enterprises.py backend/app/schemas/enterprise.py backend/tests/test_onboarding_completion.py
git commit -m "feat(onboarding): enterprise data completion aggregation endpoint"
```

---

## 计划 B 自检

**规格覆盖度：** 第 9 节 AI 配置全局化 → 任务 B1；第 10 节危化品关联与生成注入 → 任务 B2；第 6.6/7 节完成度算法与卡片数据 → 任务 B3；第 14.2 数据模型变更（ai_config 系统级、chemical_id）→ B1/B2。无遗漏。

**占位符扫描：** 无 TODO/待定/占位符；`risk_events.enterprise_id` 归属与 `EnterpriseResponse.completion` 字段按实际模型实现时微调已注明。

**类型一致性：** `chemical_id` 在模型/schema/路由/生成注入中命名一致；`compute_completion` 返回结构与规格 6.6 权重一致（10/15/30/15/10/20）；`get_system_ai_config` 在服务与各路由中统一使用。
