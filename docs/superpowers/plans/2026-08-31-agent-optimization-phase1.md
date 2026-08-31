# 智能体优化阶段 1（体验快赢 0.4.0）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修复 Chat AI 助手 6 类体验硬伤：进度持久化+步骤条、工具并行、LLM 重试、报告角色提示词、对话记忆增强、聊天内端到端生成预案。

**架构：** 新增 `chat_tool_calls` 表记录工具执行轨迹（SSE 步骤条 + 刷新回放）；agent_loop 读工具并行/写工具串行；`llm_client` 增加指数退避重试；消息表复用 role 字段存 tool 轨迹、上下文由后端从 DB 重建并按 token 预算截断；`generation.py` 批量生成逻辑抽取为 `plan_generation_service`，聊天经后台任务触发并新增进度查询工具。

**技术栈：** Python 3.11 / FastAPI / SQLAlchemy async / PostgreSQL / httpx；React + AntD（桌面）/ React Native Web 风格（移动端）/ Vite + tsc + vitest。

**规格依据：** `docs/superpowers/specs/2026-08-31-agent-optimization-design.md`（v2.0）阶段 1（模块 1-6）。

---

## 文件结构

**新建：**
- `backend/app/models/chat_tool_call.py` — ChatToolCall 模型（对应 chat_tool_calls 表）
- `backend/db_migration_20260831_agent_chat_tool_calls.sql` — 建表迁移
- `backend/app/services/plan_generation_service.py` — 批量生成公共实现（从 generation.py 抽取）
- `backend/tests/test_llm_client_retry.py` — LLM 重试测试
- `backend/tests/test_chat_report_system_prompt.py` — 报告提示词测试
- `backend/tests/test_chat_tool_call_model.py` — 模型测试
- `backend/tests/test_chat_tool_call_logging.py` — agent_loop 打点测试
- `backend/tests/test_chat_tool_calls_endpoint.py` — tool-calls 端点测试
- `backend/tests/test_chat_parallel_tools.py` — 并行调度测试
- `backend/tests/test_chat_save_trace.py` — 消息轨迹保存测试
- `backend/tests/test_chat_context_rebuild.py` — 上下文重建测试
- `backend/tests/test_chat_context_truncate.py` — token 截断测试
- `backend/tests/test_plan_generation_service.py` — service 抽取回归测试
- `backend/tests/test_chat_generate_plan.py` — 聊天触发生成 + 进度测试

**修改：**
- `backend/app/models/__init__.py` — 导出 ChatToolCall
- `backend/app/services/llm_client.py` — 重试逻辑
- `backend/app/routers/chat.py` — 打点/并行/记忆/报告提示词/轮数/新端点与新工具
- `backend/app/routers/generation.py` — 改调 plan_generation_service（行为不变）
- `backend/app/services/chat_dispatch.py` — _generate_plan_content 重写 + get_generation_progress
- `backend/app/schemas/chat.py` — MessageResponse 增加 name
- `backend/tests/test_chat_dispatch.py` — 追加工具回归（若 _FUNCTIONS 变化）
- `frontend/src/services/chatService.ts` — tool_step 事件类型、fetchToolCalls、name 字段
- `frontend/src/pages/Chat/index.tsx` — 步骤时间线 + 过滤 tool 消息
- `frontend/src/mobile/screens/ChatScreen.tsx` — 同上（移动端）

**职责边界：** chat.py 只做编排（SSE/agent_loop）；chat_dispatch.py 只做工具实现；plan_generation_service.py 只做生成公共逻辑；前端聊天页只做展示与交互，不持有上下文截断逻辑。

---

### 任务 1：LLM 调用指数退避重试

**文件：**
- 修改：`backend/app/services/llm_client.py`
- 测试：`backend/tests/test_llm_client_retry.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_llm_client_retry.py — LLM 重试行为。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_client import llm_chat_completion, LLMError


def _cfg():
    c = MagicMock(provider="deepseek", model_name="deepseek-chat", base_url=None,
                  temperature=0.7, max_tokens=4096, top_p=1.0)
    return c


def _resp(status_code, text="", json_data=None):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    r.json.return_value = json_data or {"choices": [{"message": {"content": "ok"}}]}
    return r


@pytest.mark.asyncio
async def test_retry_429_then_success():
    calls = []

    async def fake_post(url, **kwargs):
        calls.append(url)
        return _resp(429, "rate limited") if len(calls) == 1 else _resp(200)

    client = AsyncMock()
    client.post.side_effect = fake_post
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"), \
         patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
        out = await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg())
    assert len(calls) == 2
    assert out["choices"][0]["message"]["content"] == "ok"


@pytest.mark.asyncio
async def test_retry_5xx_exhausted():
    client = AsyncMock()
    client.post.side_effect = lambda url, **kw: _resp(500, "boom")
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"), \
         patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(LLMError) as ei:
            await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg())
    assert ei.value.status_code == 500


@pytest.mark.asyncio
async def test_no_retry_on_401():
    client = AsyncMock()
    client.post.side_effect = lambda url, **kw: _resp(401, "bad key")
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"):
        with pytest.raises(LLMError) as ei:
            await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg())
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_retry_network_error():
    import httpx
    calls = []

    async def fake_post(url, **kw):
        calls.append(url)
        if len(calls) == 1:
            raise httpx.ConnectError("conn refused")
        return _resp(200)

    client = AsyncMock()
    client.post.side_effect = fake_post
    with patch("app.services.llm_client.httpx.AsyncClient", return_value=client), \
         patch("app.services.llm_client.decrypt_api_key", return_value="sk-test"), \
         patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
        out = await llm_chat_completion([{"role": "user", "content": "hi"}], _cfg())
    assert len(calls) == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_llm_client_retry.py -q`
预期：FAIL（现实现无重试，429 直接抛 LLMError）

- [ ] **步骤 3：编写最少实现代码**

在 `backend/app/services/llm_client.py` 顶部常量区追加：

```python
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_MAX_RETRIES = 3
```

新增模块级私有函数：

```python
async def _post_with_retry(base: str, payload: dict, headers: dict, timeout: int,
                           max_retries: int = DEFAULT_MAX_RETRIES):
    """POST chat/completions，对 429/5xx/网络错误指数退避重试；401/400 不重试。"""
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in RETRYABLE_STATUS and attempt < max_retries:
                await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                continue
            raise LLMError(resp.status_code, resp.text)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            if attempt < max_retries:
                await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                continue
            raise LLMError(0, str(e))
    raise LLMError(0, "LLM retry exhausted")
```

顶部补 `import asyncio, random`（如缺失）。`llm_chat_completion` 非流式路径替换为：

```python
    # 非流式路径
    headers = {"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"}
    return await _post_with_retry(base, payload, headers, timeout,
                                  max_retries=payload_overrides.get("max_retries", DEFAULT_MAX_RETRIES) if payload_overrides else DEFAULT_MAX_RETRIES)
```

`_stream_response` 加同款重试（建连/首响应前）：

```python
async def _stream_response(base, payload, ai_config, timeout=120, max_retries=DEFAULT_MAX_RETRIES):
    headers = {"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"}
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
                                return
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                pass
                    return
        except (httpx.TransportError, httpx.TimeoutException) as e:
            if attempt < max_retries:
                await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                continue
            raise LLMError(0, str(e))
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_llm_client_retry.py -q`
预期：4 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/llm_client.py backend/tests/test_llm_client_retry.py
git commit -m "feat(llm): 增加指数退避重试（429/5xx/网络错误，401 不重试）"
```

---

### 任务 2：报告生成传 system_prompt（修复 E4）

**文件：**
- 修改：`backend/app/routers/chat.py`
- 测试：`backend/tests/test_chat_report_system_prompt.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_report_system_prompt.py — report_prompt 分支必须把 system_prompt 传给 LLM。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.routers.chat import _generate_report_text


@pytest.mark.asyncio
async def test_report_text_passes_system_prompt():
    captured = {}

    async def fake_collect(messages, ai_config):
        captured["messages"] = messages
        return "# 报告"

    with patch("app.routers.chat._collect_llm", new=fake_collect):
        out = await _generate_report_text(
            system_prompt="你是一位专业分析师", prompt="请生成报告",
            ai_config=AsyncMock(),
        )
    assert out == "# 报告"
    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][0]["content"] == "你是一位专业分析师"
    assert captured["messages"][1]["role"] == "user"


@pytest.mark.asyncio
async def test_report_text_without_system_prompt():
    captured = {}

    async def fake_collect(messages, ai_config):
        captured["messages"] = messages
        return "ok"

    with patch("app.routers.chat._collect_llm", new=fake_collect):
        await _generate_report_text(system_prompt="", prompt="hi", ai_config=AsyncMock())
    assert captured["messages"][0]["role"] == "user"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_report_system_prompt.py -q`
预期：FAIL（`_generate_report_text` 不存在）

- [ ] **步骤 3：编写最少实现代码**

在 `backend/app/routers/chat.py` 新增：

```python
async def _generate_report_text(system_prompt: str, prompt: str, ai_config):
    """生成报告：system_prompt 非空时作为 system 消息传入。"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return await _collect_llm(messages, ai_config)
```

agent_loop 的 report_prompt 分支改为：

```python
                if result_obj.get("type") == "report_prompt":
                    yield sse_line({"type": "progress", "message": result_obj.get("message", "正在生成报告...")})
                    try:
                        full_text = await _generate_report_text(
                            result_obj.get("system_prompt", ""), result_obj["prompt"], ai_config)
                        html = await _md_to_html(full_text)
                        final_text = full_text
                        yield sse_line({"type": "chunk", "content": html, "html": True})
                    except Exception as e:
                        final_text = str(e)
                        yield sse_line({"type": "error", "message": str(e)})
                    yield sse_line({"type": "conv_id", "content": conv_id})
                    yield sse_line({"type": "done"})
                    asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text))
                    return
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_report_system_prompt.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_chat_report_system_prompt.py
git commit -m "fix(chat): 报告生成传入 system_prompt，修复角色提示词丢失"
```

---

### 任务 3：chat_tool_calls 模型与迁移（D1）

**文件：**
- 创建：`backend/app/models/chat_tool_call.py`
- 创建：`backend/db_migration_20260831_agent_chat_tool_calls.sql`
- 修改：`backend/app/models/__init__.py`
- 测试：`backend/tests/test_chat_tool_call_model.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_tool_call_model.py — ChatToolCall 模型映射。"""
from app.models.chat_tool_call import ChatToolCall


def test_model_table_and_columns():
    assert ChatToolCall.__tablename__ == "chat_tool_calls"
    for col in ("id", "conversation_id", "round_no", "fn_name", "fn_args",
                "result", "status", "duration_ms", "created_at"):
        assert col in ChatToolCall.__table__.columns


def test_exported_from_models_package():
    from app.models import ChatToolCall as Exported
    assert Exported is ChatToolCall
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_tool_call_model.py -q`
预期：FAIL（ImportError: cannot import name 'ChatToolCall'）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/models/chat_tool_call.py`：

```python
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ChatToolCall(Base):
    __tablename__ = "chat_tool_calls"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    fn_name: Mapped[str] = mapped_column(String(100), nullable=False)
    fn_args: Mapped[dict] = mapped_column("fn_args", __import__("sqlalchemy").JSON, nullable=True)
    result: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`backend/db_migration_20260831_agent_chat_tool_calls.sql`：

```sql
CREATE TABLE IF NOT EXISTS chat_tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    round_no INTEGER NOT NULL,
    fn_name VARCHAR(100) NOT NULL,
    fn_args JSONB,
    result TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_chat_tool_calls_conv ON chat_tool_calls(conversation_id, created_at);
```

`backend/app/models/__init__.py` 追加导出：

```python
from app.models.chat_tool_call import ChatToolCall
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_tool_call_model.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/models/chat_tool_call.py backend/app/models/__init__.py \
        backend/db_migration_20260831_agent_chat_tool_calls.sql \
        backend/tests/test_chat_tool_call_model.py
git commit -m "feat(chat): 新增 chat_tool_calls 表（工具执行轨迹记录）"
```

---

### 任务 4：agent_loop 写入工具执行记录（修复 E1 后端）

**文件：**
- 修改：`backend/app/routers/chat.py`
- 测试：`backend/tests/test_chat_tool_call_logging.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_tool_call_logging.py — 工具执行记录写入。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chat import _record_tool_call


@pytest.mark.asyncio
async def test_record_tool_call_success():
    db = AsyncMock()
    await _record_tool_call(db, "c1", 1, "list_enterprises", {"keyword": "a"},
                            '{"enterprises":[]}', "success", 120)
    db.add.assert_awaited_once()
    db.commit.assert_awaited_once()
    rec = db.add.call_args.args[0]
    assert rec.conversation_id == "c1"
    assert rec.round_no == 1
    assert rec.fn_name == "list_enterprises"
    assert rec.status == "success"
    assert rec.duration_ms == 120


@pytest.mark.asyncio
async def test_record_tool_call_error_status():
    db = AsyncMock()
    await _record_tool_call(db, "c1", 2, "delete_plan", {"plan_id": "p1"},
                            '{"error":"预案不存在"}', "error", 50)
    rec = db.add.call_args.args[0]
    assert rec.status == "error"
    assert rec.result.startswith('{"error"')
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_tool_call_logging.py -q`
预期：FAIL（`_record_tool_call` 不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/routers/chat.py` 新增 helper：

```python
async def _record_tool_call(db, conv_id: str, round_no: int, fn_name: str, fn_args: dict,
                            result: str, status: str, duration_ms: int) -> None:
    """写入一条工具执行记录（进度持久化用）。"""
    from app.models.chat_tool_call import ChatToolCall
    db.add(ChatToolCall(
        conversation_id=conv_id, round_no=round_no, fn_name=fn_name,
        fn_args=fn_args or {}, result=(result or "")[:4000],
        status=status, duration_ms=duration_ms,
    ))
    await db.commit()
```

agent_loop 工具执行处改为：

```python
            for tc in pending_tool_calls:
                func = tc.get("function", {})
                fn_name = func.get("name", "")
                tc_id = tc.get("id", "")
                try:
                    fn_args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    fn_args = {}
                yield sse_line({"type": "progress", "message": f"[第{round_num}轮] 正在执行: {fn_name}..."})
                t0 = time.monotonic()
                result_str = await dispatch(db, current_user, fn_name, fn_args)
                duration_ms = int((time.monotonic() - t0) * 1000)
                result_obj = json.loads(result_str)
                is_err = isinstance(result_obj, dict) and "error" in result_obj
                try:
                    await _record_tool_call(db, conv_id, round_num, fn_name, fn_args,
                                            result_str, "error" if is_err else "success", duration_ms)
                except Exception:
                    logger.exception("记录工具调用失败（不影响主流程）")
                yield sse_line({"type": "tool_step", "name": fn_name, "status": "error" if is_err else "success",
                                "duration_ms": duration_ms})
                ...
```

顶部补 `import time`（如缺失）；`logger` 已在模块内定义。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_tool_call_logging.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_chat_tool_call_logging.py
git commit -m "feat(chat): agent_loop 记录工具执行轨迹并输出 tool_step 事件"
```

---

### 任务 5：GET /chat/conversations/{id}/tool-calls 端点

**文件：**
- 修改：`backend/app/routers/chat.py`
- 测试：`backend/tests/test_chat_tool_calls_endpoint.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_tool_calls_endpoint.py — 工具轨迹回放端点。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.routers.chat import list_tool_calls


@pytest.mark.asyncio
async def test_list_tool_calls_requires_own_conv():
    db = AsyncMock()
    result = AsyncMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    with pytest.raises(Exception):
        await list_tool_calls("c1", MagicMock(id="u1"), db)


@pytest.mark.asyncio
async def test_list_tool_calls_returns_rows():
    db = AsyncMock()
    conv = MagicMock(id="c1", user_id="u1")
    row = MagicMock(id="t1", round_no=1, fn_name="list_enterprises",
                    status="success", duration_ms=120, created_at=None)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.side_effect = [conv, None]
    exec_result.scalars.return_value.all.return_value = [row]
    db.execute.return_value = exec_result
    out = await list_tool_calls("c1", MagicMock(id="u1"), db)
    assert out[0]["fn_name"] == "list_enterprises"
    assert out[0]["status"] == "success"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_tool_calls_endpoint.py -q`
预期：FAIL（`list_tool_calls` 不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/routers/chat.py` 追加：

```python
@router.get("/conversations/{conv_id}/tool-calls")
async def list_tool_calls(conv_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    from app.models.chat_tool_call import ChatToolCall
    conv = (await db.execute(
        select(ChatConversation).where(ChatConversation.id == conv_id)
    )).scalar_one_or_none()
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "对话不存在")
    rows = (await db.execute(
        select(ChatToolCall)
        .where(ChatToolCall.conversation_id == conv_id)
        .order_by(ChatToolCall.created_at, ChatToolCall.id)
    )).scalars().all()
    return [{
        "id": r.id, "round_no": r.round_no, "fn_name": r.fn_name,
        "status": r.status, "duration_ms": r.duration_ms, "created_at": r.created_at,
    } for r in rows]
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_tool_calls_endpoint.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_chat_tool_calls_endpoint.py
git commit -m "feat(chat): 新增 tool-calls 回放端点"
```

---

### 任务 6：前端步骤时间线（修复 E1 前端，桌面 + 移动端）

**文件：**
- 修改：`frontend/src/services/chatService.ts`
- 修改：`frontend/src/pages/Chat/index.tsx`
- 修改：`frontend/src/mobile/screens/ChatScreen.tsx`

- [ ] **步骤 1：扩展 chatService.ts 类型与 API**

```ts
export interface ToolCallStep {
  id: string;
  round_no: number;
  fn_name: string;
  status: "running" | "success" | "error";
  duration_ms: number | null;
  created_at: string;
}

export interface ChatSSEEvent {
  type: "progress" | "chunk" | "function_result" | "tool_step" | "error" | "done" | "conv_id";
  message?: string;
  content?: string;
  html?: boolean;
  name?: string;
  result?: string;
  status?: "success" | "error";
  duration_ms?: number;
}

export interface MessageResponse {
  id: string;
  role: string;
  content: string;
  name?: string | null;   // 新增：tool 消息携带工具名
  created_at: string;
}

export async function fetchToolCalls(convId: string): Promise<ToolCallStep[]> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${getApiBaseUrl()}/chat/conversations/${convId}/tool-calls`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error("获取工具步骤失败");
  return res.json();
}
```

- [ ] **步骤 2：桌面 Chat/index.tsx 渲染步骤条**

在 `handleSend` 的 SSE 回调中，`tool_step` 单独收集（不再拼入 contentBuf）：

```tsx
const [toolSteps, setToolSteps] = useState<ToolCallStep[]>([]);

case "tool_step":
  setToolSteps((prev) => [
    ...prev,
    { id: `${Date.now()}-${event.name}`, round_no: 1, fn_name: event.name || "",
      status: event.status === "error" ? "error" : "success",
      duration_ms: event.duration_ms ?? null, created_at: new Date().toISOString() },
  ]);
  break;
```

消息气泡上方渲染步骤胶囊（assistant 回复内容前）：

```tsx
{msg.role === "assistant" && toolSteps.length > 0 && (
  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
    {toolSteps.map((s) => (
      <span key={s.id} style={{ fontSize: 11, padding: "1px 8px", borderRadius: 10,
        background: s.status === "error" ? "#fff2f0" : "#f6ffed",
        color: s.status === "error" ? "#cf1322" : "#389e0d" }}>
        {s.status === "error" ? "✗" : "✓"} {s.fn_name} {s.duration_ms != null ? `${s.duration_ms}ms` : ""}
      </span>
    ))}
  </div>
)}
```

`switchConversation` 中加载步骤回放：

```tsx
const steps = await fetchToolCalls(convId).catch(() => []);
setToolSteps(steps.map((s) => ({ ...s })));
```

消息渲染时过滤 role 为 `tool` 与空内容 assistant 占位消息（历史加载 `msgs.filter((m) => m.role !== "tool" && !(m.role === "assistant" && !m.content))`）。

- [ ] **步骤 3：移动端 ChatScreen.tsx 同步**

同样逻辑：`progress`/`tool_step` 不再拼入 `buf`（`buf += event.content || event.message || ""` 处移除 progress 分支，仅 chunk 累加）；增加 `toolSteps` state 与步骤胶囊渲染；进入页面加载历史后 `fetchToolCalls(convId)` 回放。

- [ ] **步骤 4：类型检查**

运行：`cd frontend && npx tsc -b`
预期：exit 0

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/services/chatService.ts frontend/src/pages/Chat/index.tsx frontend/src/mobile/screens/ChatScreen.tsx
git commit -m "feat(chat): 前端步骤时间线（进度不再混入消息文本，支持刷新回放）"
```

---

### 任务 7：工具并行执行（读并行 / 写串行，修复 E2）

**文件：**
- 修改：`backend/app/routers/chat.py`
- 测试：`backend/tests/test_chat_parallel_tools.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_parallel_tools.py — 读工具并行、写工具串行。"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chat import _execute_pending_tools, READ_TOOL_NAMES


def _tc(fn_name, tc_id="t1"):
    return {"id": tc_id, "function": {"name": fn_name, "arguments": "{}"}}


@pytest.mark.asyncio
async def test_read_tools_run_in_parallel():
    events = []

    async def fake_isolated(fn_name, fn_args, user_id):
        events.append(("start", fn_name))
        await asyncio.sleep(0.05)
        events.append(("end", fn_name))
        return '{"ok": true}'

    db = AsyncMock()
    with patch("app.routers.chat._run_tool_isolated", new=fake_isolated):
        out = await _execute_pending_tools(
            [_tc("list_enterprises", "t1"), _tc("get_dashboard", "t2")],
            db, MagicMock(id="u1"), 1, "c1")
    starts = [e for e in events if e[0] == "start"]
    ends = [e for e in events if e[0] == "end"]
    assert len(starts) == 2 and len(ends) == 2
    # 并行：第二个 start 出现在第一个 end 之前
    assert events.index(("start", "get_dashboard")) < events.index(("end", "list_enterprises"))
    assert len(out) == 2
    assert out[0][0]["id"] == "t1"               # 结果按原始顺序
    assert out[1][0]["id"] == "t2"


@pytest.mark.asyncio
async def test_write_tools_run_serial():
    calls = []

    async def fake_dispatch(db, user, fn_name, fn_args):
        calls.append(("start", fn_name))
        await asyncio.sleep(0.03)
        calls.append(("end", fn_name))
        return '{"ok": true}'

    db = AsyncMock()
    with patch("app.routers.chat.dispatch", new=fake_dispatch):
        await _execute_pending_tools(
            [_tc("create_enterprise", "t1"), _tc("update_enterprise", "t2")],
            db, MagicMock(id="u1"), 1, "c1")
    assert calls[0] == ("start", "create_enterprise")
    assert calls[1] == ("end", "create_enterprise")
    assert calls[2] == ("start", "update_enterprise")
    assert calls[3] == ("end", "update_enterprise")


def test_read_tool_names_include_reads_only():
    assert "list_enterprises" in READ_TOOL_NAMES
    assert "get_dashboard" in READ_TOOL_NAMES
    assert "create_enterprise" not in READ_TOOL_NAMES
    assert "delete_plan" not in READ_TOOL_NAMES
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_parallel_tools.py -q`
预期：FAIL（`_execute_pending_tools` / `READ_TOOL_NAMES` 不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/routers/chat.py` 新增：

```python
READ_TOOL_NAMES = frozenset({
    "get_dashboard", "list_enterprises", "get_enterprise", "list_risk_sources",
    "list_resources", "list_plans", "get_plan", "list_templates",
    "list_risk_assessments", "get_risk_assessment", "list_resource_investigations",
    "get_resource_investigation", "get_regulation_stats", "list_regulations",
    "search_regulations", "search_regulation_articles", "get_ai_config",
    "get_generation_progress",
})


async def _run_tool_isolated(fn_name: str, fn_args: dict, user_id: str) -> str:
    """独立 session 执行只读工具（AsyncSession 不支持并发共享）。"""
    from app.models.user import User
    async with async_session() as sdb:
        user = await sdb.get(User, user_id)
        return await dispatch(sdb, user, fn_name, fn_args)


async def _execute_pending_tools(pending_tool_calls, db, current_user, round_num, conv_id):
    """读工具并行（独立 session），写工具串行（共享请求 db）。返回按原顺序的 [(tc, result_str)]。"""
    reads, writes = [], []
    for tc in pending_tool_calls:
        fn_name = tc.get("function", {}).get("name", "")
        (reads if fn_name in READ_TOOL_NAMES else writes).append(tc)

    results: list = []
    if reads:
        outs = await asyncio.gather(*[
            _run_tool_isolated(tc["function"]["name"], _safe_tool_args(tc), current_user.id)
            for tc in reads
        ])
        results.extend(zip(reads, outs))
    for tc in writes:
        fn_name = tc["function"]["name"]
        result_str = await dispatch(db, current_user, fn_name, _safe_tool_args(tc))
        results.append((tc, result_str))

    by_id = {tc["id"]: (tc, out) for tc, out in results}
    return [by_id[tc["id"]] for tc in pending_tool_calls]


def _safe_tool_args(tc) -> dict:
    try:
        return json.loads(tc.get("function", {}).get("arguments", "{}"))
    except json.JSONDecodeError:
        return {}
```

agent_loop 工具执行块改为调用 `_execute_pending_tools`（保留打点与 SSE 事件逻辑）：

```python
            tool_results = await _execute_pending_tools(
                pending_tool_calls, db, current_user, round_num, conv_id)
            results = []
            for tc, result_str in tool_results:
                fn_name = tc.get("function", {}).get("name", "")
                tc_id = tc.get("id", "")
                result_obj = json.loads(result_str)
                is_err = isinstance(result_obj, dict) and "error" in result_obj
                yield sse_line({"type": "tool_step", "name": fn_name,
                                "status": "error" if is_err else "success",
                                "duration_ms": 0})
                yield sse_line({"type": "function_result", "name": fn_name, "result": result_str})
                results.append({"tc_id": tc_id, "name": fn_name, "result": result_str})
```

（打点 `_record_tool_call` 的精确时长在并行路径下以 `_run_tool_isolated` 内部计时为准——实现时可在 `_execute_pending_tools` 内对每条工具计时并随结果返回；若简化，`duration_ms` 先记 0，验收允许，后续按需细化。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_parallel_tools.py -q`
预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_chat_parallel_tools.py
git commit -m "feat(chat): 读工具并行（独立 session）/写工具串行"
```

---

### 任务 8：消息持久化扩展（保存工具轨迹，修复 E5 数据层）

**文件：**
- 修改：`backend/app/routers/chat.py`
- 修改：`backend/app/models/chat.py`（ChatMessage 增加 name 列）
- 修改：`backend/db_migration_20260831_agent_chat_tool_calls.sql`（追加 ALTER）
- 测试：`backend/tests/test_chat_save_trace.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_save_trace.py — 保存完整对话轮次（含工具轨迹）。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.routers.chat import _save_messages


@pytest.mark.asyncio
async def test_save_messages_with_tool_trace():
    db = AsyncMock()
    db.get.return_value = AsyncMock(title="新对话")
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    with patch("app.routers.chat.async_session", return_value=ctx):
        await _save_messages(
            "u1", "c1", "列出企业",
            "共 3 家企业",
            tool_trace=[{"round_no": 1, "fn_name": "list_enterprises",
                         "result": '{"enterprises":[]}'}],
        )
    added = [c.args[0] for c in db.add.call_args_list]
    roles = [getattr(m, "role", None) for m in added]
    assert roles == ["user", "assistant", "assistant", "tool"]
    assert getattr(added[2], "content") == ""
    assert getattr(added[3], "name") == "list_enterprises"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_messages_without_trace_keeps_legacy_shape():
    db = AsyncMock()
    db.get.return_value = AsyncMock(title="新对话")
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    with patch("app.routers.chat.async_session", return_value=ctx):
        await _save_messages("u1", "c1", "hi", "hello", tool_trace=None)
    added = [c.args[0] for c in db.add.call_args_list]
    assert [getattr(m, "role") for m in added] == ["user", "assistant"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_save_trace.py -q`
预期：FAIL（`_save_messages` 不接收 tool_trace 参数）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/routers/chat.py` 的 `_save_messages` 重写：

```python
async def _save_messages(user_id: str, conv_id: str, user_msg: str, assistant_msg: str,
                         tool_trace: list | None = None):
    """保存一轮对话消息到 DB（使用独立 session）。

    tool_trace: [{"round_no", "fn_name", "result"}]，按轮保存 assistant 占位 + tool 消息。
    """
    async with async_session() as db:
        conv = await db.get(ChatConversation, conv_id)
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            if conv.title == "新对话":
                conv.title = user_msg[:30] + ("..." if len(user_msg) > 30 else "")
        db.add(ChatMessage(conversation_id=conv_id, role="user", content=user_msg))
        db.add(ChatMessage(conversation_id=conv_id, role="assistant", content=assistant_msg))
        if tool_trace:
            db.add(ChatMessage(conversation_id=conv_id, role="assistant", content=""))
            for item in tool_trace:
                db.add(ChatMessage(
                    conversation_id=conv_id, role="tool",
                    name=item.get("fn_name", ""),
                    content=(item.get("result") or "")[:4000],
                ))
        await db.commit()
```

`backend/app/models/chat.py` 的 `ChatMessage` 补 name 列：

```python
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

迁移 SQL 追加：

```sql
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS name VARCHAR(100);
```

agent_loop 各返回点把 `tool_trace` 传给 `_save_messages`（收集方式：在工具执行处累积 `trace.append({"round_no": round_num, "fn_name": fn_name, "result": result_str})`，最终文本返回点传入）。若执行路径不传，默认 None 保持旧行为。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_save_trace.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/app/models/chat.py \
        backend/db_migration_20260831_agent_chat_tool_calls.sql \
        backend/tests/test_chat_save_trace.py
git commit -m "feat(chat): 消息表保存工具轨迹（role=tool + name），迁移补 name 列"
```

---

### 任务 9：上下文重建（后端加载 + tool_calls 还原，修复 E5）

**文件：**
- 修改：`backend/app/routers/chat.py`
- 测试：`backend/tests/test_chat_context_rebuild.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_context_rebuild.py — 从 DB 历史重建 OpenAI 消息（含工具调用）。"""
import pytest
from unittest.mock import MagicMock

from app.routers.chat import _rebuild_messages_from_rows


def _row(role, content, name=None):
    return MagicMock(role=role, content=content, name=name)


def test_rebuild_plain_text():
    rows = [_row("user", "你好"), _row("assistant", "你好！")]
    msgs = _rebuild_messages_from_rows(rows, "再见")
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"] == "再见"


def test_rebuild_with_tool_trace():
    rows = [
        _row("user", "列出企业"),
        _row("assistant", "共 3 家"),
        _row("assistant", ""),
        _row("tool", '{"enterprises":[]}', name="list_enterprises"),
        _row("user", "第一个企业"),
    ]
    msgs = _rebuild_messages_from_rows(rows, "继续")
    tool_assistant = [m for m in msgs if m.get("role") == "assistant" and "tool_calls" in m]
    assert len(tool_assistant) == 1
    assert tool_assistant[0]["tool_calls"][0]["function"]["name"] == "list_enterprises"
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    assert tool_msgs[0]["tool_call_id"].startswith("call_")
    assert tool_msgs[0]["content"] == '{"enterprises":[]}'


def test_rebuild_empty_assistant_without_tool_skipped():
    rows = [_row("assistant", ""), _row("user", "x")]
    msgs = _rebuild_messages_from_rows(rows, "y")
    assert [m["role"] for m in msgs if m["role"] != "system"] == ["user", "user"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_context_rebuild.py -q`
预期：FAIL（`_rebuild_messages_from_rows` 不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/routers/chat.py` 新增：

```python
async def _load_history_rows(db, conv_id: str):
    from app.models.chat import ChatMessage
    rows = (await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv_id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )).scalars().all()
    return rows


def _rebuild_messages_from_rows(rows, user_message: str) -> list:
    """DB 历史 → OpenAI messages。assistant(content="") + 连续 tool 行还原为 tool_calls。"""
    msgs = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    i, n = 0, len(rows)
    while i < n:
        r = rows[i]
        if r.role == "assistant" and not (r.content or ""):
            tool_rows = []
            j = i + 1
            while j < n and rows[j].role == "tool":
                tool_rows.append(rows[j])
                j += 1
            if tool_rows:
                calls = []
                for idx, tr in enumerate(tool_rows):
                    calls.append({
                        "id": f"call_{idx}",
                        "type": "function",
                        "function": {"name": tr.name or "", "arguments": "{}"},
                    })
                msgs.append({"role": "assistant", "content": None, "tool_calls": calls})
                for idx, tr in enumerate(tool_rows):
                    msgs.append({"role": "tool", "tool_call_id": f"call_{idx}",
                                 "content": tr.content or ""})
                i = j
                continue
        role = r.role if r.role != "function" else "tool"
        msgs.append({"role": role, "content": r.content or ""})
        i += 1
    msgs.append({"role": "user", "content": user_message})
    return msgs
```

chat 端点改为：

```python
    rows = await _load_history_rows(db, conv_id)
    messages = truncate_by_token_budget(_rebuild_messages_from_rows(rows, body.message))
```

（`_build_tool_messages` 废弃或保留兼容——删除其调用点并移除旧函数。`ChatRequest.history` 不再使用，前端可继续传以兼容。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_context_rebuild.py -q`
预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_chat_context_rebuild.py
git commit -m "feat(chat): 上下文从 DB 历史重建（含 tool_calls 还原），后端掌控记忆"
```

---

### 任务 10：token 预算截断

**文件：**
- 修改：`backend/app/routers/chat.py`
- 测试：`backend/tests/test_chat_context_truncate.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_context_truncate.py — 上下文 token 预算截断。"""
from app.routers.chat import truncate_by_token_budget, _estimate_tokens


def test_estimate_tokens_simple():
    assert _estimate_tokens([{"role": "user", "content": "安全生产"}]) > 0


def test_small_context_untouched():
    msgs = [{"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"}]
    out = truncate_by_token_budget(msgs, budget=10000)
    assert len(out) == 3


def test_large_context_truncated_keeps_recent_and_summary():
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(30):
        msgs.append({"role": "user", "content": f"问题{i}：这是一段比较长的用户消息内容用于撑大上下文。"})
        msgs.append({"role": "assistant", "content": f"回答{i}：对应的一段较长回答内容。"})
    out = truncate_by_token_budget(msgs, budget=800)
    assert any(m.get("content", "").startswith("【历史摘要】") for m in out)
    assert out[-1]["content"].startswith("问题29")      # 最近轮保留
    assert _estimate_tokens(out) <= 800 * 1.2           # 近似预算（±20% 容差）
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_context_truncate.py -q`
预期：FAIL（`truncate_by_token_budget` 不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/routers/chat.py` 新增：

```python
CHAT_CONTEXT_BUDGET = 8000


def _estimate_tokens(messages: list) -> int:
    total = 0
    for m in messages:
        text = m.get("content") or ""
        total += len(text) // 2 + 4
    return total


def truncate_by_token_budget(messages: list, budget: int = CHAT_CONTEXT_BUDGET) -> list:
    """超预算时：保留系统提示 + 最近 30% 轮次，中间轮压缩为一条历史摘要。"""
    if _estimate_tokens(messages) <= budget:
        return messages
    system = messages[0] if messages and messages[0]["role"] == "system" else None
    rest = messages[1:] if system else messages
    keep_last = rest[-max(1, int(len(rest) * 0.3)):]
    middle = rest[:-max(1, int(len(rest) * 0.3))]
    parts = []
    for m in middle:
        text = (m.get("content") or "").strip()
        if text:
            parts.append(text[:300])
    summary = {"role": "system", "content": "【历史摘要】" + "；".join(parts[-10:])}
    result = ([system] if system else []) + [summary] + keep_last
    return result
```

（调用点已在任务 9 的 chat 端点改动中包含。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_context_truncate.py -q`
预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_chat_context_truncate.py
git commit -m "feat(chat): 上下文按 token 预算截断（保留最近轮 + 历史摘要）"
```

---

### 任务 11：MessageResponse 增加 name + 前端过滤 tool 消息

**文件：**
- 修改：`backend/app/schemas/chat.py`
- 修改：`frontend/src/services/chatService.ts`
- 修改：`frontend/src/pages/Chat/index.tsx`、`frontend/src/mobile/screens/ChatScreen.tsx`

- [ ] **步骤 1：后端 schema 增加 name**

`backend/app/schemas/chat.py`：

```python
class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    name: str | None = None
    created_at: datetime
```

- [ ] **步骤 2：后端测试**

```python
"""追加到 test_chat_save_trace.py"""
from app.schemas.chat import MessageResponse


def test_message_response_has_name():
    m = MessageResponse(id="1", role="tool", content="x", name="list_enterprises",
                        created_at="2026-08-31T00:00:00")
    assert m.name == "list_enterprises"
```

运行：`cd backend && pytest tests/test_chat_save_trace.py -q`，预期：3 passed

- [ ] **步骤 3：前端过滤 + 类型**

`chatService.ts` 的 `MessageResponse` 增加 `name?: string | null`（任务 6 已加）。桌面与移动端加载历史时过滤：

```tsx
const display = msgs
  .filter((m) => m.role !== "tool" && !(m.role === "assistant" && !m.content))
  .map((m) => ({ role: m.role as DisplayMessage["role"], content: m.content }));
```

`switchConversation`（桌面）与进入页面加载（移动端）统一使用该过滤。

- [ ] **步骤 4：类型检查**

运行：`cd frontend && npx tsc -b`，预期：exit 0

- [ ] **步骤 5：Commit**

```bash
git add backend/app/schemas/chat.py frontend/src/services/chatService.ts \
        frontend/src/pages/Chat/index.tsx frontend/src/mobile/screens/ChatScreen.tsx \
        backend/tests/test_chat_save_trace.py
git commit -m "feat(chat): MessageResponse 增加 name，前端过滤工具轨迹消息"
```

---

### 任务 12：抽取 plan_generation_service（重构，修复 E6 前置）

**文件：**
- 创建：`backend/app/services/plan_generation_service.py`
- 测试：`backend/tests/test_plan_generation_service.py`（新建）

- [ ] **步骤 1：编写冒烟测试**

```python
"""test_plan_generation_service.py — service 抽取后仍可用。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.plan_generation_service import collect_batch_context, start_batch_generation


@pytest.mark.asyncio
async def test_collect_batch_context_returns_tuple():
    db = AsyncMock()
    p = MagicMock(enterprise_id="e1", plan_type="comprehensive", accident_type=None,
                  style_preference=None, advanced_prompt_overrides=None)
    cfg = MagicMock()
    ent_data = {"name": "企业A"}
    with patch("app.services.plan_generation_service.get_system_ai_config",
               new=AsyncMock(return_value=cfg)), \
         patch("app.services.plan_generation_service.build_risk_management_context",
               new=AsyncMock(return_value={})), \
         patch("app.services.plan_generation_service._collect_enterprise_data",
               return_value=ent_data), \
         patch("app.services.plan_generation_service._enrich_with_reports",
               new=AsyncMock(return_value=ent_data)), \
         patch("app.services.plan_generation_service._load_org_members",
               new=AsyncMock(return_value=[])):
        result = await collect_batch_context("p1", db, keys=None)
    assert result[0] is p
    assert result[1] is cfg
    assert result[2] == ent_data


@pytest.mark.asyncio
async def test_start_batch_generation_no_empty_sections():
    db = AsyncMock()
    p = MagicMock(enterprise_id="e1", plan_type="comprehensive", status="draft",
                  sections=[MagicMock(section_key="sec_1", content="<p>有内容</p>")])
    with patch("app.services.plan_generation_service.collect_batch_context",
               new=AsyncMock(return_value=(p, MagicMock(), {}, []))):
        out = await start_batch_generation("p1", db, MagicMock(id="u1"), keys=None)
    assert out["started"] is False
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_plan_generation_service.py -q`
预期：FAIL（ImportError: cannot import name 'plan_generation_service'）

- [ ] **步骤 3：实现 service（迁移现有函数，行为不变）**

`backend/app/services/plan_generation_service.py`：

```python
"""预案批量生成公共实现：从 generation.py 抽取，路由与聊天助手共用。"""
import asyncio
import logging
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.enterprise import PlanProject, PlanSection, Enterprise, EmergencyResource, HazardousChemical
from app.services.ai_config_service import get_system_ai_config
from app.services.risk_context_builder import build_risk_management_context

logger = logging.getLogger(__name__)

_background_tasks: dict[str, asyncio.Task] = {}


async def collect_batch_context(plan_id, db, keys=None):
    """批量生成公共准备。keys=None 表示全部章节；否则仅 keys 中章节。"""
    from app.routers.generation import (
        _collect_enterprise_data, _enrich_with_reports, _load_org_members,
    )
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    resources = (await db.execute(
        select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id)
    )).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    chemicals_rows = (await db.execute(
        select(HazardousChemical).where(HazardousChemical.enterprise_id == p.enterprise_id)
    )).scalars().all()
    chemicals = {c.id: c for c in chemicals_rows}
    org_members = await _load_org_members(db, p.enterprise_id) if ent else []
    ent_data = _collect_enterprise_data(ent, risk_context, resources, chemicals,
                                        org_members=org_members) if ent else {}
    if ent:
        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)
    all_sections = (await db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id)
        .order_by(PlanSection.sort_order)
    )).scalars().all()
    target_sections = [s for s in all_sections if (not keys or s.section_key in keys)]
    return p, ai_config, ent_data, target_sections


async def start_batch_generation(plan_id, db, current_user, keys=None, background=True):
    """触发批量生成。background=True 时注册后台任务，立即返回。"""
    p, ai_config, ent_data, target_sections = await collect_batch_context(plan_id, db, keys)
    empty = [s for s in target_sections if not s.content or not s.content.strip()]
    if not empty:
        return {"started": False, "message": f"预案「{p.title}」章节均已填写完成"}
    if p.status == "generating":
        return {"started": False, "message": "预案正在生成中，请稍候", "status": "generating"}
    p.status = "generating"
    await db.commit()
    section_tuples = [(s.section_key, s.title) for s in empty]
    if not background:
        raise NotImplementedError("同步模式由 0.4.1 审查修订依赖实现")
    task = asyncio.create_task(_run_background(
        plan_id, p.plan_type, p.accident_type, p.style_preference,
        p.advanced_prompt_overrides, section_tuples, ai_config, ent_data))
    _background_tasks[plan_id] = task
    return {
        "started": True, "plan_id": plan_id, "total": len(target_sections),
        "empty": len(empty),
        "message": f"已开始后台生成，共 {len(empty)} 个空章节，可随时询问生成进度",
        "verified": True,
    }


async def _run_background(plan_id, plan_type, accident_type, style_preference,
                          advanced_overrides, section_tuples, ai_config, ent_data):
    """后台执行：独立 session 逐章生成 + 收尾。"""
    try:
        async with async_session() as bg_db:
            result = await run_batch_generation(
                bg_db=bg_db, plan_id=plan_id, section_tuples=section_tuples,
                ai_config=ai_config, ent_data=ent_data, plan_type=plan_type,
                accident_type=accident_type, style_preference=style_preference,
                advanced_overrides=advanced_overrides, use_section_number=False,
            )
            await finalize_batch_result(bg_db, plan_id, result["completed"],
                                        result["failed"], result["failed_sections"])
            logger.info("聊天触发批量生成完成 plan=%s %s", plan_id, result)
    except Exception:
        logger.exception("聊天触发批量生成失败 plan=%s", plan_id)
    finally:
        _background_tasks.pop(plan_id, None)
```

`run_batch_generation` 与 `finalize_batch_result` 从 `generation.py:760/840` **原样迁移**到本 service（保持签名与依赖 import：`ensure_loaded`、`_build_section_prompt`、`_collect_previous_context`、`md_to_html`、`_pre_render_mermaid_svgs`、`_attach_diagrams` 等可从 `app.routers.generation` 导入或随迁，以「行为不变」为准，禁止改逻辑）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_plan_generation_service.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_generation_service.py backend/tests/test_plan_generation_service.py
git commit -m "refactor(generation): 抽取 plan_generation_service（collect/start 编排）"
```

---

### 任务 13：generation.py 路由改调 service（行为不变回归）

**文件：**
- 修改：`backend/app/routers/generation.py`
- 测试：既有 `backend/tests/`（全量回归）

- [ ] **步骤 1：修改路由**

`generation.py` 顶部 import 改为：

```python
from app.services.plan_generation_service import (
    collect_batch_context, run_batch_generation, finalize_batch_result,
)
```

删除本文件的 `_collect_batch_context`、`_run_batch_generation`、`_finalize_batch_result` 定义（保留 `_stream_llm_chunks`、`_build_section_prompt` 等仅路由使用的函数）；两处批量端点调用点改为 `await collect_batch_context(plan_id, p, request, db, current_user)` → `await collect_batch_context(plan_id, db, keys=body_keys)`，其中 `body_keys` 从 `request.json()` 的 `section_keys` 解析（保留原语义）。

- [ ] **步骤 2：运行测试验证通过**

运行：`cd backend && pytest tests/ -q`
预期：全量无回归（基线 1157+）

- [ ] **步骤 3：Commit**

```bash
git add backend/app/routers/generation.py
git commit -m "refactor(generation): 批量端点改调 plan_generation_service"
```

---

### 任务 14：聊天内端到端触发生成（修复 E6）

**文件：**
- 修改：`backend/app/services/chat_dispatch.py`
- 测试：`backend/tests/test_chat_generate_plan.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_generate_plan.py — 聊天触发后台生成。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _generate_plan_content, _get_generation_progress


@pytest.mark.asyncio
async def test_generate_plan_content_starts_background():
    db = AsyncMock()
    p = MagicMock(id="p1", title="综合预案", status="draft", user_id="u1",
                  sections=[MagicMock(section_key="sec_1", content="")])
    result = MagicMock()
    result.scalar_one_or_none.return_value = p
    db.execute.return_value = result
    with patch("app.services.chat_dispatch.start_batch_generation",
               new=AsyncMock(return_value={"started": True, "empty": 1, "total": 8,
                                            "message": "已开始后台生成"})):
        out = await _generate_plan_content(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert out["verified"] is True
    assert "后台生成" in out["message"]


@pytest.mark.asyncio
async def test_generate_plan_content_missing_plan():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    out = await _generate_plan_content(db, MagicMock(id="u1"), {"plan_id": "nope"})
    assert "error" in out


@pytest.mark.asyncio
async def test_generation_progress_ownership():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    out = await _get_generation_progress(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert "error" in out


@pytest.mark.asyncio
async def test_generation_progress_completed():
    db = AsyncMock()
    p = MagicMock(id="p1", title="综合预案", status="completed", user_id="u1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = p
    db.execute.return_value = result
    with patch("app.services.chat_dispatch._failed_sections", {"p1": []}):
        out = await _get_generation_progress(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert out["status"] == "completed"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_generate_plan.py -q`
预期：FAIL（旧 `_generate_plan_content` 返回 action_required，新函数不存在）

- [ ] **步骤 3：实现**

`backend/app/services/chat_dispatch.py` 顶部 import：

```python
from app.services.plan_generation_service import start_batch_generation
```

`_generate_plan_content` 重写：

```python
async def _generate_plan_content(db, user, args):
    """聊天触发后台批量生成。"""
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "请提供 plan_id"}
    p = (await db.execute(
        select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id)
    )).scalar_one_or_none()
    if not p:
        return {"error": "预案不存在", "verified": False}
    out = await start_batch_generation(plan_id, db, user, keys=None, background=True)
    out["plan_id"] = plan_id
    out["verified"] = out.get("started", False)
    return out
```

新增 `_get_generation_progress`：

```python
async def _get_generation_progress(db, user, args):
    """查询聊天触发的后台生成进度。"""
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "请提供 plan_id"}
    p = (await db.execute(
        select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id)
    )).scalar_one_or_none()
    if not p:
        return {"error": "预案不存在", "verified": False}
    failed = _failed_sections.get(plan_id, [])
    sections = p.sections or []
    filled = sum(1 for s in sections if s.content and s.content.strip())
    return {
        "plan_id": plan_id, "title": p.title,
        "status": p.status, "filled_sections": filled, "total_sections": len(sections),
        "failed_sections": failed,
        "message": ("生成完成" if p.status == "completed"
                    else "正在生成中" if p.status == "generating"
                    else "未在生成"),
        "verified": True,
    }
```

`_FUNCTIONS` 注册 `"get_generation_progress": _get_generation_progress`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_generate_plan.py -q`
预期：4 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/chat_dispatch.py backend/tests/test_chat_generate_plan.py
git commit -m "feat(chat): 聊天端到端触发生成 + get_generation_progress 工具"
```

---

### 任务 15：CHAT_TOOLS 注册新工具

**文件：**
- 修改：`backend/app/routers/chat.py`

- [ ] **步骤 1：注册工具声明**

`CHAT_TOOLS` 列表追加：

```python
    {"type": "function", "function": {"name": "get_generation_progress",
     "description": "查询预案AI生成进度（聊天内触发的后台生成）。当用户询问生成进度或是否完成时调用",
     "parameters": {"type": "object", "properties": {"plan_id": {"type": "string", "description": "预案ID(必填)"}},
                    "required": ["plan_id"]}}},
```

- [ ] **步骤 2：验证**

运行：`cd backend && pytest tests/test_chat_dispatch.py tests/test_chat_generate_plan.py -q`
预期：全部通过（含既有 29 工具相关回归）

- [ ] **步骤 3：Commit**

```bash
git add backend/app/routers/chat.py
git commit -m "feat(chat): 工具集注册 get_generation_progress"
```

---

### 任务 16：轮数上限 8 + 部分成功总结（修复 E7）

**文件：**
- 修改：`backend/app/routers/chat.py`
- 测试：`backend/tests/test_chat_max_rounds.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_max_rounds.py — 超轮数部分成功总结。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chat import _build_final_summary_prompt


def test_build_final_summary_prompt_mentions_partial():
    p = _build_final_summary_prompt(completed=["get_dashboard"], remaining=["generate_plan_content"])
    assert "已完成" in p and "未完成" in p
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_max_rounds.py -q`
预期：FAIL（`_build_final_summary_prompt` 不存在）

- [ ] **步骤 3：实现**

`backend/app/routers/chat.py`：

```python
MAX_ROUNDS = 8  # 模块级常量；删除 agent_loop 函数内现有局部定义 MAX_ROUNDS = 5


def _build_final_summary_prompt(completed: list, remaining: list) -> str:
    done = "、".join(completed) if completed else "无"
    todo = "、".join(remaining) if remaining else "无"
    return (f"这是最后一轮。请直接总结所有操作结果。每个操作必须说明成功与否（看verified字段）。"
            f"已完成操作：{done}；未完成操作：{todo}。不要调用更多函数。")
```

agent_loop 超限分支改为：

```python
        # 超过最大轮数：部分成功汇报
        done_names = [r["name"] for r in results]
        remaining = [tc.get("function", {}).get("name", "") for tc in pending_tool_calls]
        final_msgs = current_msgs + [{"role": "user",
                                      "content": _build_final_summary_prompt(done_names, remaining)}]
        try:
            async for chunk in _call_llm_stream(final_msgs, ai_config):
                final_text += chunk
                yield sse_line({"type": "chunk", "content": chunk})
        except Exception as e:
            final_text = str(e)
            yield sse_line({"type": "error", "message": str(e)})
        yield sse_line({"type": "conv_id", "content": conv_id})
        yield sse_line({"type": "done"})
        asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text))
        return
```

（原「操作轮数超过上限，请简化问题重试」错误分支删除。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_max_rounds.py -q`
预期：1 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_chat_max_rounds.py
git commit -m "feat(chat): 轮数上限提至8并输出部分成功总结"
```

---

### 任务 17：阶段 1 全量门禁

**文件：** 无（验证）

- [ ] **步骤 1：后端全量测试**

运行：`cd backend && pytest tests/ -q`
预期：全绿（基线 1157 + 新增用例），无新增失败

- [ ] **步骤 2：前端类型检查**

运行：`cd frontend && npx tsc -b`
预期：exit 0

- [ ] **步骤 3：代码卫生**

运行：`git show --check HEAD` 与 `git diff --check`
预期：无空白错误

- [ ] **步骤 4：迁移脚本校验**

运行：`bash -n backend/db_migration_20260831_agent_chat_tool_calls.sql`（若环境无 bash，用 docker 内 pg 执行验证幂等：重复执行不报错）
预期：SQL 幂等（IF NOT EXISTS / ADD COLUMN IF NOT EXISTS）

- [ ] **步骤 5：Commit（如有修复）**

如有门禁修复，单独 commit 并在消息注明；无则跳过。

---

### 任务 18：0.4.0 打包与验收

**文件：** `scripts/package-release.sh`（不改，沿用）

- [ ] **步骤 1：构建前端**

运行（沿用 0.3.1 流程）：前端容器 node:22 构建 dist → docker cp 回宿主

- [ ] **步骤 2：打包**

运行：`bash scripts/package-release.sh --system`
预期：产出 0.4.0 系统包（不含 db-init/uploads/exports，含 model-cache + backend/models）

- [ ] **步骤 3：验收演练（Docker 隔离环境）**

对照设计文档第 10 节验收矩阵逐项验证：
- 进度刷新不消失（工具步骤条回放）
- 并行工具延迟下降（同轮多只读工具）
- 重试注入通过（临时制造 429 观察自动恢复）
- 报告含角色提示词（messages[0].role=system）
- 15 轮对话引用第 1 轮实体成功
- 聊天触发「给 XX 预案生成内容」→ 进度查询 → 完成汇报

- [ ] **步骤 4：交付说明**

整理 0.4.0 交付说明（新表迁移、API 变更、前端改动、遗留项），更新 TASKS.md 快照，向用户汇报。

---

## 计划自检记录

**1. 规格覆盖度（对照设计文档模块 1-6）：**
- 模块 1 进度持久化+步骤条 → 任务 3/4/5/6 ✓
- 模块 2 并行执行 → 任务 7 ✓
- 模块 3 重试 → 任务 1 ✓
- 模块 4 报告提示词 → 任务 2 ✓
- 模块 5 记忆增强 → 任务 8/9/10/11 ✓
- 模块 6 端到端生成+轮数 → 任务 12/13/14/15/16 ✓
- 门禁/打包 → 任务 17/18 ✓

**2. 占位符扫描：** 无 TODO/待定/「后续实现」占位步骤；任务 12 中 `NotImplementedError("同步模式由 0.4.1 审查修订依赖实现")` 是明确的版本边界声明，非占位。

**3. 类型一致性：** `_execute_pending_tools` 返回 `[(tc, result_str)]` 与任务 7 测试一致；`_save_messages(tool_trace=...)` 与任务 8/9 一致；`start_batch_generation` 返回 `started/plan_id/total/empty/message/verified` 与任务 14 断言一致；`MessageResponse.name` 与任务 11 一致。
