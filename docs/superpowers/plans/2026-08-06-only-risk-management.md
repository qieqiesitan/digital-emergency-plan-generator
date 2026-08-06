# 只保留风险分级管控实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将企业风险数据入口收口为「风险分级管控」，完成旧风险源迁移闭环、下游链路切换和旧入口下线。

**架构：** 后端新增 `risk_source_migration_service` 和 `risk_stats_service`，通过 `build_risk_management_context` 统一向预案生成、风险评估、chat 提供新五层数据；前端迁移向导改为调用后端原子迁移接口，Web 和移动端不再暴露旧风险源入口。

**技术栈：** FastAPI + SQLAlchemy + PostgreSQL、React 19 + TypeScript + Ant Design、pytest、Vitest、Playwright。

---

## 任务 1：新增 legacy_source_id 字段和迁移 SQL

**文件：**
- 修改：`backend/app/models/risk_management.py`
- 创建：`backend/db_migration_risk_source_consolidation.sql`
- 测试：`backend/tests/test_risk_source_migration_baseline.py`

- [ ] **步骤 1：编写失败测试**

```python
import os

from app.models.risk_management import RiskObject

SQL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "db_migration_risk_source_consolidation.sql",
)


def test_risk_object_has_legacy_source_id():
    cols = {c.name for c in RiskObject.__table__.columns}
    assert "legacy_source_id" in cols


def test_migration_sql_adds_legacy_source_id():
    with open(SQL_PATH, encoding="utf-8") as f:
        sql = f.read()
    assert "ADD COLUMN IF NOT EXISTS legacy_source_id" in sql
    assert "idx_ro_legacy_source" in sql
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_source_migration_baseline.py -v`

预期：FAIL，`RiskObject` 没有 `legacy_source_id`，SQL 文件不存在。

- [ ] **步骤 3：实现模型字段**

在 `backend/app/models/risk_management.py` 的 `RiskObject` 类中，`description` 字段后新增：

```python
    legacy_source_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
```

- [ ] **步骤 4：创建迁移 SQL**

```sql
BEGIN;

ALTER TABLE risk_objects
    ADD COLUMN IF NOT EXISTS legacy_source_id VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_ro_legacy_source
    ON risk_objects(enterprise_id, legacy_source_id);

COMMIT;
```

- [ ] **步骤 5：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_source_migration_baseline.py -v`

预期：PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/models/risk_management.py backend/db_migration_risk_source_consolidation.sql backend/tests/test_risk_source_migration_baseline.py
git commit -m "feat(risk-management): add legacy source id migration baseline"
```

---

## 任务 2：新增迁移 Schema 和迁移服务

**文件：**
- 修改：`backend/app/schemas/risk_management.py`
- 创建：`backend/app/services/risk_source_migration_service.py`
- 测试：`backend/tests/test_risk_source_migration_service.py`

- [ ] **步骤 1：编写失败测试**

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.risk_source_migration_service import (
    build_default_mapping,
    execute_migration,
    split_control_measures,
)


def test_split_control_measures_supports_common_delimiters():
    text = "巡检；安装报警\n定期演练; 清理"
    result = split_control_measures(text)
    assert len(result) == 4
    assert "安装报警" in result


def test_default_mapping_uses_source_fields():
    src = MagicMock()
    src.id = "src-1"
    src.name = "火灾"
    src.categories = "火灾,电气"
    src.location = "仓库东区"
    src.likelihood = 4
    src.severity = 5
    src.control_measures = "定期巡检"

    item = build_default_mapping(src)

    assert item["suggested_object"] == "火灾"
    assert item["suggested_event"] == "火灾"
    assert item["source_categories"] == ["火灾", "电气"]
    assert item["suggested_params"] == {"l": 4, "s": 5}


def test_execute_migration_marks_sources_and_commits():
    db = AsyncMock()
    source = MagicMock()
    source.id = "src-1"
    source.enterprise_id = "ent-1"
    source.name = "火灾"
    source.categories = "火灾"
    source.location = "仓库"
    source.location_x = 10
    source.location_y = 20
    source.description = "可燃物堆积"
    source.likelihood = 3
    source.severity = 3
    source.control_measures = "定期巡检；安装报警"
    source.migrated = False

    mapping = MagicMock()
    mapping.source_id = "src-1"
    mapping.zone_name = "历史风险源"
    mapping.object_name = "火灾"
    mapping.accident_type = "火灾"
    mapping.method_params = {"l": 3, "s": 3}

    floor = MagicMock()
    floor.id = "floor-1"
    rating = MagicMock()
    rating.risk_level = "一般"
    rating.risk_score = "R=9"

    db.execute.return_value = AsyncMock()
    db.execute.return_value.scalars.return_value.all.return_value = [source]
    db.execute.return_value.scalar_one_or_none.side_effect = [None, None]
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with patch(
        "app.services.risk_source_migration_service.ensure_default_floor",
        new=AsyncMock(return_value=floor),
    ), patch(
        "app.services.risk_source_migration_service.get_active_method_config",
        new=AsyncMock(return_value={"risk_thresholds": []}),
    ), patch(
        "app.services.risk_source_migration_service.compute_risk",
        return_value=rating,
    ):
        result = asyncio.run(execute_migration(db, "ent-1", [mapping]))

    assert result["migrated"] == 1
    assert result["created"]["objects"] == 1
    assert source.migrated is True
    db.commit.assert_awaited_once()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_source_migration_service.py -v`

预期：FAIL，模块不存在。

- [ ] **步骤 3：新增迁移 Schema**

在 `backend/app/schemas/risk_management.py` 中替换迁移 Schema 区块：

```python
class MigrationPreviewItem(BaseModel):
    source_id: str
    source_name: str
    source_location: str | None = None
    source_categories: list[str] = []
    suggested_zone: str = "历史风险源"
    suggested_object: str = ""
    suggested_event: str = "安全生产事故"
    suggested_params: dict[str, int] = {"l": 3, "s": 3}
    control_measures: str | None = None


class MigrationPreviewResponse(BaseModel):
    items: list[MigrationPreviewItem]
    total: int
    migrated_total: int = 0


class MigrationExecuteItem(BaseModel):
    source_id: str
    zone_name: str
    object_name: str
    accident_type: str
    method_params: dict[str, int] = {"l": 3, "s": 3}


class MigrationExecuteRequest(BaseModel):
    mappings: list[MigrationExecuteItem]


class MigrationExecuteResponse(BaseModel):
    migrated: int = 0
    skipped: int = 0
    created: dict[str, int] = {}
```

- [ ] **步骤 4：实现迁移服务**

创建 `backend/app/services/risk_source_migration_service.py`：

```python
"""旧版 RiskSource 迁移到风险分级管控五层结构的服务。"""
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import RiskSource
from app.models.risk_management import RiskZone, RiskObject, RiskEvent, RiskMeasure
from app.services.risk_mapping_service import ensure_default_floor
from app.services.risk_method_engine import compute_risk, get_active_method_config


def split_control_measures(text: str | None) -> list[str]:
    """把旧控制措施自由文本按常见分隔符拆成多条措施。"""
    if not text or not text.strip():
        return []
    parts = re.split(r"[\n；;]+", text)
    return [p.strip() for p in parts if p.strip()]


def _clamp_ls(value) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        return 3
    return num if 1 <= num <= 5 else 3


def build_default_mapping(source: RiskSource) -> dict:
    """构造旧风险源到新五层的默认映射。"""
    categories = [
        c.strip()
        for c in (source.categories or "").split(",")
        if c.strip()
    ]
    return {
        "source_id": source.id,
        "source_name": source.name,
        "source_location": source.location,
        "source_categories": categories,
        "suggested_zone": "历史风险源",
        "suggested_object": source.name,
        "suggested_event": source.name or "安全生产事故",
        "suggested_params": {
            "l": _clamp_ls(source.likelihood),
            "s": _clamp_ls(source.severity),
        },
        "control_measures": source.control_measures,
    }


async def build_migration_preview(
    db: AsyncSession,
    enterprise_id: str,
    ai_mappings: list[dict] | None = None,
) -> dict:
    """返回未迁移旧风险源的默认映射，可叠加 AI 建议。"""
    sources = (
        await db.execute(
            select(RiskSource).where(
                RiskSource.enterprise_id == enterprise_id,
                RiskSource.migrated.is_(False),
            ).order_by(RiskSource.sort_order)
        )
    ).scalars().all()
    items = [build_default_mapping(s) for s in sources]
    migrated_total = (
        await db.execute(
            select(RiskSource).where(
                RiskSource.enterprise_id == enterprise_id,
                RiskSource.migrated.is_(True),
            )
        )
    ).scalars().all()

    if ai_mappings:
        by_id = {m.get("source_id"): m for m in ai_mappings if isinstance(m, dict)}
        for item in items:
            ai = by_id.get(item["source_id"], {})
            item["suggested_zone"] = ai.get("suggested_zone") or item["suggested_zone"]
            item["suggested_object"] = ai.get("suggested_object") or item["suggested_object"]
            item["suggested_event"] = (
                ai.get("suggested_accident_type")
                or ai.get("suggested_event")
                or item["suggested_event"]
            )
            params = ai.get("suggested_params") or item["suggested_params"]
            if isinstance(params, dict):
                item["suggested_params"] = {
                    "l": _clamp_ls(params.get("l")),
                    "s": _clamp_ls(params.get("s")),
                }

    return {
        "items": items,
        "total": len(items),
        "migrated_total": len(migrated_total),
    }


async def execute_migration(
    db: AsyncSession,
    enterprise_id: str,
    mappings: list,
) -> dict:
    """单事务迁移旧风险源到新五层，并写回 migrated。"""
    source_ids = [m.source_id for m in mappings]
    sources = (
        await db.execute(
            select(RiskSource).where(
                RiskSource.id.in_(source_ids),
                RiskSource.enterprise_id == enterprise_id,
                RiskSource.migrated.is_(False),
            )
        )
    ).scalars().all()
    source_map = {s.id: s for s in sources}
    floor = await ensure_default_floor(db, enterprise_id)
    config = await get_active_method_config(db, enterprise_id, "LS")
    if not config:
        config = {
            "risk_thresholds": [
                {"min": 20, "max": 25, "level": "重大", "action": "立即整改", "deadline": "立即"},
                {"min": 15, "max": 19, "level": "较大", "action": "限期整改", "deadline": "1 个月"},
                {"min": 10, "max": 14, "level": "一般", "action": "限期整改", "deadline": "3 个月"},
                {"min": 1, "max": 9, "level": "低", "action": "加强日常管理", "deadline": "持续"},
            ]
        }
    created = {"zones": 0, "objects": 0, "events": 0, "measures": 0}
    migrated = 0
    skipped = 0

    try:
        for mapping in mappings:
            source = source_map.get(mapping.source_id)
            if not source:
                skipped += 1
                continue

            existing = (
                await db.execute(
                    select(RiskObject).where(
                        RiskObject.enterprise_id == enterprise_id,
                        RiskObject.legacy_source_id == mapping.source_id,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                source.migrated = True
                migrated += 1
                continue

            zone = (
                await db.execute(
                    select(RiskZone).where(
                        RiskZone.enterprise_id == enterprise_id,
                        RiskZone.floor_id == floor.id,
                        RiskZone.name == mapping.zone_name,
                    )
                )
            ).scalar_one_or_none()
            if not zone:
                zone = RiskZone(
                    enterprise_id=enterprise_id,
                    floor_id=floor.id,
                    name=mapping.zone_name,
                )
                db.add(zone)
                await db.flush()
                created["zones"] += 1

            categories = [
                c.strip()
                for c in (source.categories or "").split(",")
                if c.strip()
            ]
            obj = RiskObject(
                enterprise_id=enterprise_id,
                zone_id=zone.id,
                floor_id=floor.id,
                name=mapping.object_name or source.name,
                category=categories[0] if categories else None,
                location=source.location,
                location_x=source.location_x,
                location_y=source.location_y,
                description=source.description,
                legacy_source_id=source.id,
            )
            db.add(obj)
            await db.flush()
            created["objects"] += 1

            params = {
                "l": _clamp_ls(mapping.method_params.get("l", source.likelihood)),
                "s": _clamp_ls(mapping.method_params.get("s", source.severity)),
            }
            rating = compute_risk("LS", params, config)
            event = RiskEvent(
                object_id=obj.id,
                accident_type=mapping.accident_type,
                description=source.description or "",
                method_type="LS",
                method_params=params,
                risk_level=rating.risk_level,
                risk_score=rating.risk_score,
            )
            db.add(event)
            await db.flush()
            created["events"] += 1

            for text in split_control_measures(source.control_measures):
                db.add(RiskMeasure(
                    event_id=event.id,
                    measure_category="management",
                    measure_type="旧数据迁移",
                    description=text,
                ))
                created["measures"] += 1

            source.migrated = True
            migrated += 1

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "migrated": migrated,
        "skipped": skipped,
        "created": created,
    }
```

- [ ] **步骤 5：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_source_migration_service.py -v`

预期：PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/schemas/risk_management.py backend/app/services/risk_source_migration_service.py backend/tests/test_risk_source_migration_service.py
git commit -m "feat(risk-management): add atomic legacy source migration service"
```

---

## 任务 3：迁移接口接入 risk_management 路由

**文件：**
- 修改：`backend/app/routers/risk_management.py`

- [ ] **步骤 1：更新导入**

在 `risk_management.py` 中新增：

```python
from app.schemas.risk_management import (
    MigrationExecuteRequest,
    MigrationExecuteResponse,
    MigrationPreviewResponse,
)
from app.services.risk_source_migration_service import (
    build_migration_preview,
    execute_migration as execute_risk_source_migration,
)
```

如果 `MigrationExecuteRequest` 已存在于原有导入行，则从原有导入行移除，避免重复导入。

- [ ] **步骤 2：替换 `/ai/migrate-preview`**

替换现有 `ai_migrate_preview` 函数体：

```python
@router.post("/ai/migrate-preview", response_model=ApiResponse[MigrationPreviewResponse])
async def ai_migrate_preview(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    mappings: list[dict] = []
    try:
        ai_config = await _get_ai_config(current_user.id, db)
        old = (await db.execute(
            select(RiskSource).where(
                RiskSource.enterprise_id == enterprise_id,
                RiskSource.migrated.is_(False),
            )
        )).scalars().all()
        if old:
            sources = [{
                "id": s.id,
                "name": s.name,
                "categories": s.categories,
                "location": s.location,
                "risk_level": s.risk_level,
                "description": s.description,
            } for s in old]
            mappings = await migrate_preview(sources, ai_config)
    except HTTPException:
        # 未配置 AI 时返回默认映射，不阻塞迁移
        mappings = []
    data = await build_migration_preview(db, enterprise_id, ai_mappings=mappings)
    return ApiResponse(data=MigrationPreviewResponse(**data))
```

- [ ] **步骤 3：替换 `GET /migrate/preview`**

```python
@router.get("/migrate/preview", response_model=ApiResponse[MigrationPreviewResponse])
async def get_migration_preview(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    data = await build_migration_preview(db, enterprise_id)
    return ApiResponse(data=MigrationPreviewResponse(**data))
```

- [ ] **步骤 4：替换 `POST /migrate/execute`**

```python
@router.post("/migrate/execute", response_model=ApiResponse[MigrationExecuteResponse])
async def execute_migration(body: MigrationExecuteRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    data = await execute_risk_source_migration(db, enterprise_id, body.mappings)
    return ApiResponse(
        data=MigrationExecuteResponse(**data),
        message=f"已迁移 {data['migrated']} 条数据",
    )
```

- [ ] **步骤 5：验证**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_source_migration_service.py backend/tests/test_risk_source_migration_baseline.py -v`

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/risk_management.py
git commit -m "feat(risk-management): wire legacy migration endpoints"
```

---

## 任务 4：前端迁移服务和向导闭环

**文件：**
- 修改：`frontend/src/types/riskManagement.ts`
- 修改：`frontend/src/services/riskManagementService.ts`
- 修改：`frontend/src/components/enterprise/RiskMigrationWizard.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`

- [ ] **步骤 1：新增前端迁移类型**

在 `frontend/src/types/riskManagement.ts` 末尾新增：

```ts
export interface MigrationPreviewItem {
  source_id: string;
  source_name: string;
  source_location: string | null;
  source_categories: string[];
  suggested_zone: string;
  suggested_object: string;
  suggested_event: string;
  suggested_params: Record<string, number>;
  control_measures: string | null;
}

export interface MigrationPreviewResponse {
  items: MigrationPreviewItem[];
  total: number;
  migrated_total: number;
}

export interface MigrationExecutePayload {
  source_id: string;
  zone_name: string;
  object_name: string;
  accident_type: string;
  method_params: Record<string, number>;
}

export interface MigrationExecuteResponse {
  migrated: number;
  skipped: number;
  created: {
    zones: number;
    objects: number;
    events: number;
    measures: number;
  };
}
```

- [ ] **步骤 2：新增前端服务**

在 `frontend/src/services/riskManagementService.ts` 中替换 `aiMigratePreview`，并新增两个函数：

```ts
export const getMigrationPreview = (eid: string) =>
  api.get<ApiResponse<MigrationPreviewResponse>>(`${BASE(eid)}/migrate/preview`).then(r => r.data.data);

export const aiMigratePreview = (eid: string) =>
  api.post<ApiResponse<MigrationPreviewResponse>>(`${BASE(eid)}/ai/migrate-preview`).then(r => r.data.data);

export const executeMigration = (eid: string, mappings: MigrationExecutePayload[]) =>
  api.post<ApiResponse<MigrationExecuteResponse>>(`${BASE(eid)}/migrate/execute`, { mappings }).then(r => r.data.data);
```

同时在文件头 import 中补充上述类型。

- [ ] **步骤 3：重写向导的数据加载和执行**

在 `RiskMigrationWizard.tsx` 中：

替换 `MigrationItem` 接口：

```ts
interface MigrationItem extends MigrationPreviewItem {
  _key: number;
  status: ItemStatus;
}
```

替换 `mapPreviewData`：

```ts
function mapPreviewData(raw: MigrationPreviewResponse): MigrationItem[] {
  return raw.items.map((item, i) => ({
    ...item,
    _key: i,
    status: "adopted" as ItemStatus,
  }));
}
```

替换 `loadPreview`：

```ts
const loadPreview = async () => {
  setLoadingPreview(true);
  try {
    const preview = await getMigrationPreview(enterpriseId);
    if (!preview || preview.items.length === 0) {
      message.warning("未检测到可迁移的旧版风险源数据");
      setItems([]);
      return;
    }
    setItems(mapPreviewData(preview));
    try {
      const aiPreview = await aiMigratePreview(enterpriseId);
      if (aiPreview?.items?.length) setItems(mapPreviewData(aiPreview));
    } catch {
      // AI 不可用时保留默认映射
    }
  } catch (e: any) {
    message.error("加载迁移预览失败: " + (e?.message || "请重试"));
    setItems([]);
  } finally {
    setLoadingPreview(false);
  }
};
```

替换 `migrateMut`：

```ts
const migrateMut = useMutation({
  mutationFn: async () => {
    const toMigrate = items.filter((it) => it.status !== "skipped");
    if (toMigrate.length === 0) {
      throw new Error("没有可迁移的项目");
    }
    const mappings: MigrationExecutePayload[] = toMigrate.map((it) => ({
      source_id: it.source_id,
      zone_name: it.suggested_zone,
      object_name: it.suggested_object,
      accident_type: it.suggested_event,
      method_params: it.suggested_params,
    }));
    return executeMigration(enterpriseId, mappings);
  },
  onSuccess: (data: MigrationExecuteResponse) => {
    message.success(`成功迁移 ${data.migrated} 条数据`);
    onRefresh();
    onClose();
  },
  onError: (e: Error) => {
    message.error("迁移失败: " + (e?.message || "未知错误"));
  },
});
```

同步更新 import：

```ts
import {
  getMigrationPreview,
  aiMigratePreview,
  executeMigration,
} from "@/services/riskManagementService";
import type {
  MigrationExecutePayload,
  MigrationExecuteResponse,
  MigrationPreviewItem,
  MigrationPreviewResponse,
} from "@/types/riskManagement";
```

- [ ] **步骤 4：挂载迁移入口**

在 `RiskManagementTab.tsx` 中：

新增 import：

```tsx
import { Alert } from "antd";
import RiskMigrationWizard from "@/components/enterprise/RiskMigrationWizard";
import { getMigrationPreview } from "@/services/riskManagementService";
```

新增状态和查询：

```tsx
const [migrationOpen, setMigrationOpen] = useState(false);
const { data: migrationPreview } = useQuery({
  queryKey: ["risk-migration-preview", enterpriseId],
  queryFn: () => getMigrationPreview(enterpriseId),
  enabled: !!enterpriseId,
});
```

在左侧树容器的 `Space` 上方新增：

```tsx
{migrationPreview && migrationPreview.total > 0 && (
  <Alert
    type="warning"
    showIcon
    style={{ marginBottom: 12 }}
    message={`检测到 ${migrationPreview.total} 条旧版风险源数据未迁移`}
    action={
      <Button size="small" type="primary" onClick={() => setMigrationOpen(true)}>
        迁移旧风险源
      </Button>
    }
  />
)}
<RiskMigrationWizard
  open={migrationOpen}
  onClose={() => setMigrationOpen(false)}
  onRefresh={() => {
    refetch();
    refetchFloors();
  }}
  enterpriseId={enterpriseId}
/>
```

- [ ] **步骤 5：验证**

运行：

```bash
cd frontend
npm run build
npm test
```

预期：`tsc -b` 无错误，Vitest 通过。

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/types/riskManagement.ts frontend/src/services/riskManagementService.ts frontend/src/components/enterprise/RiskMigrationWizard.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx
git commit -m "feat(risk-management): complete migration wizard loop"
```

---

## 任务 5：补齐风险上下文字段

**文件：**
- 修改：`backend/app/services/risk_context_builder.py`
- 测试：`backend/tests/test_risk_context_builder.py`

- [ ] **步骤 1：编写失败测试**

```python
from unittest.mock import MagicMock

from app.services.risk_context_builder import _risk_source_item


def test_risk_source_item_keeps_legacy_prompt_fields():
    zone = MagicMock(); zone.name = "生产区"
    obj = MagicMock(); obj.name = "原料仓库"; obj.category = "火灾"; obj.location = "东区"
    unit = MagicMock(); unit.name = "一号仓"
    event = MagicMock()
    event.accident_type = "火灾"
    event.risk_level = "较大"
    event.risk_score = "R=15"
    event.description = "可燃物堆积"
    event.trigger_conditions = "明火"
    event.consequences = "财产损失"
    measure = MagicMock()
    measure.measure_category = "management"
    measure.description = "定期巡检"
    event.measures = [measure]

    item = _risk_source_item(zone, obj, unit, event)

    assert item["name"] == "原料仓库"
    assert item["categories"] == "火灾"
    assert item["location"] == "东区"
    assert item["control_measures"] == "定期巡检"
    assert item["zone"] == "生产区"
    assert item["unit"] == "一号仓"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_context_builder.py -v`

预期：FAIL，`_risk_source_item` 不存在。

- [ ] **步骤 3：实现上下文补字段**

在 `risk_context_builder.py` 中新增辅助函数：

```python
def _risk_source_item(zone: RiskZone, obj: RiskObject, unit: RiskUnit | None, event: RiskEvent) -> dict:
    measures = [
        {"category": m.measure_category, "description": m.description}
        for m in event.measures
    ]
    return {
        "zone": zone.name,
        "object": obj.name,
        "unit": unit.name if unit else None,
        "name": obj.name,
        "categories": obj.category or "",
        "location": obj.location or "",
        "accident_type": event.accident_type,
        "risk_level": event.risk_level,
        "risk_score": event.risk_score,
        "description": event.description,
        "triggers": event.trigger_conditions,
        "consequences": event.consequences,
        "control_measures": "；".join(m["description"] for m in measures),
        "measures": measures,
    }
```

把原循环中两处手工构造列表替换为：

```python
risk_sources_list.append(_risk_source_item(zone, obj, None, event))
```

和：

```python
risk_sources_list.append(_risk_source_item(zone, obj, unit, event))
```

把 `enterprise` 返回字典补齐为：

```python
        "enterprise": {
            "name": ent.name,
            "industry": ent.industry,
            "address": ent.address,
            "employee_count": ent.employee_count,
            "business_scope": ent.business_scope,
            "building_overview": ent.building_overview,
            "surrounding_info": ent.surrounding_info,
            "legal_representative": ent.legal_representative,
            "credit_code": ent.credit_code,
            "economic_type": ent.economic_type,
            "established_date": str(ent.established_date) if ent.established_date else None,
            "registered_capital": ent.registered_capital,
            "phone": ent.phone,
            "land_area": ent.land_area,
            "building_area": ent.building_area,
            "safety_officer": ent.safety_officer,
            "safety_standardization": ent.safety_standardization,
            "fire_approval": ent.fire_approval,
            "main_products": ent.main_products,
            "hazardous_chemicals": ent.hazardous_chemicals,
            "special_equipment": ent.special_equipment,
            "fire_protection_summary": ent.fire_protection_summary,
            "special_equipment_detail": ent.special_equipment_detail,
            "main_equipment_list": ent.main_equipment_list,
            "natural_conditions": ent.natural_conditions,
        },
```

- [ ] **步骤 4：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_context_builder.py -v`

预期：PASS。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_context_builder.py backend/tests/test_risk_context_builder.py
git commit -m "feat(risk-management): enrich risk context for legacy prompts"
```

---

## 任务 6：预案生成和外部生成切换新上下文

**文件：**
- 修改：`backend/app/routers/generation.py`
- 修改：`backend/app/routers/external.py`
- 测试：`backend/tests/test_generation_enterprise_data.py`

- [ ] **步骤 1：编写失败测试**

```python
from unittest.mock import MagicMock

from app.routers.generation import _collect_enterprise_data


def test_collect_enterprise_data_uses_hierarchical_risk_context():
    ent = MagicMock()
    ent.name = "测试企业"
    ent.address = "测试地址"
    ent.industry = "化工"
    ent.business_scope = "生产"
    ent.employee_count = 100
    ent.building_overview = ""
    ent.org_structure = []
    ent.surrounding_info = {}
    ent.legal_representative = ""
    ent.credit_code = ""
    ent.economic_type = ""
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = ""
    ent.land_area = None
    ent.building_area = None
    ent.safety_officer = ""
    ent.safety_standardization = ""
    ent.fire_approval = ""
    ent.main_products = ""
    ent.hazardous_chemicals = ""
    ent.special_equipment = ""

    risk_context = {
        "risk_sources": [{
            "zone": "生产区",
            "object": "原料仓",
            "unit": None,
            "name": "原料仓",
            "categories": "火灾",
            "location": "东区",
            "accident_type": "火灾",
            "risk_level": "较大",
            "description": "可燃物",
            "triggers": "明火",
            "consequences": "损失",
            "control_measures": "巡检",
            "measures": [],
        }]
    }
    resources = []

    data = _collect_enterprise_data(ent, risk_context, resources)

    assert data["risk_sources"][0]["name"] == "原料仓"
    assert data["risk_sources"][0]["categories"] == "火灾"
    assert data["risk_sources"][0]["control_measures"] == "巡检"
    assert data["risk_sources"][0]["accident_type"] == "火灾"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_generation_enterprise_data.py -v`

预期：FAIL，当前 `_collect_enterprise_data` 仍按旧 ORM 字段构造。

- [ ] **步骤 3：修改 `_collect_enterprise_data`**

把 `generation.py` 中的：

```python
def _collect_enterprise_data(enterprise: Enterprise, risk_sources: list, resources: list) -> dict:
```

改为：

```python
def _collect_enterprise_data(enterprise: Enterprise, risk_context: dict, resources: list) -> dict:
```

并把返回字典中的 `risk_sources` 列表替换为：

```python
        "risk_sources": [
            {
                "categories": rs.get("categories", ""),
                "name": rs.get("name", ""),
                "location": rs.get("location", ""),
                "description": rs.get("description", ""),
                "risk_level": rs.get("risk_level", ""),
                "control_measures": rs.get("control_measures", ""),
                "zone": rs.get("zone", ""),
                "object": rs.get("object", ""),
                "unit": rs.get("unit", ""),
                "accident_type": rs.get("accident_type", ""),
                "triggers": rs.get("triggers", ""),
                "consequences": rs.get("consequences", ""),
            }
            for rs in risk_context.get("risk_sources", [])
        ],
```

- [ ] **步骤 4：替换 `generation.py` 的 5 处旧查询**

每处都按同一模式替换：

```python
    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    ent_data = _collect_enterprise_data(ent, risk_context, resources) if ent else {}
```

在 `generation.py` 顶部新增：

```python
from app.services.risk_context_builder import build_risk_management_context
```

- [ ] **步骤 5：替换 `external.py`**

在 `external.py` 顶部新增：

```python
from app.services.risk_context_builder import build_risk_management_context
```

把：

```python
            risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == enterprise_id))).scalars().all()
            resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == enterprise_id))).scalars().all()
            ent_data = _collect_enterprise_data(ent, risk_sources, resources, accident_type) if ent else {}
```

替换为：

```python
            resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == enterprise_id))).scalars().all()
            risk_context = await build_risk_management_context(enterprise_id, db) if ent else {}
            ent_data = _collect_enterprise_data(ent, risk_context, resources) if ent else {}
```

同时从 `external.py` 的 import 中移除 `RiskSource`。

- [ ] **步骤 6：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_generation_enterprise_data.py backend/tests/test_risk_context_builder.py -v`

预期：PASS。

- [ ] **步骤 7：Commit**

```bash
git add backend/app/routers/generation.py backend/app/routers/external.py backend/tests/test_generation_enterprise_data.py
git commit -m "feat(risk-management): switch plan generation to risk context"
```

---

## 任务 7：风险评估前置检查切换

**文件：**
- 修改：`backend/app/routers/risk_assessment.py`
- 修改：`backend/app/services/risk_assessment_service.py`

- [ ] **步骤 1：修改前置检查**

在 `risk_assessment.py` 中：

删除：

```python
    risk_count = (await db.execute(
        select(RiskSource).where(RiskSource.enterprise_id == enterprise_id)
    )).scalars().all()
    if len(risk_count) == 0:
        raise HTTPException(400, "请先录入风险源数据")
```

替换为：

```python
    context = await build_risk_management_context(enterprise_id, db)
    if context["total_events"] == 0:
        raise HTTPException(400, "请先录入风险分级管控数据")
```

删除原有的：

```python
    context = await build_risk_management_context(enterprise_id, db)
```

避免重复调用。

同时删除 `from app.models.enterprise import Enterprise, RiskSource, AIConfig` 中的 `RiskSource`。

- [ ] **步骤 2：让旧上下文函数委托新构建器**

在 `risk_assessment_service.py` 中：

删除 `RiskSource` import，新增：

```python
from app.services.risk_context_builder import build_risk_management_context
```

将 `build_risk_assessment_context` 函数体替换为：

```python
async def build_risk_assessment_context(enterprise_id: str, db: AsyncSession) -> dict:
    return await build_risk_management_context(enterprise_id, db)
```

删除函数内原有的 `RiskSource` 查询和 `RISK_ORDER` 排序逻辑；如果 `RISK_ORDER` 仍被其他函数使用，则保留定义。

- [ ] **步骤 3：验证**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_context_builder.py -v`

预期：PASS。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/routers/risk_assessment.py backend/app/services/risk_assessment_service.py
git commit -m "feat(risk-management): switch assessment precheck to risk events"
```

---

## 任务 8：统计服务与 Web 统计切换

**文件：**
- 创建：`backend/app/services/risk_stats_service.py`
- 修改：`backend/app/schemas/enterprise.py`
- 修改：`backend/app/schemas/dashboard.py`
- 修改：`backend/app/routers/enterprises.py`
- 修改：`backend/app/routers/dashboard.py`
- 修改：`frontend/src/types/enterprise.ts`
- 修改：`frontend/src/types/dashboard.ts`
- 修改：`frontend/src/pages/Enterprise/EnterpriseListPage.tsx`
- 修改：`frontend/src/pages/Dashboard/DashboardPage.tsx`
- 测试：`backend/tests/test_risk_stats_service.py`

- [ ] **步骤 1：编写失败测试**

```python
import asyncio
from unittest.mock import AsyncMock

from app.services.risk_stats_service import count_enterprise_risk_events


def test_count_enterprise_risk_events_returns_count():
    db = AsyncMock()
    result = AsyncMock()
    result.scalar.return_value = 7
    db.execute.return_value = result

    count = asyncio.run(count_enterprise_risk_events(db, "ent-1"))

    assert count == 7
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_stats_service.py -v`

预期：FAIL，模块不存在。

- [ ] **步骤 3：实现统计服务**

```python
"""风险事件统计服务，统一新旧 UI 的统计口径。"""
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent


async def count_enterprise_risk_events(db: AsyncSession, enterprise_id: str) -> int:
    return (
        await db.execute(
            select(func.count(func.distinct(RiskEvent.id)))
            .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
            .join(
                RiskObject,
                or_(
                    RiskEvent.object_id == RiskObject.id,
                    RiskUnit.object_id == RiskObject.id,
                ),
            )
            .join(RiskZone, RiskObject.zone_id == RiskZone.id)
            .where(RiskZone.enterprise_id == enterprise_id)
        )
    ).scalar() or 0


async def count_user_risk_events(db: AsyncSession, user_id: str) -> int:
    return (
        await db.execute(
            select(func.count(func.distinct(RiskEvent.id)))
            .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
            .join(
                RiskObject,
                or_(
                    RiskEvent.object_id == RiskObject.id,
                    RiskUnit.object_id == RiskObject.id,
                ),
            )
            .join(RiskZone, RiskObject.zone_id == RiskZone.id)
            .join(Enterprise, RiskZone.enterprise_id == Enterprise.id)
            .where(Enterprise.user_id == user_id)
        )
    ).scalar() or 0


async def count_enterprises_risk_events(
    db: AsyncSession,
    enterprise_ids: list[str],
) -> dict[str, int]:
    if not enterprise_ids:
        return {}
    rows = (
        await db.execute(
            select(
                RiskZone.enterprise_id,
                func.count(func.distinct(RiskEvent.id)),
            )
            .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
            .join(
                RiskObject,
                or_(
                    RiskEvent.object_id == RiskObject.id,
                    RiskUnit.object_id == RiskObject.id,
                ),
            )
            .join(RiskZone, RiskObject.zone_id == RiskZone.id)
            .where(RiskZone.enterprise_id.in_(enterprise_ids))
            .group_by(RiskZone.enterprise_id)
        )
    ).all()
    return {row[0]: row[1] for row in rows}
```

- [ ] **步骤 4：更新 Schema**

`backend/app/schemas/enterprise.py` 的 `EnterpriseResponse` 中，在 `risk_sources_count` 后新增：

```python
    risk_events_count: int = 0
```

`backend/app/schemas/dashboard.py` 的 `DashboardStats` 中新增：

```python
    risk_event_count: int = 0
```

- [ ] **步骤 5：更新企业路由**

`enterprises.py`：

```python
from app.services.risk_stats_service import (
    count_enterprise_risk_events,
    count_enterprises_risk_events,
)
```

修改 `_build_response` 增加 `risk_events_count` 参数：

```python
def _build_response(e: Enterprise, risk_events_count: int = 0) -> EnterpriseResponse:
    ...
    risk_sources_count=len(e.risk_sources) if e.risk_sources else 0,
    risk_events_count=risk_events_count,
```

`list_enterprises` 在构造 `items` 前新增：

```python
    event_counts = await count_enterprises_risk_events(db, [e.id for e in rows])
    items = [_build_response(e, event_counts.get(e.id, 0)) for e in rows]
```

`get_enterprise` 返回前新增：

```python
    risk_events_count = await count_enterprise_risk_events(db, enterprise_id)
    return ApiResponse(data=_build_response(e, risk_events_count))
```

- [ ] **步骤 6：更新 Dashboard 路由**

`dashboard.py`：

```python
from app.services.risk_stats_service import count_user_risk_events
```

把：

```python
    rs_query = select(func.count(RiskSource.id)).join(Enterprise).where(Enterprise.user_id == current_user.id)
    rs_count = (await db.execute(rs_query)).scalar() or 0
    stats = DashboardStats(enterprise_count=ent_count, plan_count=plan_count, completed_plan_count=completed, risk_source_count=rs_count)
```

替换为：

```python
    rs_count = (await db.execute(
        select(func.count(RiskSource.id)).join(Enterprise).where(Enterprise.user_id == current_user.id)
    )).scalar() or 0
    risk_event_count = await count_user_risk_events(db, current_user.id)
    stats = DashboardStats(
        enterprise_count=ent_count,
        plan_count=plan_count,
        completed_plan_count=completed,
        risk_source_count=rs_count,
        risk_event_count=risk_event_count,
    )
```

- [ ] **步骤 7：更新前端类型和页面**

`frontend/src/types/enterprise.ts`：

```ts
risk_events_count: number;
```

`frontend/src/types/dashboard.ts`：

```ts
risk_event_count: number;
```

`EnterpriseListPage.tsx`：

```tsx
{ title: "风险事件数", dataIndex: "risk_events_count" },
```

`DashboardPage.tsx`：

```tsx
<Statistic title="风险事件数" value={stats.risk_event_count} prefix={<WarningOutlined />} />
```

- [ ] **步骤 8：验证**

运行：

```bash
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_stats_service.py -v
cd frontend
npm run build
```

预期：PASS，前端构建通过。

- [ ] **步骤 9：Commit**

```bash
git add backend/app/services/risk_stats_service.py backend/app/schemas/enterprise.py backend/app/schemas/dashboard.py backend/app/routers/enterprises.py backend/app/routers/dashboard.py frontend/src/types/enterprise.ts frontend/src/types/dashboard.ts frontend/src/pages/Enterprise/EnterpriseListPage.tsx frontend/src/pages/Dashboard/DashboardPage.tsx backend/tests/test_risk_stats_service.py
git commit -m "feat(risk-management): switch statistics to risk events"
```

---

## 任务 9：chat 助手读取新数据并移除旧 CRUD 工具

**文件：**
- 修改：`backend/app/routers/chat.py`
- 修改：`backend/app/services/chat_dispatch.py`

- [ ] **步骤 1：更新 chat 工具**

在 `chat.py` 中：

删除 `create_risk_source`、`update_risk_source`、`delete_risk_source` 三个工具定义。

修改 `get_dashboard` 描述：

```python
{"type": "function", "function": {"name": "get_dashboard", "description": "获取仪表盘统计概览：企业数、预案数(含已完成/生成中)、风险事件数、应急资源数", "parameters": {"type": "object", "properties": {}, "required": []}}}
```

修改 `get_enterprise` 描述：

```python
{"type": "function", "function": {"name": "get_enterprise", "description": "获取企业详情：基本信息+风险分级管控列表+应急资源列表+预案列表", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string"}, "name": {"type": "string", "description": "企业名称模糊匹配"}}, "required": []}}}
```

修改 `list_risk_sources` 描述：

```python
{"type": "function", "function": {"name": "list_risk_sources", "description": "列出指定企业的风险分级管控数据", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"}}, "required": ["enterprise_id"]}}}
```

修改系统提示中的「管理风险源」为「查看风险分级管控」。

- [ ] **步骤 2：更新 chat_dispatch 读取逻辑**

在 `chat_dispatch.py` 中新增：

```python
from app.services.risk_context_builder import build_risk_management_context
from app.services.risk_stats_service import count_user_risk_events
```

把 `_get_dashboard` 中的 `rs_count` 逻辑保留，并把返回字典中的 `risk_source_count` 保留，新增：

```python
    risk_event_count = await count_user_risk_events(db, user.id)
```

返回字典新增 `risk_event_count`。

把 `_get_enterprise` 的 `risk_sources` 列表替换为：

```python
    context = await build_risk_management_context(ent.id, db)
    return {
        "id": ent.id, "name": ent.name, "industry": ent.industry, "address": ent.address,
        "employee_count": ent.employee_count, "credit_code": ent.credit_code,
        "legal_representative": ent.legal_representative, "phone": ent.phone,
        "safety_officer": ent.safety_officer, "safety_officer_phone": ent.safety_officer_phone,
        "risk_sources": context.get("risk_sources", []),
        "resources": [{"id": r.id, "name": r.name, "category": r.category, "quantity": r.quantity, "unit": r.unit, "location": r.location} for r in (ent.resources or [])],
        "plans": [{"id": p.id, "title": p.title, "plan_type": p.plan_type, "status": p.status} for p in (ent.plans or [])],
    }
```

把 `_list_risk_sources` 替换为：

```python
async def _list_risk_sources(db, user, args):
    ent_id = args.get("enterprise_id", "")
    if not ent_id:
        return {"error": "请提供 enterprise_id"}
    ent = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == ent_id,
            Enterprise.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在"}
    context = await build_risk_management_context(ent_id, db)
    return {"risk_sources": context.get("risk_sources", [])}
```

删除 `_FUNCTIONS` 中的 `create_risk_source`、`update_risk_source`、`delete_risk_source` 三行。

如果 `_RS_CFG` 不再被引用，保留它作为旧 CRUD 兼容配置；不要删除 `_generic_*` 函数。

- [ ] **步骤 3：验证**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_risk_context_builder.py backend/tests/test_risk_source_migration_service.py -v`

预期：PASS。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/routers/chat.py backend/app/services/chat_dispatch.py
git commit -m "feat(risk-management): update chat to risk hierarchy"
```

---

## 任务 10：Web 和移动端入口切换

**文件：**
- 修改：`frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskAssessmentTab.tsx`
- 修改：`frontend/src/mobile/routes.tsx`
- 修改：`frontend/src/mobile/screens/EnterpriseDetailScreen.tsx`
- 修改：`frontend/src/mobile/screens/PlanCreateScreen.tsx`
- 修改：`frontend/src/mobile/components/plan/AIGenerationSheet.tsx`
- 创建：`frontend/src/mobile/screens/RiskManagementListScreen.tsx`

- [ ] **步骤 1：Web 移除旧风险源 Tab**

在 `EnterpriseDetailPage.tsx` 中：

删除：

```tsx
import RiskSourceForm from "@/components/enterprise/RiskSourceForm";
```

删除：

```tsx
    {
      key: "risk-sources",
      label: <span>风险源 <Badge count={enterprise.risk_sources_count} style={{ marginLeft: 4 }} /></span>,
      children: <RiskSourceForm enterpriseId={id!} floorPlanUrl={enterprise.floor_plan_url} />,
    },
```

在 `RiskAssessmentTab.tsx` 中，把「系统将基于已录入的风险源数据自动生成」改为「系统将基于风险分级管控数据自动生成」。

- [ ] **步骤 2：新增移动端风险分级列表**

创建 `frontend/src/mobile/screens/RiskManagementListScreen.tsx`：

```tsx
// @ts-nocheck
import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { getFullHierarchy } from "@/services/riskManagementService";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Card from "@/mobile/components/ui/Card";
import Badge from "@/mobile/components/ui/Badge";
import EmptyState from "@/mobile/components/ui/EmptyState";

const LEVEL_ORDER = ["重大", "较大", "一般", "低"];

export default function RiskManagementListScreen() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: zones = [] } = useQuery({
    queryKey: ["risk-hierarchy", enterpriseId],
    queryFn: () => getFullHierarchy(enterpriseId!),
    enabled: !!enterpriseId,
  });

  const rows = zones.flatMap((zone) =>
    (zone.objects || []).flatMap((obj) => {
      const objectEvents = (obj.events || []).map((ev) => ({ ...ev, object: obj.name, unit: null }));
      const unitEvents = (obj.units || []).flatMap((unit) =>
        (unit.events || []).map((ev) => ({ ...ev, object: obj.name, unit: unit.name }))
      );
      return [...objectEvents, ...unitEvents];
    })
  ).sort((a, b) => LEVEL_ORDER.indexOf(a.risk_level) - LEVEL_ORDER.indexOf(b.risk_level));

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh pb-20">
      <NavBar title="风险分级管控" showBack onBack={() => navigate(-1)} />
      <div className="px-md pt-sm space-y-2">
        {rows.length === 0 ? (
          <EmptyState title="暂无风险事件" description="请先在 Web 端维护风险分级管控数据" />
        ) : rows.map((row, index) => (
          <Card key={`${row.id}-${index}`} className="p-md">
            <div className="flex items-center gap-sm">
              <div className="flex-1 min-w-0">
                <p className="text-h3 font-semibold text-neutral-900">{row.accident_type}</p>
                <p className="text-caption text-neutral-500 mt-0.5">
                  {zoneName(zones, row)} · {row.object}{row.unit ? ` · ${row.unit}` : ""}
                </p>
              </div>
              {row.risk_level && <Badge variant="warning">{row.risk_level}</Badge>}
            </div>
          </Card>
        ))}
      </div>
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2">
        <button className="flex items-center gap-1 text-primary-600 text-caption" onClick={() => navigate(-1)}>
          <ChevronLeft size={14} /> 返回企业详情
        </button>
      </div>
    </SafeArea>
  );
}

function zoneName(zones, row) {
  for (const zone of zones) {
    for (const obj of zone.objects || []) {
      if (obj.name === row.object) return zone.name;
    }
  }
  return "未分区";
}
```

- [ ] **步骤 3：更新移动端路由**

`frontend/src/mobile/routes.tsx`：

```tsx
const RiskManagementListScreen = lazy(() => import("@/mobile/screens/RiskManagementListScreen"));
```

把：

```tsx
      { path: "enterprises/:id/risk-sources", element: <RiskSourceListScreen /> },
```

替换为：

```tsx
      { path: "enterprises/:id/risk-management", element: <RiskManagementListScreen /> },
```

删除 `RiskSourceListScreen` 的 import。

- [ ] **步骤 4：更新移动端企业详情**

`EnterpriseDetailScreen.tsx`：

- 删除 `listRiskSources` import。
- 新增 `getFullHierarchy` import。
- Tab label 从 `风险源` 改为 `风险管控`。
- 统计卡片从 `risk_sources_count` 改为 `risk_events_count`，文案改为「风险事件」。
- `RiskTab` 改为读取 `getFullHierarchy`，展示风险事件摘要，跳转 `/m/enterprises/${enterpriseId}/risk-management`。

关键替换：

```tsx
import { getFullHierarchy } from "@/services/riskManagementService";
```

```tsx
const { data: zones = [] } = useQuery({
  queryKey: ["risk-hierarchy", enterpriseId],
  queryFn: () => getFullHierarchy(enterpriseId),
  enabled: !!enterpriseId,
});
const eventCount = zones.reduce(
  (sum, zone) =>
    sum +
    (zone.objects || []).reduce(
      (s, obj) =>
        s +
        (obj.events || []).length +
        (obj.units || []).reduce((us, unit) => us + (unit.events || []).length, 0),
      0,
    ),
  0,
);
```

- [ ] **步骤 5：更新移动端新建预案**

`PlanCreateScreen.tsx`：

删除 `listRiskSources` import，新增：

```tsx
import { getFullHierarchy } from "@/services/riskManagementService";
```

替换查询：

```tsx
const { data: riskHierarchy = [] } = useQuery({
  queryKey: ["risk-hierarchy", selectedEnterpriseId],
  queryFn: () => getFullHierarchy(selectedEnterpriseId),
  enabled: !!selectedEnterpriseId,
});

const accidentOptions = useMemo(
  () => [
    ...new Set(
      riskHierarchy.flatMap((zone) =>
        (zone.objects || []).flatMap((obj) => [
          ...(obj.events || []).map((ev) => ev.accident_type),
          ...(obj.units || []).flatMap((unit) => (unit.events || []).map((ev) => ev.accident_type)),
        ])
      )
    ),
  ],
  [riskHierarchy]
);
```

把企业摘要中的「风险源」改为「风险事件」，值改为 `enterprise.risk_events_count`。

`AIGenerationSheet.tsx` 中把「风险源数量」改为「风险事件数量」，并把 `contextSummary.riskCount` 语义约定为风险事件数。

- [ ] **步骤 6：验证**

运行：

```bash
cd frontend
npm run build
npm test
```

预期：构建通过，Vitest 通过。

- [ ] **步骤 7：Commit**

```bash
git add frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx frontend/src/pages/Enterprise/RiskAssessmentTab.tsx frontend/src/mobile/routes.tsx frontend/src/mobile/screens/EnterpriseDetailScreen.tsx frontend/src/mobile/screens/PlanCreateScreen.tsx frontend/src/mobile/components/plan/AIGenerationSheet.tsx frontend/src/mobile/screens/RiskManagementListScreen.tsx
git commit -m "feat(risk-management): retire old risk source entry"
```

---

## 任务 11：全量验证和收尾

**文件：**
- 修改：`TASKS.md`

- [ ] **步骤 1：后端全量测试**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests -q`

预期：无 FAIL，原有风险模块和新增测试全部通过。

- [ ] **步骤 2：前端静态检查、单测和构建**

运行：

```bash
cd frontend
npm run build
npm test
```

预期：`tsc -b` 无错误，Vitest 通过。

- [ ] **步骤 3：Playwright 回归**

运行：`cd frontend; npx playwright test`

预期：现有风险分级管控相关 E2E 通过；如因旧入口文案变化失败，只更新断言文案，不恢复旧入口。

- [ ] **步骤 4：真实接口冒烟**

使用超管账号，选择一个存在旧风险源的企业：

1. 打开企业详情 → 风险分级管控，确认迁移横幅出现。
2. 打开迁移向导，执行迁移。
3. 刷新后确认旧迁移横幅消失，层级树出现迁移数据。
4. 调用 `GET /dashboard`，确认 `risk_event_count` 与 `risk_events` 表一致。
5. 调用一次预案生成接口，确认不再依赖旧 `risk_sources` 查询。

- [ ] **步骤 5：更新 TASKS.md 并提交**

```bash
git add TASKS.md
git commit -m "chore(risk-management): record consolidation verification"
```

---

## 自检记录

- 规格覆盖：迁移闭环、下游链路、统计、chat、Web、移动端、旧入口下线均有对应任务。
- 占位符扫描：本计划不含 TODO、待定、占位代码。
- 类型一致性：后端使用 `MigrationExecuteItem`，前端使用 `MigrationExecutePayload`，请求字段一致；统计字段后端 `risk_event_count`、前端 `risk_event_count`，企业字段后端 `risk_events_count`、前端 `risk_events_count`。

## 执行交接

计划已完成并保存到 `docs/superpowers/plans/2026-08-06-only-risk-management.md`。两种执行方式：

1. 子代理驱动（推荐）：每个任务调度一个新的子代理，任务间进行审查，快速迭代。
2. 内联执行：在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点。
