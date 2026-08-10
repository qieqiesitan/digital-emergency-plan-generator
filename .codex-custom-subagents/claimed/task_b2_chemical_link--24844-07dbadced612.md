# Codex Custom Subagents task handoff v1

Task: task_b2_chemical_link

## 任务：危化品 ↔ 风险事件关联 + 生成上下文注入（易用性优化计划 B 任务 B2）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 B1 提交（adc0843）。启动时 `cd` 到该目录，git status 确认干净（chroma.sqlite3 若有未暂存改动属测试副作用，可恢复）。

### 步骤 1：编写失败测试

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

运行确认失败：`cd backend && python -m pytest tests/test_risk_event_chemical.py -v`。

### 步骤 2：迁移 SQL + 模型 + schema

新建 `backend/db_migration_risk_event_chemical.sql`：

```sql
-- 风险事件关联危化品（可空，删除化学品时置空）
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS chemical_id UUID REFERENCES hazardous_chemicals(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_risk_events_chemical ON risk_events(chemical_id);
```

`backend/app/models/risk_management.py` 的 `RiskEvent` 增加：

```python
    chemical_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("hazardous_chemicals.id", ondelete="SET NULL"), nullable=True, index=True)
```

`backend/app/schemas/risk_management.py` 修改（RiskEventCreate/RiskEventUpdate 增加 chemical_id 字段）：

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

### 步骤 3：路由透传 chemical_id

`backend/app/routers/risk_management.py` 中创建/更新事件处透传（按实际代码结构调整）：

创建：
```python
event = RiskEvent(
    unit_id=data.unit_id, object_id=data.object_id,
    accident_type=data.accident_type, description=data.description,
    trigger_conditions=data.trigger_conditions, consequences=data.consequences,
    method_type=data.method_type, method_params=data.method_params,
    chemical_id=data.chemical_id,
)
```

更新：
```python
if data.chemical_id is not None:
    event.chemical_id = data.chemical_id
```

### 步骤 4：生成上下文注入

`backend/app/services/risk_context_builder.py` 的 `_risk_source_item` 增加字段：

```python
        "chemical_id": event.chemical_id,
```

`backend/app/routers/generation.py`：

1. `_collect_enterprise_data` 增加参数 `chemicals: dict`（chemical_id → HazardousChemical 映射），返回 dict 增加：

```python
    "chemicals": [
        {"name": c.name, "cas_no": c.cas_no, "flash_point": c.flash_point,
         "explosion_limit": c.explosion_limit, "location": c.location, "max_storage": c.max_storage}
        for c in chemicals.values()
    ],
```

2. `risk_sources` 列表推导内增加 chemical 属性（引用 chemicals 映射，无关联时为 None）：

```python
            "chemical": chemicals.get(rs.get("chemical_id")) and {
                "name": chemicals[rs["chemical_id"]].name,
                "cas_no": chemicals[rs["chemical_id"]].cas_no,
                "flash_point": chemicals[rs["chemical_id"]].flash_point,
                "explosion_limit": chemicals[rs["chemical_id"]].explosion_limit,
            },
```

3. 返回 dict 增加：

```python
    "risk_method_config": enterprise.risk_method_config,
    "last_plan_filing_date": str(enterprise.last_plan_filing_date) if enterprise.last_plan_filing_date else None,
    "last_plan_filing_authority": enterprise.last_plan_filing_authority,
```

4. `_collect_enterprise_data` 的调用处（generate_section / _run_batch_generation / generate_preview 等）增加化学品查询并传参：

```python
from app.models.hazardous_chemicals import HazardousChemical
chemicals_rows = (await db.execute(
    select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id)
)).scalars().all()
chemicals = {c.id: c for c in chemicals_rows}
```

（先读 generation.py 确认调用处数量与签名，逐一更新；保持签名演进一致。）

### 步骤 5：运行测试验证通过

运行：`cd backend && python -m pytest tests/test_risk_event_chemical.py -v`

预期：3 个测试 PASS。

### 步骤 6：全量后端测试 + Commit

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（与基线一致）。

```bash
git add backend/db_migration_risk_event_chemical.sql backend/app/models/risk_management.py backend/app/schemas/risk_management.py backend/app/routers/risk_management.py backend/app/routers/generation.py backend/app/services/risk_context_builder.py backend/tests/test_risk_event_chemical.py
git commit -m "feat(risk): link risk events to hazardous chemicals and inject into generation context"
```

## 上下文

- B1 已把 AI 配置切到系统级（不影响本任务）；generation.py 现有结构以 worktree 实际为准（附图扩展已合入，_collect_enterprise_data 已有 risk_events/zones/risk_objects 字段，本任务在其基础上追加）。
- 现有代码：RiskEvent 模型（risk_management.py）、RiskEventCreate/Update schema、risk_management.py 路由（create_event/update_event）、generation.py `_collect_enterprise_data`、risk_context_builder.py `_risk_source_item`。
- HazardousChemical 模型在 `backend/app/models/hazardous_chemicals.py`（enterprise_id/name/cas_no/flash_point/explosion_limit/location/max_storage）。

## 开始之前

对需求/方案/依赖有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述 TDD 实现
2. 运行测试验证（步骤 5/6）
3. 提交（步骤 6）
4. 自审：chemical_id 在模型/schema/路由/上下文注入命名一致？所有 _collect_enterprise_data 调用处都传了 chemicals？无残留旧签名？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、测试结果、提交 SHA、自审发现、任何疑虑
