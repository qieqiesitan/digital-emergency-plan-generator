# Codex Custom Subagents task handoff v1

Task: task_02_dict_service

## 目标

实现「风险分级管控增强（A 阶段）」实现计划的任务 2：数据字典合并服务（企业 > 系统，60s 缓存）+ 系统/企业管理接口，按 TDD 完成并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`bf61245`，任务 1 已完成）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 背景

任务 1 已落地 `data_dicts` 表与 `DataDict` 模型（含系统种子）。本任务提供合并读取服务与 CRUD 接口。测试约定（已核实）：无 db fixture，服务测试用 `unittest.mock`（`AsyncMock`/`MagicMock`），async 测试必须 `@pytest.mark.asyncio`。

## 文件

- 创建：`backend/app/services/data_dict_service.py`
- 创建：`backend/app/schemas/data_dict.py`
- 创建：`backend/app/routers/data_dicts.py`
- 修改：`backend/app/main.py`（注册路由）
- 测试：`backend/tests/test_data_dict.py`（追加 2 个用例）

## 步骤（TDD）

- [ ] **步骤 1：追加失败测试**（`backend/tests/test_data_dict.py` 末尾追加）

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.data_dict_service import get_dict_map
from app.models.data_dict import DataDict

@pytest.mark.asyncio
async def test_enterprise_overrides_system():
    db = MagicMock()
    db.execute = AsyncMock()
    rows = [
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.5}, scope="system", is_system=True),
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.3}, scope="enterprise", enterprise_id="ent-1"),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result
    merged = await get_dict_map(db, "ent-1", "measure_factors")
    assert merged["engineering"]["value"]["factor"] == 0.3

@pytest.mark.asyncio
async def test_disabled_entry_excluded():
    db = MagicMock()
    db.execute = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        DataDict(dict_type="measure_factors", code="ppe", label="个体防护",
                 value={"factor": 0.85}, scope="system", enabled=False, is_system=True),
    ]
    db.execute.return_value = result
    merged = await get_dict_map(db, "ent-1", "measure_factors")
    assert "ppe" not in merged
```

- [ ] **步骤 2：运行测试验证失败**

运行：在 `backend` 目录 `python -m pytest tests/test_data_dict.py -v`
预期：新增 2 用例 FAIL（`ImportError: cannot import name 'get_dict_map'`），原有 2 用例 PASS

- [ ] **步骤 3：实现合并服务**（`backend/app/services/data_dict_service.py`）

```python
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.data_dict import DataDict

_CACHE_TTL = 60
_cache: dict[tuple[str, str], tuple[float, dict[str, dict]]] = {}

async def get_dict_map(db: AsyncSession, enterprise_id: str | None, dict_type: str) -> dict[str, dict]:
    """合并读取：企业条目 > 系统默认；60s 进程内缓存。返回 {code: {label, value, description}}。"""
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

`backend/app/schemas/data_dict.py`：

```python
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

`backend/app/routers/data_dicts.py`（注意：企业归属校验**不要**从 `risk_management` 路由导入 `_get_ent`，改为在本文件写一个本地 `_get_enterprise` 辅助函数，避免跨路由耦合；用 `Enterprise` 模型按 `id` + `user_id` 查询，不存在抛 404「企业不存在」）：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.data_dict import DataDict
from app.models.enterprise import Enterprise
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.data_dict import DataDictCreate, DataDictUpdate
from app.services.data_dict_service import invalidate_dict_cache

router = APIRouter(tags=["Data Dicts"])

async def _get_enterprise(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id, Enterprise.user_id == user_id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent

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
    await _get_enterprise(enterprise_id, current_user.id, db)
    stmt = select(DataDict).where(
        (DataDict.enterprise_id == enterprise_id) | (DataDict.enterprise_id.is_(None)))
    if dict_type:
        stmt = stmt.where(DataDict.dict_type == dict_type)
    rows = (await db.execute(stmt.order_by(DataDict.scope, DataDict.dict_type, DataDict.sort_order))).scalars().all()
    return ApiResponse(data=[_serialize(r) for r in rows])

@router.post("/enterprises/{enterprise_id}/data-dicts", response_model=ApiResponse, status_code=201)
async def create_enterprise_dict(enterprise_id: str, body: DataDictCreate,
                                 current_user: User = Depends(get_current_user), db=Depends(get_db)):
    await _get_enterprise(enterprise_id, current_user.id, db)
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

`backend/app/main.py`：import 列表加 `data_dicts`，并加 `app.include_router(data_dicts.router, prefix="/api/v1")`。

- [ ] **步骤 5：运行测试验证通过**

运行：在 `backend` 目录 `python -m pytest tests/test_data_dict.py -v`
预期：4 passed（原 2 + 新 2）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/data_dict_service.py backend/app/schemas/data_dict.py backend/app/routers/data_dicts.py backend/app/main.py backend/tests/test_data_dict.py
git commit -m "feat(data-dict): merged dict service with system and enterprise override endpoints"
```

在 `.worktrees\dual-prevention` 内执行 git；不要提交 TASKS.md；commit 消息精确匹配。

## 验证要求

1. `python -m pytest tests/test_data_dict.py -v` 4 passed；
2. `python -m pytest tests/ -q` 无回归；
3. `git diff --check` 干净；
4. commit 仅含上述 5 个文件（新增 3 + 修改 2）。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_02_dict_service --claim-id <claim_id> --exit-code 0 --summary "字典合并服务+管理接口完成"
```

最终回复报告：task_id、claim_id、claim 路径、commit SHA、测试结果、自审结论。

## 规则

- 严格 TDD；用 `apply_patch` 创建/编辑文件；
- 只改本任务列出的文件；不顺手重构；
- 阻塞或有疑问时停下汇报，不猜测跳过。

## 主控修复指示（2026-08-15）：合并顺序 bug + 反序测试

你自报的观察正确：`get_dict_map` 的合并依赖 `order_by(DataDict.scope, ...)`，字符串升序下 `enterprise < system`，真实 DB 里系统行后到并覆盖企业行，与「企业 > 系统」语义相反。按以下方式修复（只动 `data_dict_service.py` 与 `test_data_dict.py`）：

**1. 合并逻辑改为「顺序无关 + 企业优先」**（`backend/app/services/data_dict_service.py`）：

把合并循环改为：

```python
    merged: dict[str, dict] = {}
    for r in rows:
        if r.code not in merged or r.enterprise_id is not None:
            merged[r.code] = {"label": r.label, "value": r.value, "description": r.description}
    _cache[key] = (now, merged)
    return merged
```

语义：企业条目（enterprise_id 非空）总是覆盖同 code 系统条目；系统条目只在无企业条目时生效。不再依赖查询行序。（查询可保留原 order_by，也可去掉，以保持可读为准。）

**2. 追加反序测试**（`backend/tests/test_data_dict.py`）：

```python
@pytest.mark.asyncio
async def test_enterprise_wins_regardless_of_row_order():
    db = MagicMock()
    db.execute = AsyncMock()
    rows = [
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.3}, scope="enterprise", enterprise_id="ent-1"),
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.5}, scope="system", is_system=True),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result
    merged = await get_dict_map(db, "ent-1", "measure_factors")
    assert merged["engineering"]["value"]["factor"] == 0.3
```

（注意企业行在前、系统行在后——若实现仍依赖行序，此测试会失败。）

**验证与提交：**

- 在 `backend` 目录 `python -m pytest tests/test_data_dict.py -v`，预期 5 passed；
- `python -m pytest tests/ -q` 无回归；
- `git diff --check` 干净；
- 在 `.worktrees\dual-prevention` 提交（消息精确）：

```bash
git add backend/app/services/data_dict_service.py backend/tests/test_data_dict.py
git commit -m "fix(data-dict): order-independent enterprise-over-system dict merge"
```

完成后报告新 commit SHA 与测试结果（complete 命令照常执行；若此前已 complete，忽略即可）。
