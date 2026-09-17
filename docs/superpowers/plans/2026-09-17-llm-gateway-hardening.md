# AI 调用网关增强（llm_client 就地增强）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修掉 `llm_client` 的两个实测缺陷（B1 超时错误码映射失效、B2 流式截断静默通过），并加上统一调用留痕与按能力选模型——让"AI 干了什么、花了多少、错在哪"可回答。

**架构：** 就地增强 `backend/app/services/llm_client.py`（不新建旁路网关），异常语义集中在 `LLMError.status_code` 上；留痕做成 best-effort 的独立服务 `llm_telemetry.py`，写库失败绝不影响主流程；模型选择下沉到 `ai_config_service`，按能力名回落系统级配置。

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x / PostgreSQL / httpx / pytest + pytest-asyncio。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §5

**缺陷证据：** `docs/系统诊断报告-2026-09-17.md` §九（mock 供应商实测）——超时经 `llm_text_completion` 变成 `500 + "AI调用失败: 0"`（`except httpx.TimeoutException` 是死代码）；流中途断连静默返回半截文本且标记 success。

**范围说明：** 本计划只覆盖"网关增强"这一层，是全站受益的基础设施改造。AI 抽取链路（资料 → 重大危险源台账）另出计划；前端另出计划。理由：留痕与缺陷修复必须先落地，否则抽取链路会把同样的错误语义复制一遍。

---

## 文件结构

**新建**

| 文件 | 职责 |
|---|---|
| `backend/app/models/llm_call_log.py` | 调用留痕 ORM（单表） |
| `backend/app/services/llm_telemetry.py` | best-effort 留痕写入，绝不影响主流程 |
| `backend/db_migration_20260917_llm_call_log.sql` | 留痕表 DDL |
| `backend/tests/test_llm_client_errors.py` | B1 / B2 回归测试 |
| `backend/tests/test_llm_telemetry.py` | 留痕服务测试 |
| `backend/tests/test_ai_config_capability.py` | 按能力选模型测试 |

**修改**

| 文件 | 改动 |
|---|---|
| `backend/app/services/llm_client.py` | B1：识别 `LLMError(status_code=0)` 中的超时并映射 504；B2：流未收到 `[DONE]` 时抛可识别异常；新增留痕钩子与 `capability` 参数 |
| `backend/app/services/ai_config_service.py` | 新增 `get_ai_config_for(db, capability)`，按能力覆盖回落系统级 |
| `backend/app/models/enterprise.py` | `AIConfig` 增加 `capability_overrides` JSONB（能力名 → 模型/参数） |

**既有约定**

- 迁移脚本 `backend/db_migration_*.sql`，由 `app/services/migration_runner.py` 按文件名排序自动执行，**不要加进 `BASELINE_MIGRATIONS`**。
- 模型用 `Mapped[...] = mapped_column(...)`；主键 `UUID(as_uuid=False)` + `default=lambda: str(uuid4())`。
- 测试 `backend/tests/`，纯服务测试用 `MagicMock` / `AsyncMock`，不连数据库。

---

## 任务 1：修 B1 —— 超时错误码映射

**文件：**

- 修改：`backend/app/services/llm_client.py:219-249`
- 测试：`backend/tests/test_llm_client_errors.py`

**背景：** `llm_text_completion` 里 `except httpx.TimeoutException → HTTPException(504)` 永远不会命中——`_post_with_retry`（同文件 68-72 行）已把超时包成 `LLMError(0, str(e))`，于是落到 `except LLMError` 分支变成 `HTTPException(500, "AI调用失败: 0")`。用户看到的是无意义的 500 与空消息。

- [ ] **步骤 1：编写失败的测试**

```python
"""llm_client 异常语义测试：B1 超时映射、B2 流截断。"""

import httpx
import pytest
from fastapi import HTTPException

from app.services import llm_client
from app.services.llm_client import LLMError, llm_text_completion


class _Cfg:
    api_key_encrypted = "00" * 16
    provider = "deepseek"
    base_url = "https://example.invalid/v1"
    model = "test-model"


@pytest.mark.asyncio
async def test_b1_timeout_maps_to_504(monkeypatch):
    """超时必须映射为 504，而不是 500 + "AI调用失败: 0"。"""
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")

    async def _boom(*a, **k):
        raise LLMError(0, "timed out")

    monkeypatch.setattr(llm_client, "llm_chat_completion", _boom)

    with pytest.raises(HTTPException) as ei:
        await llm_text_completion([{"role": "user", "content": "hi"}], _Cfg(), timeout=1)
    assert ei.value.status_code == 504
    assert "超时" in ei.value.detail


@pytest.mark.asyncio
async def test_b1_non_timeout_status_zero_still_502(monkeypatch):
    """status_code=0 但不是超时（如连接被拒）应映射 502，不能一律 504。"""
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")

    async def _boom(*a, **k):
        raise LLMError(0, "connection refused")

    monkeypatch.setattr(llm_client, "llm_chat_completion", _boom)
    with pytest.raises(HTTPException) as ei:
        await llm_text_completion([{"role": "user", "content": "hi"}], _Cfg(), timeout=1)
    assert ei.value.status_code == 502


@pytest.mark.asyncio
async def test_b1_401_still_500_with_hint(monkeypatch):
    """401 语义不变：500 + 重新配置提示。"""
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")

    async def _boom(*a, **k):
        raise LLMError(401, "unauthorized")

    monkeypatch.setattr(llm_client, "llm_chat_completion", _boom)
    with pytest.raises(HTTPException) as ei:
        await llm_text_completion([{"role": "user", "content": "hi"}], _Cfg(), timeout=1)
    assert ei.value.status_code == 500
    assert "API Key" in ei.value.detail
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_llm_client_errors.py -v
```

预期：`test_b1_timeout_maps_to_504` FAIL（实际得到 500），另两例 PASS

- [ ] **步骤 3：编写实现**

在 `backend/app/services/llm_client.py` 的常量区追加超时识别关键字：

```python
# httpx 的超时在 _post_with_retry / _stream_response 里已被包成 LLMError(0, str(e))，
# 因此上层无法再按异常类型区分。这里用消息特征判定，并保留 _post_with_retry 抛错时
# 附带的结构化标记作为首选依据。
TIMEOUT_MARKERS = ("timed out", "timeout", "ReadTimeout", "ConnectTimeout", "PoolTimeout")


def is_timeout_error(exc: "LLMError") -> bool:
    """判断 LLMError(status_code=0) 是否源自超时。"""
    if exc.status_code != 0:
        return False
    text = str(exc)
    return any(marker.lower() in text.lower() for marker in TIMEOUT_MARKERS)
```

把 `llm_text_completion` 的异常分支改为：

```python
    try:
        data = await llm_chat_completion(messages, ai_config, stream=False, timeout=timeout)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except HTTPException:
        raise
    except LLMError as e:
        if e.status_code == 401:
            raise HTTPException(500, "AI API Key 无效或已过期，请在系统设置中重新配置 AI 模型")
        if is_timeout_error(e):
            raise HTTPException(504, f"AI 响应超时（{timeout}s），请稍后重试") from e
        if e.status_code == 0:
            raise HTTPException(502, f"AI 服务连接失败: {e}") from e
        raise HTTPException(500, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"AI 服务连接失败: {e}") from e
```

同时删除已经失效的 `except httpx.TimeoutException:` 分支（它永远不会命中）。

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_llm_client_errors.py -v
```

预期：`3 passed`

- [ ] **步骤 5：跑相关回归**

运行：

```bash
cd backend && python -m pytest tests/ -q -k "llm or chat or generation or plan_generation"
```

预期：全绿

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/llm_client.py backend/tests/test_llm_client_errors.py
git commit -m "fix(llm): 超时错误码映射失效（B1）—— LLMError(0) 区分超时映射 504（任务 1）"
```

---

## 任务 2：修 B2 —— 流式截断可识别

**文件：**

- 修改：`backend/app/services/llm_client.py:148-193`（`_stream_response`）
- 测试：`backend/tests/test_llm_client_errors.py`（追加）

**背景：** `_stream_response` 在 `async for line in resp.aiter_lines()` 之后直接 `return`。若供应商中途断开（没有收到 `data: [DONE]`），生成器正常结束，调用方把半截正文当完整结果落库——用户拿到半截报告却没有任何错误提示。

- [ ] **步骤 1：编写失败的测试（追加）**

```python
class _FakeResp:
    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    async def aread(self):
        return b""

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *a):
        return False


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, *a, **k):
        return _FakeStreamCtx(self._resp)


def _patch_httpx(monkeypatch, lines):
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")
    monkeypatch.setattr(
        llm_client.httpx, "AsyncClient", lambda *a, **k: _FakeClient(_FakeResp(lines))
    )


@pytest.mark.asyncio
async def test_b2_truncated_stream_raises(monkeypatch):
    """中途断连（没有 [DONE]）必须抛可识别异常，不能静默返回半截文本。"""
    _patch_httpx(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"content":"前半段"}}]}',
            'data: {"choices":[{"delta":{"content":"后半段"}}]}',
        ],
    )
    chunks = []
    with pytest.raises(llm_client.LLMStreamTruncatedError):
        async for c in llm_client._stream_response("https://x/v1", {}, _Cfg()):
            chunks.append(c)
    assert chunks == ["前半段", "后半段"], "已收到的分片应已产出，再由异常收尾"


@pytest.mark.asyncio
async def test_b2_complete_stream_ok(monkeypatch):
    """正常收到 [DONE] 不应抛异常。"""
    _patch_httpx(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"content":"完整"}}]}',
            "data: [DONE]",
        ],
    )
    chunks = [c async for c in llm_client._stream_response("https://x/v1", {}, _Cfg())]
    assert chunks == ["完整"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_llm_client_errors.py -k b2 -v
```

预期：`test_b2_truncated_stream_raises` FAIL（`LLMStreamTruncatedError` 不存在）

- [ ] **步骤 3：编写实现**

在 `llm_client.py` 的 `LLMError` 之后追加异常类型：

```python
class LLMStreamTruncatedError(RuntimeError):
    """流式响应未正常结束（未收到 [DONE]）——结果不完整，调用方不得落库。"""

    def __init__(self, received_chars: int = 0):
        super().__init__(f"LLM 流式响应中断：未收到结束标记，已收到 {received_chars} 字符")
        self.received_chars = received_chars
```

把 `_stream_response` 的循环改为记录是否收到结束标记：

```python
    received = 0
    finished = False
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{base}/chat/completions",
                                         json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        if resp.status_code in RETRYABLE_STATUS and attempt < max_retries:
                            await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                            continue
                        raise LLMError(resp.status_code, err.decode("utf-8", errors="replace"))
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                finished = True
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                reasoning, content = _delta_texts(delta)
                                if reasoning and reasoning_cb:
                                    try:
                                        reasoning_cb(reasoning)
                                    except Exception:
                                        logger.exception("reasoning_cb failed")
                                if content:
                                    received += len(content)
                                    yield content
                            except json.JSONDecodeError:
                                pass
                    if finished:
                        return
                    raise LLMStreamTruncatedError(received)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            if attempt < max_retries:
                await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                continue
            raise LLMError(0, str(e))
    raise LLMError(0, "LLM retry exhausted")
```

> 注意：`LLMStreamTruncatedError` 继承 `RuntimeError`，不会被上面的
> `except (httpx.TransportError, httpx.TimeoutException)` 捕获，因此**中途断连不重试**——
> 与文件原注释"建连/首响应前可重试，中途断流不重试"一致，且此时部分内容已对外产出，重试会导致重复。

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_llm_client_errors.py -v
```

预期：`5 passed`

- [ ] **步骤 5：跑流式相关回归**

运行：

```bash
cd backend && python -m pytest tests/ -q -k "stream or generation or chapter"
```

预期：全绿；若有用例依赖"截断返回正常"，属测试需同步更新，逐个确认后改断言而非放宽实现

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/llm_client.py backend/tests/test_llm_client_errors.py
git commit -m "fix(llm): 流式截断静默通过（B2）—— 未收到 [DONE] 抛 LLMStreamTruncatedError（任务 2）"
```

---

## 任务 3：调用留痕（best-effort）

**文件：**

- 创建：`backend/app/models/llm_call_log.py`
- 创建：`backend/app/services/llm_telemetry.py`
- 创建：`backend/db_migration_20260917_llm_call_log.sql`
- 测试：`backend/tests/test_llm_telemetry.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""调用留痕服务测试：写入成功、失败不影响主流程。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_telemetry import LlmCallRecord, record_call


def _db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_record_call_persists_row():
    db = _db()
    await record_call(
        db,
        LlmCallRecord(
            module="major_hazard",
            capability="extract",
            model="deepseek-chat",
            duration_ms=1234,
            success=True,
            total_tokens=456,
        ),
    )
    assert db.add.called
    row = db.add.call_args[0][0]
    assert row.module == "major_hazard"
    assert row.capability == "extract"
    assert row.duration_ms == 1234
    assert row.success is True
    assert row.total_tokens == 456
    assert row.truncated is False
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_record_call_swallows_db_failure():
    """留痕是 best-effort：写库炸了也绝不能把业务请求带崩。"""
    db = _db()
    db.commit = AsyncMock(side_effect=RuntimeError("db down"))
    # 不应抛异常
    await record_call(db, LlmCallRecord(module="m", capability="c", model="x"))


@pytest.mark.asyncio
async def test_record_call_marks_failure_and_retry():
    db = _db()
    await record_call(
        db,
        LlmCallRecord(
            module="m",
            capability="c",
            model="x",
            success=False,
            error_code=429,
            error_message="rate limited",
            retry_count=3,
            truncated=True,
        ),
    )
    row = db.add.call_args[0][0]
    assert row.success is False
    assert row.error_code == 429
    assert row.retry_count == 3
    assert row.truncated is True


def test_migration_sql_declares_table():
    import re
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1] / "db_migration_20260917_llm_call_log.sql"
    ).read_text(encoding="utf-8")
    assert re.search(r"CREATE TABLE IF NOT EXISTS\s+llm_call_logs\b", sql)
    for col in ("module", "capability", "model", "duration_ms", "success", "truncated"):
        assert col in sql, col
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_llm_telemetry.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.llm_telemetry'`

- [ ] **步骤 3：编写 ORM**

```python
"""LLM 调用留痕 ORM。

一行 = 一次供应商调用。用于回答三个问题：这个月花了多少、哪几次失败了、
用户投诉的那次是不是流被截断了。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LlmCallLog(Base):
    __tablename__ = "llm_call_logs"
    __table_args__ = (Index("idx_llm_log_module_time", "module", "created_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(120))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_code: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    enterprise_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **步骤 4：编写留痕服务**

```python
"""LLM 调用留痕：best-effort 写入，绝不因留痕失败影响业务请求。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_call_log import LlmCallLog

logger = logging.getLogger("llm_telemetry")


@dataclass
class LlmCallRecord:
    module: str
    capability: str
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    duration_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    success: bool = True
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    truncated: bool = False
    user_id: Optional[str] = None
    enterprise_id: Optional[str] = None


async def record_call(db: AsyncSession, record: LlmCallRecord) -> Optional[str]:
    """写一条留痕。任何异常都被吞掉并记日志——留痕失败不是业务失败。"""
    try:
        row = LlmCallLog(
            module=record.module,
            capability=record.capability,
            model=record.model,
            prompt_version=record.prompt_version,
            duration_ms=record.duration_ms,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            success=record.success,
            error_code=record.error_code,
            error_message=(record.error_message or "")[:2000] or None,
            retry_count=record.retry_count,
            truncated=record.truncated,
            user_id=record.user_id,
            enterprise_id=record.enterprise_id,
        )
        db.add(row)
        await db.commit()
        return getattr(row, "id", None)
    except Exception:
        logger.exception("LLM 调用留痕写入失败（已忽略，不影响业务）")
        return None
```

- [ ] **步骤 5：编写迁移**

```sql
-- 20260917 LLM 调用留痕：回答"花了多少 / 哪次失败 / 是不是被截断"
CREATE TABLE IF NOT EXISTS llm_call_logs (
    id UUID PRIMARY KEY,
    module VARCHAR(64) NOT NULL,
    capability VARCHAR(64) NOT NULL,
    model VARCHAR(120),
    prompt_version VARCHAR(64),
    duration_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_code INTEGER,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    truncated BOOLEAN NOT NULL DEFAULT FALSE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    enterprise_id UUID REFERENCES enterprises(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_llm_log_module_time ON llm_call_logs (module, created_at);
CREATE INDEX IF NOT EXISTS ix_llm_log_created_at ON llm_call_logs (created_at);
```

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_llm_telemetry.py -v
```

预期：`4 passed`

- [ ] **步骤 7：Commit**

```bash
git add backend/app/models/llm_call_log.py backend/app/services/llm_telemetry.py backend/db_migration_20260917_llm_call_log.sql backend/tests/test_llm_telemetry.py
git commit -m "feat(llm): 调用留痕表与服务（best-effort，写库失败不影响业务）（任务 3）"
```

---

## 任务 4：按能力选模型

**文件：**

- 修改：`backend/app/models/enterprise.py`（`AIConfig` 加 `capability_overrides`）
- 修改：`backend/app/services/ai_config_service.py`
- 创建：`backend/db_migration_20260917_ai_config_capability.sql`
- 测试：`backend/tests/test_ai_config_capability.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""按能力选模型：命中覆盖用覆盖，未命中回落系统级。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai_config_service import (
    apply_capability_override,
    get_ai_config_for,
)


def _cfg(model="big-model", overrides=None):
    c = MagicMock()
    c.model = model
    c.capability_overrides = overrides or {}
    return c


def test_apply_capability_override_replaces_model():
    cfg = _cfg(model="big-model", overrides={"extract": {"model": "small-model"}})
    out = apply_capability_override(cfg, "extract")
    assert out["model"] == "small-model"
    assert out["base_config"] is cfg


def test_apply_capability_override_falls_back():
    """未配置的能力回落系统级模型，不报错。"""
    cfg = _cfg(model="big-model", overrides={})
    out = apply_capability_override(cfg, "report")
    assert out["model"] == "big-model"


def test_apply_capability_override_ignores_unknown_keys():
    """覆盖里只认白名单键，防止把任意参数透传进请求体（历史 B19 教训）。"""
    cfg = _cfg(overrides={"extract": {"model": "s", "max_retries": 9, "evil": 1}})
    out = apply_capability_override(cfg, "extract")
    assert out["model"] == "s"
    assert "evil" not in out
    assert "max_retries" not in out


@pytest.mark.asyncio
async def test_get_ai_config_for_returns_none_when_missing():
    db = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    assert await get_ai_config_for(db, "extract") is None


def test_migration_adds_column():
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1] / "db_migration_20260917_ai_config_capability.sql"
    ).read_text(encoding="utf-8")
    assert "capability_overrides" in sql
    assert "ADD COLUMN IF NOT EXISTS" in sql
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ai_config_capability.py -q
```

预期：FAIL，`ImportError: cannot import name 'apply_capability_override'`

- [ ] **步骤 3：加字段与迁移**

在 `backend/app/models/enterprise.py` 的 `AIConfig` 类里追加（放在 `is_active` 附近）：

```python
    # 能力级模型覆盖：{"extract": {"model": "small"}, "report": {"model": "big"}}
    # 只认白名单键（见 ai_config_service.ALLOWED_OVERRIDE_KEYS）
    capability_overrides: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
```

`backend/db_migration_20260917_ai_config_capability.sql`：

```sql
-- 20260917 AI 配置支持按能力覆盖模型（如抽取用小模型、报告用强模型）
ALTER TABLE ai_configs
    ADD COLUMN IF NOT EXISTS capability_overrides JSONB NOT NULL DEFAULT '{}'::jsonb;
```

> 表名已核对：`AIConfig.__tablename__ == "ai_configs"`（`backend/app/models/enterprise.py:229`）。

- [ ] **步骤 4：写服务函数**

在 `backend/app/services/ai_config_service.py` 追加：

```python
from typing import Any

# 只允许覆盖这些键，其余一律忽略——历史教训 B19：客户端参数混入请求体会被严格 API 400。
ALLOWED_OVERRIDE_KEYS = ("model", "temperature", "max_tokens", "timeout")


def apply_capability_override(ai_config: Any, capability: str) -> dict:
    """返回该能力实际使用的模型参数；未命中覆盖时回落系统级配置。"""
    overrides = getattr(ai_config, "capability_overrides", None) or {}
    entry = overrides.get(capability) or {}
    out: dict = {"base_config": ai_config, "model": getattr(ai_config, "model", None)}
    for key in ALLOWED_OVERRIDE_KEYS:
        if key in entry and entry[key] is not None:
            out[key] = entry[key]
    return out


async def get_ai_config_for(db: AsyncSession, capability: str):
    """取系统级 AI 配置（能力覆盖由 apply_capability_override 处理）。"""
    return await get_system_ai_config(db)
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ai_config_capability.py -v
```

预期：`5 passed`

- [ ] **步骤 6：跑 AI 配置相关回归**

运行：

```bash
cd backend && python -m pytest tests/ -q -k "ai_config or llm"
```

预期：全绿

- [ ] **步骤 7：Commit**

```bash
git add backend/app/models/enterprise.py backend/app/services/ai_config_service.py backend/db_migration_20260917_ai_config_capability.sql backend/tests/test_ai_config_capability.py
git commit -m "feat(llm): 按能力选模型（白名单覆盖 + 系统级回落）（任务 4）"
```

---

## 验收清单

- [ ] `cd backend && python -m pytest tests/ -q` 全绿，且失败数不高于既有基线（当前基线为 4 个既有失败）
- [ ] B1 回归：mock 超时 → 返回 **504**，不再出现 `500 + "AI调用失败: 0"`
- [ ] B2 回归：mock 流中途断连 → 抛 `LLMStreamTruncatedError`，不落库
- [ ] 留痕：连续两次失败调用后，`llm_call_logs` 能查出对应 `success=false` 与 `error_code`
- [ ] 留痕降级：把 `llm_call_logs` 表改名后再发起一次调用，业务请求仍成功（只记日志）
- [ ] 能力覆盖：给 `extract` 配小模型后，抽取类调用的请求体里 `model` 是小模型，报告类仍用系统级
- [ ] 迁移幂等：`db_migration_20260917_llm_call_log.sql` 与 `..._ai_config_capability.sql` 连跑两次无报错

## 未纳入本计划（后续计划）

- **接线上留痕**：把 `record_call` 接到各业务 AI 端点上（本计划只提供能力，不逐个改造 24 个既有端点，避免一次性大范围回归）
- **AI 抽取链路**：资料 → 重大危险源台账（依赖本计划的网关）
- **AI 能力注册表与管理页**（规格 P3）
- **存量 24 个 AI 端点迁移到统一入口**（规格决策：随模块演进顺手迁移）
