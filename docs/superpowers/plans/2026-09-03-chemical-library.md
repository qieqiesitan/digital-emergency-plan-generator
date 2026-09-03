# 危险化学品公共库（选择预填）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 建立系统级危险化学品公共库（管理员维护），企业添加危化品时先从库选择、选中后预填 MSDS 标准字段，保存为企业台账快照并记录 `library_id` 来源。

**架构：** 新建强类型表 `chemical_library`（无企业私有字段），企业表 `hazardous_chemicals` 加 `library_id`（FK，`ON DELETE SET NULL`）。库 = 模板，企业台账 = 快照副本，现有报告/预案注入链路零改动。管理员通过系统设置新页"化学品库管理"维护库并从企业台账"一键收录"；企业侧添加改两步式（库选择弹窗 → 预填表单）。

**技术栈：** FastAPI + SQLAlchemy(async) + PostgreSQL（backend 容器 emergency-plan-backend，8000）；React 19 + antd 6 + react-query + vitest（frontend 容器 emergency-plan-frontend 5173 / 静态 8082 shuzihuahuayuan）。

**运行环境（先读）：**

- 后端代码：宿主 `backend/app` bind mount 到容器 `/app/app`，改代码即时可见，但 uvicorn 无 `--reload`，真实 API 变更需 `docker restart emergency-plan-backend`。
- 后端测试：`backend/tests` 不在 bind mount，每次新建/修改测试文件后需
  `docker cp backend/tests/<file>.py emergency-plan-backend:/app/tests/<file>.py`，再
  `docker exec emergency-plan-backend pytest tests/<file>.py -v`。
- 迁移 SQL：`backend/db_migration_*.sql` 不在 bind mount，新增后需
  `docker cp backend/db_migration_xxx.sql emergency-plan-backend:/app/`，重启 backend 时
  由 migration_runner 自动应用（启动失败会 fail-fast）。
- 前端：宿主 `frontend/src` bind mount 到容器 `/app/src`（dev 5173 即时生效）；
  静态 8082 与宿主 `frontend/dist` 需在宿主目录跑 `npx tsc -b`/`npx vitest run`，
  build 在 frontend 容器执行后 docker cp 同步。
- git：TASKS.md 永不 add；工作区有大量他人/历史未提交文件（generation.py、risk_assessment.py、
  uploads 删除等），每次 commit 用 pathspec 只加本任务文件；commit 前先 `git status --short`
  核对；如遇 `.git/index.lock`，先 `Get-Process git*` 确认无进程再删 0 字节锁。

---

## 文件结构

后端：

- 创建 `backend/app/models/chemical_library.py`：`ChemicalLibrary` 模型（库条目，无企业字段）
- 修改 `backend/app/models/hazardous_chemicals.py`：加 `library_id` 列
- 创建 `backend/app/schemas/chemical_library.py`：Create/Update/Response/CollectRequest
- 修改 `backend/app/schemas/hazardous_chemicals.py`：三处加 `library_id`
- 创建 `backend/app/routers/chemical_library.py`：通用 GET + admin CRUD + collect 组
- 修改 `backend/app/main.py`：import 并注册 `chemical_library.router`
- 创建 `backend/db_migration_20260903_chemical_library.sql`：建表/索引/加列/FK/权限补种
- 创建 `backend/tests/test_chemical_library.py`：查重/CRUD/collect/403 测试
- 修改 `backend/tests/test_hazardous_library_id.py`（新）：企业侧 library_id 透传测试

前端：

- 创建 `frontend/src/types/chemicalLibrary.ts`：库条目类型
- 修改 `frontend/src/types/hazardousChemical.ts`：加 `library_id`
- 创建 `frontend/src/services/chemicalLibraryService.ts`：库与管理端点 API
- 创建 `frontend/src/utils/chemicalLibraryPrefill.ts`：库条目 → 表单预填纯函数
- 创建 `frontend/src/utils/chemicalLibraryPrefill.test.ts`
- 创建 `frontend/src/components/enterprise/ChemicalLibraryPickerModal.tsx`：两步式选择弹窗
- 修改 `frontend/src/pages/Enterprise/HazardousChemicalsTab.tsx`：两步式改造 + "标准库"标签
- 创建 `frontend/src/pages/Settings/ChemicalLibraryManagePage.tsx`：管理页（列表/编辑/收录）
- 修改 `frontend/src/utils/menuMap.ts`：注册 `/settings/chemical-library`
- 修改 `frontend/src/layouts/MainLayout.tsx`：系统管理组加菜单项
- 修改 `frontend/src/routes/index.tsx`：注册路由
- 创建 `frontend/src/services/chemicalLibraryService.test.ts`

---

### 任务 1：迁移 SQL + 模型（建表、加列、权限补种）

**文件：**
- 创建：`backend/db_migration_20260903_chemical_library.sql`
- 创建：`backend/app/models/chemical_library.py`
- 修改：`backend/app/models/hazardous_chemicals.py`（`enterprise_id` 列之后加 `library_id`）

- [ ] **步骤 1：编写迁移 SQL**

```sql
-- 2026-09-03 危化品公共库：chemical_library 表 + 企业台账来源列 + 菜单权限补种
-- 幂等：IF NOT EXISTS / ON CONFLICT，可重复执行。

CREATE TABLE IF NOT EXISTS chemical_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    cas_no VARCHAR(50),
    un_no VARCHAR(20),
    physical_state VARCHAR(200),
    flash_point VARCHAR(50),
    explosion_limit VARCHAR(50),
    ignition_temp VARCHAR(50),
    density VARCHAR(50),
    boiling_point VARCHAR(50),
    health_hazard TEXT,
    fire_hazard TEXT,
    leak_response TEXT,
    storage_transport TEXT,
    first_aid TEXT,
    protective_measures TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_chemical_library_cas
    ON chemical_library(cas_no) WHERE cas_no IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chemical_library_name ON chemical_library(name);

ALTER TABLE hazardous_chemicals
    ADD COLUMN IF NOT EXISTS library_id UUID REFERENCES chemical_library(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_hazardous_chemicals_library
    ON hazardous_chemicals(library_id);

INSERT INTO permissions (id, code, name, resource, action, category) VALUES
  (gen_random_uuid(), 'menu:chemical_library', '化学品库管理', 'menu', 'chemical_library', 'menu')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code = 'menu:chemical_library'
WHERE r.code IN ('super_admin', 'admin')
ON CONFLICT DO NOTHING;
```

- [ ] **步骤 2：创建模型文件**

`backend/app/models/chemical_library.py`：

```python
from datetime import datetime
from uuid import uuid4
from typing import Optional
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ChemicalLibrary(Base):
    """系统级危险化学品公共库条目（MSDS 标准属性，跨企业共享）。"""
    __tablename__ = "chemical_library"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cas_no: Mapped[Optional[str]] = mapped_column(String(50))
    un_no: Mapped[Optional[str]] = mapped_column(String(20))
    physical_state: Mapped[Optional[str]] = mapped_column(String(200))
    flash_point: Mapped[Optional[str]] = mapped_column(String(50))
    explosion_limit: Mapped[Optional[str]] = mapped_column(String(50))
    ignition_temp: Mapped[Optional[str]] = mapped_column(String(50))
    density: Mapped[Optional[str]] = mapped_column(String(50))
    boiling_point: Mapped[Optional[str]] = mapped_column(String(50))
    health_hazard: Mapped[Optional[str]] = mapped_column(Text)
    fire_hazard: Mapped[Optional[str]] = mapped_column(Text)
    leak_response: Mapped[Optional[str]] = mapped_column(Text)
    storage_transport: Mapped[Optional[str]] = mapped_column(Text)
    first_aid: Mapped[Optional[str]] = mapped_column(Text)
    protective_measures: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **步骤 3：企业模型加来源列**

`backend/app/models/hazardous_chemicals.py` 中 `enterprise_id` 列定义之后插入：

```python
    library_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("chemical_library.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
```

- [ ] **步骤 4：拷入容器并重启应用迁移**

运行：
```bash
docker cp backend/db_migration_20260903_chemical_library.sql emergency-plan-backend:/app/db_migration_20260903_chemical_library.sql
docker restart emergency-plan-backend
```
预期：容器重启成功（迁移 fail-fast 会中止启动），随后：

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "\d chemical_library"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT column_name FROM information_schema.columns WHERE table_name='hazardous_chemicals' AND column_name='library_id';"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id JOIN roles r ON r.id=rp.role_id WHERE p.code='menu:chemical_library';"
```
预期：表结构完整、`library_id` 存在、权限行关联到 super_admin 与 admin。

- [ ] **步骤 5：Commit**

```bash
git add backend/db_migration_20260903_chemical_library.sql backend/app/models/chemical_library.py backend/app/models/hazardous_chemicals.py
git commit -m "feat(chemical-library): chemical_library 表与企业台账 library_id 来源列（含菜单权限补种）"
```

---

### 任务 2：Pydantic schemas

**文件：**
- 创建：`backend/app/schemas/chemical_library.py`
- 修改：`backend/app/schemas/hazardous_chemicals.py`

- [ ] **步骤 1：创建库条目 schemas**

`backend/app/schemas/chemical_library.py`：

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


def _strip(v: Optional[str]) -> Optional[str]:
    return v.strip() if isinstance(v, str) else v


class ChemicalLibraryCreate(BaseModel):
    name: str
    cas_no: Optional[str] = None
    un_no: Optional[str] = None
    physical_state: Optional[str] = None
    flash_point: Optional[str] = None
    explosion_limit: Optional[str] = None
    ignition_temp: Optional[str] = None
    density: Optional[str] = None
    boiling_point: Optional[str] = None
    health_hazard: Optional[str] = None
    fire_hazard: Optional[str] = None
    leak_response: Optional[str] = None
    storage_transport: Optional[str] = None
    first_aid: Optional[str] = None
    protective_measures: Optional[str] = None

    @field_validator("name", "cas_no", mode="before")
    @classmethod
    def _clean(cls, v: object) -> object:
        return _strip(v)  # type: ignore[arg-type]


class ChemicalLibraryUpdate(BaseModel):
    name: Optional[str] = None
    cas_no: Optional[str] = None
    un_no: Optional[str] = None
    physical_state: Optional[str] = None
    flash_point: Optional[str] = None
    explosion_limit: Optional[str] = None
    ignition_temp: Optional[str] = None
    density: Optional[str] = None
    boiling_point: Optional[str] = None
    health_hazard: Optional[str] = None
    fire_hazard: Optional[str] = None
    leak_response: Optional[str] = None
    storage_transport: Optional[str] = None
    first_aid: Optional[str] = None
    protective_measures: Optional[str] = None

    @field_validator("name", "cas_no", mode="before")
    @classmethod
    def _clean(cls, v: object) -> object:
        return _strip(v)  # type: ignore[arg-type]


class ChemicalLibraryResponse(BaseModel):
    id: str
    name: str
    cas_no: Optional[str] = None
    un_no: Optional[str] = None
    physical_state: Optional[str] = None
    flash_point: Optional[str] = None
    explosion_limit: Optional[str] = None
    ignition_temp: Optional[str] = None
    density: Optional[str] = None
    boiling_point: Optional[str] = None
    health_hazard: Optional[str] = None
    fire_hazard: Optional[str] = None
    leak_response: Optional[str] = None
    storage_transport: Optional[str] = None
    first_aid: Optional[str] = None
    protective_measures: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _dt_to_str(cls, v: object) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v is not None else ""


class ChemicalLibraryCollectRequest(BaseModel):
    enterprise_id: str
    chemical_id: str
```

- [ ] **步骤 2：企业 schema 加 library_id**

`backend/app/schemas/hazardous_chemicals.py` 三处各加一行（Create 在 `name` 后、Update 在 `name` 后、Response 在 `enterprise_id` 后）：

```python
    library_id: Optional[str] = None
```

Response 中为：
```python
    library_id: Optional[str] = None
```

- [ ] **步骤 3：import 冒烟**

```bash
docker exec emergency-plan-backend python -c "from app.schemas.chemical_library import ChemicalLibraryCreate, ChemicalLibraryUpdate, ChemicalLibraryResponse, ChemicalLibraryCollectRequest; from app.schemas.hazardous_chemicals import HazardousChemicalCreate, HazardousChemicalUpdate, HazardousChemicalResponse; print('ok')"
```
预期：`ok`。另验证 trim 与时间序列化：

```bash
docker exec emergency-plan-backend python -c "from app.schemas.chemical_library import ChemicalLibraryCreate; c=ChemicalLibraryCreate(name=' 乙醇 ', cas_no=' 67-56-1 '); assert c.name=='乙醇' and c.cas_no=='67-56-1'; print(c)"
```

- [ ] **步骤 4：Commit**

```bash
git add backend/app/schemas/chemical_library.py backend/app/schemas/hazardous_chemicals.py
git commit -m "feat(chemical-library): 库条目与企业台账 schemas 增加字段"
```

---

### 任务 3：router 通用查询与 admin CRUD（含查重）+ 测试

**文件：**
- 创建：`backend/app/routers/chemical_library.py`
- 修改：`backend/app/main.py`（import 列表与注册点）
- 创建：`backend/tests/test_chemical_library.py`

- [ ] **步骤 1：编写失败测试**

`backend/tests/test_chemical_library.py`（先只写 CRUD/查重/403 部分；collect 用例任务 4 追加）：

```python
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.chemical_library import ChemicalLibrary
from app.models.hazardous_chemicals import HazardousChemical
from app.models.user import User
from app.schemas.chemical_library import ChemicalLibraryCreate, ChemicalLibraryUpdate
from app.routers import chemical_library as router_mod


def _lib(**kw):
    defaults = dict(id="lib-1", name="乙醇", cas_no="67-56-1", created_at=datetime.now(), updated_at=datetime.now())
    defaults.update(kw)
    return ChemicalLibrary(**defaults)


def _admin():
    return User(id="u-admin", role="admin", email="a@x.com", name="A")


def _db(*results):
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: results[0] if results else None)
    return db


def test_create_duplicate_cas_conflict():
    existing = _lib()
    db = _db(existing)
    body = ChemicalLibraryCreate(name="酒精", cas_no="67-56-1")
    with pytest.raises(HTTPException) as exc:
        router_mod.create_library_item(body, _admin(), db)
    assert exc.value.status_code == 409
    assert "已存在" in exc.value.detail


def test_create_duplicate_name_when_no_cas():
    existing = _lib(id="lib-x", name="玻璃水", cas_no=None)
    db = _db(existing)
    body = ChemicalLibraryCreate(name="玻璃水", cas_no=None)
    with pytest.raises(HTTPException) as exc:
        router_mod.create_library_item(body, _admin(), db)
    assert exc.value.status_code == 409


def test_create_success():
    db = _db(None)
    body = ChemicalLibraryCreate(name="乙醇", cas_no="67-56-1", flash_point="12℃")
    resp = router_mod.create_library_item(body, _admin(), db)
    assert resp.data.name == "乙醇"
    assert db.add.called and db.commit.await_count == 1


def test_update_rename_conflict_excludes_self():
    existing_other = _lib(id="lib-2", name="甲醇", cas_no="67-56-1")
    db = AsyncMock()
    db.get.return_value = _lib()  # 被编辑条目自身
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: existing_other)
    body = ChemicalLibraryUpdate(name="乙醇", cas_no="67-56-1")
    with pytest.raises(HTTPException) as exc:
        router_mod.update_library_item("lib-1", body, _admin(), db)
    assert exc.value.status_code == 409


def test_delete_missing_404():
    db = AsyncMock()
    db.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        router_mod.delete_library_item("nope", _admin(), db)
    assert exc.value.status_code == 404


def test_admin_endpoints_reject_normal_user():
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[get_current_user] = lambda: User(id="u1", role="user", email="u@x.com", name="U")
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    client = TestClient(app)
    r = client.post("/chemical-library", json={"name": "乙醇"})
    assert r.status_code == 403
```

运行（先拷贝后跑，预期失败）：
```bash
docker cp backend/tests/test_chemical_library.py emergency-plan-backend:/app/tests/test_chemical_library.py
docker exec emergency-plan-backend pytest tests/test_chemical_library.py -v
```
预期：FAIL（`ModuleNotFoundError: app.routers.chemical_library`）。

- [ ] **步骤 2：实现 router（CRUD + 查重）**

`backend/app/routers/chemical_library.py`：

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.chemical_library import ChemicalLibrary
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.schemas.chemical_library import (
    ChemicalLibraryCreate,
    ChemicalLibraryUpdate,
    ChemicalLibraryResponse,
)

router = APIRouter(prefix="/chemical-library", tags=["Chemical Library"])


def _serialize(item: ChemicalLibrary) -> ChemicalLibraryResponse:
    return ChemicalLibraryResponse.model_validate(item)


async def _find_conflict(
    db: AsyncSession, name: str, cas_no: str | None, exclude_id: str | None = None
) -> ChemicalLibrary | None:
    """查重：CAS 非空按 CAS 精确匹配；CAS 为空按 trim 后名称匹配。"""
    cas = (cas_no or "").strip() or None
    stmt = select(ChemicalLibrary)
    if cas:
        stmt = stmt.where(ChemicalLibrary.cas_no == cas)
    else:
        stmt = stmt.where(ChemicalLibrary.cas_no.is_(None), ChemicalLibrary.name == (name or "").strip())
    if exclude_id:
        stmt = stmt.where(ChemicalLibrary.id != exclude_id)
    return (await db.execute(stmt.limit(1))).scalar_one_or_none()


@router.get("", response_model=PaginatedResponse[ChemicalLibraryResponse])
async def list_library_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: str = Query(""),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(ChemicalLibrary)
    if keyword.strip():
        like = f"%{keyword.strip()}%"
        base = base.where(or_(
            ChemicalLibrary.name.ilike(like),
            ChemicalLibrary.cas_no.ilike(like),
            ChemicalLibrary.un_no.ilike(like),
        ))
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(ChemicalLibrary.name).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedResponse(data=PaginatedData(
        items=[_serialize(r) for r in rows], total=total, page=page, page_size=page_size,
    ))


@router.post("", response_model=ApiResponse[ChemicalLibraryResponse], status_code=201)
async def create_library_item(
    body: ChemicalLibraryCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    conflict = await _find_conflict(db, body.name, body.cas_no)
    if conflict:
        raise HTTPException(409, f"库中已存在该化学品条目（{conflict.name}），可改为编辑该条目")
    data = body.model_dump()
    item = ChemicalLibrary(**data)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ApiResponse(data=_serialize(item))


@router.put("/{item_id}", response_model=ApiResponse[ChemicalLibraryResponse])
async def update_library_item(
    item_id: str,
    body: ChemicalLibraryUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ChemicalLibrary, item_id)
    if not item:
        raise HTTPException(404, "库条目不存在")
    patch = body.model_dump(exclude_unset=True)
    new_name = patch.get("name", item.name)
    new_cas = patch.get("cas_no", item.cas_no)
    conflict = await _find_conflict(db, new_name, new_cas, exclude_id=item_id)
    if conflict:
        raise HTTPException(409, f"库中已存在该化学品条目（{conflict.name}），可改为编辑该条目")
    for key, value in patch.items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return ApiResponse(data=_serialize(item))


@router.delete("/{item_id}", response_model=ApiResponse[None])
async def delete_library_item(
    item_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ChemicalLibrary, item_id)
    if not item:
        raise HTTPException(404, "库条目不存在")
    await db.delete(item)
    await db.commit()
    return ApiResponse(data=None)
```

- [ ] **步骤 3：注册 router**

`backend/app/main.py`：

- import 列表（第 4 行附近 `from app.routers import ...`）中追加 `chemical_library,`；
- `app.include_router` 区域（`data_dicts` 之前任意位置）追加：

```python
app.include_router(chemical_library.router, prefix="/api/v1")
```

- [ ] **步骤 4：拷测试并运行（红 → 绿）**

```bash
docker cp backend/tests/test_chemical_library.py emergency-plan-backend:/app/tests/test_chemical_library.py
docker exec emergency-plan-backend pytest tests/test_chemical_library.py -v
```
预期：6 passed（create 冲突/无 CAS 同名冲突/create 成功/update 排除自身/delete 404/普通用户 403）。

- [ ] **步骤 5：重启并真实 API 冒烟**

```bash
docker restart emergency-plan-backend
curl -s http://localhost:8000/api/v1/chemical-library?keyword=乙醇 | Select-Object -First 1
curl -s -X POST http://localhost:8000/api/v1/chemical-library -H "Content-Type: application/json" -d '{"name":"x"}' | Select-Object -First 1
```
预期：GET 返回 401（未带 token，说明需要登录）；POST 同样 401 而非 404/500。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/chemical_library.py backend/app/main.py backend/tests/test_chemical_library.py
git commit -m "feat(chemical-library): 库条目通用查询与管理员 CRUD（CAS/名称查重 409）"
```

---

### 任务 4：collect 收录端点（含管理员企业搜索与台账列表）

**文件：**
- 修改：`backend/app/routers/chemical_library.py`
- 修改：`backend/tests/test_chemical_library.py`

- [ ] **步骤 1：追加失败测试（同文件末尾）**

```python
def test_collect_success_backfills_library_id():
    ent = MagicMock(id="ent-1")
    chem = MagicMock(id="chem-1", enterprise_id="ent-1", name="次氯酸钠溶液",
                     cas_no="7681-52-9", location="1#仓库", max_storage="2t")
    db = AsyncMock()
    db.get.side_effect = lambda model, pk: {Enterprise: ent, HazardousChemical: chem}.get(model)
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)  # 无冲突
    from app.schemas.chemical_library import ChemicalLibraryCollectRequest
    req = ChemicalLibraryCollectRequest(enterprise_id="ent-1", chemical_id="chem-1")
    resp = router_mod.collect_from_enterprise(req, _admin(), db)
    assert resp.data.name == "次氯酸钠溶液"
    assert chem.library_id == resp.data.id
    assert db.commit.await_count == 1


def test_collect_missing_chemical_404():
    ent = MagicMock(id="ent-1")
    db = AsyncMock()
    db.get.side_effect = lambda model, pk: ent if model is Enterprise else None
    from app.schemas.chemical_library import ChemicalLibraryCollectRequest
    req = ChemicalLibraryCollectRequest(enterprise_id="ent-1", chemical_id="missing")
    with pytest.raises(HTTPException) as exc:
        router_mod.collect_from_enterprise(req, _admin(), db)
    assert exc.value.status_code == 404


def test_collect_cas_conflict_409():
    ent = MagicMock(id="ent-1")
    chem = MagicMock(id="chem-1", enterprise_id="ent-1", name="乙醇", cas_no="67-56-1")
    db = AsyncMock()
    db.get.side_effect = lambda model, pk: {Enterprise: ent, HazardousChemical: chem}.get(model)
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: _lib())  # 已有同 CAS 条目
    from app.schemas.chemical_library import ChemicalLibraryCollectRequest
    req = ChemicalLibraryCollectRequest(enterprise_id="ent-1", chemical_id="chem-1")
    with pytest.raises(HTTPException) as exc:
        router_mod.collect_from_enterprise(req, _admin(), db)
    assert exc.value.status_code == 409
```

同时更新测试文件顶部 import：
```python
from app.models.enterprise import Enterprise
```

运行预期 FAIL：`AttributeError: module ... has no attribute 'collect_from_enterprise'`。

- [ ] **步骤 2：实现 collect 与管理员辅助端点**

`backend/app/routers/chemical_library.py` 追加 import 与端点：

```python
from app.models.enterprise import Enterprise
from app.models.hazardous_chemicals import HazardousChemical
from app.schemas.chemical_library import ChemicalLibraryCollectRequest
from app.schemas.hazardous_chemicals import HazardousChemicalResponse
```

追加辅助常量与端点：

```python
COLLECT_FIELDS = [
    "name", "cas_no", "un_no", "physical_state", "flash_point", "explosion_limit",
    "ignition_temp", "density", "boiling_point", "health_hazard", "fire_hazard",
    "leak_response", "storage_transport", "first_aid", "protective_measures",
]


@router.get("/collect/enterprises", response_model=ApiResponse[list[dict]])
async def list_collect_enterprises(
    keyword: str = Query("", max_length=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员收录用：跨用户搜索企业（返回 id/name，最多 20 条）。"""
    stmt = select(Enterprise.id, Enterprise.name)
    if keyword.strip():
        stmt = stmt.where(Enterprise.name.ilike(f"%{keyword.strip()}%"))
    rows = (await db.execute(stmt.order_by(Enterprise.name).limit(20))).all()
    return ApiResponse(data=[{"id": r[0], "name": r[1]} for r in rows])


@router.get("/collect/enterprises/{enterprise_id}/chemicals",
            response_model=ApiResponse[list[HazardousChemicalResponse]])
async def list_collect_chemicals(
    enterprise_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ent = await db.get(Enterprise, enterprise_id)
    if not ent:
        raise HTTPException(404, "企业不存在")
    rows = (await db.execute(
        select(HazardousChemical)
        .where(HazardousChemical.enterprise_id == enterprise_id)
        .order_by(HazardousChemical.name)
    )).scalars().all()
    return ApiResponse(data=[HazardousChemicalResponse.model_validate(r) for r in rows])


@router.post("/collect", response_model=ApiResponse[ChemicalLibraryResponse], status_code=201)
async def collect_from_enterprise(
    body: ChemicalLibraryCollectRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ent = await db.get(Enterprise, body.enterprise_id)
    if not ent:
        raise HTTPException(404, "企业不存在")
    chem = await db.get(HazardousChemical, body.chemical_id)
    if not chem or chem.enterprise_id != body.enterprise_id:
        raise HTTPException(404, "该企业的化学品记录不存在")
    conflict = await _find_conflict(db, chem.name, chem.cas_no)
    if conflict:
        raise HTTPException(409, f"库中已存在该化学品条目（{conflict.name}），可改为编辑该条目")
    item = ChemicalLibrary(**{f: getattr(chem, f) for f in COLLECT_FIELDS})
    db.add(item)
    chem.library_id = item.id
    await db.commit()
    await db.refresh(item)
    return ApiResponse(data=_serialize(item))
```

- [ ] **步骤 3：拷测试运行（红 → 绿）**

```bash
docker cp backend/tests/test_chemical_library.py emergency-plan-backend:/app/tests/test_chemical_library.py
docker exec emergency-plan-backend pytest tests/test_chemical_library.py -v
```
预期：9 passed。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/routers/chemical_library.py backend/tests/test_chemical_library.py
git commit -m "feat(chemical-library): 从企业台账一键收录（查重 409 + 源记录回填 library_id）"
```

---

### 任务 5：企业侧 library_id 透传测试

**说明**：`hazardous_chemicals.py` 的 create/update 用 `body.model_dump()` 全量透传，schema 加字段后无需改 router 代码；本任务补测试锁定该行为，防止未来改动破坏。

**文件：**
- 创建：`backend/tests/test_hazardous_library_id.py`

- [ ] **步骤 1：编写测试**

`backend/tests/test_hazardous_library_id.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.models.enterprise import Enterprise
from app.routers import hazardous_chemicals as hc
from app.schemas.hazardous_chemicals import HazardousChemicalCreate, HazardousChemicalUpdate


def _db_with_ent(ent):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    db.execute.return_value = result
    return db


def test_create_carries_library_id():
    ent = MagicMock(id="ent-1", user_id="u1")
    db = _db_with_ent(ent)
    body = HazardousChemicalCreate(name="乙醇", cas_no="67-56-1", library_id="lib-9")
    # _get_enterprise 内部 execute().scalar_one_or_none()
    db.execute.return_value = result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    resp = hc.create_chemical("ent-1", body, MagicMock(id="u1"), db)
    added: HazardousChemical = db.add.call_args[0][0]
    assert added.library_id == "lib-9"
    assert resp.data.library_id == "lib-9"


def test_update_preserves_library_id():
    ent = MagicMock(id="ent-1", user_id="u1")
    chem = MagicMock()
    chem.library_id = "lib-9"
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: chem)
    body = HazardousChemicalUpdate(location="2#仓库")
    resp = hc.update_chemical("ent-1", "chem-1", body, MagicMock(id="u1"), db)
    assert resp.data.library_id == "lib-9"
```

运行预期 FAIL：红（create 端点不存在或 library_id 不落库）。

- [ ] **步骤 2：必要时修 schema/router 并转绿**

若失败因 `HazardousChemicalCreate` 尚无 `library_id`，回到任务 2 步骤 2 核对 schema 已加。若因 create 未透传，检查 `create_chemical` 使用 `body.model_dump(exclude_none=True)`（当前实现已透传，无需改）。

```bash
docker cp backend/tests/test_hazardous_library_id.py emergency-plan-backend:/app/tests/test_hazardous_library_id.py
docker exec emergency-plan-backend pytest tests/test_hazardous_library_id.py -v
```
预期：2 passed。

- [ ] **步骤 3：Commit**

```bash
git add backend/tests/test_hazardous_library_id.py
git commit -m "test(chemical-library): 企业创建/更新记录 library_id 透传"
```

---

### 任务 6：前端类型 + 预填工具 + 服务层（TDD）

**文件：**
- 创建：`frontend/src/types/chemicalLibrary.ts`
- 修改：`frontend/src/types/hazardousChemical.ts`
- 创建：`frontend/src/utils/chemicalLibraryPrefill.ts`
- 创建：`frontend/src/utils/chemicalLibraryPrefill.test.ts`
- 创建：`frontend/src/services/chemicalLibraryService.ts`
- 创建：`frontend/src/services/chemicalLibraryService.test.ts`

- [ ] **步骤 1：编写失败测试（util + service）**

`frontend/src/utils/chemicalLibraryPrefill.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import { libraryItemToPrefill } from "./chemicalLibraryPrefill";
import type { ChemicalLibraryItem } from "@/types/chemicalLibrary";

describe("libraryItemToPrefill", () => {
  it("maps standard fields and attaches library_id", () => {
    const item: ChemicalLibraryItem = {
      id: "lib-1",
      name: "乙醇",
      cas_no: "67-56-1",
      un_no: "1170",
      physical_state: "液体",
      flash_point: "12℃",
      explosion_limit: null,
      ignition_temp: null,
      density: null,
      boiling_point: null,
      health_hazard: "中枢神经抑制",
      fire_hazard: null,
      leak_response: null,
      storage_transport: null,
      first_aid: null,
      protective_measures: null,
      created_at: "",
      updated_at: "",
    };
    const out = libraryItemToPrefill(item);
    expect(out.name).toBe("乙醇");
    expect(out.cas_no).toBe("67-56-1");
    expect(out.flash_point).toBe("12℃");
    expect(out.health_hazard).toBe("中枢神经抑制");
    expect(out.library_id).toBe("lib-1");
    expect(out).not.toHaveProperty("location");
    expect(out).not.toHaveProperty("created_at");
  });
});
```

`frontend/src/services/chemicalLibraryService.test.ts`：

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import api from "./api";
import {
  listLibrary,
  createLibraryItem,
  collectEnterprises,
  collectChemical,
} from "./chemicalLibraryService";

vi.mock("./api", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

describe("chemicalLibraryService", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    vi.mocked(api.post).mockReset();
  });

  it("listLibrary calls GET /chemical-library", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { data: { items: [], total: 0, page: 1, page_size: 20 } },
    });
    await listLibrary("乙醇");
    expect(api.get).toHaveBeenCalledWith(
      "/chemical-library",
      expect.objectContaining({ params: expect.objectContaining({ keyword: "乙醇" }) }),
    );
  });

  it("collectChemical posts enterprise_id + chemical_id", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { data: { id: "lib-2" } } });
    await collectChemical("ent-1", "chem-1");
    expect(api.post).toHaveBeenCalledWith(
      "/chemical-library/collect",
      { enterprise_id: "ent-1", chemical_id: "chem-1" },
    );
  });
});
```

运行（宿主 frontend 目录）：
```bash
cd frontend
npx vitest run src/utils/chemicalLibraryPrefill.test.ts src/services/chemicalLibraryService.test.ts
```
预期：FAIL（模块不存在）。

- [ ] **步骤 2：类型**

`frontend/src/types/chemicalLibrary.ts`：

```ts
export interface ChemicalLibraryItem {
  id: string;
  name: string;
  cas_no: string | null;
  un_no: string | null;
  physical_state: string | null;
  flash_point: string | null;
  explosion_limit: string | null;
  ignition_temp: string | null;
  density: string | null;
  boiling_point: string | null;
  health_hazard: string | null;
  fire_hazard: string | null;
  leak_response: string | null;
  storage_transport: string | null;
  first_aid: string | null;
  protective_measures: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChemicalLibraryPayload {
  name: string;
  cas_no?: string | null;
  un_no?: string | null;
  physical_state?: string | null;
  flash_point?: string | null;
  explosion_limit?: string | null;
  ignition_temp?: string | null;
  density?: string | null;
  boiling_point?: string | null;
  health_hazard?: string | null;
  fire_hazard?: string | null;
  leak_response?: string | null;
  storage_transport?: string | null;
  first_aid?: string | null;
  protective_measures?: string | null;
}

export interface ChemicalLibraryCreate extends ChemicalLibraryPayload {}
export type ChemicalLibraryUpdate = Partial<ChemicalLibraryPayload>;

export interface CollectEnterpriseOption {
  id: string;
  name: string;
}
```

`frontend/src/types/hazardousChemical.ts` 的 `HazardousChemical`（`enterprise_id` 后）与 `HazardousChemicalCreate`（`name` 后）各加：

```ts
  library_id?: string | null;
```

（`HazardousChemical` 响应对象中该字段类型为 `string | null`，见步骤 3 说明——若放在 `HazardousChemical` 接口则写 `library_id: string | null;`，前端 `setFieldsValue` 与提交共用一套结构，实际运行按后端返回 null 处理。）

- [ ] **步骤 3：实现 util**

`frontend/src/utils/chemicalLibraryPrefill.ts`：

```ts
import type { ChemicalLibraryItem } from "@/types/chemicalLibrary";

/** 库条目 → 企业台账表单预填值（标准字段复制 + library_id 来源标记）。 */
export function libraryItemToPrefill(item: ChemicalLibraryItem): Record<string, unknown> {
  const keys = [
    "name", "cas_no", "un_no", "physical_state", "flash_point", "explosion_limit",
    "ignition_temp", "density", "boiling_point", "health_hazard", "fire_hazard",
    "leak_response", "storage_transport", "first_aid", "protective_measures",
  ] as const;
  const out: Record<string, unknown> = { library_id: item.id };
  for (const k of keys) {
    out[k] = item[k] ?? undefined;
  }
  return out;
}
```

- [ ] **步骤 4：实现 service**

`frontend/src/services/chemicalLibraryService.ts`：

```ts
import api from "./api";
import type { ApiResponse, PaginatedResponse } from "@/types/common";
import type { AxiosRequestConfig } from "axios";
import type {
  ChemicalLibraryCreate,
  ChemicalLibraryItem,
  ChemicalLibraryUpdate,
  CollectEnterpriseOption,
} from "@/types/chemicalLibrary";
import type { HazardousChemical } from "@/types/hazardousChemical";

export async function listLibrary(
  keyword?: string,
  params?: Record<string, unknown>,
  config?: AxiosRequestConfig,
): Promise<PaginatedResponse<ChemicalLibraryItem>> {
  const res = await api.get<PaginatedResponse<ChemicalLibraryItem>>(
    "/chemical-library",
    { params: { ...(keyword ? { keyword } : {}), ...params }, ...config },
  );
  return res.data;
}

export async function createLibraryItem(
  data: ChemicalLibraryCreate,
  config?: AxiosRequestConfig,
): Promise<ChemicalLibraryItem> {
  const res = await api.post<ApiResponse<ChemicalLibraryItem>>(
    "/chemical-library",
    data,
    config,
  );
  return res.data.data;
}

export async function updateLibraryItem(
  id: string,
  patch: ChemicalLibraryUpdate,
  config?: AxiosRequestConfig,
): Promise<ChemicalLibraryItem> {
  const res = await api.put<ApiResponse<ChemicalLibraryItem>>(
    `/chemical-library/${id}`,
    patch,
    config,
  );
  return res.data.data;
}

export async function deleteLibraryItem(
  id: string,
  config?: AxiosRequestConfig,
): Promise<void> {
  await api.delete(`/chemical-library/${id}`, config);
}

export async function collectEnterprises(
  keyword: string,
  config?: AxiosRequestConfig,
): Promise<CollectEnterpriseOption[]> {
  const res = await api.get<ApiResponse<CollectEnterpriseOption[]>>(
    "/chemical-library/collect/enterprises",
    { params: { keyword }, ...config },
  );
  return res.data.data;
}

export async function listEnterpriseChemicals(
  enterpriseId: string,
  config?: AxiosRequestConfig,
): Promise<HazardousChemical[]> {
  const res = await api.get<ApiResponse<HazardousChemical[]>>(
    `/chemical-library/collect/enterprises/${enterpriseId}/chemicals`,
    config,
  );
  return res.data.data;
}

export async function collectChemical(
  enterpriseId: string,
  chemicalId: string,
  config?: AxiosRequestConfig,
): Promise<ChemicalLibraryItem> {
  const res = await api.post<ApiResponse<ChemicalLibraryItem>>(
    "/chemical-library/collect",
    { enterprise_id: enterpriseId, chemical_id: chemicalId },
    config,
  );
  return res.data.data;
}
```

- [ ] **步骤 5：运行测试（红 → 绿）+ 类型检查**

```bash
cd frontend
npx vitest run src/utils/chemicalLibraryPrefill.test.ts src/services/chemicalLibraryService.test.ts
node node_modules/typescript/bin/tsc -b
```
预期：2 个测试文件全绿；tsc 无新增错误。

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/types/chemicalLibrary.ts frontend/src/types/hazardousChemical.ts frontend/src/utils/chemicalLibraryPrefill.ts frontend/src/utils/chemicalLibraryPrefill.test.ts frontend/src/services/chemicalLibraryService.ts frontend/src/services/chemicalLibraryService.test.ts
git commit -m "feat(chemical-library): 前端类型、库服务与预填工具"
```

---

### 任务 7：企业侧两步式选择（PickerModal + HazardousChemicalsTab 改造）

**文件：**
- 创建：`frontend/src/components/enterprise/ChemicalLibraryPickerModal.tsx`
- 修改：`frontend/src/pages/Enterprise/HazardousChemicalsTab.tsx`

- [ ] **步骤 1：创建选择弹窗组件**

`frontend/src/components/enterprise/ChemicalLibraryPickerModal.tsx`：

```tsx
import { useEffect, useState } from "react";
import { Button, Empty, Input, Modal, Table } from "antd";
import { listLibrary } from "@/services/chemicalLibraryService";
import type { ChemicalLibraryItem } from "@/types/chemicalLibrary";

interface Props {
  open: boolean;
  onSelect: (item: ChemicalLibraryItem) => void;
  onManual: () => void;
  onClose: () => void;
}

export default function ChemicalLibraryPickerModal({ open, onSelect, onManual, onClose }: Props) {
  const [keyword, setKeyword] = useState("");
  const [items, setItems] = useState<ChemicalLibraryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const fetch = async (kw: string, pg: number) => {
    setLoading(true);
    try {
      const res = await listLibrary(kw, { page: pg, page_size: PAGE_SIZE });
      setItems(res.data.items || []);
      setTotal(res.data.total || 0);
      setPage(pg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      setKeyword("");
      fetch("", 1);
    }
  }, [open]);

  const columns = [
    { title: "化学品名称", dataIndex: "name", key: "name", width: 200 },
    { title: "CAS号", dataIndex: "cas_no", key: "cas_no", width: 130, render: (v: string | null) => v || "-" },
    { title: "UN号", dataIndex: "un_no", key: "un_no", width: 90, render: (v: string | null) => v || "-" },
    { title: "物理状态", dataIndex: "physical_state", key: "physical_state", width: 100, render: (v: string | null) => v || "-" },
    { title: "闪点", dataIndex: "flash_point", key: "flash_point", width: 100, render: (v: string | null) => v || "-" },
  ];

  return (
    <Modal
      title="从化学品库选择"
      open={open}
      onCancel={onClose}
      footer={null}
      width={820}
      destroyOnHidden
    >
      <Input.Search
        placeholder="按名称 / CAS号 / UN号搜索"
        allowClear
        enterButton="搜索"
        onSearch={(v) => fetch(v.trim(), 1)}
        style={{ marginBottom: 12 }}
      />
      <Table
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total,
          onChange: (p) => fetch(keyword, p),
          showTotal: (t) => `共 ${t} 条`,
        }}
        onRow={(record) => ({
          onClick: () => onSelect(record),
          style: { cursor: "pointer" },
        })}
        locale={{
          emptyText: (
            <Empty
              description="化学品库暂无匹配条目"
            >
              <Button type="link" onClick={onManual}>未找到？手动填写</Button>
            </Empty>
          ),
        }}
      />
    </Modal>
  );
}
```

- [ ] **步骤 2：改造 HazardousChemicalsTab**

`frontend/src/pages/Enterprise/HazardousChemicalsTab.tsx`：

1. import 增加 `Tag`（antd）、`ChemicalLibraryPickerModal`、`libraryItemToPrefill`、`ChemicalLibraryItem`。
2. state 增加：

```tsx
  const [pickerOpen, setPickerOpen] = useState(false);
```

3. `handleAdd` 改为打开选择器（不再直接开空表单）：

```tsx
  const handleAdd = () => {
    setPickerOpen(true);
  };
```

4. 新增两个回调：

```tsx
  const handlePick = (item: ChemicalLibraryItem) => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue(libraryItemToPrefill(item));
    setPickerOpen(false);
    setModalOpen(true);
  };

  const handleManualAdd = () => {
    setEditing(null);
    form.resetFields();
    setPickerOpen(false);
    setModalOpen(true);
  };
```

5. 列表"操作"列前增加来源列（columns 数组第 2 项插入新列对象）：

```tsx
  {
    title: "来源",
    dataIndex: "library_id",
    key: "library_id",
    width: 90,
    render: (v: string | null) => (v ? <Tag color="blue">标准库</Tag> : "-"),
  },
```

6. Modal 渲染区（"AI 智能生成"按钮附近）加入选择器：

```tsx
      <ChemicalLibraryPickerModal
        open={pickerOpen}
        onSelect={handlePick}
        onManual={handleManualAdd}
        onClose={() => setPickerOpen(false)}
      />
```

- [ ] **步骤 3：类型检查**

```bash
cd frontend
node node_modules/typescript/bin/tsc -b
npx vitest run src/pages/Enterprise/riskTableParser.test.ts src/services/riskAssessmentService.test.ts
```
预期：tsc 无新增错误；抽样回归通过（TiptapEditor.tsx:92 既有 1 条 tsc 错误不算新增）。

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/enterprise/ChemicalLibraryPickerModal.tsx frontend/src/pages/Enterprise/HazardousChemicalsTab.tsx
git commit -m "feat(chemical-library): 企业添加危化品两步式（库选择→预填）"
```

---

### 任务 8：管理员化学品库管理页（列表 / 编辑 / 收录）

**文件：**
- 创建：`frontend/src/pages/Settings/ChemicalLibraryManagePage.tsx`

- [ ] **步骤 1：创建页面（参照 DataDictManagePage 结构）**

`frontend/src/pages/Settings/ChemicalLibraryManagePage.tsx`（核心结构，字段编辑沿用任务 7 组件两栏布局风格）：

```tsx
import { useEffect, useMemo, useState } from "react";
import {
  App as AntApp, Button, Drawer, Form, Input, Modal, Popconfirm, Space, Table, Tag,
} from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined, ImportOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import {
  collectChemical, collectEnterprises, createLibraryItem, deleteLibraryItem,
  listEnterpriseChemicals, listLibrary, updateLibraryItem,
} from "@/services/chemicalLibraryService";
import type { ChemicalLibraryItem, ChemicalLibraryUpdate, CollectEnterpriseOption } from "@/types/chemicalLibrary";
import type { HazardousChemical } from "@/types/hazardousChemical";

const { TextArea } = Input;

const FORM_ITEMS: { key: string; label: string; textarea?: boolean; span?: 1 | 2 }[] = [
  { key: "name", label: "化学品名称" },
  { key: "cas_no", label: "CAS号" },
  { key: "un_no", label: "UN号" },
  { key: "physical_state", label: "物理状态" },
  { key: "flash_point", label: "闪点" },
  { key: "explosion_limit", label: "爆炸极限" },
  { key: "ignition_temp", label: "引燃温度" },
  { key: "density", label: "密度" },
  { key: "boiling_point", label: "沸点" },
  { key: "health_hazard", label: "健康危害", textarea: true, span: 2 },
  { key: "fire_hazard", label: "火灾爆炸危险", textarea: true, span: 2 },
  { key: "leak_response", label: "泄漏应急处置", textarea: true, span: 2 },
  { key: "storage_transport", label: "储存与运输", textarea: true, span: 2 },
  { key: "first_aid", label: "急救措施", textarea: true, span: 2 },
  { key: "protective_measures", label: "防护措施", textarea: true, span: 2 },
];

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return d || "未知错误";
}

export default function ChemicalLibraryManagePage() {
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<ChemicalLibraryItem | null>(null);
  const [collectOpen, setCollectOpen] = useState(false);
  const [entOptions, setEntOptions] = useState<CollectEnterpriseOption[]>([]);
  const [entKeyword, setEntKeyword] = useState("");
  const [selectedEnt, setSelectedEnt] = useState<string | null>(null);
  const [entChemicals, setEntChemicals] = useState<HazardousChemical[]>([]);
  const [chemLoading, setChemLoading] = useState(false);
  const [collectingId, setCollectingId] = useState<string | null>(null);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["chemical-library", keyword, page],
    queryFn: () => listLibrary(keyword || undefined, { page, page_size: 20 }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["chemical-library"] });
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setDrawerOpen(true);
  };

  const openEdit = (record: ChemicalLibraryItem) => {
    setEditing(record);
    form.setFieldsValue(record);
    setDrawerOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await updateLibraryItem(editing.id, values as ChemicalLibraryUpdate);
        message.success("已更新");
      } else {
        await createLibraryItem(values);
        message.success("已创建");
      }
      setDrawerOpen(false);
      invalidate();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteLibraryItem(id);
      message.success("已删除（企业已添加的数据不受影响）");
      invalidate();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  // ── 收录 ──
  useEffect(() => {
    if (!collectOpen) return;
    collectEnterprises("").then(setEntOptions).catch(() => setEntOptions([]));
  }, [collectOpen]);

  const searchEnt = async (kw: string) => {
    setEntKeyword(kw);
    try {
      const rows = await collectEnterprises(kw);
      setEntOptions(rows);
    } catch {
      message.error("企业搜索失败");
    }
  };

  const pickEnt = async (entId: string) => {
    setSelectedEnt(entId);
    setChemLoading(true);
    try {
      const rows = await listEnterpriseChemicals(entId);
      setEntChemicals(rows);
    } catch (e) {
      message.error(errMsg(e));
      setEntChemicals([]);
    } finally {
      setChemLoading(false);
    }
  };

  const doCollect = async (chem: HazardousChemical) => {
    if (!selectedEnt) return;
    setCollectingId(chem.id);
    try {
      await collectChemical(selectedEnt, chem.id);
      message.success(`已收录「${chem.name}」`);
      invalidate();
      await pickEnt(selectedEnt);
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setCollectingId(null);
    }
  };

  const columns = [
    { title: "化学品名称", dataIndex: "name", key: "name", width: 180 },
    { title: "CAS号", dataIndex: "cas_no", key: "cas_no", width: 130, render: (v: string | null) => v || "-" },
    { title: "UN号", dataIndex: "un_no", key: "un_no", width: 90, render: (v: string | null) => v || "-" },
    { title: "物理状态", dataIndex: "physical_state", key: "physical_state", width: 100, render: (v: string | null) => v || "-" },
    { title: "闪点", dataIndex: "flash_point", key: "flash_point", width: 100, render: (v: string | null) => v || "-" },
    {
      title: "操作",
      key: "actions",
      width: 140,
      render: (_: unknown, record: ChemicalLibraryItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm
            title="仅删除库条目，企业已添加的数据不受影响。确定删除？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="化学品库管理"
        description="系统级危化品 MSDS 公共库：企业添加时可从库中选择并自动预填。"
      />
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增条目</Button>
        <Button icon={<ImportOutlined />} onClick={() => setCollectOpen(true)}>从企业台账收录</Button>
        <Input.Search
          placeholder="按名称 / CAS / UN 搜索"
          allowClear
          enterButton
          onSearch={(v) => { setKeyword(v.trim()); setPage(1); }}
          style={{ width: 300 }}
        />
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={isLoading}
        columns={columns}
        dataSource={data?.data.items || []}
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.data.total || 0,
          onChange: setPage,
          showTotal: (t) => `共 ${t} 条`,
        }}
        scroll={{ x: 900 }}
      />

      <Drawer
        title={editing ? "编辑库条目" : "新增库条目"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={720}
        destroyOnHidden
        extra={
          <Space>
            <Button onClick={() => setDrawerOpen(false)}>取消</Button>
            <Button type="primary" onClick={handleSave}>保存</Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
            {FORM_ITEMS.map((f) => (
              <Form.Item
                key={f.key}
                name={f.key}
                label={f.label}
                rules={f.key === "name" ? [{ required: true, message: "请输入化学品名称" }] : []}
                style={f.span === 2 ? { gridColumn: "1 / -1" } : undefined}
              >
                {f.textarea ? <TextArea rows={3} /> : <Input />}
              </Form.Item>
            ))}
          </div>
        </Form>
      </Drawer>

      <Modal
        title="从企业台账收录到公共库"
        open={collectOpen}
        onCancel={() => setCollectOpen(false)}
        footer={null}
        width={860}
      >
        <Input.Search
          placeholder="搜索企业"
          allowClear
          value={entKeyword}
          onChange={(e) => setEntKeyword(e.target.value)}
          onSearch={searchEnt}
          style={{ marginBottom: 12 }}
        />
        <Space wrap style={{ marginBottom: 12 }}>
          {entOptions.map((o) => (
            <Tag
              key={o.id}
              color={selectedEnt === o.id ? "blue" : undefined}
              style={{ cursor: "pointer" }}
              onClick={() => pickEnt(o.id)}
            >
              {o.name}
            </Tag>
          ))}
        </Space>
        {selectedEnt && (
          <Table
            rowKey="id"
            size="small"
            loading={chemLoading}
            dataSource={entChemicals}
            pagination={false}
            columns={[
              { title: "化学品名称", dataIndex: "name", key: "name" },
              { title: "CAS号", dataIndex: "cas_no", key: "cas_no", render: (v: string | null) => v || "-" },
              { title: "存放位置", dataIndex: "location", key: "location", render: (v: string | null) => v || "-" },
              {
                title: "操作",
                key: "act",
                width: 100,
                render: (_: unknown, c: HazardousChemical) => (
                  <Button
                    type="link"
                    size="small"
                    loading={collectingId === c.id}
                    onClick={() => doCollect(c)}
                  >
                    收录
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Modal>
    </div>
  );
}
```

说明：`PageHeader`、`ImportOutlined` 均为既有导出；若 `ImportOutlined` 不存在则改用 `DownloadOutlined`。运行 tsc 时以实际报错为准微调图标 import。

- [ ] **步骤 2：类型检查**

```bash
cd frontend
node node_modules/typescript/bin/tsc -b
```
预期：除既有 TiptapEditor.tsx:92 错误外无新增。

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/pages/Settings/ChemicalLibraryManagePage.tsx
git commit -m "feat(chemical-library): 管理员化学品库管理页（列表/编辑/从台账收录）"
```

---

### 任务 9：菜单、路由与权限接入

**文件：**
- 修改：`frontend/src/utils/menuMap.ts`
- 修改：`frontend/src/layouts/MainLayout.tsx`
- 修改：`frontend/src/routes/index.tsx`

- [ ] **步骤 1：menuMap 注册路径**

`frontend/src/utils/menuMap.ts` 末尾追加：

```ts
  "/settings/chemical-library": "menu:chemical_library",
```

- [ ] **步骤 2：MainLayout 加菜单项（系统管理组）**

`frontend/src/layouts/MainLayout.tsx`：

1. `showSystemGroup` 条件加 `|| hasMenu("/settings/chemical-library")`；
2. `system-group` children 数组（"数据字典管理"条目后）加：

```tsx
            ...(hasMenu("/settings/chemical-library") ? [{ key: "/settings/chemical-library", icon: <DatabaseOutlined />, label: "化学品库管理" }] : []),
```

（`DatabaseOutlined` 已 import，无需新增。）

- [ ] **步骤 3：routes 注册**

`frontend/src/routes/index.tsx`：

1. import 区（`RegulationManagePage`/`DataDictManagePage` import 附近）加：

```tsx
import ChemicalLibraryManagePage from "@/pages/Settings/ChemicalLibraryManagePage";
```

2. 路由数组（`/settings/data-dicts` 行后）加：

```tsx
  { path: "/settings/chemical-library", element: <ChemicalLibraryManagePage /> },
```

- [ ] **步骤 4：类型检查**

```bash
cd frontend
node node_modules/typescript/bin/tsc -b
```
预期：除既有错误外无新增。

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/utils/menuMap.ts frontend/src/layouts/MainLayout.tsx frontend/src/routes/index.tsx
git commit -m "feat(chemical-library): 化学品库管理菜单/路由/权限接入"
```

---

### 任务 10：全量回归与部署同步

**文件：** 无新增（验证与部署）

- [ ] **步骤 1：后端全量相关回归**

```bash
docker exec emergency-plan-backend pytest tests/test_chemical_library.py tests/test_hazardous_library_id.py -v
docker exec emergency-plan-backend pytest tests/ -q 2>&1 | Select-Object -Last 15
```
预期：新测试全绿；全量无新增失败（既有环境相关失败记录基线）。

- [ ] **步骤 2：前端全量验证**

```bash
cd frontend
npx vitest run
node node_modules/typescript/bin/tsc -b
```
预期：vitest 全绿（既有 186+ 用例 + 新增）；tsc 无新增错误。

- [ ] **步骤 3：构建并同步静态资源**

```bash
docker exec emergency-plan-frontend npm run build
docker cp emergency-plan-frontend:/app/dist/. ./frontend/dist/
docker cp ./frontend/dist/. shuzihuayuan:/app/dist/
docker restart emergency-plan-backend
```
预期：build 成功；`curl -s -o /dev/null -w "%{http_code}" http://localhost:8082/` 返回 200；backend health 200。

- [ ] **步骤 4：Commit（如有遗漏改动）**

```bash
git status --short
git add <上一步列出的本功能文件>
git commit -m "chore(chemical-library): 构建产物同步与收尾"
```
（若无新改动则跳过。）

---

### 任务 11：端到端验收冒烟

**文件：** 无（手工/脚本验证）

- [ ] **步骤 1：后端 API 冒烟（登录拿 token 后按角色验证）**

需要 admin 与普通用户各一个有效账号。若没有现成 admin 账号，先用数据库现有 admin 用户或按部署账号操作（具体账号由执行者从部署配置确认；403 已有 pytest 覆盖，本步骤若无法取得账号可跳过并记录）。

```bash
# 登录取 token（按实际账号替换 email/password）
$login = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login -ContentType "application/json" -Body '{"email":"...","password":"..."}'
$token = $login.data.access_token
$headers = @{ Authorization = "Bearer $token" }
# 建条目
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/chemical-library -Headers $headers -ContentType "application/json" -Body '{"name":"冒烟乙醇","cas_no":"64-17-5","flash_point":"12℃"}'
# 列表含新条目
(Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chemical-library?keyword=冒烟乙醇" -Headers $headers).data.items
# 重复建同 CAS → 409
```
预期：创建成功 → 搜索命中 → 重复创建抛 409（detail 提示已存在）。

- [ ] **步骤 2：UI 冒烟清单（对照 spec §8 端到端场景）**

在浏览器（8082 桌面端，需刷新加载新包）逐一验证并记录结果：

1. 管理员 → 系统管理 → 化学品库管理：列表/搜索正常；"新增条目"保存后出现在列表。
2. 管理员 → 从企业台账收录：选企业 → 列表出现台账 → 点收录成功；对已收录 CAS 再次收录提示 409 文案。
3. 普通用户 → 企业管理 → 某企业 → 危险化学品 → 添加危险化学品：弹出库选择；搜索命中；点击行 → 表单已预填（品名/CAS/闪点/MSDS），补"存放位置/最大储存量"保存成功；列表显示"标准库"标签。
4. 库选择弹窗搜索无结果 → "未找到？手动填写" → 打开空表单可正常保存（无来源标签）。
5. 编辑已有记录 → 保存后来源标签不丢。
6. 管理员删除库条目 → 确认文案出现；删除后企业对应记录仍在、来源标签消失（FK SET NULL）。

- [ ] **步骤 3：汇报**

整理：commit 列表、pytest/vitest/tsc 输出摘要、UI 冒烟结果（通过/遗留）、以及"现有 31 条台账整理入库"的管理员操作建议（spec §10）。

---

## 自检记录（计划作者内联执行）

- 规格覆盖度：spec §3 数据模型 → 任务 1-2；§4 查重 → 任务 3-4；§5 API → 任务 3-5；§6.1 管理页 → 任务 8-9；§6.2 两步式 → 任务 7；§6.3 服务层 → 任务 6；§7 错误处理 → 各任务实现与 409/403 测试；§8 测试验收 → 任务 3/4/5/10/11；§9 范围外 → 不实现；§10 上线数据整理 → 任务 11 步骤 3 建议；§11 文件清单 → 与文件结构一致。
- 占位符扫描：无 TODO/待定；账号凭据属执行环境事实，已在任务 11 注明"无法取得则跳过并记录"，有 pytest 403 兜底。
- 类型一致性：`library_id` 后端 Create/Update/Response/前端类型/服务透传一致；`ChemicalLibraryResponse` 字段与前端 `ChemicalLibraryItem` 一致（不含 location/max_storage/enterprise_id）；collect 字段列表与模型字段一致。
