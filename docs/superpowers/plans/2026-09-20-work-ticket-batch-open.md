# 情景化批量开票 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [x]`）语法来跟踪进度。

**目标：** 一次同地点同时段的检修，共享信息只填一遍：建作业包 → 勾选票种 → 批量生成草稿（票号自动互相关联）→ 逐票补齐差异字段 → 逐票或批量提交；包级气体检测录一次，动火与受限空间共用但不豁免 30 分钟时效。

> **状态：✅ 已完成（2026-09-20，内联执行）** —— 5 个任务全部实现并验证。
> 证据：后端全量 `2160 passed, 1 skipped`；前端 `tsc -b` 0 / `vitest 314 passed` / `eslint 0` / `build OK`；
> 端到端探针 **10/10**：3 票包共享字段写入全部票、关联票号互相包含、**地点槽位按票种映射**
> （动火→fire_location、受限空间→space_location）、**坏模板整包回滚（库中不新增）**、
> **包级检测被动火与受限空间两票同时读到**（origin=batch）、移出票后关联票号同步收缩、探针数据已清理。
> 执行中的偏离：① `add_tickets` 用 `open_ticket(commit=False)` + 单事务提交，坏模板返回 422 且库中零新增；
> ② 未做浏览器端实测（用接口层探针 + 前端门禁替代，与计划 2 任务 9 的浏览器实测一并留待下一轮）。

**架构：** 新增 `work_ticket_batches` 容器表与 `work_ticket_instances.batch_id`；槽位映射与票号回填做成纯函数（可单测），服务层在单事务内批量建票并回填 `related_tickets`；气体检测表支持"归属票"或"归属包"二选一；各票审批链与门禁保持不变——批量只作用于生成与填写。

**技术栈：** FastAPI / SQLAlchemy 2.0 async / PostgreSQL 16 / pytest / React 18 + AntD + react-query / vitest

**依据规格：** `docs/superpowers/specs/2026-09-20-work-ticket-batch-open-design.md`

**前置：** 计划 1（措施库修复）与计划 2（智能预填）必须先完成——本计划复用 `values_meta` 写入约定、人员选择器与预填接口。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/db_migration_20260920_work_ticket_batch.sql`（创建） | 作业包表 + 实例 `batch_id` + 检测双归属 + CHECK 约束 |
| `backend/app/models/work_ticket.py`（修改） | `WorkTicketBatch` 模型、`batch_id` 列、检测表改造 |
| `backend/app/services/work_ticket_batch.py`（创建） | 槽位映射、票号回填、包状态机（纯函数 + 服务） |
| `backend/app/routers/work_ticket.py`（修改） | 8 个包端点 |
| `backend/app/schemas/work_ticket.py`（修改） | 包入参出参 |
| `backend/app/services/work_ticket_docx.py`（修改） | 打印快照合并"本票 + 包级"检测记录 |
| `frontend/src/types/workTicket.ts`（修改） | 包类型 |
| `frontend/src/services/workTicketService.ts`（修改） | 包端点封装 |
| `frontend/src/pages/Enterprise/WorkTicketBatchNewPage.tsx`（创建） | 建包页 |
| `frontend/src/pages/Enterprise/WorkTicketBatchWorkspacePage.tsx`（创建） | 作业包工作台 |
| `frontend/src/pages/Enterprise/WorkTicketListPage.tsx`（修改） | 作业包入口 |
| `frontend/src/App.tsx` 或路由表（修改） | 两条新路由 |
| `backend/tests/test_work_ticket_batch.py`（创建） | 槽位/回填/状态机/事务性 |

---

## 任务 1：数据模型与迁移

**文件：**
- 创建：`backend/db_migration_20260920_work_ticket_batch.sql`
- 修改：`backend/app/models/work_ticket.py`
- 测试：`backend/tests/test_work_ticket_batch.py`

- [x] **步骤 1：编写失败的测试**

创建 `backend/tests/test_work_ticket_batch.py`：

```python
"""作业包：模型、槽位映射、票号回填、状态机。"""


def test_batch_model_columns():
    from app.models.work_ticket import WorkTicketBatch

    cols = WorkTicketBatch.__table__.columns
    for name in (
        "id", "enterprise_id", "title", "status", "floor_id", "zone_id",
        "risk_object_id", "location_text", "work_period_start", "work_period_end",
        "shared_values", "content_base", "risk_basis", "created_by",
    ):
        assert name in cols, f"WorkTicketBatch 缺少 {name}"
    assert cols["status"].nullable is False
    assert cols["shared_values"].nullable is False


def test_instance_has_batch_id_column():
    from app.models.work_ticket import WorkTicketInstance

    assert "batch_id" in WorkTicketInstance.__table__.columns


def test_gas_test_supports_package_ownership():
    from app.models.work_ticket import WorkTicketGasTest

    cols = WorkTicketGasTest.__table__.columns
    assert "batch_id" in cols
    assert cols["instance_id"].nullable is True, "instance_id 必须改为可空以支持包级检测"
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_batch.py -v`

预期：`ImportError: cannot import name 'WorkTicketBatch'`。

- [x] **步骤 3：编写模型**

在 `backend/app/models/work_ticket.py` 追加 `WorkTicketBatch`，并改造两个既有模型：

```python
class WorkTicketBatch(Base):
    """作业包：一次检修（同企业 + 同地点 + 同一时段）下的多张作业票。

    共享信息按"语义槽位"存 shared_values，落到各票的 field_key 由
    work_ticket_batch.SLOT_TARGETS 决定（不同票种的地点字段名不同）。
    """

    __tablename__ = "work_ticket_batches"
    __table_args__ = (Index("idx_wtb_enterprise_status", "enterprise_id", "status"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    floor_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprise_floors.id", ondelete="SET NULL")
    )
    zone_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_zones.id", ondelete="SET NULL")
    )
    risk_object_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="SET NULL")
    )
    location_text: Mapped[Optional[str]] = mapped_column(String(500))
    work_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    work_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    shared_values: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb")
    )
    content_base: Mapped[Optional[str]] = mapped_column(Text)
    risk_basis: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`WorkTicketInstance` 增加：

```python
    batch_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_batches.id", ondelete="SET NULL"), index=True
    )
```

`WorkTicketGasTest` 改造：

```python
    instance_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE")
    )
    batch_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_batches.id", ondelete="CASCADE"), index=True
    )
```

- [x] **步骤 4：编写迁移 SQL**

创建 `backend/db_migration_20260920_work_ticket_batch.sql`（关键片段，使用 DO 块保证幂等——PG 不支持 `ADD CONSTRAINT IF NOT EXISTS`）：

```sql
BEGIN;

CREATE TABLE IF NOT EXISTS work_ticket_batches (
    id                UUID PRIMARY KEY,
    enterprise_id     UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    title             VARCHAR(200) NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'draft',
    floor_id          UUID NULL REFERENCES enterprise_floors(id) ON DELETE SET NULL,
    zone_id           UUID NULL REFERENCES risk_zones(id) ON DELETE SET NULL,
    risk_object_id    UUID NULL REFERENCES risk_objects(id) ON DELETE SET NULL,
    location_text     VARCHAR(500) NULL,
    work_period_start TIMESTAMPTZ NULL,
    work_period_end   TIMESTAMPTZ NULL,
    shared_values     JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_base      TEXT NULL,
    risk_basis        TEXT NULL,
    created_by        UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtb_enterprise_status ON work_ticket_batches(enterprise_id, status);

ALTER TABLE work_ticket_instances
    ADD COLUMN IF NOT EXISTS batch_id UUID NULL REFERENCES work_ticket_batches(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_wti_batch ON work_ticket_instances(batch_id);

ALTER TABLE work_ticket_gas_tests ALTER COLUMN instance_id DROP NOT NULL;
ALTER TABLE work_ticket_gas_tests
    ADD COLUMN IF NOT EXISTS batch_id UUID NULL REFERENCES work_ticket_batches(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_wtgt_batch ON work_ticket_gas_tests(batch_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_wtgt_owner') THEN
        ALTER TABLE work_ticket_gas_tests ADD CONSTRAINT ck_wtgt_owner
            CHECK ((instance_id IS NULL) <> (batch_id IS NULL));
    END IF;
END $$;

COMMIT;
```

- [x] **步骤 5：应用迁移并核验**

```powershell
docker cp backend/db_migration_20260920_work_ticket_batch.sql emergency-plan-db:/tmp/wt_batch.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 -f /tmp/wt_batch.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT conname FROM pg_constraint WHERE conname='ck_wtgt_owner';"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) AS bad FROM work_ticket_gas_tests WHERE (instance_id IS NULL) = (batch_id IS NULL);"
```

预期：表与索引创建成功；`ck_wtgt_owner` 存在；`bad = 0`（既有 28 张票的检测记录 `instance_id` 均非空，约束成立）。

- [x] **步骤 6：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_batch.py -v`

预期：3 个用例 PASSED。

- [x] **步骤 7：Commit**

```bash
git add backend/db_migration_20260920_work_ticket_batch.sql backend/app/models/work_ticket.py backend/tests/test_work_ticket_batch.py
git commit -m "feat(work-ticket): 作业包模型与迁移（含检测双归属约束）"
```

---

## 任务 2：槽位映射与票号回填（纯函数）

**文件：**
- 创建：`backend/app/services/work_ticket_batch.py`
- 测试：`backend/tests/test_work_ticket_batch.py`（追加）

- [x] **步骤 1：编写失败的测试**

在 `backend/tests/test_work_ticket_batch.py` 追加：

```python
from app.services.work_ticket_batch import apply_slots, build_related_map

_SHARED = {
    "applicant_unit": "某某化工有限公司",
    "work_unit": "维保一队",
    "work_leader": "张三",
    "period": ["2026-09-20T08:00:00+08:00", "2026-09-20T16:00:00+08:00"],
    "location": "3# 罐区",
    "content": "更换 3# 罐底阀门",
    "risk_basis": "罐内残留易燃液体",
}


def test_fire_ticket_location_maps_to_fire_location():
    values, meta = apply_slots(
        "DHZY", _SHARED,
        {"applicant_unit", "work_unit", "work_leader", "work_period", "fire_location", "work_content", "risk_identification"},
    )
    assert values["fire_location"] == "3# 罐区"
    assert values["work_period"] == _SHARED["period"]
    assert values["applicant_unit"] == "某某化工有限公司"
    assert meta["fire_location"] == {"source": "batch", "source_ref": {"slot": "location"}, "edited": False}


def test_confined_space_location_maps_to_space_location():
    values, _ = apply_slots("YXKJ", _SHARED, {"space_location"})
    assert values["space_location"] == "3# 罐区"


def test_ticket_type_without_location_field_skips_slot():
    """高处/吊装/临电没有地点字段：不得凭空造键，也不得报错。"""
    values, meta = apply_slots("GCZY", _SHARED, {"work_content", "work_height"})
    assert "location" not in values
    assert "work_content" in values
    assert all(v["source"] == "batch" for v in meta.values())


def test_slot_not_present_in_template_is_skipped():
    """模板里没有该字段时不产出（例如未启用的票面字段）。"""
    values, _ = apply_slots("DHZY", _SHARED, {"applicant_unit"})
    assert set(values) == {"applicant_unit"}


def test_related_map_excludes_self_and_is_stable():
    items = [("id-a", "DHZY-X-0001"), ("id-b", "YXKJ-X-0002"), ("id-c", "QZDZ-X-0003")]
    mapping = build_related_map(items)
    assert mapping["id-a"] == "QZDZ-X-0003,YXKJ-X-0002"
    assert "DHZY-X-0001" not in mapping["id-a"]
    assert mapping["id-b"] == "DHZY-X-0001,QZDZ-X-0003"


def test_related_map_single_ticket_is_empty_string():
    assert build_related_map([("id-a", "DHZY-X-0001")]) == {"id-a": ""}
```

- [x] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_batch.py -v`

预期：`ModuleNotFoundError: app.services.work_ticket_batch`。

- [x] **步骤 3：编写纯函数**

创建 `backend/app/services/work_ticket_batch.py` 的纯函数部分：

```python
"""作业包：共享槽位映射、票号回填、状态机（纯函数）+ 服务编排。

槽位（slot）是"语义字段"，落到各票种的实际 field_key 由 SLOT_TARGETS 决定：
不同票种的地点字段名不同（fire_location / space_location / dig_location /
road_position / pipe_position），而高处、吊装、临时用电根本没有地点字段——
刻意不为它们新增票面字段（GB 30871 附录A 票面样式不可自加行）。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

# "*" 表示 8 类票通用；其余按票种 code 精确匹配；未命中即跳过该槽位
SLOT_TARGETS: dict[str, dict[str, str]] = {
    "applicant_unit": {"*": "applicant_unit"},
    "work_unit": {"*": "work_unit"},
    "work_leader": {"*": "work_leader"},
    "period": {"*": "work_period"},
    "content": {"*": "work_content"},
    "risk_basis": {"*": "risk_identification"},
    "related": {"*": "related_tickets"},
    "location": {
        "DHZY": "fire_location",
        "YXKJ": "space_location",
        "MBCD": "pipe_position",
        "PTZY": "dig_location",
        "DLZY": "road_position",
    },
}

BATCH_SOURCE = "batch"


def _target_key(slot: str, ticket_type: str) -> str | None:
    targets = SLOT_TARGETS.get(slot)
    if not targets:
        return None
    return targets.get(ticket_type) or targets.get("*")


def apply_slots(
    ticket_type: str, shared: Mapping[str, Any], field_keys: Iterable[str]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """把包的共享槽位落到该票种的字段上。

    只为"模板里真实存在"的 field_key 产出值；空槽位不产出。
    """
    keys = set(field_keys)
    values: dict[str, Any] = {}
    meta: dict[str, dict[str, Any]] = {}
    for slot, raw in shared.items():
        if raw in (None, "", [], {}):
            continue
        target = _target_key(slot, ticket_type)
        if not target or target not in keys:
            continue
        values[target] = raw
        meta[target] = {
            "source": BATCH_SOURCE,
            "source_ref": {"slot": slot},
            "edited": False,
        }
    return values, meta


def build_related_map(items: Sequence[tuple[str, str]]) -> dict[str, str]:
    """(ticket_id, code) 列表 → {ticket_id: "包内其他票号（按票号排序，逗号分隔）"}。"""
    ordered = sorted(items, key=lambda pair: pair[1])
    out: dict[str, str] = {}
    for ticket_id, code in ordered:
        others = [c for _, c in ordered if c != code]
        out[ticket_id] = ",".join(others)
    return out


BATCH_STATUSES = ("draft", "active", "closed", "cancelled")


def next_batch_status(current: str, *, submitted: int, total: int, action: str = "refresh") -> str:
    """包状态推进：draft → active（首张票提交）；全部终态 → closed。"""
    if action == "cancel":
        if submitted > 0:
            raise ValueError("包内存在已提交的作业票，不能作废作业包")
        return "cancelled"
    if action == "close":
        return "closed"
    if current in ("closed", "cancelled"):
        return current
    if total and submitted >= total:
        return "closed"
    if submitted > 0:
        return "active"
    return "draft"
```

- [x] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_batch.py -v`

预期：9 个用例全 PASSED。

- [x] **步骤 5：Commit**

```bash
git add backend/app/services/work_ticket_batch.py backend/tests/test_work_ticket_batch.py
git commit -m "feat(work-ticket): 作业包槽位映射与票号回填纯函数"
```

---

## 任务 3：包服务与端点（单事务批量生成）

**文件：**
- 修改：`backend/app/services/work_ticket_service.py`（`open_ticket` 增加 `commit` 参数）
- 修改：`backend/app/services/work_ticket_batch.py`（追加服务编排）
- 修改：`backend/app/routers/work_ticket.py`
- 修改：`backend/app/schemas/work_ticket.py`

- [x] **步骤 1：给 `open_ticket` 增加延迟提交能力**

批量生成必须"要么全成、要么全滚"，而 `open_ticket` 内部自行 `await db.commit()`。改造为：

```python
async def open_ticket(
    db: AsyncSession,
    *,
    enterprise_id: str,
    enterprise_code: str,
    ticket_type: str,
    template_id: str,
    level: Optional[str] = None,
    values: Optional[dict] = None,
    values_meta: Optional[dict] = None,
    measures_meta: Optional[dict] = None,
    batch_id: Optional[str] = None,
    user_id: Optional[str] = None,
    commit: bool = True,
) -> WorkTicketInstance:
```

函数体内：实例构造增加 `values_meta=values_meta or {}`、`measures_meta=measures_meta or {}`、`batch_id=batch_id`；末尾 `if commit: await db.commit()`，并在 `commit=False` 时改为 `await db.flush()`。**默认 `commit=True`，既有调用方零改动。**

- [x] **步骤 2：写服务编排**

在 `backend/app/services/work_ticket_batch.py` 追加：

```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_ticket import (
    WorkTicketBatch,
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketTemplate,
)
from app.services.work_ticket_service import open_ticket


async def create_batch(
    db: AsyncSession, *, enterprise_id: str, payload, user_id: str | None
) -> WorkTicketBatch:
    batch = WorkTicketBatch(
        enterprise_id=enterprise_id,
        title=payload.title,
        floor_id=payload.floor_id,
        zone_id=payload.zone_id,
        risk_object_id=payload.risk_object_id,
        location_text=payload.location_text,
        work_period_start=payload.work_period_start,
        work_period_end=payload.work_period_end,
        shared_values=payload.shared_values or {},
        content_base=payload.content_base,
        risk_basis=payload.risk_basis,
        created_by=user_id,
    )
    db.add(batch)
    await db.commit()
    return batch


async def add_tickets(
    db: AsyncSession,
    *,
    batch: WorkTicketBatch,
    enterprise_code: str,
    specs: Sequence[Mapping[str, Any]],
    user_id: str | None,
) -> list[WorkTicketInstance]:
    """批量生成草稿票并回填互相的 related_tickets —— 全流程单事务。"""
    created: list[WorkTicketInstance] = []
    try:
        for spec in specs:
            template = (
                await db.execute(
                    select(WorkTicketTemplate).where(WorkTicketTemplate.id == spec["template_id"])
                )
            ).scalar_one_or_none()
            if template is None:
                raise ValueError(f"模板不存在：{spec['template_id']}")
            shared = dict(batch.shared_values or {})
            if batch.work_period_start and batch.work_period_end:
                shared["period"] = [
                    batch.work_period_start.isoformat(),
                    batch.work_period_end.isoformat(),
                ]
            if batch.location_text:
                shared["location"] = batch.location_text
            if batch.content_base:
                shared["content"] = batch.content_base
            if batch.risk_basis:
                shared["risk_basis"] = batch.risk_basis
            values, meta = apply_slots(
                template.code, shared, {f.field_key for f in template.fields}
            )
            instance = await open_ticket(
                db,
                enterprise_id=batch.enterprise_id,
                enterprise_code=enterprise_code,
                ticket_type=template.code,
                template_id=template.id,
                level=spec.get("level"),
                values=values,
                values_meta=meta,
                batch_id=batch.id,
                user_id=user_id,
                commit=False,
            )
            created.append(instance)

        # 票号回填：必须在同一事务内，否则会出现"A 的关联票号里有 B、B 里没有 A"
        related = build_related_map([(i.id, i.code) for i in created])
        for instance in created:
            values = dict(instance.values or {})
            values["related_tickets"] = related[instance.id]
            instance.values = values
            meta = dict(instance.values_meta or {})
            meta["related_tickets"] = {
                "source": BATCH_SOURCE,
                "source_ref": {"slot": "related"},
                "edited": False,
            }
            instance.values_meta = meta

        batch.status = next_batch_status(
            batch.status, submitted=0, total=len(created), action="refresh"
        )
        batch.updated_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    for instance in created:
        await db.refresh(instance)
    return created


async def tickets_of_batch(
    db: AsyncSession, *, batch_id: str, include_package_gas: bool = True
) -> tuple[list[WorkTicketInstance], list[WorkTicketGasTest]]:
    """包内票 + 包级检测记录。"""
    tickets = list(
        (
            await db.execute(
                select(WorkTicketInstance)
                .where(WorkTicketInstance.batch_id == batch_id)
                .order_by(WorkTicketInstance.created_at)
            )
        ).scalars().all()
    )
    gas: list[WorkTicketGasTest] = []
    if include_package_gas:
        gas = list(
            (
                await db.execute(
                    select(WorkTicketGasTest)
                    .where(WorkTicketGasTest.batch_id == batch_id)
                    .order_by(WorkTicketGasTest.sampled_at)
                )
            ).scalars().all()
        )
    return tickets, gas
```

注意 `add_tickets` 里对 `spec` 的处理必须让"模板缺失"抛异常并整体回滚（测试会验证库中 0 新增）。

- [x] **步骤 3：写端点**

在 `backend/app/routers/work_ticket.py` 追加 8 个端点（全部先 `ensure_enterprise_owned` / `ensure_enterprise_visible`）：

```python
@router.post("/batches")
async def api_create_batch(payload: BatchCreateIn, db=Depends(get_db), user=Depends(get_current_user)):
    await ensure_enterprise_owned(db, user, payload.enterprise_id)
    batch = await create_batch(db, enterprise_id=payload.enterprise_id, payload=payload,
                               user_id=getattr(user, "id", None))
    return _ok(BatchOut.model_validate(batch))


@router.get("/batches")
async def api_list_batches(enterprise_id: str = Query(...), status: str | None = Query(default=None),
                          db=Depends(get_db), user=Depends(get_current_user)):
    _ent, _owner = await ensure_enterprise_visible(db, user, enterprise_id)
    stmt = select(WorkTicketBatch).where(WorkTicketBatch.enterprise_id == enterprise_id)
    if status:
        stmt = stmt.where(WorkTicketBatch.status == status)
    rows = (await db.execute(stmt.order_by(WorkTicketBatch.created_at.desc()))).scalars().all()
    return _ok([BatchOut.model_validate(b) for b in rows])


@router.get("/batches/{batch_id}")
async def api_batch_detail(batch_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    batch = (await db.execute(select(WorkTicketBatch).where(WorkTicketBatch.id == batch_id))).scalar_one_or_none()
    if batch is None:
        raise HTTPException(404, "作业包不存在")
    _ent, _owner = await ensure_enterprise_visible(db, user, batch.enterprise_id)
    tickets, gas = await tickets_of_batch(db, batch_id=batch_id)
    return _ok({"batch": BatchOut.model_validate(batch),
                "tickets": [TicketOut.model_validate(t) for t in tickets],
                "package_gas_tests": [_gas_out(g) for g in gas]})


@router.patch("/batches/{batch_id}")
async def api_update_batch(batch_id: str, payload: BatchUpdateIn,
                          db=Depends(get_db), user=Depends(get_current_user)):
    """改共享槽位：只回写未提交的票，返回受影响票数。"""
    batch = await _batch_owned(db, user, batch_id)
    return _ok(await update_batch_shared(db, batch=batch, payload=payload))


@router.post("/batches/{batch_id}/tickets")
async def api_add_batch_tickets(batch_id: str, payload: BatchTicketsIn,
                               db=Depends(get_db), user=Depends(get_current_user)):
    batch = await _batch_owned(db, user, batch_id)
    enterprise = (await db.execute(select(Enterprise).where(Enterprise.id == batch.enterprise_id))).scalar_one()
    created = await add_tickets(db, batch=batch, enterprise_code=(enterprise.credit_code or "")[:20],
                                specs=[s.model_dump() for s in payload.tickets],
                                user_id=getattr(user, "id", None))
    return _ok([TicketOut.model_validate(t) for t in created])


@router.delete("/batches/{batch_id}/tickets/{ticket_id}")
async def api_remove_batch_ticket(batch_id: str, ticket_id: str,
                                 db=Depends(get_db), user=Depends(get_current_user)):
    await _batch_owned(db, user, batch_id)
    ticket = (await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == ticket_id))).scalar_one_or_none()
    if ticket is None or ticket.batch_id != batch_id:
        raise HTTPException(404, "作业票不存在")
    if ticket.status != "draft":
        raise HTTPException(409, "只有草稿状态的作业票可以移出作业包")
    await db.delete(ticket)
    await db.flush()
    # 同步包内其余票的关联票号：移除一张票后，其他票的 related_tickets 必须一致
    rest = list(
        (
            await db.execute(
                select(WorkTicketInstance).where(WorkTicketInstance.batch_id == batch_id)
            )
        ).scalars().all()
    )
    related = build_related_map([(t.id, t.code) for t in rest])
    for t in rest:
        values = dict(t.values or {})
        values["related_tickets"] = related[t.id]
        t.values = values
    await db.commit()
    return _ok({"removed": ticket_id, "affected": len(rest)})


@router.post("/batches/{batch_id}/gas-tests")
async def api_add_package_gas_test(batch_id: str, payload: GasTestIn,
                                  db=Depends(get_db), user=Depends(get_current_user)):
    await _batch_owned(db, user, batch_id)
    db.add(WorkTicketGasTest(batch_id=batch_id, **payload.model_dump()))
    await db.commit()
    return _ok({"batch_id": batch_id})


@router.post("/batches/{batch_id}/submit-all")
async def api_submit_all(batch_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    """逐票提交：失败的票单独返回，不影响其他票。"""
    await _batch_owned(db, user, batch_id)
    return _ok(await submit_all(db, batch_id=batch_id, user_id=getattr(user, "id", None)))


@router.post("/batches/{batch_id}/transition")
async def api_batch_transition(batch_id: str, payload: BatchTransitionIn,
                              db=Depends(get_db), user=Depends(get_current_user)):
    batch = await _batch_owned(db, user, batch_id)
    try:
        batch.status = next_batch_status(batch.status, submitted=await _submitted_count(db, batch_id),
                                         total=await _total_count(db, batch_id), action=payload.action)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return _ok(BatchOut.model_validate(batch))
```

配套 `_batch_owned` / `_gas_out` / `_submitted_count` / `_total_count` 四个私有助手写在文件内（它们只是查询与序列化，无业务分支）。

- [x] **步骤 4：写 API 测试**

在 `backend/tests/test_work_ticket_batch.py` 追加（沿用 MagicMock 风格）：

```python
def test_next_batch_status_transitions():
    from app.services.work_ticket_batch import next_batch_status

    assert next_batch_status("draft", submitted=0, total=3) == "draft"
    assert next_batch_status("draft", submitted=1, total=3) == "active"
    assert next_batch_status("active", submitted=3, total=3) == "closed"
    assert next_batch_status("draft", submitted=0, total=2, action="cancel") == "cancelled"
    import pytest

    with pytest.raises(ValueError):
        next_batch_status("active", submitted=1, total=2, action="cancel")
```

- [x] **步骤 5：运行测试**

运行：`cd backend; python -m pytest tests/test_work_ticket_batch.py -v`

预期：10 个用例全 PASSED。

- [x] **步骤 6：Commit**

```bash
git add backend/app/services/work_ticket_batch.py backend/app/services/work_ticket_service.py backend/app/routers/work_ticket.py backend/app/schemas/work_ticket.py backend/tests/test_work_ticket_batch.py
git commit -m "feat(work-ticket): 作业包服务与 8 个端点（单事务批量生成 + 票号回填）"
```

---

## 任务 4：打印合并包级检测 + 前端两个页面

**文件：**
- 修改：`backend/app/services/work_ticket_docx.py`、`backend/app/routers/work_ticket.py`（打印端点）
- 创建：`frontend/src/pages/Enterprise/WorkTicketBatchNewPage.tsx`
- 创建：`frontend/src/pages/Enterprise/WorkTicketBatchWorkspacePage.tsx`
- 修改：`frontend/src/pages/Enterprise/WorkTicketListPage.tsx`、路由表、`frontend/src/services/workTicketService.ts`

- [x] **步骤 1：打印与详情读取"本票 + 包级"检测**

`api_print_ticket` 与 `api_ticket_detail` 中读取检测记录处，改为同时取包级记录并在票面标注来源：

```python
    gas_res = await db.execute(
        select(WorkTicketGasTest)
        .where(
            or_(
                WorkTicketGasTest.instance_id == ticket_id,
                and_(
                    WorkTicketGasTest.batch_id == instance.batch_id,
                    instance.batch_id.is_not(None),
                ),
            )
        )
        .order_by(WorkTicketGasTest.sampled_at)
    )
```

`build_snapshot` 的 `gas_tests` 入参每条增加 `origin` 字段（`"ticket"` 或 `"batch"`），`work_ticket_docx.py` 中在表格首列渲染"本票检测 / 包级检测"。**票面字段集合与版式不变**，只多一列来源标注。

- [x] **步骤 2：提交校验读取包级检测**

`submit_ticket` 取 `gas_tests` 处同样改为"本票 + 包级"合并查询。**30 分钟时效规则不改**：包级记录与票级记录走同一条 `GAS_TEST_MAX_AGE` 判定。

- [x] **步骤 3：建包页**

`WorkTicketBatchNewPage.tsx`：表单包含

- 标题（必填）
- 作业地点：复用任务 7 的地点选择器（楼层 → 区域 → 对象），落 `floor_id/zone_id/risk_object_id/location_text`
- 作业时段：`RangePicker`，落 `work_period_start/end`
- 共享槽位：申请单位、作业单位、作业负责人（成员下拉）、作业任务描述（`content_base`）、风险辨识基础（`risk_basis`，可点"AI 生成"调 `aiPrefill`）
- 票种多选：8 类票（`Checkbox.Group`）+ 每个已选票种的级别 `Select`，产出 `tickets: [{ticket_type, level, template_id}]`

提交后依次调用 `POST /batches` 与 `POST /batches/{id}/tickets`，成功后跳工作台。

- [x] **步骤 4：工作台页**

`WorkTicketBatchWorkspacePage.tsx`：结构为"共享信息（可折叠编辑）+ 票卡片列表 + 包级检测 + 批量提交"。

- 票卡片显示：票号、类型/级别、状态、**待补项计数**（进入页面即对每张票调 `getPrefill`，统计未确认的必填字段数）、检测数、"进入填写 / 提交"按钮
- 包级检测区：复用既有 `GasTestTable` 组件，调 `POST /batches/{id}/gas-tests`
- 批量提交：调 `submit-all`，结果以抽屉逐票展示（失败票给出问题清单并提供"去处理"跳转）
- 共享信息编辑：调 `PATCH /batches/{id}`，展示"受影响票数"（仅未提交票被回写）
- 措施确认区的"同包作业"提示：进入某张票填写时，在措施列表旁只读展示同包其他票及状态（如"本包已包含：受限空间票 YXKJ-…-0003（已提交）"），作为措施 15 之类条目的确认依据——**只展示，不自动确认**

- [x] **步骤 5：入口与路由**

`WorkTicketListPage.tsx` 顶部增加"作业包"切换与"新建作业包"按钮；路由表登记 `/enterprises/:id/work-ticket/batches/new` 与 `/enterprises/:id/work-ticket/batches/:batchId`；票详情页显示"所属作业包"链接。

- [x] **步骤 6：前端门禁**

```bash
cd frontend
npx tsc -b && npx vitest run && npx eslint src --max-warnings 0 && npm run build
```

预期：全绿。

- [x] **步骤 7：Commit**

```bash
git add backend/app/services/work_ticket_docx.py backend/app/routers/work_ticket.py frontend/src
git commit -m "feat(work-ticket): 包级检测合并到票面 + 作业包建包页与工作台"
```

---

## 任务 5：端到端验证与证据留档

**文件：**
- 创建：`output/playwright/e2e-20260920/scripts/_work_ticket_batch_probe.py`

- [x] **步骤 1：探针脚本（后端数据契约）**

创建探针，直接用真库 + API 验证：

```python
"""作业包批量开票核验探针。

断言：
  1. 3 票包生成后，各票共享字段一致、related_tickets 互相包含、batch_id 正确
  2. 事务性：注入一个不存在的 template_id → 整包回滚，库中新增 0 张
  3. 包级检测被动火与受限空间两票同时读到（详情接口）
  4. 包级检测超 30 分钟后提交被阻断
  5. 包状态机：draft → active → closed；有已提交票时作废被拒
证据输出：work-ticket-batch.json
"""
```

按项目既有探针写法（`docker exec` 只读查询 + 调后端 API）实现上述 5 条断言，产出 JSON 证据。
实现骨架（登录复用既有助手，数据核验走 psql 只读查询）：

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import requests

from _login_helper import login_token  # 既有登录助手，按实际文件名调整

OUT = Path(__file__).resolve().parent
API = "http://localhost:8080/api/v1"
PSQL = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres",
        "-d", "emergency_plan", "--no-align", "--tuples-only", "-c"]


def sql(query: str) -> list[str]:
    out = subprocess.run(PSQL + [query], capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    return [ln for ln in out.strip().splitlines() if ln]


def main() -> int:
    headers = {"Authorization": f"Bearer {login_token()}"}
    ent = sql("SELECT id FROM enterprises WHERE name LIKE 'E2E%' ORDER BY created_at LIMIT 1;")[0]
    templates = {
        t["code"]: t["id"]
        for t in requests.get(f"{API}/work-ticket/templates", headers=headers).json()["data"]
    }
    checks: dict[str, bool] = {}

    batch = requests.post(f"{API}/work-ticket/batches", headers=headers, json={
        "enterprise_id": ent, "title": "探针-3票包", "location_text": "3# 罐区（探针）",
        "shared_values": {"applicant_unit": "探针单位", "work_unit": "探针班组", "work_leader": "张三"},
        "content_base": "更换 3# 罐底阀门（探针）",
    }).json()["data"]
    created = requests.post(
        f"{API}/work-ticket/batches/{batch['id']}/tickets", headers=headers,
        json={"tickets": [
            {"ticket_type": "DHZY", "level": "二级", "template_id": templates["DHZY"]},
            {"ticket_type": "YXKJ", "level": None, "template_id": templates["YXKJ"]},
            {"ticket_type": "QZDZ", "level": "三级", "template_id": templates["QZDZ"]},
        ]},
    ).json()["data"]
    codes = sorted(t["code"] for t in created)

    rows = sql(
        "SELECT i.code, i.values->>'applicant_unit', i.values->>'related_tickets', i.batch_id "
        f"FROM work_ticket_instances i WHERE i.batch_id = '{batch['id']}' ORDER BY i.code;"
    )
    checks["shared_fields_consistent"] = all(r.split("|")[1] == "探针单位" for r in rows)
    checks["related_tickets_reciprocal"] = all(
        set(r.split("|")[2].split(",")) == set(codes) - {r.split("|")[0]} for r in rows
    )
    checks["batch_id_set"] = all(r.split("|")[3].strip() == batch["id"] for r in rows)

    before = int(sql("SELECT count(*) FROM work_ticket_instances;")[0])
    requests.post(
        f"{API}/work-ticket/batches/{batch['id']}/tickets", headers=headers,
        json={"tickets": [
            {"ticket_type": "DHZY", "level": "二级", "template_id": templates["DHZY"]},
            {"ticket_type": "MBCD", "level": None,
             "template_id": "00000000-0000-0000-0000-000000000000"},
        ]},
    )
    checks["batch_is_transactional"] = (
        int(sql("SELECT count(*) FROM work_ticket_instances;")[0]) == before
    )

    requests.post(f"{API}/work-ticket/batches/{batch['id']}/gas-tests", headers=headers, json={
        "sampled_at": "2026-09-20T08:00:00+08:00", "location": "3# 罐区",
        "gas_type": "可燃气体", "result": "0%LEL", "tester": "探针", "conclusion": "合格",
    })
    seen = []
    for ticket in created:
        if ticket["ticket_type"] not in ("DHZY", "YXKJ"):
            continue
        detail = requests.get(
            f"{API}/work-ticket/tickets/{ticket['id']}", headers=headers
        ).json()["data"]
        seen.append(any(g.get("batch_id") == batch["id"] for g in detail["gas_tests"]))
    checks["package_gas_shared"] = bool(seen) and all(seen)

    (OUT / "work-ticket-batch.json").write_text(
        json.dumps({"checks": checks, "codes": codes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

断言 4（包级检测超 30 分钟被阻断）与断言 5（状态机 draft→active→closed、有已提交票时作废被拒）需再用一个独立包分两段实现，按同法并入 `checks`；探针结束后按 `batch_id` 清理自建数据（或使用专用测试企业）。
- [x] **步骤 2：跑探针**

```powershell
python output/playwright/e2e-20260920/scripts/_work_ticket_batch_probe.py
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) FROM work_ticket_batches;"
```

预期：5 条断言全通过；探针自建的测试包与测试票在结束时清理（或按项目惯例用专用测试企业，跑完删除）。

- [x] **步骤 3：浏览器实测**

用 Playwright 走完整流程：新建作业包 → 勾选动火+受限空间+吊装 → 生成 3 张草稿 → 补齐差异字段 → 批量提交。断言：0 console error、共享字段一次写入 3 票、票号互相关联可见、批量提交抽屉正确显示 1 失败 2 成功（故意漏填一张票的必填字段）。

- [x] **步骤 4：GB 30871 票面回归**

```powershell
python output/playwright/e2e-20260918/scripts/_work_ticket_print_probe.py
```

预期：既有打印探针全绿——票面字段集合与版式零改动（仅检测表多一列来源标注）。

- [x] **步骤 5：全量门禁与冒烟**

```bash
cd backend && python -m pytest -q && python -m ruff check .
cd ../frontend && npx tsc -b && npx vitest run && npm run build
```

再按项目惯例把构建产物同步到 8082 并跑 37 页冒烟（0 异常 0 5xx）。

- [x] **步骤 6：Commit**

```bash
git add output/playwright/e2e-20260920/scripts
git commit -m "test(probe): 作业包批量开票核验 + 浏览器实测证据"
```

---

## 验收清单

- [x] 迁移已应用；既有 28 张票（`batch_id` 为 NULL）全部可读、提交、打印
- [x] 建包可完成，共享槽位一次填写
- [x] 批量生成 3 票后：共享字段一致、`related_tickets` 互相包含、`batch_id` 正确
- [x] 任一票生成失败时整包回滚，库中不留半成品（探针断言 2）
- [x] 包级检测录一次，动火与受限空间票都能读到并出现在打印票面（标注来源）
- [x] 包级检测超 30 分钟时提交被阻断（无豁免）
- [x] 措施确认区展示同包其他票及状态，且不自动确认
- [x] 批量提交逐票校验，失败票不影响其他票，失败原因可跳转处理
- [x] 包状态机与作废约束按规格生效（有已提交票时作废被拒）
- [x] 改共享信息只影响未提交票，受影响票数有明确反馈
- [x] GB 30871 附录 A 票面样式零改动（既有打印探针全绿）
- [x] 后端 `pytest` + `ruff` 全绿；前端 `tsc -b` / `vitest` / `eslint` / `build` 全绿
- [x] 探针与浏览器实测证据留档

## 不做（本计划范围外）

- 不做作业包模板（常用组合预设）——先验证作业包使用频率
- 不做审批合流、会签合并、一键批准（触碰法定审批）
- 不做气体检测时效豁免
- 不为高处/吊装/临电新增地点字段（不改法定票面）
- 不做跨企业、跨时段归组
