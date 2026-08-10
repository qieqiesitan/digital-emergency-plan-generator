# Codex Custom Subagents task handoff v1

Task: task_b1_ai_config_system

## 任务：AI 配置全局化（系统级单例）——易用性优化计划 B 任务 B1

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含计划 A 全部提交（b688aab）。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：编写失败测试

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

运行确认失败：`cd backend && python -m pytest tests/test_ai_config_system.py -v`（预期 ModuleNotFoundError）。

### 步骤 2：迁移 SQL + 模型 + 统一服务

新建 `backend/db_migration_ai_config_system.sql`：

```sql
-- AI 配置全局化：user_id 可空（NULL = 系统级配置），加 is_system 标记
ALTER TABLE ai_configs ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE ai_configs ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;
```

`backend/app/models/enterprise.py` 中 `AIConfig` 修改（user_id 可空 + is_system 字段；移除 user_id 的 unique=True）：

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

### 步骤 3：改造取配置调用点为系统级

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

`backend/app/routers/generation.py`：将函数内所有形如

```python
ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id, AIConfig.is_active == True))).scalar_one_or_none()
```

的查询替换为：

```python
from app.services.ai_config_service import get_system_ai_config
ai_config = await get_system_ai_config(db)
```

未配置处统一返回 400「系统未配置 AI 模型，请联系管理员」（保持与现有错误语义一致）。

`backend/app/routers/chat.py`、`hazardous_chemicals.py`、`resources_ext.py`、`regulations.py`：按同一模式替换（regulations.py 的 _get_ai_config helper 内部改为调用 get_system_ai_config(db)）。

`backend/app/routers/external.py`：`AIConfig.user_id == user_id` 的查询替换为 get_system_ai_config(db)。

`backend/app/services/chat_dispatch.py`：get_ai_config tool 的查询替换为系统配置（返回 provider/model 供前端展示）。

注意：先逐一读文件确认现有查询写法（可能带 is_active 条件），替换为系统级查询；保持函数签名与返回类型不变；删除不再使用的 AIConfig 导入（若文件不再直接引用）。

### 步骤 4：ai_config.py 路由改为系统级（管理员）

`backend/app/routers/ai_config.py` 改造：

- get_ai_config：查询系统配置（user_id IS NULL 且 is_system=True），未配置返回 404「尚未配置 AI」；加 Depends(require_admin)。
- update_ai_config：upsert 系统配置（user_id=None, is_system=True, is_active=True），不再绑定 current_user；加 Depends(require_admin)。
- delete_ai_config：删除系统配置；加 Depends(require_admin)。
- test_ai_connection 不变。
- 顶部导入追加 `from app.dependencies import require_admin`。

三个 handler 核心代码：

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

### 步骤 5：运行测试验证通过

运行：`cd backend && python -m pytest tests/test_ai_config_system.py -v`

预期：3 个测试 PASS。

### 步骤 6：全量后端测试 + Commit

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（基线全量已通过；若个别环境失败，说明并对比基线）。

```bash
git add backend/db_migration_ai_config_system.sql backend/app/models/enterprise.py backend/app/services/ai_config_service.py backend/app/services/risk_ai_service.py backend/app/routers/ai_config.py backend/app/routers/generation.py backend/app/routers/chat.py backend/app/routers/chat_dispatch.py backend/app/routers/external.py backend/app/routers/hazardous_chemicals.py backend/app/routers/regulations.py backend/app/routers/resources_ext.py backend/tests/test_ai_config_system.py
git commit -m "refactor(ai): consolidate AI config to system-level singleton"
```

## 上下文

- 计划 A 已完成（分支 codex/usability-overhaul，HEAD b688aab）。附图扩展已合入 master，generation.py 现有结构以 worktree 实际为准。
- 这是把「每用户配置 AI」改为「系统级单例」的关键后端改造，影响面广（9 个文件调用点），务必逐一确认替换完整、不残留 user_id 查询。
- 测试风格：纯单元测试 + MagicMock/AsyncMock + asyncio.run，从 backend/ 目录执行 pytest（conftest 处理 sys.path）。

## 开始之前

对需求/方案/依赖有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述 TDD 实现
2. 运行测试验证（步骤 5/6）
3. 提交（步骤 6）
4. 自审：全库是否还有 `AIConfig.user_id == current_user.id` 的生成/聊天取配置残留？is_system 迁移是否完整？普通用户路径是否不再取用户级配置？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、测试结果、提交 SHA、自审发现、任何疑虑
