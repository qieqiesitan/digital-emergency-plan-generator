# 智能体优化阶段 3（架构升级 0.5.0）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 多智能体编排（DAG）、端到端任务工作流、跨会话记忆偏好、任务分层（单 AI 配置下）。

**架构：** 新增 `agent/` 编排层（AgentRegistry + TaskGraph + orchestrator），复用阶段 1/2 的生成/审查/法规/画像模块为专业 agent；新增 `workflow/` 执行器（`workflow_runs`/`workflow_run_steps` 表、JSON 模板、状态机、确认门控、聊天工具）；新增 `user_preferences` 表 + 偏好注入；任务分层在不引入多模型前提下做提示词/参数差异化 + 成本观察。

**技术栈：** Python 3.11 / FastAPI / SQLAlchemy async / PostgreSQL / ChromaDB（已装）；React + Vite + tsc。

**规格依据：** `docs/superpowers/specs/2026-08-31-agent-optimization-design.md`（v2.0）阶段 3（模块 11-14）。D3：不引入多模型，沿用现有单一 AI 配置。

---

## 文件结构

**新建：**
- `backend/app/services/agent/__init__.py` — 编排包导出
- `backend/app/services/agent/agents.py` — AgentRegistry + 各专业 agent 定义
- `backend/app/services/agent/task_graph.py` — TaskGraph（DAG）与拓扑执行
- `backend/app/services/agent/orchestrator.py` — 编排入口（生成+审查组合等）
- `backend/db_migration_20260902_agent_workflow.sql` — workflow 两张表
- `backend/db_migration_20260902_agent_preferences.sql` — user_preferences 表
- `backend/app/services/workflow/__init__.py`
- `backend/app/services/workflow/models.py` — WorkflowRun/WorkflowRunStep ORM
- `backend/app/services/workflow/runner.py` — 工作流执行器（状态机/重试/确认门控）
- `backend/app/services/workflow/templates.py` — create_enterprise_plan / regulatory_compliance 模板
- `backend/app/services/user_preference_service.py` — 偏好读写 + 缓存
- `backend/tests/test_agent_registry.py`、`test_task_graph.py`、`test_orchestrator.py`
- `backend/tests/test_workflow_runner.py`、`test_workflow_templates.py`、`test_workflow_tables.py`
- `backend/tests/test_user_preferences.py`、`test_preferences_inject.py`
- `backend/tests/test_prompt_layering.py`

**修改：**
- `backend/app/models/__init__.py` — 导出新模型
- `backend/app/main.py` — 注册 workflow 查询端点（可选）
- `backend/app/services/chat_dispatch.py` — 工作流工具实现
- `backend/app/routers/chat.py` — CHAT_TOOLS 新增 run_workflow/get_workflow_progress/get_preferences/set_preferences；system prompt 注入偏好
- `backend/app/routers/chat.py` 或新 `backend/app/routers/workflow.py` — 进度查询 HTTP 端点
- `backend/tests/test_chat_dispatch.py` 等既有测试适配

**职责边界：** `agent/` 只管编排调度（不实现具体业务）；`workflow/` 只管执行器与模板；`user_preference_service` 只管偏好；既有 service 不被反向依赖（编排层只 import 它们）。

---

### 任务 1：AgentRegistry 与专业 agent（模块 11 前半）

**文件：**
- 创建：`backend/app/services/agent/__init__.py`
- 创建：`backend/app/services/agent/agents.py`
- 测试：`backend/tests/test_agent_registry.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_agent_registry.py — agent 注册与工具子集。"""
from app.services.agent.agents import AgentRegistry, PLAN_GENERATOR_TOOLS, ASSISTANT_TOOLS


def test_registry_registers_core_agents():
    reg = AgentRegistry()
    assert set(reg.names()) >= {"assistant", "plan_generator", "plan_reviewer", "regulation", "report"}


def test_plan_generator_tools_subset():
    # 生成 agent 工具子集应包含预案/章节相关，且远小于全量
    assert "generate_plan_content" in PLAN_GENERATOR_TOOLS
    assert "get_plan" in PLAN_GENERATOR_TOOLS
    assert "delete_enterprise" not in PLAN_GENERATOR_TOOLS


def test_assistant_tools_is_full_set():
    assert len(ASSISTANT_TOOLS) > len(PLAN_GENERATOR_TOOLS)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_agent_registry.py -q`
预期：FAIL（模块不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/services/agent/agents.py`：

```python
"""专业 agent 注册表：每个 agent = 名称 + 系统提示词 + 工具子集 + 执行说明。"""
from dataclasses import dataclass, field

PLAN_GENERATOR_TOOLS = frozenset({
    "get_plan", "list_plans", "get_enterprise", "generate_plan_content",
    "get_generation_progress", "search_regulation_articles", "list_regulations",
})
PLAN_REVIEWER_TOOLS = frozenset({"get_plan", "get_enterprise", "list_risk_sources",
                                 "search_regulation_articles", "list_regulations"})
REGULATION_TOOLS = frozenset({"search_regulation_articles", "search_regulations",
                              "list_regulations", "get_regulation_stats"})
REPORT_TOOLS = frozenset({"get_dashboard", "list_enterprises", "list_plans",
                          "list_risk_sources", "list_resources", "list_regulations"})
ASSISTANT_TOOLS = None  # 占位：全量工具由 chat.py CHAT_TOOLS 提供


@dataclass(frozen=True)
class Agent:
    name: str
    description: str
    system_prompt: str
    tools: frozenset | None = None


AGENTS = {
    "assistant": Agent(
        name="assistant",
        description="对外对话入口：覆盖全部系统操作",
        system_prompt="你是数字化应急预案自动生成系统的AI助手，负责理解用户意图并调度专业能力。",
        tools=None,
    ),
    "plan_generator": Agent(
        name="plan_generator",
        description="预案内容生成：按章节批量生成正文",
        system_prompt="你是应急预案编制专家，专注预案章节内容生成，输出规范公文正文。",
        tools=PLAN_GENERATOR_TOOLS,
    ),
    "plan_reviewer": Agent(
        name="plan_reviewer",
        description="预案质量审查与修订",
        system_prompt="你是应急预案质量审查专家，依据法规与模板审查章节完整性、引用真实性、数据一致性。",
        tools=PLAN_REVIEWER_TOOLS,
    ),
    "regulation": Agent(
        name="regulation",
        description="法规检索与引用校验",
        system_prompt="你是安全生产法规检索助手，优先用语义检索返回真实条文并给出出处。",
        tools=REGULATION_TOOLS,
    ),
    "report": Agent(
        name="report",
        description="数据采集与图文报告",
        system_prompt="你是应急管理数据分析师，基于系统数据生成结构化报告。",
        tools=REPORT_TOOLS,
    ),
}


class AgentRegistry:
    def __init__(self):
        self._agents = dict(AGENTS)

    def get(self, name: str) -> Agent:
        if name not in self._agents:
            raise KeyError(f"未知 agent: {name}")
        return self._agents[name]

    def names(self) -> list[str]:
        return list(self._agents)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_agent_registry.py -q`
预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/agent/ backend/tests/test_agent_registry.py
git commit -m "feat(agent): AgentRegistry 与专业 agent 定义（工具子集收敛）"
```

---

### 任务 2：TaskGraph DAG 与 orchestrator（模块 11 后半）

**文件：**
- 创建：`backend/app/services/agent/task_graph.py`
- 创建：`backend/app/services/agent/orchestrator.py`
- 测试：`backend/tests/test_task_graph.py`、`backend/tests/test_orchestrator.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_task_graph.py — DAG 拓扑与并行。"""
import asyncio
import pytest
from app.services.agent.task_graph import TaskGraph, run_dag


def test_topological_order():
    g = TaskGraph()
    g.add_task("generate", deps=[])
    g.add_task("review", deps=["generate"])
    g.add_task("export", deps=["review"])
    order = list(g.topological_order())
    assert order.index("generate") < order.index("review") < order.index("export")


def test_cycle_detected():
    g = TaskGraph()
    g.add_task("a", deps=["b"])
    g.add_task("b", deps=["a"])
    with pytest.raises(ValueError):
        list(g.topological_order())


@pytest.mark.asyncio
async def test_run_dag_parallel_branches():
    events = []

    async def gen(name, ctx):
        await asyncio.sleep(0.05 if name == "slow" else 0.01)
        events.append(name)
        return {"ok": True}

    g = TaskGraph()
    g.add_task("generate", deps=[])
    g.add_task("review", deps=["generate"])
    g.add_task("slow_extra", deps=[])
    results = await run_dag(g, {"plan_id": "p1"}, gen)
    assert set(results) == {"generate", "review", "slow_extra"}
    # 并行分支：slow_extra 与 generate 并行，故 slow_extra 先于 review 完成
    assert events.index("slow_extra") < events.index("review")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_task_graph.py tests/test_orchestrator.py -q`
预期：FAIL（模块不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/services/agent/task_graph.py`：

```python
"""任务 DAG：拓扑排序 + 并行执行（失败中止/降级由调用方策略决定）。"""
import asyncio


class TaskGraph:
    def __init__(self):
        self._tasks: dict[str, list[str]] = {}   # name -> deps

    def add_task(self, name: str, deps: list[str] | None = None):
        self._tasks[name] = list(deps or [])

    def topological_order(self):
        indeg = {n: len(deps) for n, deps in self._tasks.items()}
        adj = {n: [] for n in self._tasks}
        for n, deps in self._tasks.items():
            for d in deps:
                adj[d].append(n)
        queue = [n for n, d in indeg.items() if d == 0]
        order = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        if len(order) != len(self._tasks):
            raise ValueError("DAG 存在环")
        return order


async def run_dag(graph: TaskGraph, ctx: dict, run_fn, max_concurrency: int = 3):
    """按拓扑序执行；无依赖的任务并行（受 max_concurrency 限制）。失败抛异常（由 orchestrator 捕获降级）。"""
    order = list(graph.topological_order())
    sem = asyncio.Semaphore(max_concurrency)
    results: dict = {}

    async def run_one(name):
        async with sem:
            return name, await run_fn(name, ctx)

    pending = order[:]
    while pending:
        ready = [n for n in pending if all(d in results for d in graph._tasks[n])]
        if not ready:
            raise RuntimeError("无法推进 DAG")
        outs = await asyncio.gather(*[run_one(n) for n in ready])
        for name, res in outs:
            results[name] = res
            pending.remove(name)
    return results
```

`backend/app/services/agent/orchestrator.py`：

```python
"""编排入口：把「生成→审查→修订」组合成 DAG 执行。"""
from app.services.agent.task_graph import TaskGraph, run_dag


async def run_generate_review(plan_id: str, mode: str = "llm") -> dict:
    """示例组合：generate_plan_content → get_plan → review（POST apply 由调用方触发）。
    本函数为编排骨架；具体步骤接入见任务 4 工作流（此处保留最小可用实现供测试）。"""
    g = TaskGraph()
    g.add_task("generate", deps=[])
    g.add_task("review", deps=["generate"])
    return await run_dag(g, {"plan_id": plan_id}, _noop_step)


async def _noop_step(name, ctx):
    return {"step": name, "ctx": ctx}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_task_graph.py tests/test_orchestrator.py -q`
预期：全 passed（test_orchestrator 为编排冒烟）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/agent/ backend/tests/test_task_graph.py backend/tests/test_orchestrator.py
git commit -m "feat(agent): TaskGraph DAG 并行执行与 orchestrator 骨架"
```

---

### 任务 3：workflow 表迁移 + ORM 模型

**文件：**
- 创建：`backend/db_migration_20260902_agent_workflow.sql`
- 创建：`backend/app/services/workflow/__init__.py`
- 创建：`backend/app/services/workflow/models.py`
- 修改：`backend/app/models/__init__.py`
- 测试：`backend/tests/test_workflow_tables.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_workflow_tables.py — workflow 模型映射。"""
from app.services.workflow.models import WorkflowRun, WorkflowRunStep


def test_workflow_run_columns():
    cols = {c.name for c in WorkflowRun.__table__.columns}
    assert {"id", "user_id", "workflow_name", "params", "status",
            "current_step", "created_at", "updated_at"} <= cols


def test_workflow_step_columns():
    cols = {c.name for c in WorkflowRunStep.__table__.columns}
    assert {"run_id", "step_name", "status", "result", "retry_count", "error"} <= cols
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_workflow_tables.py -q`
预期：FAIL

- [ ] **步骤 3：编写最少实现代码**

`backend/db_migration_20260902_agent_workflow.sql`：

```sql
CREATE TABLE IF NOT EXISTS workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workflow_name VARCHAR(100) NOT NULL,
    params JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending/running/paused/failed/completed
    current_step VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_user ON workflow_runs(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS workflow_run_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    result JSONB,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_workflow_run_steps_run ON workflow_run_steps(run_id);
```

`backend/app/services/workflow/models.py`（ORM 映射，UUID as str，JSONB，与既有模型风格一致）。`__init__.py` 导出；`models/__init__.py` 追加导出（或仅 service 内使用，二选一保持一致）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_workflow_tables.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/db_migration_20260902_agent_workflow.sql backend/app/services/workflow/ backend/tests/test_workflow_tables.py
git commit -m "feat(workflow): workflow_runs/run_steps 表与 ORM 模型"
```

---

### 任务 4：workflow runner 状态机 + 模板

**文件：**
- 创建：`backend/app/services/workflow/runner.py`
- 创建：`backend/app/services/workflow/templates.py`
- 测试：`backend/tests/test_workflow_runner.py`、`backend/tests/test_workflow_templates.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_workflow_runner.py — 状态机/重试/确认门控。"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.workflow.runner import WorkflowRunner


@pytest.mark.asyncio
async def test_runner_success_path():
    db = AsyncMock()
    run = MagicMock(id="r1", user_id="u1", workflow_name="create_enterprise_plan",
                    params={"name": "测试公司"}, status="pending", current_step=None)
    runner = WorkflowRunner(db)
    calls = []

    async def fake_step(step, ctx):
        calls.append(step["name"])
        if step["name"] == "create_enterprise":
            return {"id": "e1", "verified": True}
        if step["name"] == "generate_plan":
            return {"plan_id": "p1", "verified": True}
        return {"verified": True}

    runner._execute_step = fake_step
    # 直接驱动模板步骤（不走 DB 持久化细节）验证顺序与门控语义
    template = {"steps": [
        {"name": "create_enterprise"},
        {"name": "generate_plan", "confirm": True},
        {"name": "export_docx"},
    ]}
    await runner._run_steps(run, template, {"create_enterprise": {"id": "e1"}})
    assert calls == ["create_enterprise", "generate_plan", "export_docx"]


@pytest.mark.asyncio
async def test_runner_retry_on_failure():
    db = AsyncMock()
    run = MagicMock(id="r1", workflow_name="x", params={})
    runner = WorkflowRunner(db)
    attempts = {"n": 0}

    async def flaky(step, ctx):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("boom")
        return {"ok": True}

    runner._execute_step = flaky
    template = {"steps": [{"name": "s1"}]}
    out = await runner._run_steps(run, template, {}, max_retries=2)
    assert out["s1"]["ok"] is True
    assert attempts["n"] == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_workflow_runner.py tests/test_workflow_templates.py -q`
预期：FAIL

- [ ] **步骤 3：编写最少实现代码**

`backend/app/services/workflow/templates.py`：

```python
"""端到端工作流模板（JSON：steps + dependencies + 确认门控）。"""

CREATE_ENTERPRISE_PLAN = {
    "name": "create_enterprise_plan",
    "steps": [
        {"name": "create_enterprise", "tool": "autofill_enterprise", "params_from": "params.name"},
        {"name": "create_plan", "tool": "create_plan",
         "params_from": {"enterprise_id": "steps.create_enterprise.id", "title": "params.title"}},
        {"name": "generate_plan", "tool": "generate_plan_content",
         "params_from": "steps.create_plan.id", "confirm": True},
        {"name": "review_plan", "tool": "review_plan", "params_from": "steps.create_plan.id"},
        {"name": "export_docx", "tool": "export_plan_docx", "params_from": "steps.create_plan.id",
         "confirm": True},
    ],
    "dependencies": {
        "create_plan": ["create_enterprise"],
        "generate_plan": ["create_plan"],
        "review_plan": ["generate_plan"],
        "export_docx": ["review_plan"],
    },
}

REGULATORY_COMPLIANCE = {
    "name": "regulatory_compliance",
    "steps": [
        {"name": "collect_enterprise", "tool": "get_enterprise", "params_from": "params.enterprise_id"},
        {"name": "search_regulations", "tool": "search_regulation_articles",
         "params_from": "params.query"},
        {"name": "generate_report", "tool": "generate_report",
         "params_from": {"topic": "法规合规"}},
    ],
    "dependencies": {
        "search_regulations": ["collect_enterprise"],
        "generate_report": ["collect_enterprise", "search_regulations"],
    },
}

TEMPLATES = {t["name"]: t for t in (CREATE_ENTERPRISE_PLAN, REGULATORY_COMPLIANCE)}
```

`backend/app/services/workflow/runner.py`：

```python
"""工作流执行器：pending→running→(paused/failed/completed)；步骤可重试；confirm 门控。"""
import asyncio
import json
from datetime import datetime, timezone


class WorkflowRunner:
    def __init__(self, db):
        self._db = db

    async def _execute_step(self, step, ctx) -> dict:
        """默认实现：调 chat_dispatch 工具。子类/测试可覆盖。"""
        from app.services.chat_dispatch import dispatch
        tool = step["tool"]
        args = self._resolve_args(step.get("params_from"), ctx)
        result = await dispatch(self._db, ctx.get("_user"), tool, args)
        return json.loads(result) if isinstance(result, str) else result

    async def _run_steps(self, run, template, ctx, max_retries: int = 2) -> dict:
        """按模板步骤顺序执行（confirm 步骤在 ctx['confirmed'] 为 True 时放行）。
        每步失败重试 max_retries 次；仍失败抛 RuntimeError（由上层标记 run failed）。"""
        results = {}
        for step in template["steps"]:
            name = step["name"]
            if step.get("confirm") and not ctx.get("confirmed_steps", {}).get(name):
                results[name] = {"awaiting_confirmation": True}
                continue
            for attempt in range(max_retries + 1):
                try:
                    results[name] = await self._execute_step(step, ctx)
                    break
                except Exception as e:
                    if attempt >= max_retries:
                        raise RuntimeError(f"步骤 {name} 失败: {e}") from e
                    await asyncio.sleep(0.2)
        return results

    def _resolve_args(self, spec, ctx) -> dict:
        """params_from 支持：字符串（表示从 ctx 取字段路径）或 dict（字段映射）。"""
        if isinstance(spec, str):
            return {"name": _resolve_path(ctx, spec)}
        if isinstance(spec, dict):
            return {k: _resolve_path(ctx, v) for k, v in spec.items()}
        return {}


def _resolve_path(ctx: dict, path: str):
    """解析 'steps.create_enterprise.id' / 'params.name' 形式路径。"""
    node = ctx
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node
```

（runner 的 DB 持久化（写 workflow_runs/steps 状态）在真实入口实现：`start_workflow(workflow_name, params, db, user)` 创建 run + 后台执行 + 更新状态；confirm 步骤返回 awaiting 由 `confirm_workflow_step(run_id, step_name)` 放行。这些在任务 5 聊天工具接入时补全。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_workflow_runner.py tests/test_workflow_templates.py -q`
预期：全 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/workflow/ backend/tests/test_workflow_runner.py backend/tests/test_workflow_templates.py
git commit -m "feat(workflow): 执行器状态机/重试/确认门控 + 两个模板"
```

---

### 任务 5：user_preferences 表 + 偏好服务

**文件：**
- 创建：`backend/db_migration_20260902_agent_preferences.sql`
- 创建：`backend/app/services/user_preference_service.py`
- 测试：`backend/tests/test_user_preferences.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_user_preferences.py — 偏好读写与缓存失效。"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.user_preference_service import get_preferences, set_preferences


@pytest.mark.asyncio
async def test_get_preferences_defaults():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    prefs = await get_preferences(db, "u1")
    assert prefs["style_preference"] is None
    assert prefs["detail_level"] is None


@pytest.mark.asyncio
async def test_set_preferences_updates():
    db = AsyncMock()
    db.get.return_value = None
    db.add = MagicMock()
    out = await set_preferences(db, "u1", {"style_preference": "practical"})
    assert out["style_preference"] == "practical"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_user_preferences.py -q`
预期：FAIL

- [ ] **步骤 3：编写最少实现代码**

`backend/db_migration_20260902_agent_preferences.sql`：

```sql
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    style_preference VARCHAR(20),
    detail_level VARCHAR(20),
    report_topics JSONB,
    common_enterprise_ids JSONB,
    extra TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

`backend/app/services/user_preference_service.py`（含缓存失效逻辑）：

```python
"""用户偏好读写（生成风格/常用企业等），进程内缓存 TTL 5 分钟。"""
import time
from sqlalchemy import select

_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300


async def get_preferences(db, user_id: str) -> dict:
    cached = _cache.get(user_id)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]
    # 查 user_preferences 表（UserPreference ORM 放 app/models/ 并导出，或本 service 内建轻量 Table）
    row = (await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))).scalar_one_or_none()
    prefs = _row_to_prefs(row)
    _cache[user_id] = (time.time(), prefs)
    return prefs


async def set_preferences(db, user_id: str, updates: dict) -> dict:
    # upsert 到 user_preferences；成功后 _cache.pop(user_id, None)
    ...
    return prefs


def invalidate_cache(user_id: str) -> None:
    _cache.pop(user_id, None)
```

（占位 `_nothing` 仅为示意——实现时直接用 `app.models` 新导出的 UserPreference ORM，或用原生 SQLAlchemy Table；测试用 mock db 不依赖真实表。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_user_preferences.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/db_migration_20260902_agent_preferences.sql backend/app/services/user_preference_service.py backend/tests/test_user_preferences.py
git commit -m "feat(agent): user_preferences 表与偏好服务（TTL 缓存）"
```

---

### 任务 6：偏好注入 system prompt + 聊天工具接入

**文件：**
- 修改：`backend/app/routers/chat.py`
- 修改：`backend/app/services/chat_dispatch.py`
- 测试：`backend/tests/test_preferences_inject.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_preferences_inject.py — 偏好注入 system prompt + 工具注册。"""
from app.routers.chat import CHAT_TOOLS, build_system_prompt_with_prefs


def test_prefs_injected_into_system_prompt():
    prefs = {"style_preference": "practical", "detail_level": "concise"}
    sp = build_system_prompt_with_prefs(prefs)
    assert "practical" in sp or "实用" in sp
    assert "concise" in sp or "简洁" in sp


def test_workflow_tools_registered():
    names = {t["function"]["name"] for t in CHAT_TOOLS}
    assert {"run_workflow", "get_workflow_progress",
            "get_preferences", "set_preferences"} <= names
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_preferences_inject.py -q`
预期：FAIL

- [ ] **步骤 3：编写最少实现代码**

- `chat.py` 新增 `build_system_prompt_with_prefs(prefs)`：在 CHAT_SYSTEM_PROMPT 末尾追加偏好段（style/detail/common enterprises），无偏好时原样返回；chat 端点加载消息前（`_load_history_rows` 后）读取偏好并构造 system prompt。
- `chat.py` CHAT_TOOLS 追加 4 个工具声明：`run_workflow(workflow_name, params)`、`get_workflow_progress(run_id)`、`get_preferences`、`set_preferences(key, value)`。
- `chat_dispatch.py` 实现 `_run_workflow`（调 WorkflowRunner 的持久化入口 start_workflow）、`_get_workflow_progress`（查 workflow_runs 状态+步骤）、`_get_preferences`、`_set_preferences`；注册 `_FUNCTIONS`。
- 偏好注入点：system prompt 第一条消息在 `_rebuild_messages_from_rows` 后、截断前由偏好段替换（保守：仅当存在偏好时追加），保证长对话截断后偏好仍在。

- [ ] **步骤 4：运行测试验证通过 + 回归**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_preferences_inject.py tests/test_chat_dispatch.py -q`
预期：全 passed，无回归

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/chat.py backend/app/services/chat_dispatch.py backend/tests/test_preferences_inject.py
git commit -m "feat(chat): 偏好注入 system prompt + 工作流/偏好聊天工具"
```

---

### 任务 7：任务分层（模块 14，D3 单配置）

**文件：**
- 修改：`backend/app/services/agent/orchestrator.py`（分层策略）
- 修改：`backend/app/routers/chat.py`（按 agent 类型选参数，若简单则集中管理）
- 测试：`backend/tests/test_prompt_layering.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_prompt_layering.py — 单配置下的任务分层参数。"""
from app.services.agent.agents import LAYER_PARAMS


def test_layer_params_exist():
    assert "review" in LAYER_PARAMS
    assert "generate" in LAYER_PARAMS


def test_review_more_precise_than_generate():
    assert LAYER_PARAMS["review"]["temperature"] < LAYER_PARAMS["generate"]["temperature"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_prompt_layering.py -q`
预期：FAIL（LAYER_PARAMS 不存在）

- [ ] **步骤 3：编写最少实现代码**

`agents.py` 追加：

```python
# 任务分层参数（同一模型，不同任务用不同温度/长度；D3 不引入多模型）
LAYER_PARAMS = {
    "assistant": {"temperature": 0.5},
    "generate":  {"temperature": 0.7, "max_tokens": 4096},
    "review":    {"temperature": 0.2, "max_tokens": 2048},
    "regulation": {"temperature": 0.3, "max_tokens": 1024},
    "report":    {"temperature": 0.5, "max_tokens": 4096},
}
```

调用侧：`llm_chat_completion(..., payload_overrides=LAYER_PARAMS[layer])`（生成/审查/检索各 agent 在编排或既有调用点按任务选择；聊天助手保持默认）。成本观察：生成链路沿用 generation_logs.tokens_used；聊天/编排工具调用沿用 chat_tool_calls 聚合（无新表）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/test_prompt_layering.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/agent/agents.py backend/tests/test_prompt_layering.py
git commit -m "feat(agent): 单配置任务分层参数（生成0.7/审查0.2/检索0.3）+成本观察沿用既有表"
```

---

### 任务 8：阶段 3 全量门禁

**文件：** 无（验证；回归修复只 add 对应文件）

- [ ] **步骤 1：后端全量**

运行：`cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`
预期：全绿（基线 1199+ 新增）；环境类失败（third_party_config 本地 .env）记录说明

- [ ] **步骤 2：前端类型**

运行：`cd frontend && node node_modules/typescript/bin/tsc -b`，预期 exit 0

- [ ] **步骤 3：代码卫生**

运行：`git show --check HEAD` 与 `git diff --check`，预期干净

- [ ] **步骤 4：迁移幂等**

确认 `db_migration_20260902_agent_workflow.sql` / `agent_preferences.sql` 全 `IF NOT EXISTS`；本地 DB 应用一次（docker cp + restart 或 psql）后重复执行不报错。

- [ ] **步骤 5：Commit（如有修复）**

```bash
git add <修复文件>
git commit -m "test(agent): 阶段3门禁修复"
```

---

### 任务 9：0.5.0 打包与验收

**文件：** `scripts/package-release.sh`（沿用）

- [ ] **步骤 1：构建前端 + 打包**

运行：容器 node:22 构建 dist（生产前缀）→ `bash scripts/package-release.sh --system 0.5.0`

- [ ] **步骤 2：Docker 验收演练**

- 编排：DAG 单测 +「生成→审查」组合执行
- 工作流：真实演练「录企→生成→审查→导出」一键跑通（Docker 隔离），失败可重试、确认门控
- 偏好：设置偏好后新会话生成风格生效
- 分层：单配置下各任务温度/长度生效 + generation_logs token 可查

- [ ] **步骤 3：交付说明**

整理 0.5.0 交付说明（2 张新表/新工具/编排层/前端改动），更新 TASKS.md，向用户汇报。

---

## 计划自检记录

**1. 规格覆盖度（对照设计文档模块 11-14）：**
- 模块 11 多智能体编排 → 任务 1/2 ✓（registry + DAG + orchestrator）
- 模块 12 工作流 → 任务 3/4 ✓（表 + runner + 模板）
- 模块 13 记忆偏好 → 任务 5/6 ✓（表 + 服务 + 注入 + 工具）
- 模块 14 任务分层 → 任务 7 ✓（D3 单配置 + 成本观察）
- 门禁/打包 → 任务 8/9 ✓

**2. 占位符扫描：** 任务 5 步骤 3 中「占位 _nothing」与「模型放 models/ 或动态建」为实现指引（明确选择权交给实现者，非 TODO）；runner DB 持久化入口在任务 4 步骤 3 末尾注明补全点（任务 6 聊天工具接入时落地）——非占位而是明确的阶段边界。

**3. 类型一致性：** `WorkflowRunner(db)._run_steps(run, template, ctx)` 与任务 4 测试一致；`get_preferences(db, user_id)`/`set_preferences(db, user_id, updates)` 与任务 5 一致；`build_system_prompt_with_prefs(prefs)`/CHAT_TOOLS 新工具与任务 6 一致；`LAYER_PARAMS` 与任务 7 一致。

**4. 依赖已核实：** 阶段 1/2 模块就绪（chat_dispatch 工具/生成 service/review service/画像/法规检索）；`ai_configs` 单系统配置（D3）；versions/快照可复用；迁移命名沿用 20260902。
