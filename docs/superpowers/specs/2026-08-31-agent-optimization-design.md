# 智能体优化三阶段设计（实现级规格）

> 版本：2.0 | 创建日期：2026-08-31 | 状态：待评审（按用户反馈细化到实现级）
> 范围：Chat AI 助手（chat.py / chat_dispatch.py）+ AI 生成引擎（llm_client / generation.py）+ 法规检索 + 前端聊天 UI（桌面 ChatPanel 与移动端 ChatScreen）

## 1. 背景与目标

系统智能体已有完整骨架：27 个 function-calling 工具、多模型适配生成引擎、法规知识图谱 + 已构建的 ChromaDB 向量库、QCC 企业工商自动填充。体检发现体验与能力均存在明确短板。用户确认按三阶段推进：

- **阶段 1 体验快赢（0.4.0）**：模块 1-6，修复聊天助手日常使用硬伤。
- **阶段 2 能力深化（0.4.1）**：模块 7-10，语义检索、自检修订、报告数据面、企业画像问答。
- **阶段 3 架构升级（0.5.0）**：模块 11-14，多智能体编排、任务工作流、记忆偏好、任务分层。

依赖链固定为 阶段1 → 阶段2 → 阶段3。每阶段独立交付、可独立上线。本规格为三阶段全部实现细节，阶段 2/3 详细设计在各自开工前按本规格直接执行。

## 2. 用户已确认的决策（决策记录）

| # | 决策 | 结论 |
|---|------|------|
| D1 | 新增 `chat_tool_calls` 表 | 接受 |
| D2 | 阶段 2 审查修订方式 | 自动执行修订 + 可回退 |
| D3 | 阶段 3 模型分层 | 不引入多模型/多 key，沿用现有单一 AI 配置（模块 14 按此修订） |

## 3. 现状盘点（代码级证据）

### 3.1 体验层缺陷

| 编号 | 缺陷 | 证据（文件:位置） |
|------|------|-------------------|
| E1 | 工具进度刷新后消失 | `frontend/src/pages/Chat/index.tsx`（桌面）与 `frontend/src/mobile/screens/ChatScreen.tsx`（移动端）均把 `progress` 事件拼进消息文本 buf；后端 `_save_messages` 只存最终文本 → 刷新后进度文本消失 |
| E2 | 工具串行执行 | `backend/app/routers/chat.py` agent_loop：`for tc in pending_tool_calls: await dispatch(...)`，同轮独立工具未并行 |
| E3 | LLM 调用无重试 | `backend/app/services/llm_client.py`：非 200 直接抛 `LLMError`，无退避重试 |
| E4 | 报告丢角色提示词 | `chat_dispatch._generate_report` 返回 `system_prompt`；`chat.py` report_prompt 分支仅用 `result_obj["prompt"]` 调 `_collect_llm` |
| E5 | 对话记忆过浅 | 桌面 `history.slice(-20)`（10 轮）/移动端 `slice(-10)`（5 轮）；`chat_messages` 不存工具轨迹，多轮任务衔接易失忆 |
| E6 | 聊天内生成预案半残 | `chat_dispatch._generate_plan_content` 仅置 `generating` 状态，要求用户去前端点按钮 |
| E7 | 5 轮上限硬错误 | `chat.py` `MAX_ROUNDS=5`，超限直接报错无部分成功汇报 |

### 3.2 能力层缺口

| 编号 | 缺口 | 证据 |
|------|------|------|
| C1 | 法规检索非语义 | `_search_regulation_articles` 用 `graph.list_nodes(keyword)` + 文件子串匹配；`vector_store.RegulationVectorStore` 已实现且 `data/chroma_db/` 已构建（chroma.sqlite3 + 向量文件），`regulations/__init__.py` 已导出 `get_vector_store`，聊天助手未接线 |
| C2 | 报告数据面窄 | `_generate_report` 仅收集 dashboard + 前 5 预案 + 前 5 企业 |
| C3 | 无生成后 AI 自检 | `plan_quality_service.check_plan` 为导出前规则检查；AI 生成后直接交付 |
| C4 | 无企业画像问答 | 用户需多步手动组合工具才能得到企业风险全景 |
| C5 | 无跨会话记忆/偏好 | 每次对话独立 |
| C6 | 27 工具无分层 | 所有任务同一模型同一提示词 |

### 3.3 可复用资产（已确认）

- `backend/requirements.txt` 含 `chromadb>=0.5.0`；`data/chroma_db/` 已构建。
- `generation.py` 已模块化：`_collect_batch_context`（720 行，读 request body 的 section_keys）、`_run_batch_generation`（760 行，接受 `bg_db` 独立 session，逐章生成/写库/失败统计，返回 `{"completed","failed","failed_sections"}`）、`_finalize_batch_result`（840 行，状态判定 + 版本快照）、`generate_batch_background`（1035 行，后台任务 + 事件队列 SSE 模式，`_background_tasks` 全局字典）。
- `chat_dispatch.py` 顶部已 `from app.regulations import get_graph, get_vector_store`。
- 前端 `chatService.ts` SSE 事件通道类型齐全（progress/chunk/function_result/error/done/conv_id）。
- 数据库表：`chat_conversations`、`chat_messages`（role 为 String(20)，当前值 user/assistant/function）；`ai_configs`（`get_system_ai_config` 返回单条 user_id IS NULL 且 is_system/is_active）。

## 4. 全局技术决策

### 4.1 数据库迁移清单

| 版本 | 迁移文件 | 内容 |
|------|----------|------|
| 0.4.0 | `backend/db_migration_20260831_agent_chat_tool_calls.sql` | 建 `chat_tool_calls` 表 + 索引 |
| 0.4.1 | （无新表；企业画像向量存 ChromaDB `enterprise_knowledge` collection） | — |
| 0.5.0 | `db_migration_2026xxxx_agent_workflow.sql` | 建 `workflow_runs`、`workflow_run_steps` 表 |
| 0.5.0 | `db_migration_2026xxxx_agent_preferences.sql` | 建 `user_preferences` 表 |

迁移沿用既有 migration_runner（advisory lock、幂等、失败阻断启动）；D1 已确认。

### 4.2 API 变更总表

| 版本 | 端点 | 变更 |
|------|------|------|
| 0.4.0 | `GET /chat/conversations/{conv_id}/tool-calls` | 新增：返回工具执行步骤（进度回放） |
| 0.4.0 | `GET /chat/conversations/{conv_id}/messages` | 响应 `MessageResponse` 增加 `name` 字段；返回行含 role=tool 的轨迹消息（前端过滤显示） |
| 0.4.0 | `POST /chat` | `ChatRequest.history` 降级为可选（后端以 DB 加载为准）；SSE `progress` 事件不再进入最终消息 |
| 0.4.0 | `POST /plans/{plan_id}/generate/batch` | 重构为调用抽取的 `plan_generation_service`，行为不变 |
| 0.4.0 | `POST /chat` 工具集 | `generate_plan_content` 改为触发真实后台生成；新增工具 `get_generation_progress(plan_id)` |
| 0.4.1 | `GET /plans/{plan_id}/review` | 新增：审查报告 |
| 0.4.1 | `POST /plans/{plan_id}/review/apply` | 新增：应用修订（含快照回退） |
| 0.4.1 | `POST /chat` 工具集 | 新增 `query_enterprise_knowledge(enterprise_id, question)` |
| 0.5.0 | `POST /chat` 工具集 | 新增 `run_workflow(workflow_name, params)`、`get_workflow_progress(run_id)` |

### 4.3 前端改动总表

| 版本 | 文件 | 改动 |
|------|------|------|
| 0.4.0 | `frontend/src/pages/Chat/index.tsx` | progress → 步骤时间线；加载 tool-calls 回放；过滤 tool 消息 |
| 0.4.0 | `frontend/src/mobile/screens/ChatScreen.tsx` | 同上（移动端） |
| 0.4.0 | `frontend/src/services/chatService.ts` | 新增 `fetchToolCalls`；`MessageResponse.name`；进度事件处理抽公共 |
| 0.4.1 | 预案编辑页（桌面/移动） | 展示审查报告 + 接受/回退修订入口 |
| 0.5.0 | 聊天页 | 工作流进度展示 |

### 4.4 错误处理与安全总则

- 工具执行失败不中断整轮：`dispatch` 返回 error JSON，agent 总结时说明失败项。
- 删除/覆盖类工具保留「先确认」规则；工作流的导出/删除步骤需用户确认。
- 所有权校验：所有按 enterprise_id 的查询沿用 `_verify_enterprise_ownership`；企业画像向量按 user_id 隔离。
- LLM 重试不重试 401（密钥错误）；流式中途失败不重试。
- 新表/新 API 沿用审计惯例（created_at/updated_at）。

### 4.5 测试门禁（每阶段通用）

- backend 全量 pytest 无回归；frontend `tsc -b` exit 0；`git show --check` 干净。
- 每模块先写失败用例（复现旧行为）→ 实现 → 转绿。
- 集成验证走 Docker 演练（沿用 0.3.x 的 e2e 模式，隔离项目名/端口/卷）。
- 打包验证沿用 `package-release.sh --system`。

## 5. 阶段 1：体验快赢（0.4.0）

### 5.1 模块 1：进度持久化 + 前端步骤条（修复 E1）

**改动文件**：新增 `backend/app/models/chat_tool_call.py`；改 `backend/app/routers/chat.py`、`backend/app/services/chat_dispatch.py`（可选打点）、`backend/app/routers/chat.py`（新端点）、`frontend/src/services/chatService.ts`、`frontend/src/pages/Chat/index.tsx`、`frontend/src/mobile/screens/ChatScreen.tsx`。

**数据模型**：

```sql
CREATE TABLE chat_tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    round_no INTEGER NOT NULL,
    fn_name VARCHAR(100) NOT NULL,
    fn_args JSONB,
    result TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running/success/error
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_chat_tool_calls_conv ON chat_tool_calls(conversation_id, created_at);
```

SQLAlchemy 模型 `ChatToolCall` 映射同构字段（UUID as str 与既有模型一致）。

**关键逻辑（chat.py agent_loop）**：

```
for round_no, tc in enumerate(pending_tool_calls, 1):
    rec = ChatToolCall(conversation_id=conv_id, round_no=round_no, fn_name=fn_name, fn_args=fn_args, status="running")
    db.add(rec); await db.commit()
    t0 = monotonic()
    result_str = await dispatch(db, user, fn_name, fn_args)   # 复用既有 db 串行路径（见模块 2）
    rec.status = "success" if '"error"' not in result_str[:80] else "error"
    rec.result = result_str[:4000]   # 截断防爆表
    rec.duration_ms = int((monotonic()-t0)*1000)
    await db.commit()
    # SSE 仍发 progress（语义改为「步骤提示」），但前端不拼入消息文本
```

SSE 增加 `tool_step` 事件类型（携带 fn_name/status/duration），前端步骤条消费；旧 `progress` 事件保留用于「正在生成第 i/N 章」类提示。

**新端点**：

```python
@router.get("/conversations/{conv_id}/tool-calls")
async def list_tool_calls(conv_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    # 校验 conversation 归属 → 按 created_at 升序返回
    # 返回 [{id, round_no, fn_name, status, duration_ms, created_at}]（result 可选参数化返回）
```

**前端步骤条**：消息流中 assistant 回复上方渲染步骤胶囊列表（✓ 查询企业 320ms / ✗ 生成章节 1200ms），数据源：本轮 SSE `tool_step` + 切换对话时 `fetchToolCalls` 回放。`progress`/`tool_step` 不再写入消息 content。

**测试用例**：
1. `test_agent_loop_records_tool_call`：mock dispatch 成功/失败，断言 chat_tool_calls 记录状态与耗时。
2. `test_tool_calls_endpoint_ownership`：非本人 conversation 返回 404。
3. `test_save_messages_excludes_progress`：最终消息不含 "[第N轮] 正在执行"。
4. 前端：SSE 收到 tool_step 渲染胶囊；切对话回放一致。

**验收标准**：真实对话中工具执行步骤实时可见；刷新/切对话后步骤条回放一致；消息区无进度文本残留。

### 5.2 模块 2：工具并行执行（修复 E2）

**约束**：请求级 `AsyncSession` 非并发安全 → 并行工具须独立 session；写操作保持串行保证顺序/幂等。

**改动文件**：`backend/app/routers/chat.py`、`backend/app/services/chat_dispatch.py`。

**关键逻辑**：

```python
READ_TOOLS = {"get_dashboard","list_enterprises","get_enterprise","list_risk_sources","list_resources",
              "list_plans","get_plan","list_templates","list_risk_assessments","get_risk_assessment",
              "list_resource_investigations","get_resource_investigation","get_regulation_stats",
              "list_regulations","search_regulations","search_regulation_articles","get_ai_config",
              "get_generation_progress"}   # 只读集合

# 同轮 pending_tool_calls 分组：读 → asyncio.gather(独立 session 调用)；写 → 串行（共享请求 db）
async def _run_tool_isolated(fn_name, fn_args, user_id):
    async with async_session() as sdb:
        user = await sdb.get(User, user_id)
        return await dispatch(sdb, user, fn_name, fn_args)
```

`dispatch` 签名不变；并行读工具各自独立 session；并行结果按原 tc 顺序归位（gather 返回顺序与传入一致）。写工具仍走请求级 `db` 串行，保证事务一致与确认语义。

**注意**：`chat_tool_calls` 记录（模块 1）使用请求级 db 串行写入，不受并行影响；每条工具记录在各自工具调用处写入。

**测试用例**：
1. `test_read_tools_run_in_parallel`：monkeypatch dispatch，断言同轮只读工具并发（gather 计数）且结果按序。
2. `test_write_tools_serial`：写工具无并发调用。
3. `test_parallel_tools_isolated_session`：两读工具各用独立 session，互不串扰（mock 计数 async_session 创建）。
4. 既有 29 工具全量回归（chat 相关测试）。

**验收标准**：同轮含 2 个以上只读工具时，端到端延迟明显下降（基准对比）；写操作行为与串行完全一致。

### 5.3 模块 3：LLM 调用重试（修复 E3）

**改动文件**：`backend/app/services/llm_client.py`。

**关键逻辑**：

```python
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

async def _post_with_retry(base, payload, headers, timeout, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200:
                return resp
            if resp.status_code not in RETRYABLE_STATUS or attempt == max_retries:
                raise LLMError(resp.status_code, resp.text)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            if attempt == max_retries:
                raise LLMError(0, str(e))   # 0 = 网络层失败（沿用现有文案兼容）
        delay = min(8, 2 ** attempt) + random.uniform(0, 0.5)
        await asyncio.sleep(delay)
    raise LLMError(0, "LLM retry exhausted")
```

- 401/400/404 等客户端错误不重试。
- 流式路径：仅在**建连/首包前**重试（复用同一函数获取 status，成功后再进入 `aiter_lines`）；响应中途断流不重试，直接抛错（避免重复消费副作用）。
- 重试参数模块级常量，调用方可覆盖（`llm_chat_completion(..., max_retries=...)`）。

**测试用例**：
1. `test_retry_429_then_success`：mock 响应序列 429→200，断言 2 次请求且成功。
2. `test_retry_5xx_exhausted`：500×4 → LLMError。
3. `test_no_retry_on_401`：401 → 1 次请求即抛。
4. `test_retry_network_error`：首请求 ConnectError → 重试成功。
5. `test_stream_no_retry_midway`：首包后断流不重试。

**验收标准**：注入 429/网络抖动时调用自动恢复；401 密钥错误秒失败不延迟。

### 5.4 模块 4：报告角色提示词修复（修复 E4）

**改动文件**：`backend/app/routers/chat.py`。

**关键逻辑**：report_prompt 分支改为：

```python
system_prompt = result_obj.get("system_prompt", "")
messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + \
           [{"role": "user", "content": result_obj["prompt"]}]
full_text = await _collect_llm(messages, ai_config)
```

**测试用例**：
1. `test_report_passes_system_prompt`：mock `llm_collect_all`，断言首条消息 role=system 且等于 `_generate_report` 返回的 system_prompt。
2. `test_report_prompt_without_system`：system_prompt 为空时不注入 system 消息（兼容旧返回）。

**验收标准**：报告生成请求中 messages[0].role=system，内容为「应急管理与安全生产领域专业分析师」设定。

### 5.5 模块 5：对话记忆增强（修复 E5）

**改动文件**：`backend/app/models/chat.py`（不改表结构，仅用既有 role 字段存 "tool"）、`backend/app/routers/chat.py`（_build_tool_messages / _save_messages / 加载历史）、`backend/app/schemas/chat.py`（MessageResponse 加 name）、`frontend/src/services/chatService.ts`、两端聊天页（过滤 tool 消息）。

**消息持久化方案**（复用 `chat_messages`，不加列）：

```
每轮保存序列：
  role=user      content=用户输入
  role=assistant content=最终总结文本           （模型回复）
  role=assistant content=""                      （中间：工具调用占位，每轮一条）
  role=tool      name=fn_name content=result     （该轮每个工具一条，紧跟占位后）
```

**上下文重建（_build_tool_messages 重写）**：

```python
async def _build_tool_messages(db, user, conv_id, user_message):
    msgs = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    rows = await load_chat_history(db, conv_id)   # 含 tool 消息，created_at 升序
    # 扫描：遇到 assistant(content=="") 且后续紧跟 tool 行 →
    #   收集 tool 行 → 生成 {"role":"assistant","content":None,"tool_calls":[...]}
    #   后接 {"role":"tool","tool_call_id":name,"content":result} 序列
    # 其余 user/assistant 文本消息原样加入
    msgs.append({"role": "user", "content": user_message})
    return truncate_by_token_budget(msgs)
```

`tool_call_id` 重建值用稳定串（如 `call_{conv_id}_{seq}`），满足 OpenAI 格式（tool 消息 tool_call_id 与 assistant tool_calls id 对应即可，不必是真实 call id）。

**token 预算截断（truncate_by_token_budget）**：默认预算 8000 token（常量 `CHAT_CONTEXT_BUDGET`，估算 `chars ≈ token*2`）。超限时：保留最近 30% 完整轮次 + 系统提示词；中间轮压缩为一条 `role=system` 摘要消息（`【历史摘要】...`，由 `_html_to_text_summary` 风格裁剪每轮至 300 字符）。前后端契约：`ChatRequest.history` 忽略，后端以 DB 为准（前端仍传以兼容）。

**前端过滤**：`fetchMessages` 返回行中 role=tool 与空 content 的 assistant 占位行不渲染为气泡（步骤条由 tool-calls 端点回放）。

**测试用例**：
1. `test_history_rebuild_with_tool_trace`：DB 含工具轨迹 → 重建 messages 含 assistant(tool_calls)+tool 对。
2. `test_history_without_tools`：纯文本对话重建不产生 tool_calls。
3. `test_truncate_budget_keeps_recent`：超预算保留最近轮 + 摘要消息。
4. `test_long_conversation_continuity`：>10 轮后仍能引用第 1 轮提到的企业名（mock LLM 收到摘要或最近轮）。
5. `test_message_response_has_name`：schema 含 name 字段。

**验收标准**：连续 15+ 轮对话，第 16 轮引用第 1 轮实体仍正确；工具轨迹可回放；请求体 token 估算不超过预算。

### 5.6 模块 6：聊天内端到端生成预案 + 轮数优化（修复 E6、E7）

**改动文件**：新增 `backend/app/services/plan_generation_service.py`；改 `backend/app/routers/generation.py`（改调 service）、`backend/app/services/chat_dispatch.py`（_generate_plan_content 重写 + 新增 _get_generation_progress）、`backend/app/routers/chat.py`（CHAT_TOOLS 增加 get_generation_progress）。

**抽取 service（行为不变重构）**：

```python
# plan_generation_service.py
async def collect_batch_context(plan_id, db, keys=None):      # 从 _collect_batch_context 抽取，去掉 request.json，keys 显式传入
async def run_batch_generation(*, bg_db, plan_id, section_tuples, ai_config, ent_data,
                               plan_type, accident_type=None, style_preference=None,
                               advanced_overrides=None, stream_fn=None, on_progress=None,
                               on_section_done=None, should_stop=None, use_section_number=True):
    # 直接迁移 generation.py:760 现有实现，不改签名
async def finalize_batch_result(bg_db, plan_id, completed, failed, failed_sections, updated=None):
    # 直接迁移 generation.py:840 现有实现
async def start_batch_generation(plan_id, db, current_user, keys=None, background=True):
    # 编排：collect context → 置 generating → 后台任务(独立 async_session + _background_tasks) 或同步执行
```

`generation.py` 路由改为调用 service 同名函数；**行为与现有一致**（全量 pytest 保障）。

**聊天触发（_generate_plan_content 重写）**：

```python
async def _generate_plan_content(db, user, args):
    # 1. 校验预案归属 + 计算空章节
    # 2. 若无空章节 → {"message": "全部章节已填写", verified: True}
    # 3. 调 plan_generation_service.start_batch_generation(plan_id, db, user, background=True)
    #    → 后台任务启动，返回 {"task_started": True, "plan_id": ..., "total": N, "empty": M,
    #                          "message": "已开始后台生成，共 N 章，可随时问我生成进度", verified: True}
```

**新工具 `get_generation_progress(plan_id)`**：

```python
async def _get_generation_progress(db, user, args):
    # 校验归属 → 读预案 status + _failed_sections[plan_id]（内存）+ 最近生成日志
    # 返回 {plan_id, status: generating/completed/failed, completed_sections, failed_sections}
```

**SSE 语义**：聊天回复「已开始后台生成，共 N 章」；用户后续问「生成好了吗」→ 模型调 get_generation_progress 汇报完成/失败章节。避免长任务占用聊天流（既有 `_call_llm_stream` 180s 超时不适用长生成）。

**轮数优化**：`MAX_ROUNDS` 8；超限时注入提示「已完成以下操作并给出部分总结，未完成 X」，随后强制总结（不再抛「请简化问题」）。

**测试用例**：
1. `test_generate_plan_content_starts_background`：mock service，断言返回 task_started 且后台任务注册。
2. `test_generate_plan_content_all_filled`：无空章节返回提示。
3. `test_generation_progress_ownership`：非本人预案 404/error。
4. `test_generation_progress_statuses`：generating/completed/failed 三态。
5. `test_agent_loop_max_rounds_partial_summary`：8 轮后输出部分成功总结。
6. 既有 generation 路由全量回归（重构不破坏）。

**验收标准**：聊天中「给 XX 预案生成内容」→ 回复已开始 + 可查询进度 + 完成后汇报成功/失败章节；generation.py 行为无回归。

## 6. 阶段 2：能力深化（0.4.1）

### 6.1 模块 7：语义法规检索接线（落地 C1）

**改动文件**：`backend/app/services/chat_dispatch.py`（_search_regulation_articles 重写）、`backend/app/regulations/retriever.py`（若已含向量融合则直接复用）。

**关键逻辑**：

```python
async def _search_regulation_articles(db, user, args):
    query, top_k = ...
    try:
        store = get_vector_store()
        hits = store.search(query, top_k=top_k)     # [{id/regulation_id/article_number/text/metadata/similarity}]
        if hits:
            # 图谱补全：graph.get_node(regulation_id) → full_name/code/status
            return {"articles": [...], "count": len(hits), "source": "vector"}
    except Exception as e:
        logger.warning("vector search failed: %s", e)
    return await _keyword_fallback(query, top_k)   # 现有关键词+子串逻辑，source="graph_fallback"
```

先确认 `retriever.py` 当前是否已做向量+图谱融合（`get_vector_store` 与 `search` 返回结构需对照 `vector_store.py:search` 的字段：`query_texts` 入参、返回 `results` 的 `text/metadata`）。若 retriever 已融合，直接改调 retriever 并保留 fallback。

**边界**：向量库空（count=0）→ fallback；ChromaDB 加载异常 → fallback + warning 日志；abolished 法规过滤沿用。

**测试用例**：
1. `test_search_regulation_articles_vector_hit`：mock store.search 返回 2 条 → 断言 source=vector、含图谱补全元数据。
2. `test_search_regulation_articles_fallback`：store.search 抛异常/空 → source=graph_fallback。
3. 真实命中率对比：10 组问题（危化品储存距离、有限空间作业审批、消防通道、应急预案备案等）新旧检索 top-8 命中率记录（验收附件）。

**验收标准**：语义检索命中率 ≥ 图谱检索，且能召回语义近义条文（如「危化品」→「危险化学品」相关条文）；无网络/依赖新装（chromadb 已在 requirements + 已构建）。

### 6.2 模块 8：生成后 AI 自检修订循环（落地 C3）

**改动文件**：新增 `backend/app/services/plan_review_service.py`；改 `backend/app/routers/plans.py`（或新增 `review.py` 路由）、`backend/app/routers/versions.py`（复用 _build_snapshot）、前端预案编辑页（桌面 + 移动）。

**审查维度**（`review_plan(plan, enterprise, sections, ai_config) -> {"issues": [...], "warnings": [...]}`）：
1. 章节完整性：对照 `MUST_HAVE_SECTION` 与模板章节集合，缺章 → issue。
2. 法规引用准确性：抽取正文 `《...》` 引用 → 与法规库节点比对（图谱 full_name 模糊匹配），不存在的引用 → issue「疑似编造法规」。
3. 占位符残留：`（待补充）` 或空章节 → issue。
4. 企业数据一致性：地址/法人/电话与档案比对（复用 `plan_quality_service` 的 normalize/匹配函数）→ issue。
5. 内容与事故类型匹配：LLM 判断章节内容是否贴合 accident_type → warning。

**修订策略（D2：自动执行 + 可回退）**：
- 确定性修复（规则）：空章节 → 触发单章重新生成；占位符/格式 → 模板补全。
- LLM 修订：对 issue 命中章节，构造修订 prompt（原内容 + 审查意见 + 企业上下文），调 `_stream_llm` 重写；修订前调 `_build_snapshot` 生成版本快照（versions 机制已有）。
- 执行顺序：先规则后 LLM；修订后章节标 `ai_generated=True`、`reviewed=True`（若 PlanSection 有该字段则复用，否则不新增字段，审查记录存 JSON 返回 + 前端展示）。

**API**：

```python
GET  /plans/{plan_id}/review        # 返回 {"issues": [...], "warnings": [...], "reviewed_at": ...}
POST /plans/{plan_id}/review/apply  # body {"mode": "auto"|"llm", "section_keys": [...]|null}
                                    # 执行修订；返回 {"applied": [...], "snapshot_id": ...}
```

回退复用既有版本/快照回退接口（versions.py），无需新回退端点。

**测试用例**：
1. `test_review_detects_missing_section`：缺 MUST_HAVE_SECTION → issue。
2. `test_review_detects_fake_regulation`：正文引用不存在法规 → issue。
3. `test_review_detects_placeholder`：含（待补充）→ issue。
4. `test_apply_rules_fix_placeholder`：确定性修复生效。
5. `test_apply_llm_revise`：mock _stream_llm，断言修订写入 + 快照生成。
6. `test_apply_snapshot_rollback`：应用修订后回退到修订前快照，内容恢复。

**验收标准**：构造含 5 类缺陷的样本预案 → 审查全部命中；自动修订后缺陷消除且可回退。

### 6.3 模块 9：报告数据面扩充（落地 C2）

**改动文件**：`backend/app/services/chat_dispatch.py`（_generate_report）。

**关键逻辑**：`_generate_report` 按 topic 采集扩展数据：

```python
EXTRA_COLLECTORS = {
    "系统概览":     collect_dashboard_only,
    "企业分析":     collect_enterprise_detail,       # 企业数/行业分布/预案完成率
    "预案进度":     collect_plan_progress,           # 按状态/类型分布
    "风险分布":     collect_risk_distribution,       # 风险源按等级/类别统计 + 重大风险摘要
    "资源覆盖":     collect_resource_coverage,       # 资源按类别/企业覆盖统计
    "法规合规":     collect_regulation_compliance,   # 法规库统计 + 生成内容引用统计
}
```

采集器返回结构化 dict，并入 data_context；prompt 按主题注入对应数据（未匹配主题回退现有逻辑）。所有采集只读、带 limit（默认 50）。

**测试用例**：
1. `test_report_risk_distribution_data`：mock 风险源数据 → data_context 含等级分布。
2. `test_report_unknown_topic_fallback`：未知主题走默认 dashboard 数据。
3. `test_report_resource_coverage`：资源覆盖主题数据正确。

**验收标准**：6 个主题报告均生成成功且数据面明显大于旧版（含风险/资源/法规维度）。

### 6.4 模块 10：企业画像问答（落地 C4）

**改动文件**：新增 `backend/app/services/enterprise_knowledge_service.py`；改 `backend/app/routers/chat.py`（CHAT_TOOLS 新增工具）、`backend/app/services/chat_dispatch.py`（实现 + 注册）；风险源/评估/资源写服务（增量更新挂点）。

**设计**：
- ChromaDB collection `enterprise_knowledge`，document 含企业上下文片段（风险源描述/等级、评估结论、资源清单、危化品信息），metadata 含 `user_id`、`enterprise_id`、`source_type`。
- `build_enterprise_index(enterprise_id, db)`：从 `build_risk_management_context` + 评估报告 + 资源调查组装文本，写入向量（先 delete 该 enterprise 旧向量再 add，保证幂等）。
- 增量挂点：风险源/评估/资源创建更新删除后调用 `rebuild_enterprise_index(enterprise_id)`（异步，不阻塞主流程）。
- 新工具：

```python
CHAT_TOOLS += [{
  "name": "query_enterprise_knowledge",
  "description": "基于企业画像（风险分级管控、评估报告、资源调查）语义问答。当用户询问某企业风险状况、管控措施、资源配备时使用",
  "parameters": {"enterprise_id": str, "question": str}
}]
```

实现：校验归属 → `store.search(question, filter_ids=[enterprise_id], top_k=6)` → 返回片段 + 元数据 → LLM 组织回答（在 agent 循环内自然完成）。

**测试用例**：
1. `test_query_enterprise_knowledge_ownership`：非本人企业 → error。
2. `test_query_enterprise_knowledge_hit`：mock store.search → 返回 top 片段。
3. `test_rebuild_index_idempotent`：两次 build 无重复（先删后加）。
4. `test_incremental_rebuild_on_risk_write`：风险源写操作后触发 rebuild（mock 断言调用）。

**验收标准**：对含风险源的样本企业问「这家企业有哪些重大风险」→ 回答引用真实风险源数据；权限隔离验证。

## 7. 阶段 3：架构升级（0.5.0）

### 7.1 模块 11：多智能体编排

**改动文件**：新增 `backend/app/services/agent/__init__.py`、`orchestrator.py`、`agents.py`、`task_graph.py`。

**设计**：
- `AgentRegistry`：注册 5 个 agent，每个含 `name`、`system_prompt`、`tools_subset`、`dispatch_fn`：
  - `assistant`（现有 chat function-calling 全集，对外入口）；
  - `plan_generator`（封装 plan_generation_service，工具子集：预案/章节/企业读取）；
  - `plan_reviewer`（封装 plan_review_service）；
  - `regulation`（封装检索 + 引用校验）；
  - `report`（封装 _generate_report + 采集器）。
- `TaskGraph`：DAG（节点=任务，边=依赖），`orchestrator.run(graph, inputs)` 拓扑排序执行：无依赖并行（独立 session）、失败节点标记并决定中止/降级（任务级策略）。
- 复杂任务入口：assistant agent 识别「生成并审查」类意图 → 委托 orchestrator 组合 plan_generator + plan_reviewer（聊天内以进度步骤汇报）。
- 每个 agent 的 system prompt 与工具子集独立（缓解 27 工具选择噪声，落地 C6 一部分）。

**测试用例**：
1. `test_task_graph_topological`：DAG 依赖排序正确。
2. `test_orchestrator_parallel_branches`：无依赖节点并行执行。
3. `test_orchestrator_failure_policy`：失败节点按策略中止/降级。
4. `test_assistant_delegates_review_workflow`：mock 意图识别 → 委托生成+审查。

**验收标准**：编排层可独立跑通「生成→审查」组合；单个 agent 工具集 ≤ 15 个时工具选择准确率提升（对比记录）。

### 7.2 模块 12：端到端任务工作流

**改动文件**：新增 `backend/app/services/workflow/`（`models.py`、`runner.py`、`templates.py`）；迁移 2 张表；改 `backend/app/routers/chat.py`、`chat_dispatch.py`（工具）；前端聊天页（进度）。

**表**：

```sql
CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workflow_name VARCHAR(100) NOT NULL,
    params JSONB, status VARCHAR(20) DEFAULT 'pending',  -- pending/running/paused/failed/completed
    current_step VARCHAR(100), created_at/updated_at ...
);
CREATE TABLE workflow_run_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_name VARCHAR(100), status VARCHAR(20), result JSONB,
    retry_count INTEGER DEFAULT 0, error TEXT, started_at/finished_at ...
);
```

**模板**（`templates.py` JSON）：

```json
{
  "create_enterprise_plan": {
    "steps": [
      {"name": "create_enterprise", "tool": "autofill_enterprise", "params_from": "params.name"},
      {"name": "risk_identify", "tool": "generate_risk_assessment", "params_from": "steps.create_enterprise.id"},
      {"name": "generate_plan", "tool": "generate_plan_content", "params_from": "steps.create_enterprise.id"},
      {"name": "review_plan", "tool": "review_plan", "params_from": "steps.generate_plan.plan_id"},
      {"name": "export_docx", "tool": "export_plan_docx", "confirm": true}
    ],
    "dependencies": {"risk_identify": ["create_enterprise"], "generate_plan": ["create_enterprise"], "review_plan": ["generate_plan"], "export_docx": ["review_plan"]}
  },
  "regulatory_compliance": { ... }
}
```

**执行器**：`runner.run(run_id)` 逐步骤执行（工具经 dispatch 或 service 直调），支持暂停/继续/重试（retry_count ≤ 2）、失败步骤记录 error；SSE 进度（复用 chat 通道或轮询工具 `get_workflow_progress(run_id)`）。

**聊天工具**：`run_workflow(workflow_name, params)`、`get_workflow_progress(run_id)`；`confirm` 步骤在工具结果中标记 `awaiting_confirmation`，由用户确认后继续（复用「删除前先确认」交互模式）。

**测试用例**：
1. `test_workflow_runner_success`：mock 各步骤 → 状态 completed、步骤全成功。
2. `test_workflow_runner_failure_retry`：某步失败 1 次后成功（retry_count=1）。
3. `test_workflow_confirm_gate`：confirm 步骤等待用户确认。
4. `test_workflow_pause_resume`：暂停后继续从 current_step 执行。
5. `test_run_workflow_chat_tool`：聊天触发 + 进度查询。

**验收标准**：真实演练「录入企业→评估→生成→审查→导出」一键跑通（Docker 隔离环境），失败可重试、可确认门控。

### 7.3 模块 13：跨会话记忆与偏好

**改动文件**：迁移 1 张表；新增 `backend/app/services/user_preference_service.py`；改 `backend/app/routers/chat.py`（system prompt 注入）、`chat_dispatch.py`（工具：get/set_preferences）、`backend/app/services/enterprise_knowledge_service.py`（profile cache 复用）。

**表**：

```sql
CREATE TABLE user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    style_preference VARCHAR(20),            -- formal/standard/practical（对齐 STYLE_PARAM_MAP）
    detail_level VARCHAR(20),                -- concise/balanced/comprehensive
    report_topics JSONB,                     -- 常用报告主题
    common_enterprise_ids JSONB,             -- 常用企业
    extra TEXT,                              -- 自由偏好说明
    created_at/updated_at ...
);
```

**设计**：
- `get_preferences(db, user_id)` 缓存（进程内 TTL 5 分钟，复用 prompt_cache 模式）；`set_preferences` 更新 + 失效缓存。
- 聊天 system prompt 追加「用户偏好」段（style/detail/常用企业）；生成引擎调用处（plan_generation_service）读取 style_preference 已有链路，聊天侧额外注入。
- `enterprise_profile_cache`：企业画像摘要（JSON）缓存于内存，生成/聊天共用，数据变更时失效（与模块 10 的 rebuild 挂点同源）。
- 聊天工具：`get_preferences`、`set_preferences(key, value)`；用户说「以后生成都用简洁风格」→ assistant 调 set_preferences。

**测试用例**：
1. `test_set_get_preferences`：写入后读取一致。
2. `test_preferences_injected_into_system_prompt`：有偏好时 system prompt 含偏好段。
3. `test_chat_updates_preference`：mock 工具调用 set_preferences 落库。
4. `test_profile_cache_invalidation`：企业数据变更后缓存失效。

**验收标准**：设置偏好后新会话生成风格生效；常用企业信息在新会话可被引用。

### 7.4 模块 14：任务分层与成本观察（D3 修订：单一配置）

**改动文件**：`backend/app/services/agent/orchestrator.py`（分层策略）、`backend/app/services/plan_generation_service.py`（参数覆盖）、`backend/app/routers/chat.py`。

**D3 结论**：不新增多模型/多 key，`ai_configs` 保持单条系统配置；模型选择沿用 `get_system_ai_config`。

**任务分层（不引入模型层）**：
- 分层体现在**提示词与工具子集**：`assistant`（全工具 + 通用 prompt）、`plan_generator`（生成专用 prompt + 生成工具子集）、`plan_reviewer`（审查专用 prompt）、`regulation`（检索专用 prompt）——每个 agent 的 system prompt 已按任务优化（模块 11 已落地）。
- 参数差异化：`payload_overrides` 支持按任务覆盖 temperature/max_tokens（如生成 0.7/4096、审查 0.2/2048、检索总结 0.3/1024），仍用同一模型。
- 成本观察（明确方案，不新增表/列）：生成链路沿用 `generation_logs.tokens_used`（既有）；聊天工具调用用 `chat_tool_calls` 既有的 `fn_name/duration_ms/round_no` 统计调用轮数与耗时（SQL 聚合即可）。若后续需要精确 token 级聊天成本，再单独评估迁移，不在本版本范围。

**简化验收**：单一配置下各 agent 任务正常；温度/长度按任务生效；生成链路 token 统计可查（generation_logs）。

## 8. 实现顺序与依赖

```
阶段 1：模块 3（重试，无依赖）→ 模块 4（提示词，无依赖）→ 模块 1（进度）→ 模块 2（并行）
        → 模块 5（记忆）→ 模块 6（端到端生成，依赖抽取 service）→ 门禁 + 0.4.0 打包
阶段 2：模块 7（检索）→ 模块 9（报告）→ 模块 10（画像，依赖 9 的数据源）→ 模块 8（自检，依赖 6 的 service）→ 门禁 + 0.4.1 打包
阶段 3：模块 11（编排，依赖 6/8）→ 模块 13（偏好）→ 模块 14（分层，依赖 11）→ 模块 12（工作流，依赖 11/14）→ 门禁 + 0.5.0 打包
```

每个模块独立 commit（Conventional Commits），commit 纪律：只 add 任务清单文件，TASKS.md 永不 commit。

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 模块 2 并行 + 独立 session 引入数据不一致 | 读并行写串行；写路径保持请求级 db；全量 pytest + Docker 演练 |
| 模块 5 消息重建格式错误（OpenAI tool_calls 校验） | tool_call_id 稳定串；重建单测覆盖空/多工具轨迹；用真实模型冒烟验证 |
| 模块 6 抽取 service 回归 | 重构先跑全量 pytest（1157+）；两个端点行为逐项对照 |
| 模块 8 LLM 修订产生新错误 | 修订前快照 + 可回退；修订后二次审查（review 再跑一遍） |
| 模块 10 向量污染/越权 | user_id/enterprise_id 过滤 + 所有权校验；rebuild 幂等 |
| 阶段 3 编排复杂度 | 每 agent 独立可测；DAG 单测先行；编排默认串行降级路径 |
| 长任务超时（模块 6/12） | 后台任务 + 进度查询工具，不占聊天流 |

## 10. 交付与验收矩阵

| 版本 | 模块 | 验收口径 |
|------|------|----------|
| 0.4.0 | 1-6 | 每缺陷「修前复现→修后通过」用例；进度刷新不消失；并行延迟下降；重试注入通过；报告 system prompt 生效；15 轮对话不失忆；聊天触发生成+进度查询 |
| 0.4.1 | 7-10 | 10 组法规问题命中率对比达标；5 类缺陷样本审查全命中且可回退；6 主题报告数据面达标；企业画像问答命中真实数据 |
| 0.5.0 | 11-14 | 编排 DAG 单测通过；「录企→评估→生成→审查→导出」演练跑通；偏好跨会话生效；单配置任务分层生效 + token 可查 |
