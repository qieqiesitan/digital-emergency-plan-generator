# 后端三连重构（LLM 统一 / 批量收尾 / chat_dispatch 收尾）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在严格行为等价前提下，消除 LLM 调用 9 处重复（统一到 llm_client）、完成批量生成准备块去重、收尾 chat_dispatch 泛化与 Enterprise schema 去重，并为每阶段补齐回归测试。

**架构：** 三阶段流水线，按 阶段2收尾 → 阶段1 → 阶段3 顺序实施，每阶段独立提交。阶段 2 基于 2026-08-08 优化后的新基线（`_run_batch_generation`/`_finalize_batch_result` 已存在），只抽公共准备函数；阶段 1 扩展 `llm_client` 统一入口并用薄包装保持各调用方错误文案；阶段 3 删死代码、收口委托样板、去重 schema 字段。

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x async / Pydantic v2 / pytest + pytest-asyncio / httpx / sse-starlette。测试命令统一在 `backend/` 下使用 `.venv\Scripts\python.exe -m pytest`。

---

## 前置：基线确认

> 实施前必须确认当前基线为绿，后续所有"全量 pytest"都以此为准。

- [ ] **步骤 1：确认后端基线**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：179 个测试函数全部 PASS（或 182 passed 计数，以 pytest 输出为准）。

- [ ] **步骤 2：确认前端不受影响（只跑类型与单测）**

```bash
cd frontend
npx tsc -b
npx vitest run
```

预期：tsc 无错误；vitest 全绿（48 passed）。

- [ ] **步骤 3：确认工作区干净（除并行会话产物外无代码改动）**

```bash
git status --short
```

预期：仅 `.graphifyignore`、`TASKS.md`、`chroma.sqlite3`、上传目录等非本次代码文件处于未跟踪/修改状态。若出现 `backend/app/` 下文件改动，先停下确认归属。

---

## 文件结构

**创建：**

- `backend/tests/test_batch_context.py` — 阶段 2：准备块助手与端点壳测试
- `backend/tests/test_llm_client_migration.py` — 阶段 1：llm_client 扩展与各调用方迁移测试
- `backend/tests/test_chat_dispatch.py` — 阶段 3：chat_dispatch 黄金测试

**修改：**

- `backend/app/routers/generation.py` — 阶段 2 准备块提取；阶段 1 `_stream_llm_chunks` LLMError 适配
- `backend/app/services/llm_client.py` — 阶段 1：`LLMError`、`tools`、`payload_overrides`、`include_top_p`、`llm_stream_all`、`llm_text_completion` 分支改造
- `backend/app/routers/chat.py` — 阶段 1：3 个 LLM 函数迁移
- `backend/app/routers/risk_assessment.py` — 阶段 1：3 个 `_stream_llm_*` 迁移
- `backend/app/regulations/sync.py` — 阶段 1：2 个函数迁移 + 解密导入收敛
- `backend/app/regulations/llm_reranker.py` — 阶段 1：`_call_llm` 迁移 + 解密导入收敛
- `backend/app/routers/ai_config.py` — 阶段 1：base URL 复用 `llm_client._get_api_base`
- `backend/app/services/chat_dispatch.py` — 阶段 3：删 3 个死函数、`_delegate_generic` 收口
- `backend/app/schemas/enterprise.py` — 阶段 3：`EnterpriseResponse` 字段去重

---

## 阶段 2 收尾：批量生成准备块去重

### 任务 B1：提取 `_get_plan_or_404` 与 `_collect_batch_context`

**文件：**
- 创建：`backend/tests/test_batch_context.py`
- 修改：`backend/app/routers/generation.py`（助手放 `_run_batch_generation` 之前，约 386 行前）

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_batch_context.py`：

```python
"""批量生成准备块提取后的回归测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.routers.generation import _get_plan_or_404, _collect_batch_context


@pytest.mark.asyncio
async def test_get_plan_or_404_raises_when_missing():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    user = MagicMock(id="u1")
    with pytest.raises(HTTPException) as exc_info:
        await _get_plan_or_404("p-missing", user, db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_plan_or_404_returns_plan():
    db = AsyncMock()
    plan = MagicMock(id="p1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = plan
    db.execute.return_value = result
    user = MagicMock(id="u1")
    assert await _get_plan_or_404("p1", user, db) is plan


@pytest.mark.asyncio
async def test_collect_batch_context_requires_ai_config():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    p = MagicMock(enterprise_id="e1")
    with pytest.raises(HTTPException) as exc_info:
        await _collect_batch_context("p1", p, MagicMock(), db, MagicMock(id="u1"))
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
@patch("app.routers.generation._enrich_with_reports",
       new=AsyncMock(side_effect=lambda data, eid, db: data))
@patch("app.routers.generation.build_risk_management_context",
       new=AsyncMock(return_value={}))
async def test_collect_batch_context_filters_sections():
    db = AsyncMock()
    ai_cfg = MagicMock()
    ent = MagicMock()
    resources = [MagicMock()]
    sec1 = MagicMock(section_key="sec_1", title="总则")
    sec2 = MagicMock(section_key="sec_2", title="风险")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: ai_cfg),          # AIConfig
        MagicMock(scalar_one_or_none=lambda: ent),             # Enterprise
        MagicMock(scalars=lambda: MagicMock(all=lambda: resources)),          # EmergencyResource
        MagicMock(scalars=lambda: MagicMock(all=lambda: [sec1, sec2])),       # PlanSection
    ])
    request = MagicMock()
    request.json = AsyncMock(return_value={"section_keys": ["sec_1"]})
    p = MagicMock(enterprise_id="e1")

    _, got_ai, ent_data, target = await _collect_batch_context("p1", p, request, db, MagicMock(id="u1"))
    assert got_ai is ai_cfg
    assert ent_data["name"] == ent.name
    assert [s.section_key for s in target] == ["sec_1"]


@pytest.mark.asyncio
@patch("app.routers.generation._enrich_with_reports",
       new=AsyncMock(side_effect=lambda data, eid, db: data))
@patch("app.routers.generation.build_risk_management_context",
       new=AsyncMock(return_value={}))
async def test_collect_batch_context_defaults_to_all_when_no_body():
    db = AsyncMock()
    ai_cfg = MagicMock()
    ent = MagicMock()
    sec1 = MagicMock(section_key="sec_1", title="总则")
    sec2 = MagicMock(section_key="sec_2", title="风险")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: ai_cfg),
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [sec1, sec2])),
    ])
    request = MagicMock()
    request.json = AsyncMock(side_effect=Exception("no body"))
    p = MagicMock(enterprise_id="e1")

    _, _, _, target = await _collect_batch_context("p1", p, request, db, MagicMock(id="u1"))
    assert [s.section_key for s in target] == ["sec_1", "sec_2"]
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_batch_context.py -q
```

预期：FAIL，报 `ImportError: cannot import name '_get_plan_or_404'`（函数尚未定义）。

- [ ] **步骤 3：实现两个助手**

在 `generation.py` 的 `_run_batch_generation` 定义（386 行）之前插入：

```python
async def _get_plan_or_404(plan_id: str, user, db: AsyncSession) -> PlanProject:
    """批量生成共用：查询预案，不存在抛 404。"""
    p = (await db.execute(
        select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == user.id)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    return p


async def _collect_batch_context(
    plan_id: str, p: PlanProject, request: Request, db: AsyncSession, current_user,
) -> tuple:
    """批量生成公共准备：AI 配置、企业上下文、目标章节。

    返回 (p, ai_config, ent_data, target_sections)。stale 守卫、空章节守卫、
    置 generating、_active_generations 赋值等端点差异逻辑留在调用端点。
    """
    ai_config = (await db.execute(
        select(AIConfig).where(AIConfig.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ai_config:
        raise HTTPException(400, "请先配置 AI 模型")

    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    resources = (await db.execute(
        select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id)
    )).scalars().all()
    risk_context = await build_risk_management_context(p.enterprise_id, db) if ent else {}
    ent_data = _collect_enterprise_data(ent, risk_context, resources) if ent else {}
    if ent:
        ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)

    try:
        body = await request.json()
        keys = body.get("section_keys")
    except Exception:
        keys = None

    all_sections = (await db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)
    )).scalars().all()
    target_sections = [s for s in all_sections if (not keys or s.section_key in keys)]
    return p, ai_config, ent_data, target_sections
```

确认 `generation.py` 顶部已导入 `AsyncSession` 与 `Request`；若缺，补 `from fastapi import Request`。

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_batch_context.py -q
```

预期：5 个测试全部 PASS。

- [ ] **步骤 5：改造 `generate_batch` 使用助手**

将 `generate_batch`（509 行起）的头部准备块替换为：

```python
async def generate_batch(plan_id: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = await _get_plan_or_404(plan_id, current_user, db)
    p, ai_config, ent_data, target_sections = await _collect_batch_context(plan_id, p, request, db, current_user)

    p.status = "generating"
    await db.commit()
    _active_generations[plan_id] = True
    plan_type = p.plan_type

    # Use a queue to stream events from background task to SSE
    event_queue: asyncio.Queue = asyncio.Queue()
    section_tuples = [(s.section_key, s.title) for s in target_sections]
```

同时删除函数体内冗余的 `import asyncio as _asyncio`（原 563 行），`run_background` 内部保持逐字不变。

- [ ] **步骤 6：改造 `generate_batch_background` 使用助手**

将 `generate_batch_background`（699 行起）的头部替换为：

```python
async def generate_batch_background(plan_id: str, request: Request, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = await _get_plan_or_404(plan_id, current_user, db)
    if p.status == "generating":
        if not _active_generations.get(plan_id):
            logger.warning(f"Plan {plan_id} has stale generating status - resetting to draft")
            p.status = "draft"
            await db.commit()
        else:
            return {"code": 0, "message": "正在生成中"}
    p, ai_config, ent_data, target_sections = await _collect_batch_context(plan_id, p, request, db, current_user)

    if not target_sections:
        return {"code": 0, "message": "没有可生成的章节"}

    p.status = "generating"
    await db.commit()
    _active_generations[plan_id] = True
    plan_type = p.plan_type

    section_ids = [(s.section_key, s.title) for s in target_sections]
```

`run_background` 内部保持逐字不变。

- [ ] **步骤 7：运行全量后端测试确认无回归**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：全部 PASS（179/182）。若失败，检查 `_collect_batch_context` 的返回顺序与端点解包是否一致。

- [ ] **步骤 8：Commit**

```bash
git add backend/app/routers/generation.py backend/tests/test_batch_context.py
git commit -m "refactor(generation): extract shared batch context helpers"
```

### 任务 B2：端点壳测试（SSE 序列 + 后台守卫）

**文件：**
- 修改：`backend/tests/test_batch_context.py`

- [ ] **步骤 1：编写失败的测试（追加到 test_batch_context.py）**

```python
@pytest.mark.asyncio
async def test_generate_batch_background_running_guard(monkeypatch):
    from app.routers import generation as gen
    db = AsyncMock()
    p = MagicMock(status="generating")
    result = MagicMock()
    result.scalar_one_or_none.return_value = p
    db.execute.return_value = result
    gen._active_generations["p1"] = True
    try:
        resp = await gen.generate_batch_background("p1", MagicMock(), MagicMock(id="u1"), db)
        assert resp == {"code": 0, "message": "正在生成中"}
    finally:
        gen._active_generations.pop("p1", None)


@pytest.mark.asyncio
@patch("app.routers.generation._enrich_with_reports",
       new=AsyncMock(side_effect=lambda data, eid, db: data))
@patch("app.routers.generation.build_risk_management_context",
       new=AsyncMock(return_value={}))
async def test_generate_batch_background_empty_sections():
    from app.routers import generation as gen
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: MagicMock(status="draft")),  # plan
        MagicMock(scalar_one_or_none=lambda: MagicMock()),                # ai_config
        MagicMock(scalar_one_or_none=lambda: MagicMock()),                # enterprise
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # resources
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # sections -> empty
    ])
    request = MagicMock()
    request.json = AsyncMock(return_value=None)
    resp = await gen.generate_batch_background("p1", request, MagicMock(id="u1"), db)
    assert resp == {"code": 0, "message": "没有可生成的章节"}


@pytest.mark.asyncio
@patch("app.routers.generation._enrich_with_reports",
       new=AsyncMock(side_effect=lambda data, eid, db: data))
@patch("app.routers.generation.build_risk_management_context",
       new=AsyncMock(return_value={}))
@patch("app.routers.generation._run_batch_generation",
       new=AsyncMock(return_value={"completed": 1, "failed": 0, "failed_sections": []}))
@patch("app.routers.generation._finalize_batch_result",
       new=AsyncMock(return_value={"completed": 1, "failed": 0, "failed_sections": [], "version": 1}))
async def test_generate_batch_sse_event_sequence():
    from app.routers import generation as gen
    db = AsyncMock()
    sec1 = MagicMock(section_key="sec_1", title="总则")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: MagicMock(status="draft")),  # plan
        MagicMock(scalar_one_or_none=lambda: MagicMock()),                # ai_config
        MagicMock(scalar_one_or_none=lambda: MagicMock()),                # enterprise
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),             # resources
        MagicMock(scalars=lambda: MagicMock(all=lambda: [sec1])),         # sections
    ])
    request = MagicMock()
    request.json = AsyncMock(return_value={"section_keys": ["sec_1"]})
    gen._failed_sections.pop("p1", None)
    try:
        resp = await gen.generate_batch("p1", request, MagicMock(id="u1"), db)
        body = b"".join([c async for c in resp.body_iterator]).decode("utf-8", errors="replace")
        assert '"type": "progress"' in body
        assert '"type": "batch_done"' in body
        assert "sec_1" in body
    finally:
        gen._active_generations.pop("p1", None)
        gen._failed_sections.pop("p1", None)
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_batch_context.py -q
```

预期：改造前用例可能 FAIL（端点尚未使用助手时 mock 不兼容）；无论红色与否，以最终实现后的 PASS 为验收。

- [ ] **步骤 3：确认实现**

B1 步骤 5/6 的实现即本任务的实现，无额外代码。

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_batch_context.py -q
```

预期：8 个测试全部 PASS。

- [ ] **步骤 5：运行全量测试**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/tests/test_batch_context.py
git commit -m "test(generation): cover batch endpoint guards and SSE sequence"
```

---

## 阶段 1：LLM 调用统一

### 任务 L1：扩展 llm_client（LLMError / tools / overrides / llm_stream_all）

**文件：**
- 创建：`backend/tests/test_llm_client_migration.py`
- 修改：`backend/app/services/llm_client.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_llm_client_migration.py`：

```python
"""llm_client 扩展与各调用方迁移回归测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException

from app.services.llm_client import LLMError, llm_chat_completion, llm_stream_all, llm_text_completion


class FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self._text = text
        self._json_data = json_data if json_data is not None else {
            "choices": [{"message": {"content": "ok"}}],
        }

    @property
    def text(self):
        return self._text

    async def aread(self):
        return self._text.encode("utf-8")

    def json(self):
        return self._json_data


class FakeStream:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeAsyncClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None, **kw):
        self.calls.append(("post", url, json, headers))
        return self._response

    async def stream(self, method, url, json=None, headers=None, **kw):
        self.calls.append(("stream", url, json, headers))
        return FakeStream(self._response)


def _cfg(**kw):
    c = MagicMock(
        provider=kw.get("provider", "deepseek"),
        base_url=kw.get("base_url"),
        model_name=kw.get("model_name", "deepseek-chat"),
        temperature=kw.get("temperature", 0.7),
        max_tokens=kw.get("max_tokens", 2000),
        top_p=kw.get("top_p", 1.0),
        api_key_encrypted="00" * 16,
    )
    return c


@pytest.mark.asyncio
async def test_llm_chat_completion_passes_tools_and_overrides(monkeypatch):
    import app.services.llm_client as lc
    fake = FakeAsyncClient(FakeResponse())
    monkeypatch.setattr(lc.httpx, "AsyncClient", lambda *a, **k: fake)
    monkeypatch.setattr(lc, "decrypt_api_key", lambda *a: "sk-test")

    await lc.llm_chat_completion(
        [{"role": "user", "content": "hi"}], _cfg(), stream=False, timeout=60,
        tools=[{"type": "function", "function": {"name": "x"}}],
        payload_overrides={"temperature": 0.1},
        include_top_p=False,
    )
    kind, url, payload, headers = fake.calls[0]
    assert kind == "post"
    assert url == "https://api.deepseek.com/v1/chat/completions"
    assert payload["tools"] == [{"type": "function", "function": {"name": "x"}}]
    assert payload["temperature"] == 0.1
    assert "top_p" not in payload
    assert payload["stream"] is False
    assert headers["Authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_llm_chat_completion_raises_llm_error(monkeypatch):
    import app.services.llm_client as lc
    fake = FakeAsyncClient(FakeResponse(status_code=500, text="boom"))
    monkeypatch.setattr(lc.httpx, "AsyncClient", lambda *a, **k: fake)
    monkeypatch.setattr(lc, "decrypt_api_key", lambda *a: "sk-test")

    with pytest.raises(LLMError) as exc_info:
        await lc.llm_chat_completion([{"role": "user", "content": "hi"}], _cfg(), stream=False)
    assert exc_info.value.status_code == 500
    assert str(exc_info.value) == "AI调用失败: 500 boom"


@pytest.mark.asyncio
async def test_llm_stream_all_collects_chunks(monkeypatch):
    import app.services.llm_client as lc

    async def fake_gen(messages, cfg, stream=False, timeout=120, **kw):
        assert stream is True
        for c in ["你", "好"]:
            yield c

    monkeypatch.setattr(lc, "llm_chat_completion", fake_gen)
    assert await lc.llm_stream_all([{"role": "user", "content": "hi"}], _cfg(), timeout=120) == "你好"


@pytest.mark.asyncio
async def test_llm_text_completion_maps_401_to_500(monkeypatch):
    import app.services.llm_client as lc
    monkeypatch.setattr(lc, "decrypt_api_key", lambda *a: "sk-test")

    async def fake_call(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(401, "bad key")

    monkeypatch.setattr(lc, "llm_chat_completion", fake_call)
    with pytest.raises(HTTPException) as exc_info:
        await lc.llm_text_completion([{"role": "user", "content": "hi"}], _cfg())
    assert exc_info.value.status_code == 500
    assert "AI API Key 无效" in str(exc_info.value.detail)
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：FAIL，报 `ImportError: cannot import name 'LLMError'`。

- [ ] **步骤 3：实现 llm_client 扩展**

在 `llm_client.py` 的 `API_BASE_MAP` 之后新增：

```python
class LLMError(Exception):
    """LLM 调用失败（非 200）。携带状态码与响应文本，供调用方按原文案重建。"""

    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        super().__init__(f"AI调用失败: {status_code} {text[:300]}")
```

将 `llm_chat_completion` 签名与 payload 构建改为：

```python
async def llm_chat_completion(
    messages: list[dict],
    ai_config: AIConfig,
    stream: bool = False,
    timeout: int = 120,
    tools: list | None = None,
    payload_overrides: dict | None = None,
    include_top_p: bool = True,
) -> dict | AsyncGenerator[str, None]:
    """统一的 LLM Chat Completion 调用入口。

    Args:
        messages: OpenAI-format 消息列表
        ai_config: AI 配置（provider, model, temperature 等）
        stream: 是否流式输出
        timeout: 超时秒数
        tools: 工具调用声明（非 None 时加入 payload）
        payload_overrides: 浅合并覆盖标准 payload（如 temperature/max_tokens）
        include_top_p: False 时不写入 top_p 键（sync/reranker 历史行为）
    """
    base = _get_api_base(ai_config.provider, ai_config.base_url)

    payload = {
        "model": ai_config.model_name,
        "messages": messages,
        "temperature": ai_config.temperature,
        "max_tokens": ai_config.max_tokens,
        "stream": stream,
    }
    if include_top_p:
        payload["top_p"] = ai_config.top_p
    if tools is not None:
        payload["tools"] = tools
    if payload_overrides:
        payload.update(payload_overrides)

    if stream:
        return _stream_response(base, payload, ai_config, timeout)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{base}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"},
        )
        if resp.status_code != 200:
            raise LLMError(resp.status_code, resp.text)
        return resp.json()
```

将 `_stream_response` 的非 200 分支改为：

```python
            if resp.status_code != 200:
                err = await resp.aread()
                raise LLMError(resp.status_code, err.decode("utf-8", errors="replace"))
```

在 `llm_collect_all` 之后新增：

```python
async def llm_stream_all(
    messages: list[dict],
    ai_config: AIConfig,
    timeout: int = 120,
) -> str:
    """流式调用并收集为完整文本。"""
    result = ""
    async for chunk in llm_chat_completion(messages, ai_config, stream=True, timeout=timeout):
        result += chunk
    return result
```

将 `llm_text_completion` 的异常分支改为：

```python
    try:
        decrypt_api_key(ai_config.api_key_encrypted)  # 提前触发解密失败，映射为 500
    except Exception:
        raise HTTPException(500, "AI 配置密钥解密失败")
    try:
        data = await llm_chat_completion(messages, ai_config, stream=False, timeout=timeout)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except httpx.TimeoutException:
        raise HTTPException(504, f"AI 响应超时（{timeout}s），请稍后重试")
    except HTTPException:
        raise
    except LLMError as e:
        if e.status_code == 401:
            raise HTTPException(500, "AI API Key 无效或已过期，请在系统设置中重新配置 AI 模型")
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(502, f"AI 服务连接失败: {e}")
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：4 个测试全部 PASS。

- [ ] **步骤 5：运行全量测试**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/llm_client.py backend/tests/test_llm_client_migration.py
git commit -m "refactor(llm): extend llm_client with tools, overrides, stream collect and LLMError"
```

### 任务 L2：迁移 chat.py 三个 LLM 函数

**文件：**
- 修改：`backend/tests/test_llm_client_migration.py`（追加）
- 修改：`backend/app/routers/chat.py`

- [ ] **步骤 1：编写失败的测试（追加）**

```python
@pytest.mark.asyncio
async def test_chat_call_llm_uses_llm_client_with_tools(monkeypatch):
    from app.routers import chat
    calls = {}

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        calls.update({"stream": stream, "timeout": timeout, "tools": kw.get("tools")})
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(chat, "llm_chat_completion", fake_chat)
    cfg = _cfg()
    result = await chat._call_llm([{"role": "user", "content": "hi"}], cfg)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert calls == {"stream": False, "timeout": 60, "tools": chat.CHAT_TOOLS}


@pytest.mark.asyncio
async def test_chat_call_llm_stream_preserves_error_message(monkeypatch):
    from app.routers import chat

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(500, "boom")

    monkeypatch.setattr(chat, "llm_chat_completion", fake_chat)
    gen = chat._call_llm_stream([{"role": "user", "content": "hi"}], _cfg())
    with pytest.raises(Exception) as exc_info:
        async for _ in gen:
            pass
    assert str(exc_info.value) == "AI调用失败: 500 boom"


@pytest.mark.asyncio
async def test_chat_collect_llm_uses_llm_collect_all(monkeypatch):
    from app.routers import chat
    calls = {}

    async def fake_collect(messages, cfg, timeout=120):
        calls["timeout"] = timeout
        return "collected"

    monkeypatch.setattr(chat, "llm_collect_all", fake_collect)
    assert await chat._collect_llm([{"role": "user", "content": "hi"}], _cfg()) == "collected"
    assert calls["timeout"] == 180
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：3 个新用例 FAIL（chat.py 仍是手写 httpx，未调用 llm_client）。

- [ ] **步骤 3：实现迁移**

修改 `chat.py` 导入：

```python
from app.services.llm_client import decrypt_api_key, llm_chat_completion, llm_collect_all, LLMError
```

若 `httpx` 在 chat.py 中无其他使用（`rg -n 'httpx' backend/app/routers/chat.py` 仅剩 import 一行），删除 `import httpx`。

将 `_call_llm`、`_call_llm_stream`、`_collect_llm` 三个函数整体替换为：

```python
async def _call_llm(messages: list, ai_config: AIConfig) -> dict:
    return await llm_chat_completion(messages, ai_config, stream=False, timeout=60, tools=CHAT_TOOLS)


async def _call_llm_stream(messages: list, ai_config: AIConfig):
    try:
        gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=180)
        async for chunk in gen:
            yield chunk
    except LLMError as e:
        # 保持原 chat.py 文案（无空格）
        raise Exception(f"AI调用失败: {e.status_code} {e.text[:300]}")


async def _collect_llm(messages: list, ai_config: AIConfig) -> str:
    return await llm_collect_all(messages, ai_config, timeout=180)
```

同时删除 chat.py 中 3 处 base URL 映射副本（原 92-93 / 107-108 / 136-137 行）。

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：全部 PASS。

- [ ] **步骤 5：全量测试**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_llm_client_migration.py
git commit -m "refactor(llm): migrate chat.py LLM calls to llm_client"
```

### 任务 L3：迁移 risk_assessment.py 三个流式函数

**文件：**
- 修改：`backend/tests/test_llm_client_migration.py`（追加）
- 修改：`backend/app/routers/risk_assessment.py`

- [ ] **步骤 1：编写失败的测试（追加）**

```python
@pytest.mark.asyncio
async def test_risk_assessment_stream_uses_llm_client_and_preserves_errors(monkeypatch):
    from app.routers import risk_assessment as ra
    calls = {}

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        calls.update({"stream": stream, "timeout": timeout})

        async def gen():
            yield "a"
            yield "b"

        return gen()

    monkeypatch.setattr(ra, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(ra, "decrypt_api_key", lambda *a: "sk-test")

    chunks = [c async for c in ra._stream_llm_with_messages_chunked(
        [{"role": "user", "content": "hi"}], _cfg())]
    assert chunks == ["a", "b"]
    assert calls == {"stream": True, "timeout": 120}

    full = await ra._stream_llm_with_messages([{"role": "user", "content": "hi"}], _cfg())
    assert full == "ab"


@pytest.mark.asyncio
async def test_risk_assessment_stream_llm_error_message(monkeypatch):
    from app.routers import risk_assessment as ra

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(500, "boom")

    monkeypatch.setattr(ra, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(ra, "decrypt_api_key", lambda *a: "sk-test")
    with pytest.raises(Exception) as exc_info:
        async for _ in ra._stream_llm_with_messages_chunked(
            [{"role": "user", "content": "hi"}], _cfg()):
            pass
    assert str(exc_info.value) == "LLM call failed: 500 boom"


@pytest.mark.asyncio
async def test_risk_assessment_decrypt_failure_maps_to_500(monkeypatch):
    from app.routers import risk_assessment as ra

    def bad_decrypt(*a):
        raise Exception("bad")

    monkeypatch.setattr(ra, "decrypt_api_key", bad_decrypt)
    with pytest.raises(HTTPException) as exc_info:
        async for _ in ra._stream_llm_with_messages_chunked(
            [{"role": "user", "content": "hi"}], _cfg()):
            pass
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "AI config key decryption failed"
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：3 个新用例 FAIL（risk_assessment.py 仍是手写 httpx）。

- [ ] **步骤 3：实现迁移**

修改 `risk_assessment.py` 顶部导入为：

```python
from app.services.llm_client import decrypt_api_key, llm_chat_completion, llm_stream_all, LLMError
```

在 `_stream_llm_with_messages` 之前新增私有守卫，并整体替换 173-228 行的三个函数：

```python
def _guard_decrypt(ai_config) -> None:
    """保持原 decrypt 失败 → HTTPException(500) 的语义。"""
    try:
        decrypt_api_key(ai_config.api_key_encrypted)
    except Exception:
        raise HTTPException(500, "AI config key decryption failed")


async def _stream_llm_with_messages(messages: list[dict], ai_config: AIConfig) -> str:
    _guard_decrypt(ai_config)
    try:
        return await llm_stream_all(messages, ai_config, timeout=120)
    except LLMError as e:
        # 保持原 risk_assessment 文案
        raise Exception(f"LLM call failed: {e.status_code} {e.text[:300]}")


async def _stream_llm_with_messages_chunked(messages: list[dict], ai_config: AIConfig):
    _guard_decrypt(ai_config)
    try:
        gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=120)
        async for chunk in gen:
            yield chunk
    except LLMError as e:
        raise Exception(f"LLM call failed: {e.status_code} {e.text[:300]}")


async def _stream_llm_with_system(prompt: str, ai_config: AIConfig) -> str:
    messages = [
        {"role": "system", "content": _get_ra_system_prompt()},
        {"role": "user", "content": prompt},
    ]
    return await _stream_llm_with_messages(messages, ai_config)
```

删除原 3 个函数体内的 base URL 映射（187-188 行）与 httpx 实现（190-215 行）。

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：全部 PASS。

- [ ] **步骤 5：全量测试**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/risk_assessment.py backend/tests/test_llm_client_migration.py
git commit -m "refactor(llm): migrate risk_assessment streaming to llm_client"
```

### 任务 L4：迁移 sync.py 两个函数

**文件：**
- 修改：`backend/tests/test_llm_client_migration.py`（追加）
- 修改：`backend/app/regulations/sync.py`

- [ ] **步骤 1：编写失败的测试（追加）**

```python
@pytest.mark.asyncio
async def test_sync_ai_extract_articles_uses_llm_client_and_swallows_errors(monkeypatch):
    from app.regulations import sync
    calls = {}

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        calls.update({
            "timeout": timeout,
            "include_top_p": kw.get("include_top_p"),
            "overrides": kw.get("payload_overrides"),
        })
        return {"choices": [{"message": {"content": '[{"number": "第一条", "text": "内容"}]'}}]}

    monkeypatch.setattr(sync, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(sync, "decrypt_api_key", lambda *a: "sk-test")

    out = await sync._ai_extract_articles("全文", _cfg(max_tokens=1000))
    assert out == [{"number": "第一条", "text": "内容"}]
    assert calls["timeout"] == 600
    assert calls["include_top_p"] is False
    assert calls["overrides"]["temperature"] == 0.1
    assert calls["overrides"]["max_tokens"] == 2000


@pytest.mark.asyncio
async def test_sync_ai_extract_articles_returns_empty_on_failure(monkeypatch):
    from app.regulations import sync

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        raise Exception("network down")

    monkeypatch.setattr(sync, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(sync, "decrypt_api_key", lambda *a: "sk-test")
    assert await sync._ai_extract_articles("全文", _cfg()) == []


@pytest.mark.asyncio
async def test_sync_ai_parse_llm_error_message(monkeypatch):
    from app.regulations import sync

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(401, "Invalid API Key")

    monkeypatch.setattr(sync, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(sync, "decrypt_api_key", lambda *a: "sk-test")
    with pytest.raises(Exception) as exc_info:
        await sync.ai_parse("全文", _cfg())
    assert "DeepSeek API Key 无效" in str(exc_info.value)
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：3 个新用例 FAIL（sync.py 仍是手写 httpx，且模块未导出 `llm_chat_completion`/`decrypt_api_key` 属性）。

- [ ] **步骤 3：实现迁移**

修改 `sync.py` 中两处函数内导入（221/224 行与 304/306 行）为：

```python
    from app.services.llm_client import decrypt_api_key, llm_chat_completion
```

将 `_ai_extract_articles`（219 行起）整体替换为：

```python
async def _ai_extract_articles(raw_text: str, ai_config) -> list[dict]:
    """用 LLM 提取条文（兜底）。返回 [{"number": str, "text": str}, ...]。"""
    import json as _json
    import re as _re
    from app.services.llm_client import decrypt_api_key, llm_chat_completion

    try:
        decrypt_api_key(ai_config.api_key_encrypted)
    except Exception:
        return []

    prompt = ARTICLE_EXTRACT_PROMPT.replace("{raw_text}", raw_text)
    messages = [
        {"role": "system", "content": "你是一个精确的JSON数据提取器。只输出JSON数组，不要解释。"},
        {"role": "user", "content": prompt},
    ]

    try:
        data = await llm_chat_completion(
            messages, ai_config, stream=False, timeout=600,
            include_top_p=False,
            payload_overrides={
                "temperature": 0.1,
                "max_tokens": min(65536, (ai_config.max_tokens or 16384) * 2),
            },
        )
        text = data["choices"][0]["message"]["content"]

        for extractor in [
            lambda t: _json.loads(t),
            lambda t: _json.loads(_re.search(r"```(?:json)?\s*\n?(.*?)\n?```", t, _re.DOTALL).group(1).strip()) if _re.search(r"```(?:json)?\s*\n?(.*?)\n?```", t, _re.DOTALL) else None,
            lambda t: _json.loads(_re.search(r"\[.*?\]", t, _re.DOTALL).group(0)) if _re.search(r"\[.*?\]", t, _re.DOTALL) else None,
            lambda t: _json.loads("[" + _re.search(r"\{.*", t, _re.DOTALL).group(0) + "]") if _re.search(r"\{.*", t, _re.DOTALL) else None,
        ]:
            try:
                result = extractor(text)
                if result:
                    if isinstance(result, dict) and "articles" in result:
                        return result["articles"]
                    if isinstance(result, list):
                        return result
            except Exception:
                continue
    except Exception:
        pass
    return []
```

将 `ai_parse`（302 行起）的 LLM 调用段（原 304-345 行附近）替换为：

```python
    from app.services.llm_client import decrypt_api_key, llm_chat_completion, LLMError
    try:
        decrypt_api_key(ai_config.api_key_encrypted)
    except Exception:
        raise Exception("API Key 解密失败，请前往 设置->AI配置 重新输入并保存 API Key")

    prompt = PARSE_PROMPT.replace("{raw_text}", raw_text)
    messages = [
        {"role": "system", "content": "你是一个精确的JSON数据提取器。只输出JSON，不要解释。"},
        {"role": "user", "content": prompt},
    ]

    try:
        data = await llm_chat_completion(
            messages, ai_config, stream=False, timeout=600,
            include_top_p=False,
            payload_overrides={
                "temperature": 0.1,
                "max_tokens": ai_config.max_tokens or 16384,
            },
        )
    except LLMError as e:
        if "Invalid API Key" in e.text or "invalid" in e.text.lower():
            raise Exception("DeepSeek API Key 无效，请前往 设置->AI配置 输入正确的 API Key")
        raise Exception(f"AI API 错误 (HTTP {e.status_code}): {e.text[:500]}")

    logger.info("DeepSeek response status: %s, model: %s", 200, data.get("model", ""))
    text = data["choices"][0]["message"]["content"]
```

> 注意：原 `ai_parse` 在 200 分支后有元数据解析逻辑，本替换只动 LLM 调用段，`text` 之后的解析代码保持原样。

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：全部 PASS。

- [ ] **步骤 5：全量测试**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/regulations/sync.py backend/tests/test_llm_client_migration.py
git commit -m "refactor(llm): migrate regulations sync LLM calls to llm_client"
```

### 任务 L5：迁移 llm_reranker.py

**文件：**
- 修改：`backend/tests/test_llm_client_migration.py`（追加）
- 修改：`backend/app/regulations/llm_reranker.py`

- [ ] **步骤 1：编写失败的测试（追加）**

```python
@pytest.mark.asyncio
async def test_reranker_call_llm_uses_llm_client(monkeypatch):
    from app.regulations import llm_reranker as mod
    from app.regulations.llm_reranker import LLMReranker
    calls = {}

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        calls.update({
            "timeout": timeout,
            "include_top_p": kw.get("include_top_p"),
            "overrides": kw.get("payload_overrides"),
        })
        return {"choices": [{"message": {"content": "[]"}}]}

    monkeypatch.setattr(mod, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(mod, "decrypt_api_key", lambda *a: "sk-test")

    reranker = LLMReranker(ai_config=_cfg())
    assert await reranker._call_llm("prompt") == "[]"
    assert calls["timeout"] == 30
    assert calls["include_top_p"] is False
    assert calls["overrides"] == {"temperature": 0, "max_tokens": 500}


@pytest.mark.asyncio
async def test_reranker_call_llm_preserves_error_message(monkeypatch):
    from app.regulations import llm_reranker as mod
    from app.regulations.llm_reranker import LLMReranker

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(500, "boom")

    monkeypatch.setattr(mod, "llm_chat_completion", fake_chat)
    monkeypatch.setattr(mod, "decrypt_api_key", lambda *a: "sk-test")
    with pytest.raises(Exception) as exc_info:
        await LLMReranker(ai_config=_cfg())._call_llm("prompt")
    assert str(exc_info.value) == "LLM API error: HTTP 500"
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：2 个新用例 FAIL。

- [ ] **步骤 3：实现迁移**

修改 `llm_reranker.py`：删除顶部 `import httpx`（13 行，确认无其他使用）；将 `_call_llm`（94 行起）整体替换为：

```python
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM API。"""
        from app.services.llm_client import decrypt_api_key, llm_chat_completion, LLMError

        try:
            decrypt_api_key(self.ai_config.api_key_encrypted)
        except Exception:
            raise Exception("API Key 解密失败")

        messages = [
            {
                "role": "system",
                "content": "你是一个精确的 JSON 数组生成器。只输出 JSON 数组，不要解释。",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            data = await llm_chat_completion(
                messages, self.ai_config, stream=False, timeout=30,
                include_top_p=False,
                payload_overrides={"temperature": 0, "max_tokens": 500},
            )
            return data["choices"][0]["message"]["content"]
        except LLMError as e:
            raise Exception(f"LLM API error: HTTP {e.status_code}")
```

同时删除 base URL 映射副本（105-106 行）。

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：全部 PASS。

- [ ] **步骤 5：全量测试**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：全部 PASS。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/regulations/llm_reranker.py backend/tests/test_llm_client_migration.py
git commit -m "refactor(llm): migrate llm_reranker to llm_client"
```

### 任务 L6：generation 适配 + base URL/解密收敛

**文件：**
- 修改：`backend/app/routers/generation.py`
- 修改：`backend/app/routers/ai_config.py`
- 修改：`backend/tests/test_llm_client_migration.py`（追加 1 个用例）

- [ ] **步骤 1：编写失败的测试（追加）**

```python
@pytest.mark.asyncio
async def test_generation_stream_llm_chunks_preserves_space_message(monkeypatch):
    from app.routers import generation as gen

    async def fake_chat(messages, cfg, stream=False, timeout=120, **kw):
        raise LLMError(500, "boom")

    monkeypatch.setattr(gen, "llm_chat_completion", fake_chat)
    with pytest.raises(HTTPException) as exc_info:
        async for _ in gen._stream_llm_chunks("prompt", _cfg()):
            pass
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "AI 调用失败: 500 boom"
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：新用例 FAIL（当前 `_stream_llm_chunks` 直接 `str(e)` 输出无空格文案）。

- [ ] **步骤 3：实现 generation.py 适配**

修改 `generation.py` 导入：

```python
from app.services.llm_client import llm_chat_completion, llm_collect_all, LLMError
```

将 `_stream_llm_chunks`（363 行起）替换为：

```python
async def _stream_llm_chunks(prompt: str, ai_config: AIConfig, plan_type: str = "*", style_preference=None, advanced_overrides=None):
    try:
        messages = [
            {"role": "system", "content": _build_system_prompt(plan_type, style_preference, advanced_overrides)},
            {"role": "user", "content": prompt},
        ]
        gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=120)
        async for chunk in gen:
            yield chunk
    except HTTPException:
        raise
    except LLMError as e:
        # 保持原 generation 文案（带空格）
        raise HTTPException(500, f"AI 调用失败: {e.status_code} {e.text[:300]}")
    except Exception as e:
        raise HTTPException(500, str(e))
```

- [ ] **步骤 4：实现 ai_config.py base URL 收敛**

修改 `test_ai_connection`（57 行起）：

```python
    try:
        from app.services.llm_client import _get_api_base
        base = _get_api_base(data.provider, data.base_url)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                json={"model": data.model_name, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                headers={"Authorization": f"Bearer {data.api_key}"},
            )
            if resp.status_code == 200:
                return ApiResponse(data=AITestResult(ok=True, detail="连接成功"))
            return ApiResponse(data=AITestResult(ok=False, detail=f"HTTP {resp.status_code}: {resp.text[:200]}"))
    except Exception as e:
        return ApiResponse(data=AITestResult(ok=False, detail=str(e)))
```

删除函数内联的厂商映射 dict。行为等价：原映射缺失 provider 时回退 `data.base_url or ""`，`_get_api_base` 同样返回 `base_url` 或 `API_BASE_MAP.get(provider, "")`。

- [ ] **步骤 5：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_llm_client_migration.py -q
```

预期：全部 PASS。

- [ ] **步骤 6：全量测试 + 确认 base URL 副本清零**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

```bash
rg -n 'dashscope\.aliyuncs|api\.deepseek' backend/app --glob '*.py'
```

预期：pytest 全部 PASS；rg 仅命中 `backend/app/services/llm_client.py`。

- [ ] **步骤 7：Commit**

```bash
git add backend/app/routers/generation.py backend/app/routers/ai_config.py backend/tests/test_llm_client_migration.py
git commit -m "refactor(llm): adapt generation error wrapper and consolidate base URL map"
```

---

## 阶段 3：chat_dispatch 收尾 + Enterprise 字段去重

### 任务 D1：删除死代码 + `_delegate_generic` 收口

**文件：**
- 创建：`backend/tests/test_chat_dispatch.py`
- 修改：`backend/app/services/chat_dispatch.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_chat_dispatch.py`：

```python
"""chat_dispatch 收尾回归测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.chat_dispatch import (
    _delegate_generic,
    _ErrorDict,
    _list_resources,
    _update_enterprise,
    _delete_plan,
    dispatch,
)


@pytest.mark.asyncio
async def test_delegate_generic_returns_error_data_on_erroDict():
    async def op(db, user, args, cfg):
        raise _ErrorDict({"error": "企业不存在或无权访问", "verified": False})

    out = await _delegate_generic(op, AsyncMock(), MagicMock(), {}, {})
    assert out == {"error": "企业不存在或无权访问", "verified": False}


@pytest.mark.asyncio
async def test_delegate_generic_passthrough():
    async def op(db, user, args, cfg):
        return {"id": "1", "verified": True}

    assert await _delegate_generic(op, AsyncMock(), MagicMock(), {}, {}) == {"id": "1", "verified": True}


@pytest.mark.asyncio
async def test_list_resources_requires_enterprise_id():
    out = await _list_resources(AsyncMock(), MagicMock(id="u1"), {})
    assert out == {"error": "请提供 enterprise_id", "verified": False}


@pytest.mark.asyncio
async def test_update_enterprise_delegates_generic():
    db = AsyncMock()
    ent = MagicMock(id="e1", name="企业A")
    result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    db.execute.return_value = result
    out = await _update_enterprise(db, MagicMock(id="u1"), {"enterprise_id": "e1", "name": "企业B"})
    assert out["verified"] is True
    assert ent.name == "企业B"


@pytest.mark.asyncio
async def test_delete_plan_missing_id():
    out = await _delete_plan(AsyncMock(), MagicMock(id="u1"), {})
    assert out["error"] == "请提供 plan_id"


@pytest.mark.asyncio
async def test_dispatch_unknown_function():
    out = await dispatch(AsyncMock(), MagicMock(id="u1"), "no_such_fn", {})
    assert "未知操作" in out
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_chat_dispatch.py -q
```

预期：FAIL，报 `ImportError: cannot import name '_delegate_generic'`。

- [ ] **步骤 3：实现**

在 `chat_dispatch.py` 的 `_generic_delete` 之后（约 165 行）新增：

```python
async def _delegate_generic(op, db, user, args, cfg):
    """generic CRUD 委托样板：统一捕获 _ErrorDict 返回其 data。"""
    try:
        return await op(db, user, args, cfg)
    except _ErrorDict as e:
        return e.data
```

将以下 5 个已接线的委托函数体替换为单行调用（保持函数名与签名不变）：

```python
async def _list_resources(db, user, args):
    return await _delegate_generic(_generic_list, db, user, args, _RES_CFG)


async def _create_resource(db, user, args):
    return await _delegate_generic(_generic_create, db, user, args, _RES_CFG)


async def _update_resource(db, user, args):
    return await _delegate_generic(_generic_update, db, user, args, _RES_CFG)


async def _delete_resource(db, user, args):
    return await _delegate_generic(_generic_delete, db, user, args, _RES_CFG)


async def _delete_plan(db, user, args):
    return await _delegate_generic(_generic_delete, db, user, args, _PLAN_CFG)
```

将 `_create_enterprise`（339 行起）的委托段改为：

```python
    try:
        return await _delegate_generic(_generic_create, db, user, args, _ENT_CFG)
    except _ErrorDict as e:
        return e.data
```

（`_create_enterprise` 保留同名查重逻辑。）

将 `_update_enterprise`（362 行起）整体替换为：

```python
async def _update_enterprise(db, user, args):
    return await _delegate_generic(_generic_update, db, user, args, _ENT_CFG)
```

删除死代码 `_create_risk_source` / `_update_risk_source` / `_delete_risk_source`（约 389-416 行，整段删除）。

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_chat_dispatch.py -q
```

预期：6 个测试全部 PASS。

- [ ] **步骤 5：确认无残留引用**

```bash
cd backend
rg -n '_create_risk_source|_update_risk_source|_delete_risk_source' app
```

预期：无输出（函数已被删除且无引用）。

- [ ] **步骤 6：全量测试 + Commit**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
git add backend/app/services/chat_dispatch.py backend/tests/test_chat_dispatch.py
git commit -m "refactor(chat): remove dead risk source handlers and delegate generic CRUD"
```

### 任务 D2：EnterpriseResponse 字段去重

**文件：**
- 修改：`backend/app/schemas/enterprise.py`
- 修改：`backend/tests/test_chat_dispatch.py`（追加 1 个用例）

- [ ] **步骤 1：编写失败的测试（追加）**

```python
def test_enterprise_response_dedup_fields():
    from app.schemas.enterprise import EnterpriseBase, EnterpriseResponse
    base = EnterpriseBase.model_fields
    resp = EnterpriseResponse.model_fields
    # 5 个同类型字段不再被 Response 重新声明：注解与 Base 完全一致
    for f in ["last_plan_filing_authority", "building_overview", "floor_plan_url", "gis_lat", "gis_lng"]:
        assert f in resp
        assert resp[f].annotation is base[f].annotation
    # 3 个日期字段保留覆盖：类型不同（输出序列化格式）
    for f in ["established_date", "fire_approval_date", "last_plan_filing_date"]:
        assert resp[f].annotation is not base[f].annotation
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_chat_dispatch.py::test_enterprise_response_dedup_fields -q
```

预期：FAIL（当前 Response 对 5 个同类型字段重新声明）。若该断言意外 PASS（Pydantic 继承复用注解对象），追加更强断言：用 `inspect.getsource(EnterpriseResponse)` 断言源码中不再出现这 5 个字段的声明行，以「Response 源码不再重复声明」为最终标准。

- [ ] **步骤 3：实现**

修改 `schemas/enterprise.py` 的 `EnterpriseResponse`，删除 5 个同类型重复字段声明，并为 3 个日期字段补注释：

```python
class EnterpriseResponse(EnterpriseBase):
    """企业响应。包含 EnterpriseBase 所有字段 + 额外响应字段。

    注意：established_date / fire_approval_date / last_plan_filing_date 在
    Base 中为 str（输入态），此处覆盖为 DatetimeStr（输出序列化格式），
    二者类型不同，不可合并，必须保留覆盖。
    """
    id: str
    established_date: DatetimeStr | None = None
    fire_approval_date: DatetimeStr | None = None
    last_plan_filing_date: DatetimeStr | None = None
    org_structure: list = []
    surrounding_info: dict | None = None
    risk_sources_count: int = 0
    risk_events_count: int = 0
    resources_count: int = 0
    plans_count: int = 0
    created_at: DatetimeStr
    updated_at: DatetimeStr

    model_config = {"from_attributes": True}
```

（删除 `last_plan_filing_authority`、`building_overview`、`floor_plan_url`、`gis_lat`、`gis_lng` 的重复声明，它们继承自 Base。）

- [ ] **步骤 4：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_chat_dispatch.py -q
```

预期：全部 PASS（含新用例）。

- [ ] **步骤 5：全量测试 + Commit**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
git add backend/app/schemas/enterprise.py backend/tests/test_chat_dispatch.py
git commit -m "refactor(schema): dedup enterprise response fields"
```

### 任务 D3：chat_dispatch 黄金测试补全

**文件：**
- 修改：`backend/tests/test_chat_dispatch.py`

- [ ] **步骤 1：编写测试（追加）**

```python
@pytest.mark.asyncio
async def test_list_enterprises_keyword_search():
    from app.services.chat_dispatch import _list_enterprises
    db = AsyncMock()
    ent = MagicMock(id="e1", name="宝岳", industry="科技", address="西安", plans=[])
    result = MagicMock()
    result.scalars.return_value.all.return_value = [ent]
    db.execute.return_value = result
    out = await _list_enterprises(db, MagicMock(id="u1"), {"keyword": "宝岳"})
    assert out["enterprises"][0]["name"] == "宝岳"


@pytest.mark.asyncio
async def test_create_enterprise_dedup():
    from app.services.chat_dispatch import _create_enterprise
    db = AsyncMock()
    existing = MagicMock(id="e1", name="宝岳")
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute.return_value = result
    out = await _create_enterprise(db, MagicMock(id="u1"), {"name": "宝岳"})
    assert out == {"id": "e1", "name": "宝岳", "message": "企业已存在，无需重复创建", "verified": True}


@pytest.mark.asyncio
async def test_create_plan_with_template(monkeypatch):
    from app.services.chat_dispatch import _create_plan
    db = AsyncMock()
    ent = MagicMock(id="e1")
    tmpl = MagicMock(structure=[{"section_key": "sec_1", "title": "总则"}])
    plan = MagicMock(id="p1", title="预案A", plan_type="comprehensive")
    results = [
        MagicMock(scalar_one_or_none=lambda: ent),     # Enterprise
        MagicMock(scalar_one_or_none=lambda: tmpl),    # PlanTemplate
    ]
    db.execute = AsyncMock(side_effect=results)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    created = {}

    def fake_create_sections(db, plan_id, structure):
        created["plan_id"] = plan_id
        created["structure"] = structure

    monkeypatch.setattr("app.services.chat_dispatch._create_sections_from_template", fake_create_sections)
    out = await _create_plan(db, MagicMock(id="u1"), {
        "enterprise_id": "e1", "title": "预案A", "plan_type": "comprehensive",
    })
    assert out["id"] == plan.id
    assert created["plan_id"] == plan.id
    assert created["structure"] == tmpl.structure
```

- [ ] **步骤 2：运行测试确认通过**

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_chat_dispatch.py -q
```

预期：全部 PASS（这些是行为固化测试，实现已存在）。

> 若 `test_create_plan_with_template` 因 `db.add`/`db.flush` mock 链失败，把 `db.add.side_effect` 设为把传入对象的 `id` 赋值为 `"p1"`，并确保 `db.flush`/`db.refresh` 为 AsyncMock。

- [ ] **步骤 3：全量测试 + Commit**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
git add backend/tests/test_chat_dispatch.py
git commit -m "test(chat): golden tests for chat_dispatch handlers"
```

---

## 任务 F：全量验证与 Docker 冒烟

**文件：** 无代码改动

- [ ] **步骤 1：后端全量**

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

预期：全部 PASS（含新增 3 个测试文件）。

- [ ] **步骤 2：前端类型与单测**

```bash
cd frontend
npx tsc -b
npx vitest run
```

预期：无错误，全绿（本次未改前端，确认无回归）。

- [ ] **步骤 3：Docker 重启并冒烟**

```bash
docker restart emergency-plan-backend
```

然后按规格验收清单逐项执行：

1. AI 对话一次（chat SSE 流式 + 工具调用）——确认流式正常、工具返回正常；
2. `/plans/{id}/generate/batch` SSE 批量生成一次——确认事件序列含 `progress`/`chunk`/`section_done`/`batch_done`，结束后 `_active_generations[id]` 为 False；
3. `/plans/{id}/generate/batch/background` 后台生成一次——确认返回消息、最终 `plan.status` 与版本快照、失败清单接口有值；
4. chat 工具调用导出 DOCX 一次——确认文件生成；
5. 法规检索链路触发一次重排（候选 >8 时）——确认 reranker 回退逻辑不报错。

- [ ] **步骤 4：提交收尾（若冒烟发现修复，单独提交并复测）**

```bash
git log --oneline -10
```

预期：阶段 2/1/3 各提交均在，工作区仅剩并行会话产物。

---

## 规格覆盖对照（自检）

| 规格章节 | 对应任务 |
|---|---|
| §5.1 llm_client 扩展（LLMError/tools/overrides/include_top_p/llm_stream_all/llm_text_completion） | L1 |
| §5.2 迁移矩阵（chat x3 / risk_assessment x3 / sync x2 / reranker x1 / generation 适配） | L2 / L3 / L4 / L5 / L6 |
| §5.3 base URL 与解密收敛（ai_config / sync / reranker 导入） | L6 / L4 / L5 |
| §5.4 阶段 1 测试 | L1-L6 各测试步骤 |
| §6.1 阶段 2 收尾（_get_plan_or_404 / _collect_batch_context / 内联 import） | B1 |
| §6.2 端点改造（守卫留在端点，内部逐字不动） | B1 步骤 5/6 |
| §6.3 阶段 2 测试（准备块 + 端点壳） | B1 / B2 |
| §7.1 死代码删除 | D1 |
| §7.2 委托样板收口（_delegate_generic） | D1 |
| §7.3 EnterpriseResponse 去重（5 合并 / 3 保留） | D2 |
| §7.4 chat_dispatch 黄金测试 | D1 / D3 |
| §3.2 验收 B（全量测试 + Docker 冒烟） | F |

## 计划自检记录

1. **规格覆盖度**：上表逐项对应，无遗漏；规格 §6.2「端点内部逐字不动」由 B1 步骤 5/6 的"run_background 保持逐字不变"落实。
2. **占位符扫描**：无 "待定/TODO/后续实现"；所有代码步骤均含完整代码或精确替换说明。
3. **类型一致性**：`_collect_batch_context` 返回 4 元组与 B1 测试解包一致；`_delegate_generic(op, db, user, args, cfg)` 在 D1 测试与实现中签名一致；`LLMError(status_code, text)` 在 L1-L6 所有测试与包装中用法一致；`llm_chat_completion` 的 `tools/payload_overrides/include_top_p` 关键字在 L1-L5 中一致。
4. **已知可接受差异（已写入任务）**：sync/reranker 迁移后 payload 多出 `stream: false` 键（OpenAI 兼容接口默认值，行为等价）；`ai_parse` 的 `logger.info` 从响应对象取值改为常量 200（仅日志，不影响业务）。
