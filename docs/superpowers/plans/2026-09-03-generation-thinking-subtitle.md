# 预案生成“思考要点字幕”实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在预案章节生成期间，把模型推理阶段实时转化为聊天式“思考要点字幕”展示在桌面/移动端，并让移动端批量轮询获得阶段、进度与要点。

**架构：** llm_client 流式响应新增可选 `reasoning_cb`（不破坏现有调用契约）；generation 层新增轻量“切句→要点筛选→截断→节流”的纯函数加工；SSE 入口新增 `thinking` 事件，后台/聊天批量在服务层自动把阶段状态写入进程内 `generation_progress` 供轮询；推理内容只存内存、结束即清。

**技术栈：** Python 3.12 / FastAPI / asyncio / httpx / SSE（sse-starlette）、React 18 + TypeScript（桌面 AntD、移动自绘组件）、pytest、vitest/tsc。

---

## 环境与验证说明（所有任务共用）

- 后端代码在 `backend/app`，测试在 `backend/tests`。运行中的容器 `emergency-plan-backend` 以 bind mount 挂载 `backend/app:/app/app`，但测试目录是镜像快照；新增/修改测试文件后需先拷入容器再运行：

```bash
docker cp backend/tests/<file>.py emergency-plan-backend:/app/tests/<file>.py
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/<file>.py
```

- 前端类型检查在 `emergency-plan-frontend` 容器内执行（`src` 已挂载）：

```bash
docker exec emergency-plan-frontend node node_modules/typescript/bin/tsc -b
```

- 每任务 commit 只 add 该任务涉及文件；**绝不 add** TASKS.md、.gitignore、graph.json、scripts/、backend/uploads 删除等他人/既有改动。不 push。
- 工作区不执行 `git save`（会 add -A 混入他人改动），每个任务提交即保存点。

---

## 文件结构

- 新建 `backend/app/services/thinking_brief.py`：推理文本→要点句加工（切句/筛选/截断/去重/节流）。
- 新建 `backend/app/services/generation_progress.py`：进程内按 plan_id 的生成状态读写清理。
- 修改 `backend/app/services/llm_client.py`：流式响应读取 `reasoning_content` 并通过可选 `reasoning_cb` 回调。
- 修改 `backend/app/routers/generation.py`：流式辅助函数透传 `reasoning_cb`；单章 SSE 增加 `thinking` 事件；批量 SSE 的 `sse_stream` 推送 `thinking`；status 端点返回阶段字段。
- 修改 `backend/app/services/plan_generation_service.py`：默认分支（后台/聊天批量）改为内部流式收集，自动维护 generation_progress。
- 修改 `backend/app/routers/risk_assessment.py` 与 `backend/app/routers/resource_investigation.py`：报告逐章生成输出 `thinking` 事件（范围扩展）。
- 前端：`frontend/src/types/plan.ts`、`frontend/src/services/generationService.ts`、`frontend/src/pages/Plan/PlanEditorPage.tsx`、`frontend/src/components/plan/AIGenerateButton.tsx`、`frontend/src/mobile/screens/PlanEditorScreen.tsx`。
- 前端（范围扩展）：`frontend/src/types/riskAssessment.ts`、`frontend/src/components/report/ReportWorkspace.tsx`（桌面两 Tab 的薄包装，SSE 在 Workspace 内）、`frontend/src/mobile/screens/RiskAssessmentScreen.tsx`、`frontend/src/mobile/screens/ResourceInvestigationScreen.tsx`。
- 新增测试：`backend/tests/test_thinking_brief.py`、`backend/tests/test_generation_progress.py`、`backend/tests/test_llm_reasoning_cb.py`、`backend/tests/test_generation_thinking_stream.py`（部分）。
- 新增测试（范围扩展）：`backend/tests/test_report_thinking.py`。

> **2026-09-07 修订**：报告侧代码已重构（ReportWorkspace、章节级端点、单章共用生成器）。任务 12–14 的落点以修订注为准；桌面字幕 UI 实际修改 `components/report/ReportWorkspace.tsx`（两处 SSE switch），Tab 文件只是薄包装。`backend/app/routers/risk_assessment.py` 存在他人未提交改动（章节摘要重建/四色图兜底）——执行报告任务前先让用户提交或 stash 该文件，或用 `git add -p` 只暂存本任务 hunk，严禁混提。

---

### 任务 1：thinking_brief 核心加工（纯函数）

**文件：**
- 创建：`backend/app/services/thinking_brief.py`
- 测试：`backend/tests/test_thinking_brief.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_thinking_brief.py"""
from app.services.thinking_brief import (
    ThinkingBriefBuffer, is_key_point, split_sentences, truncate_brief,
)


def test_split_sentences_splits_on_chinese_punctuation_and_newline():
    text = "第一句。第二句！\n第三句？"
    assert split_sentences(text) == ["第一句", "第二句", "第三句"]


def test_is_key_point_requires_reasonable_length_and_keyword():
    assert is_key_point("需要结合火灾风险源分布确定处置分工")
    assert not is_key_point("嗯")
    assert not is_key_point("这是一个没有关键词但长度足够凑数的普通句子内容")


def test_truncate_brief_keeps_max_chars_with_ellipsis():
    sentence = "结合火灾风险源分布与应急组织架构确定报警与初起处置分工以及信息报告要素"
    out = truncate_brief(sentence, max_chars=20)
    assert out.endswith("…")


def test_buffer_returns_newest_key_point_once():
    buf = ThinkingBriefBuffer()
    out1 = buf.feed("需要结合火灾风险源分布确定分工。其次考虑组织架构。")
    assert out1 is not None and "风险源" in out1
    assert buf.feed("需要结合火灾风险源分布确定分工。") is None


def test_buffer_returns_none_without_key_point():
    buf = ThinkingBriefBuffer()
    assert buf.feed("嗯嗯好的。") is None
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_thinking_brief.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_thinking_brief.py`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.thinking_brief'`

- [ ] **步骤 3：编写最少实现代码**

```python
"""思考要点加工：切句、筛选、截断、去重。仅供内存实时展示，不落库。"""
import re

_KEY_WORDS = (
    "分析", "结合", "需要", "根据", "确保", "考虑", "风险", "资源",
    "组织", "疏散", "法规", "火灾", "事故", "处置", "报告", "检查",
)
_SENTENCE_END = re.compile(r"[。！？!?；;\n]+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text or "") if s.strip()]


def is_key_point(sentence: str) -> bool:
    return 8 <= len(sentence) <= 60 and any(k in sentence for k in _KEY_WORDS)


def truncate_brief(sentence: str, max_chars: int = 40) -> str:
    sentence = (sentence or "").strip()
    if len(sentence) <= max_chars:
        return sentence
    return sentence[:max_chars].rstrip() + "…"


class ThinkingBriefBuffer:
    """累积一段推理文本，产出“最新一条尚未展示过的要点句”。"""

    def __init__(self, max_chars: int = 40):
        self._buffer = ""
        self._shown: set[str] = set()
        self._max_chars = max_chars

    def feed(self, piece: str) -> str | None:
        self._buffer += piece or ""
        parts = split_sentences(self._buffer)
        if not parts:
            return None
        if not self._buffer.rstrip().endswith(("。", "！", "？", "!", "?", "；", ";")):
            self._buffer = parts.pop()
        else:
            self._buffer = ""
        for sentence in reversed(parts):
            if is_key_point(sentence) and sentence not in self._shown:
                self._shown.add(sentence)
                return truncate_brief(sentence, self._max_chars)
        return None
```

- [ ] **步骤 4：运行测试验证通过**

运行：同步骤 2 命令
预期：PASS（5 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/thinking_brief.py backend/tests/test_thinking_brief.py
git commit -m "feat(gen): 思考要点切句筛选与去重加工模块"
```

---

### 任务 2：CaptionThrottle 节流（可注入时钟）

**文件：**
- 修改：`backend/app/services/thinking_brief.py`
- 测试：`backend/tests/test_thinking_brief.py`

- [ ] **步骤 1：追加失败的测试**

```python
from app.services.thinking_brief import CaptionThrottle


def test_caption_throttle_respects_min_interval():
    clock = {"now": 100.0}
    throttle = CaptionThrottle("发现事故第一响应", min_interval=1.5, now=lambda: clock["now"])
    assert throttle.push("需要结合火灾风险源分布确定分工。") is not None
    clock["now"] += 0.5
    assert throttle.push("其次考虑组织架构中的分工。") is None
    clock["now"] += 1.1
    assert throttle.push("其次考虑组织架构中的分工。") is not None


def test_caption_throttle_falls_back_when_no_key_point():
    throttle = CaptionThrottle("发现事故第一响应")
    assert throttle.push("嗯嗯。嗯嗯。") is None
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_thinking_brief.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_thinking_brief.py`
预期：FAIL，`ImportError: cannot import name 'CaptionThrottle'`

- [ ] **步骤 3：追加实现**

```python
import time as _time


def fallback_caption(section_title: str) -> str:
    return f"正在分析「{section_title or '本章'}」所需的企业风险与法规信息…"


class CaptionThrottle:
    """对要点句做 >=min_interval 秒的节流；无要点句时返回 None。"""

    def __init__(self, section_title: str, min_interval: float = 1.5,
                 now=None, max_chars: int = 40):
        self._buffer = ThinkingBriefBuffer(max_chars=max_chars)
        self._min_interval = min_interval
        self._now = now or _time.time
        self._last_emit: float | None = None
        self.section_title = section_title

    def push(self, piece: str) -> str | None:
        caption = self._buffer.feed(piece)
        if not caption:
            return None
        now = self._now()
        if self._last_emit is not None and now - self._last_emit < self._min_interval:
            return None
        self._last_emit = now
        return caption
```

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（7 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/thinking_brief.py backend/tests/test_thinking_brief.py
git commit -m "feat(gen): 思考要点字幕节流与兜底文案"
```

---

### 任务 3：generation_progress 进程内状态

**文件：**
- 创建：`backend/app/services/generation_progress.py`
- 测试：`backend/tests/test_generation_progress.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_generation_progress.py"""
from app.services import generation_progress as gp


def test_set_get_clear_roundtrip():
    gp.clear_progress("p1")
    assert gp.get_progress("p1") == {}
    gp.set_progress("p1", phase="thinking", section_key="sec_1", index=1, total=7)
    state = gp.get_progress("p1")
    assert state["phase"] == "thinking"
    assert state["section_key"] == "sec_1"
    assert state["index"] == 1 and state["total"] == 7
    assert "updated_at" in state
    gp.clear_progress("p1")
    assert gp.get_progress("p1") == {}


def test_set_merges_fields_and_refreshes_updated_at():
    gp.clear_progress("p1")
    gp.set_progress("p1", phase="thinking")
    first = gp.get_progress("p1")["updated_at"]
    gp.set_progress("p1", thinking_brief="要点")
    state = gp.get_progress("p1")
    assert state["phase"] == "thinking"
    assert state["thinking_brief"] == "要点"
    assert state["updated_at"] >= first
    gp.clear_progress("p1")
```

- [ ] **步骤 2：运行测试验证失败**

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.generation_progress'`

- [ ] **步骤 3：实现**

```python
"""预案生成进程内状态（keyed by plan_id）：仅供轮询，重启即失，不落库。"""
import time

_PROGRESS: dict[str, dict] = {}


def set_progress(plan_id: str, **fields) -> None:
    state = _PROGRESS.setdefault(plan_id, {})
    state.update(fields)
    state["updated_at"] = time.time()


def get_progress(plan_id: str) -> dict:
    return dict(_PROGRESS.get(plan_id) or {})


def clear_progress(plan_id: str) -> None:
    _PROGRESS.pop(plan_id, None)
```

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（2 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/generation_progress.py backend/tests/test_generation_progress.py
git commit -m "feat(gen): 生成进度进程内状态模块"
```

---

### 任务 4：llm_client 透传 reasoning_content

**文件：**
- 修改：`backend/app/services/llm_client.py`（`llm_chat_completion`、`_stream_response`）
- 测试：`backend/tests/test_llm_reasoning_cb.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_llm_reasoning_cb.py"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import llm_client


def test_delta_texts_extracts_reasoning_and_content():
    assert llm_client._delta_texts({"reasoning_content": "想", "content": "答"}) == ("想", "答")
    assert llm_client._delta_texts({}) == ("", "")


@pytest.mark.asyncio
async def test_llm_chat_completion_stream_passes_reasoning_cb(monkeypatch):
    captured = {}

    async def fake_stream(base, payload, ai_config, timeout=120, max_retries=2, reasoning_cb=None):
        captured["reasoning_cb"] = reasoning_cb
        return AsyncMock()

    monkeypatch.setattr(llm_client, "_stream_response", fake_stream)
    cb = lambda piece: None
    await llm_client.llm_chat_completion(
        [{"role": "user", "content": "hi"}],
        MagicMock(provider="x", model_name="m", temperature=0.7, max_tokens=512, top_p=1),
        stream=True, reasoning_cb=cb,
    )
    assert captured["reasoning_cb"] is cb
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_llm_reasoning_cb.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_llm_reasoning_cb.py`
预期：FAIL，`TypeError: llm_chat_completion() got an unexpected keyword argument 'reasoning_cb'`

- [ ] **步骤 3：实现**

在 `llm_client.py` 增加纯函数：

```python
def _delta_texts(delta: dict) -> tuple[str, str]:
    """从 SSE delta 提取 (reasoning_content, content)。"""
    delta = delta or {}
    return delta.get("reasoning_content") or "", delta.get("content") or ""
```

`llm_chat_completion` 签名增加 `reasoning_cb=None`，流式分支改为：

```python
    if stream:
        return _stream_response(base, payload, ai_config, timeout, reasoning_cb=reasoning_cb)
```

`_stream_response` 签名增加 `reasoning_cb=None`，流循环中 delta 处理改为：

```python
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            reasoning, content = _delta_texts(delta)
                            if reasoning and reasoning_cb:
                                try:
                                    reasoning_cb(reasoning)
                                except Exception:
                                    logger.exception("reasoning_cb failed")
                            if content:
                                yield content
```

替换原有 `content = delta.get("content", "")` 逻辑；`_delta_texts` 放在 `_stream_response` 之前。

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（2 passed）；随后跑既有 llm 相关回归：

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_chat_dispatch.py tests/test_generation_batch_refactor.py
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/llm_client.py backend/tests/test_llm_reasoning_cb.py
git commit -m "feat(llm): 流式响应透传 reasoning_content 回调"
```

---

### 任务 5：generation.py 流式辅助函数支持 reasoning_cb

**文件：**
- 修改：`backend/app/routers/generation.py`（`_stream_llm_chunks`、`_stream_llm_chunks_with_retry`）
- 测试：`backend/tests/test_generation_thinking_stream.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""test_generation_thinking_stream.py"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers import generation as gen


@pytest.mark.asyncio
async def test_stream_llm_chunks_forwards_reasoning_cb(monkeypatch):
    captured = {}

    async def fake_completion(messages, ai_config, stream=True, timeout=120,
                              payload_overrides=None, reasoning_cb=None):
        captured["reasoning_cb"] = reasoning_cb

        async def _gen():
            yield "正文"

        return _gen()

    monkeypatch.setattr(gen, "llm_chat_completion", fake_completion)
    cb = lambda piece: None
    chunks = []
    async for c in gen._stream_llm_chunks("p", MagicMock(), reasoning_cb=cb):
        chunks.append(c)
    assert chunks == ["正文"]
    assert captured["reasoning_cb"] is cb


@pytest.mark.asyncio
async def test_collect_stream_text_concatenates_chunks(monkeypatch):
    calls = {"n": 0}

    async def fake_chunks(prompt, ai_config, plan_type="*", style_preference=None,
                          advanced_overrides=None, payload_overrides=None, reasoning_cb=None):
        calls["n"] += 1
        for piece in ("<p>一", "段</p>"):
            yield piece

    monkeypatch.setattr(gen, "_stream_llm_chunks", fake_chunks)
    text = await gen._collect_stream_text("p", MagicMock(), "comprehensive")
    assert text == "<p>一段</p>"
    assert calls["n"] == 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_generation_thinking_stream.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_generation_thinking_stream.py`
预期：FAIL，`TypeError: _stream_llm_chunks() got an unexpected keyword argument 'reasoning_cb'` 与 `AttributeError: ... has no attribute '_collect_stream_text'`

- [ ] **步骤 3：实现**

`_stream_llm_chunks` 签名增加 `reasoning_cb=None`，两处 `llm_chat_completion` 调用追加 `reasoning_cb=reasoning_cb`。

`_stream_llm_chunks_with_retry` 签名增加 `reasoning_cb=None`，内部对 `_stream_llm_chunks` 的调用追加 `reasoning_cb=reasoning_cb`。

在 `_stream_llm_chunks_with_retry` 之后新增：

```python
async def _collect_stream_text(prompt: str, ai_config: AIConfig, plan_type: str = "*",
                               style_preference=None, advanced_overrides=None,
                               payload_overrides=None, reasoning_cb=None) -> str:
    """流式收集完整文本（不重试，重试由 run_batch_generation 负责）。"""
    full = ""
    async for chunk in _stream_llm_chunks(
        prompt, ai_config, plan_type, style_preference, advanced_overrides,
        payload_overrides=payload_overrides, reasoning_cb=reasoning_cb,
    ):
        full += chunk
    return full
```

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（2 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/generation.py backend/tests/test_generation_thinking_stream.py
git commit -m "feat(gen): 流式辅助函数支持推理回调并新增文本收集器"
```

---

### 任务 6：单章 SSE（generate_section）推送 thinking 事件

**文件：**
- 修改：`backend/app/routers/generation.py`（`generate_section` 的 `event_generator`）

- [ ] **步骤 1：改造 event_generator 为队列模式**

将 `event_generator` 中直接 `async for _stream_llm_chunks_with_retry` 的部分替换为“后台收集任务 + 事件队列”，保留原有落库与错误处理：

```python
            from app.services.thinking_brief import CaptionThrottle
            events: asyncio.Queue = asyncio.Queue()
            throttle = CaptionThrottle(s.title)

            def _on_reasoning(piece: str) -> None:
                caption = throttle.push(piece)
                if caption:
                    events.put_nowait(("thinking", caption))

            async def _run_stream() -> str:
                full = ""
                async for chunk_content in _stream_llm_chunks_with_retry(
                    prompt, _ai_cfg, p.plan_type, p.style_preference,
                    p.advanced_prompt_overrides, payload_overrides=LAYER_PARAMS["generate"],
                    reasoning_cb=_on_reasoning,
                ):
                    full += chunk_content
                    events.put_nowait(("chunk", chunk_content))
                events.put_nowait(("end", full))
                return full

            task = asyncio.create_task(_run_stream())
            full = ""
            while True:
                kind, payload = await events.get()
                if kind == "thinking":
                    yield sse_event("thinking", section_key=section_key, message=payload)
                elif kind == "chunk":
                    full += payload
                    yield sse_event("chunk", content=payload)
                elif kind == "end":
                    full = payload
                    break
            await task
```

> 原 `full = ""` 与 `async for` 循环删除；空值判断、独立 session 落库、错误回滚保持原样。

- [ ] **步骤 2：运行既有回归**

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_generation_batch_refactor.py tests/test_generation_thinking_stream.py
```
预期：PASS

- [ ] **步骤 3：Commit**

```bash
git add backend/app/routers/generation.py
git commit -m "feat(gen): 单章生成 SSE 推送思考要点事件"
```

---

### 任务 7：桌面批量 SSE（generate_batch）推送 thinking 事件

**文件：**
- 修改：`backend/app/routers/generation.py`（`generate_batch` 内 `sse_stream`）

- [ ] **步骤 1：修改 sse_stream**

在 `generate_batch` 的 `run_background` 中，为 `sse_stream` 增加节流器与推理回调，把要点作为 `thinking` 事件放入 `event_queue`：

```python
                caption_throttles: dict = {}

                def _make_on_reasoning(section_key: str, title: str):
                    def _on_reasoning(piece: str) -> None:
                        throttle = caption_throttles.get(section_key)
                        if throttle is None:
                            from app.services.thinking_brief import CaptionThrottle
                            throttle = CaptionThrottle(title)
                            caption_throttles[section_key] = throttle
                        caption = throttle.push(piece)
                        if caption:
                            event_queue.put_nowait(sse_event(
                                "thinking", section_key=section_key, message=caption,
                            ))
                    return _on_reasoning

                async def sse_stream(prompt, cfg, pt, sp, ao):
                    full = ""
                    key = section_key_holder.get("key")
                    title = section_key_holder.get("title", key)
                    on_reasoning = _make_on_reasoning(key, title)
                    try:
                        async for chunk in _stream_llm_chunks(
                            prompt, cfg, pt, sp, ao,
                            payload_overrides=LAYER_PARAMS["generate"],
                            reasoning_cb=on_reasoning,
                        ):
                            full += chunk
                            await event_queue.put(sse_event("chunk", content=chunk, section_key=key))
                        return full
                    except Exception as e:
                        await event_queue.put(sse_event(
                            "error", message=f"「{title}」生成失败: {e}", section_key=key,
                        ))
                        raise
```

> `run_batch_generation` 对 `stream_fn` 返回值的空值重试保持不变。

- [ ] **步骤 2：运行既有回归**

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_generation_batch_refactor.py tests/test_plan_generation_service.py tests/test_chat_generate_plan.py
```
预期：PASS

- [ ] **步骤 3：Commit**

```bash
git add backend/app/routers/generation.py
git commit -m "feat(gen): 桌面批量 SSE 推送思考要点事件"
```

---

### 任务 8：后台/聊天批量维护进程内进度

**文件：**
- 修改：`backend/app/services/plan_generation_service.py`（`run_batch_generation` 默认分支）
- 修改：`backend/app/routers/generation.py`（`get_generation_status`；`generate_batch_background` finally 清理）
- 测试：`backend/tests/test_generation_thinking_stream.py`

- [ ] **步骤 1：编写失败的测试**

```python
@pytest.mark.asyncio
async def test_run_batch_generation_default_branch_updates_progress(monkeypatch):
    from app.services import generation_progress as gp
    from app.services.plan_generation_service import run_batch_generation
    from app.routers import generation as gen

    gp.clear_progress("p-progress")
    bg_db = AsyncMock()
    sec1 = MagicMock()
    sec1.section_key = "sec_1"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [sec1]
    bg_db.execute.return_value = result

    async def fake_chunks(prompt, ai_config, plan_type="*", style_preference=None,
                          advanced_overrides=None, payload_overrides=None, reasoning_cb=None):
        if reasoning_cb:
            reasoning_cb("需要结合火灾风险源分布确定分工。")
        yield "<p>ok</p>"

    monkeypatch.setattr(gen, "_stream_llm_chunks", fake_chunks)
    monkeypatch.setattr(gen, "_build_section_prompt", lambda *a, **k: "prompt")
    monkeypatch.setattr(gen, "_collect_previous_context", lambda *a, **k: None)
    monkeypatch.setattr(gen, "_pre_render_mermaid_svgs", AsyncMock(return_value=[]))
    monkeypatch.setattr(gen, "_attach_diagrams", lambda *a, **k: None)

    await run_batch_generation(
        bg_db=bg_db, plan_id="p-progress",
        section_tuples=[("sec_1", "总则")], ai_config=MagicMock(), ent_data={},
        plan_type="comprehensive", use_section_number=False,
    )
    state = gp.get_progress("p-progress")
    assert state.get("section_key") == "sec_1"
    assert state.get("thinking_brief")
    gp.clear_progress("p-progress")
```

- [ ] **步骤 2：运行测试验证失败**

预期：FAIL（状态为空或 thinking_brief 为空）

- [ ] **步骤 3：实现**

在 `plan_generation_service.py` 的 `run_batch_generation` 函数内局部导入并维护状态：

```python
    from app.services import generation_progress as _gp
    from app.services.thinking_brief import CaptionThrottle
    from app.routers.generation import _collect_stream_text
```

`stream_fn is None` 分支改为内部流式收集：

```python
            async def _fetch_full():
                if stream_fn is None:
                    _gp.set_progress(
                        plan_id, phase="thinking", section_key=section_key,
                        section_title=section_title, index=i + 1,
                        total=len(section_tuples), thinking_brief=None,
                        started_at=__import__("time").time(),
                    )
                    throttle = CaptionThrottle(section_title)

                    def _on_reasoning(piece: str) -> None:
                        caption = throttle.push(piece)
                        if caption:
                            _gp.set_progress(plan_id, thinking_brief=caption)

                    return await _collect_stream_text(
                        prompt_text, ai_config, plan_type, style_preference,
                        advanced_overrides, payload_overrides=LAYER_PARAMS["generate"],
                        reasoning_cb=_on_reasoning,
                    )
                return await stream_fn(prompt_text, ai_config, plan_type, style_preference, advanced_overrides)
```

空返回自动重试逻辑保持不变（对 `_fetch_full()` 结果判空后重试一次）。

`get_generation_status` 增加阶段字段：

```python
    from app.services import generation_progress as _gp
    import time as _time
    state = _gp.get_progress(plan_id)
    return {
        "code": 0,
        "data": {
            "generating": _active_generations.get(plan_id, False),
            "failed_sections": _failed_sections.get(plan_id, []),
            "phase": state.get("phase", "idle"),
            "section_key": state.get("section_key"),
            "section_title": state.get("section_title"),
            "index": state.get("index"),
            "total": state.get("total"),
            "thinking_brief": state.get("thinking_brief"),
            "elapsed_seconds": int(_time.time() - state["started_at"]) if state.get("started_at") else None,
        },
    }
```

`generate_batch_background` 的 `run_background` finally 增加清理：

```python
        finally:
            _clear_generation_state(plan_id)
            from app.services import generation_progress as _gp
            _gp.clear_progress(plan_id)
```

- [ ] **步骤 4：运行测试验证通过**

预期：PASS；随后跑服务/聊天回归：

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_plan_generation_service.py tests/test_chat_generate_plan.py tests/test_generation_thinking_stream.py tests/test_generation_batch_refactor.py
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_generation_service.py backend/app/routers/generation.py backend/tests/test_generation_thinking_stream.py
git commit -m "feat(gen): 后台批量维护进程内阶段状态并扩展 status 接口"
```

---

### 任务 9：前端类型与桌面端字幕 UI

**文件：**
- 修改：`frontend/src/types/plan.ts`
- 修改：`frontend/src/services/generationService.ts`
- 修改：`frontend/src/pages/Plan/PlanEditorPage.tsx`
- 修改：`frontend/src/components/plan/AIGenerateButton.tsx`

- [ ] **步骤 1：类型与 service 扩展**

`types/plan.ts` 的 `SSEEventType` 增加 `"thinking"`；新增 `GenerationStatusData`：

```ts
export interface GenerationStatusData {
  generating: boolean;
  failed_sections: Array<{ section_key: string; title: string }>;
  phase?: "idle" | "thinking" | "writing" | "done";
  section_key?: string;
  section_title?: string;
  index?: number;
  total?: number;
  thinking_brief?: string;
  elapsed_seconds?: number;
}
```

`generationService.ts` 的 `getGenerationStatus` 返回类型改为 `Promise<{ code: number; data: GenerationStatusData }>`（并补充 `import type { GenerationStatusData } from "@/types/plan";`）。

- [ ] **步骤 2：PlanEditorPage 处理 thinking 事件并渲染**

新增状态 `const [thinkingText, setThinkingText] = useState("");`。

`generateBatchStream` 事件 switch 中，在 `case "progress"` 前增加：

```ts
case "thinking":
  if (event.message) setThinkingText(event.message);
  break;
```

在 `case "chunk"` 分支里 `setThinkingText("")`；在 `progress` 事件（新章节）`setThinkingText("")`；在 `batch_done`/`error`/停止时清空。

在批量进度 UI（显示 `batchProgress.message` 的位置）下方渲染：

```tsx
{thinkingText && (
  <div style={{ marginTop: 4, fontSize: 13, color: "#374151", lineHeight: 1.6 }}>
    {thinkingText}<span style={{ color: "#1a56db" }}>▌</span>
  </div>
)}
```

- [ ] **步骤 3：AIGenerateButton（桌面单章）显示字幕**

新增 `const [thinkingText, setThinkingText] = useState("");`。

`generateSectionStream` 回调 switch 中，在 `event.type === "chunk"` 判断前增加：

```ts
if (event.type === "thinking") {
  setThinkingText(event.message || "");
} else if (event.type === "chunk" && event.content) {
  setThinkingText("");
  ...
} else if (event.type === "done") {
  setThinkingText("");
  ...
}
```

在“生成中... 停止”按钮后渲染：

```tsx
{thinkingText && (
  <span style={{ marginLeft: 10, fontSize: 12, color: "#374151" }}>
    {thinkingText}
  </span>
)}
```

（selection 重写模式 `regenerateSelectionStream` 本期不加字幕。）

- [ ] **步骤 4：类型检查**

运行：`docker exec emergency-plan-frontend node node_modules/typescript/bin/tsc -b`
预期：exit 0

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/types/plan.ts frontend/src/services/generationService.ts frontend/src/pages/Plan/PlanEditorPage.tsx frontend/src/components/plan/AIGenerateButton.tsx
git commit -m "feat(frontend): 桌面端思考要点字幕展示"
```

---

### 任务 10：移动端单章字幕与批量轮询升级

**文件：**
- 修改：`frontend/src/mobile/screens/PlanEditorScreen.tsx`

- [ ] **步骤 1：单章 SSE 处理 thinking**

新增状态 `const [thinkingBrief, setThinkingBrief] = useState("");`。

`handleAIGenerate` 的 `onData` 中，在 `progress/chapter_start` 分支前增加：

```ts
if (event.type === "thinking") {
  setThinkingBrief(event.message || "");
} else if (event.type === "chunk" && (event.content || event.token || event.chunk)) {
  setThinkingBrief("");
  // 原有正文累积逻辑保持不变
}
```

在生成横幅下方渲染：

```tsx
{thinkingBrief ? (
  <div style={{ fontSize: 12, color: "#374151", marginTop: 4, lineHeight: 1.5 }}>
    {thinkingBrief}
  </div>
) : null}
```

在 `handleAIGenerate` 启动、`onComplete`、`onError`、`handleCancelGeneration` 中调用 `setThinkingBrief("")`。

- [ ] **步骤 2：批量轮询升级**

`pollGenerationStatus` 改为默认 `attempts = 200, intervalMs = 3000`，并在每次查询后更新字幕与阶段：

```ts
const pollGenerationStatus = useCallback(
  async (planId: string, attempts = 200, intervalMs = 3000) => {
    for (let i = 0; i < attempts; i++) {
      await new Promise((r) => setTimeout(r, intervalMs));
      try {
        const status = await getGenerationStatus(planId);
        const failed = status?.data?.failed_sections ?? [];
        setThinkingBrief(status?.data?.thinking_brief || "");
        const label = status?.data?.phase === "writing" ? "正在撰写" : "思考中";
        if (status?.data?.section_title) {
          setGenProgressMsg(
            `${status.data.index ?? ""}/${status.data.total ?? ""} · ${label} ${
              status.data.elapsed_seconds != null ? `${status.data.elapsed_seconds} 秒` : ""
            }`
          );
        }
        if (!status?.data?.generating || failed.length > 0) {
          setThinkingBrief("");
          setFailedSections(failed);
          return failed;
        }
      } catch {
        // 轮询失败继续尝试
      }
    }
    setThinkingBrief("");
    return [];
  },
  []
);
```

`runBatchGeneration` 中调用处不变（自动使用新默认参数）。

- [ ] **步骤 3：类型检查**

运行：`docker exec emergency-plan-frontend node node_modules/typescript/bin/tsc -b`
预期：exit 0

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/mobile/screens/PlanEditorScreen.tsx
git commit -m "feat(mobile): 单章思考字幕与批量 3 秒轮询"
```

---

### 任务 11：回归与真实验收（预案部分）

- [ ] **步骤 1：后端相关全量回归**

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_thinking_brief.py tests/test_generation_progress.py tests/test_llm_reasoning_cb.py tests/test_generation_thinking_stream.py tests/test_generation_batch_refactor.py tests/test_plan_generation_service.py tests/test_chat_generate_plan.py tests/test_prompt_layering.py tests/test_generation_enterprise_data.py tests/test_plan_review_routes.py tests/test_plan_review_service.py
```
预期：全部 PASS

- [ ] **步骤 2：前端类型与单测**

```bash
docker exec emergency-plan-frontend node node_modules/typescript/bin/tsc -b
docker exec emergency-plan-frontend npx vitest run 2>&1 | tail -5
```
预期：exit 0 / vitest PASS

- [ ] **步骤 3：重启后端并手动验收**

```bash
docker restart emergency-plan-backend
```

验收清单：
1. 桌面批量生成：思考期出现字幕、约 2 秒变化、写作开始消失、正文流式上屏。
2. 桌面单章 AI 生成：按钮旁出现字幕。
3. 移动端单章 AI 生成：横幅下出现字幕。
4. 移动端批量：3 秒轮询显示“2/7 · 思考中 N 秒”与字幕；长任务不再约 2 分钟静默放弃。
5. 后端日志无推理原文；`/generate/status` 在生成结束后返回 `phase` 为空/idle（内存已清）。

- [ ] **步骤 4：Commit（如有遗留修正）**

按修正涉及文件分别 commit，不混入他人改动。

---

### 任务 12：报告流共享事件辅助函数（risk_assessment.py）

**文件：**
- 修改：`backend/app/routers/risk_assessment.py`（`_stream_llm_with_messages_chunked` 增加 `reasoning_cb`；新增 `_stream_chapter_events`）
- 测试：`backend/tests/test_report_thinking.py`

> **2026-09-07 修订**：本任务内容不变。确认 `resource_investigation.py` 从 `app.routers.risk_assessment` 复用导入 `_stream_llm_with_messages_chunked`（若已改为本地定义，则在本地函数同步加 `reasoning_cb`）。risk_assessment.py 当前有他人未提交改动，按文件结构节顶部修订注处理后再开始。

- [ ] **步骤 1：编写失败的测试**

```python
"""test_report_thinking.py"""
from unittest.mock import MagicMock

import pytest

from app.routers import risk_assessment as ra
from app.services.thinking_brief import CaptionThrottle


@pytest.mark.asyncio
async def test_stream_chapter_events_emits_caption_then_chunks(monkeypatch):
    async def fake_chunked(messages, ai_config, reasoning_cb=None):
        if reasoning_cb:
            reasoning_cb("需要结合风险源分布确定辨识范围。")
        yield "第一段"
        yield "第二段"

    monkeypatch.setattr(ra, "_stream_llm_with_messages_chunked", fake_chunked)
    events = []
    async for kind, payload in ra._stream_chapter_events(
        [], MagicMock(), CaptionThrottle("风险辨识"), "ch1",
    ):
        events.append((kind, payload))
    kinds = [k for k, _ in events]
    assert kinds[0] == "thinking"
    assert "chunk" in kinds
    assert ("end", "第一段第二段") in events


@pytest.mark.asyncio
async def test_stream_chapter_events_propagates_error(monkeypatch):
    async def boom(messages, ai_config, reasoning_cb=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(ra, "_stream_llm_with_messages_chunked", boom)
    with pytest.raises(RuntimeError):
        async for _ in ra._stream_chapter_events(
            [], MagicMock(), CaptionThrottle("风险辨识"), "ch1",
        ):
            pass
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker cp backend/tests/test_report_thinking.py emergency-plan-backend:/app/tests/ && docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_report_thinking.py`
预期：FAIL，`AttributeError: ... has no attribute '_stream_chapter_events'`

- [ ] **步骤 3：实现**

`_stream_llm_with_messages_chunked` 签名增加 `reasoning_cb=None`，内部调用改为：

```python
        gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=120,
                                        reasoning_cb=reasoning_cb)
```

在其后新增：

```python
async def _stream_chapter_events(messages, ai_config, throttle, section_key):
    """逐章产出 ("thinking", caption) / ("chunk", text)；结束产出 ("end", full_text)。"""
    import asyncio as _asyncio

    events: _asyncio.Queue = _asyncio.Queue()

    def _on_reasoning(piece):
        caption = throttle.push(piece)
        if caption:
            events.put_nowait(("thinking", caption))

    async def _run():
        full = ""
        try:
            async for chunk in _stream_llm_with_messages_chunked(
                messages, ai_config, reasoning_cb=_on_reasoning,
            ):
                full += chunk
                events.put_nowait(("chunk", chunk))
            events.put_nowait(("end", full))
        except Exception as e:
            events.put_nowait(("error", e))

    task = _asyncio.create_task(_run())
    while True:
        kind, payload = await events.get()
        if kind == "error":
            await task
            raise payload
        yield kind, payload
        if kind == "end":
            await task
            return
```

- [ ] **步骤 4：运行测试验证通过**

预期：PASS（2 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/risk_assessment.py backend/tests/test_report_thinking.py
git commit -m "feat(report): 报告逐章事件队列支持推理要点"
```

---

### 任务 13：风险评估 / 资源调查 generate 端点输出 thinking 事件

**文件：**
- 修改：`backend/app/routers/risk_assessment.py`（`generate_risk_assessment` 逐章循环）
- 修改：`backend/app/routers/resource_investigation.py`（`generate_resource_investigation` 逐章循环，导入并复用 `_stream_chapter_events`）

> **2026-09-07 修订**：除两个“全量生成”逐章循环外，**同样替换**两个单章/重生成共用生成器（`_risk_section_event_generator`、`_ri_section_event_generator`）中的 `_stream_llm_with_messages_chunked` 流式循环——桌面 ReportWorkspace 的单章生成走的是 `generate/section` 端点（复用这两个生成器），必须一并覆盖。四处替换共用同一模式；全量循环保留现有的逐章落库（`_persist_*_generation`）、取消与错误处理代码不动。resource_investigation.py 若仍从 risk_assessment 导入 `_stream_llm_with_messages_chunked`，则 `_stream_chapter_events` 同样从 risk_assessment 导入。

- [ ] **步骤 1：替换两端点的逐章流式循环**

`risk_assessment.py` 的 `event_generator` 中，把：

```python
                ch_content = ""
                async for chunk_content in _stream_llm_with_messages_chunked(messages, ai_config):
                    ch_content += chunk_content
                    yield sse_event("chunk", content=chunk_content, section_key=ck)
```

替换为：

```python
                ch_content = ""
                from app.services.thinking_brief import CaptionThrottle
                async for ev_kind, ev_payload in _stream_chapter_events(
                    messages, ai_config, CaptionThrottle(ctitle), ck,
                ):
                    if ev_kind == "thinking":
                        yield sse_event("thinking", section_key=ck, message=ev_payload)
                    elif ev_kind == "chunk":
                        ch_content += ev_payload
                        yield sse_event("chunk", content=ev_payload, section_key=ck)
                    else:
                        ch_content = ev_payload or ch_content
```

`resource_investigation.py` 做同样替换，并在文件顶部导入追加：

```python
from app.routers.risk_assessment import _stream_chapter_events
```

（原 `_stream_llm_with_messages_chunked` 导入可保留，供其它调用使用。）

- [ ] **步骤 2：运行回归**

```bash
docker exec emergency-plan-backend python -m pytest -q -p no:cacheprovider tests/test_report_thinking.py tests/test_risk_assessment.py tests/test_resource_investigation.py
```

> 如容器内无对应测试文件，先 `docker cp backend/tests/<file>.py emergency-plan-backend:/app/tests/`。预期：PASS

- [ ] **步骤 3：Commit**

```bash
git add backend/app/routers/risk_assessment.py backend/app/routers/resource_investigation.py
git commit -m "feat(report): 两份报告逐章生成推送思考要点事件"
```

---

### 任务 14：报告前端（桌面 ReportWorkspace、移动 Screen ×2）展示字幕

**文件：**
- 修改：`frontend/src/types/riskAssessment.ts`
- 修改：`frontend/src/components/report/ReportWorkspace.tsx`（替代原 Tab 修改：全量生成 ~329-410 与单章生成 ~421-470 两处 SSE switch）
- 修改：`frontend/src/mobile/screens/RiskAssessmentScreen.tsx`
- 修改：`frontend/src/mobile/screens/ResourceInvestigationScreen.tsx`

> **2026-09-07 修订**：桌面 `RiskAssessmentTab.tsx` / `ResourceInvestigationTab.tsx` 已改为 ReportWorkspace 薄包装，不再直接处理 SSE；字幕 state、事件分支与渲染全部放在 `components/report/ReportWorkspace.tsx`。移动端两个 Screen 仍走全量 SSE，处理方式不变。`ReportWorkspace` 需要一处共享 `thinkingText` state：全量生成与单章生成的事件回调都更新它，`chunk/section_done/batch_done/done/error` 时清空；渲染插在批量进度 `batchProgress.message`（约 827-832 行）下方，单章生成时也可复用同区域/章节操作条附近。

- [ ] **步骤 1：类型扩展**

`types/riskAssessment.ts` 的 `SSEEvent.type` union 增加 `"thinking"`：

```ts
type: "progress" | "chunk" | "section_done" | "batch_done" | "error" | "token" | "chapter_start" | "chapter_end" | "done" | "complete" | "thinking";
```

- [ ] **步骤 2：桌面 Tab（RiskAssessmentTab / ResourceInvestigationTab）**

两个文件分别新增 `const [thinkingText, setThinkingText] = useState("");`，在 SSE switch 中：

```ts
case "thinking": {
  setThinkingText(event.message || "");
  break;
}
```

在 `case "chunk"` 与 `case "section_done"` 中 `setThinkingText("")`；`batch_done`/`error` 也清空。

在展示“批量生成进度/章节状态”的同一面板内（`batchProgress.message` 渲染处）下方插入：

```tsx
{thinkingText && (
  <div style={{ marginTop: 4, fontSize: 13, color: "#374151", lineHeight: 1.6 }}>
    {thinkingText}<span style={{ color: "#1a56db" }}>▌</span>
  </div>
)}
```

- [ ] **步骤 3：移动 Screen（RiskAssessmentScreen / ResourceInvestigationScreen）**

两个文件分别新增 `const [thinkingText, setThinkingText] = useState("");`，在 `onData` 回调的 `progress/chapter_start` 分支前增加：

```ts
if (event.type === "thinking") {
  setThinkingText(event.message || "");
} else if (event.type === "chunk" || event.type === "token") {
  setThinkingText("");
  // 原有正文累积逻辑保持不变
}
```

在进度文本与 `ProgressBar` 之间渲染：

```tsx
{thinkingText ? (
  <div style={{ fontSize: 12, color: "#374151", marginTop: 4, lineHeight: 1.5 }}>
    {thinkingText}
  </div>
) : null}
```

`done/complete/batch_done/error` 分支中调用 `setThinkingText("")`。

- [ ] **步骤 4：类型检查**

运行：`docker exec emergency-plan-frontend node node_modules/typescript/bin/tsc -b`
预期：exit 0

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/types/riskAssessment.ts frontend/src/pages/Enterprise/RiskAssessmentTab.tsx frontend/src/pages/Enterprise/ResourceInvestigationTab.tsx frontend/src/mobile/screens/RiskAssessmentScreen.tsx frontend/src/mobile/screens/ResourceInvestigationScreen.tsx
git commit -m "feat(frontend): 风险评估与资源调查报告思考字幕"
```

---

### 任务 15：回归与真实验收（含报告）

- [ ] **步骤 1：后端全量回归**

在任务 11 命令基础上追加 `tests/test_report_thinking.py`、`tests/test_risk_assessment.py`、`tests/test_resource_investigation.py`；预期全部 PASS。

- [ ] **步骤 2：前端类型与单测**

```bash
docker exec emergency-plan-frontend node node_modules/typescript/bin/tsc -b
docker exec emergency-plan-frontend npx vitest run 2>&1 | tail -5
```
预期：exit 0 / vitest PASS

- [ ] **步骤 3：重启后端并手动验收**

```bash
docker restart emergency-plan-backend
```

验收清单（新增）：
1. 桌面端企业详情 → 风险评估报告（ReportWorkspace）：全量“一键生成”与单章生成均出现思考字幕，约 2 秒更新，写作开始消失。
2. 桌面端应急资源调查报告（ReportWorkspace）同 1。
3. 移动端 RiskAssessmentScreen / ResourceInvestigationScreen 同 1。
4. 后端日志无推理原文。

- [ ] **步骤 4：Commit（如有遗留修正）**

按文件分别 commit，不混入他人改动。

---

## 自检结果

- 规格覆盖：范围（桌面批量/两端单章/移动批量）、字幕形态 v2、隐私 memory-only、轮询 3s/200 次、阶段兜底、SSE `thinking` 事件、generation_progress 与 status 扩展均有对应任务（任务 1-11）；范围扩展（风险评估/资源调查：全量循环 ×2 + 单章共用生成器 ×2、ReportWorkspace + 移动 Screen ×2）对应任务 12-15。
- 占位符：无 TODO/待定；代码变更步骤均含实际代码或精确 diff 说明。
- 类型一致性：`CaptionThrottle.push`、`ThinkingBriefBuffer.feed`、`_collect_stream_text`、`generation_progress.set/get/clear`、前端 `GenerationStatusData` 与 `thinking` 事件在任务间保持一致；`reasoning_cb` 全部为可选参数，默认 None。
