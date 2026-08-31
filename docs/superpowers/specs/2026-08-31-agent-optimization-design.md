# 智能体优化三阶段设计（体验快赢 → 能力深化 → 架构升级）

> 版本：1.0 | 创建日期：2026-08-31 | 状态：待评审
> 范围：Chat AI 助手（chat.py / chat_dispatch.py）+ AI 生成引擎（llm_client / generation.py）+ 法规检索 + 前端聊天 UI（桌面 ChatPanel 与移动端 ChatScreen）

## 1. 背景与目标

系统智能体已有完整骨架：27 个 function-calling 工具（企业/风险源/应急资源/预案/评估报告/调查报告/法规库/导出/报告生成/正文生成）、多模型适配生成引擎（OpenAI/通义/文心/DeepSeek）、法规知识图谱与已构建的 ChromaDB 向量库、QCC 企业工商自动填充。但体检发现体验与能力均存在明确短板，用户认可按三阶段推进：

- **阶段 1 体验快赢（0.4.0）**：修复聊天助手日常使用的硬伤（进度持久化、并行工具、重试、报告角色提示词、记忆增强、聊天内端到端生成）。
- **阶段 2 能力深化（0.4.1）**：语义法规检索接线、生成后 AI 自检修订循环、报告数据面扩充、企业画像问答。
- **阶段 3 架构升级（0.5.0）**：多智能体编排、端到端任务工作流、跨会话记忆偏好、模型成本分层路由。

依赖链固定为 阶段1 → 阶段2 → 阶段3，每阶段独立交付、可独立上线。

## 2. 现状盘点（代码证据）

### 2.1 体验层缺陷

| 编号 | 缺陷 | 证据 |
|------|------|------|
| E1 | 工具执行进度刷新后消失 | 前端 `Chat/index.tsx` 把 `progress` 事件直接拼进消息文本（contentBuf）；后端 `_save_messages` 仅保存最终文本 → 刷新对话后进度文本消失，前后不一致 |
| E2 | 工具串行执行 | `chat.py` agent_loop 中 `for tc in pending_tool_calls` 逐个 `await dispatch(...)`，同轮独立工具未并行 |
| E3 | LLM 调用无重试 | `llm_client.py` 非 200 直接抛 `LLMError`，无退避重试 |
| E4 | 报告生成丢角色提示词 | `_generate_report` 返回 `system_prompt`，但 `chat.py` report_prompt 分支仅用 `result_obj["prompt"]` 调 `_collect_llm`，角色提示词被丢弃 |
| E5 | 对话记忆过浅 | 前端 `slice(-20)` 仅保留最近 10 轮文本，消息表不存工具调用轨迹，多轮任务衔接易失忆 |
| E6 | 聊天内生成预案半残 | `_generate_plan_content` 仅把预案标记 `generating`，要求用户去前端点「批量生成」或回复「确定开始生成」，智能体不能端到端完成 |
| E7 | 5 轮上限硬错误 | 超过 `MAX_ROUNDS=5` 直接报「操作轮数超过上限」，无部分成功汇报 |

### 2.2 能力层缺口

| 编号 | 缺口 | 证据 |
|------|------|------|
| C1 | 法规检索非语义 | `chat_dispatch._search_regulation_articles` 用 `graph.list_nodes(keyword=...)` + 文件子串匹配；`vector_store.py` 已实现且 `data/chroma_db` 已构建，但聊天助手未接线 |
| C2 | 报告数据面窄 | `_generate_report` 仅收集 dashboard + 前 5 预案 + 前 5 企业 |
| C3 | 无生成后 AI 自检 | `plan_quality_service.check_plan` 为导出前规则检查，AI 生成后直接交付，无「生成 → 审查 → 修订」闭环 |
| C4 | 无企业画像问答 | 聊天助手需用户多步手动组合工具才能得到「某企业主要风险」的完整答案 |
| C5 | 无跨会话记忆/偏好 | 每次对话独立，无企业常用信息与用户偏好沉淀 |
| C6 | 27 工具无分层 | 所有任务走同一模型同一提示词，无成本/能力分层 |

### 2.3 已就绪可复用资产

- `backend/requirements.txt` 已含 `chromadb>=0.5.0`；`backend/app/regulations/data/chroma_db/` 已构建（chroma.sqlite3 + 向量文件）。
- `generation.py` 的 `_run_batch_generation` 已实现批量章节生成 + 失败恢复 + SSE 进度，可抽取复用。
- `plan_quality_service.py` 规则检查可作自检循环的基线。
- 前端已有 SSE 事件通道（progress/chunk/function_result/error/done/conv_id），移动端 `ChatScreen.tsx` 与桌面共用后端。

## 3. 阶段 1：体验快赢（0.4.0）

### 3.1 模块 1：进度持久化 + 前端步骤条（修复 E1）

**数据模型**：新增 `chat_tool_calls` 表：

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

（随 0.4.0 提供 `db_migration_2026xxxx_chat_tool_calls.sql`，走既有 migration_runner。）

**后端**：`chat.py` agent_loop 在每轮工具调用前写 `running` 记录，`dispatch` 返回后更新 `status/duration_ms/result`。`_save_messages` 保持只存最终文本。新增 `GET /chat/conversations/{conv_id}/tool-calls` 返回步骤记录。

**前端**：`Chat/index.tsx` 与移动端 `ChatScreen.tsx` 将 `progress` 事件渲染为步骤时间线（非消息文本）；切换对话时并行加载 tool-calls 记录回放。消息区只展示最终总结。

**测试**：单测 agent_loop 写入/更新记录；SSE 集成验证 progress 不进入最终消息；前端刷新后步骤条回放一致。

### 3.2 模块 2：工具并行执行（修复 E2）

**约束**：请求级 `AsyncSession` 不支持并发，并行工具须使用独立 session。

**设计**：
- `chat.py` 不再向 `dispatch` 传共享 `db`；`dispatch` 改为按调用创建 `async_session()`（工具内部无 `db` 参数需求时可直接用）。为控制改动面：读取型工具并行（gather），写入/删除型工具串行执行（保持顺序与幂等语义）。
- 并行结果按原顺序返回（`asyncio.gather` + 结果排序），模型看到的 tool 消息顺序稳定。

**测试**：mock dispatch 记录并发调用（验证 gather）；读工具并行、写工具串行的调度单测；DB 独立 session 无串扰集成测试。

### 3.3 模块 3：LLM 调用重试（修复 E3）

**设计**：`llm_client.llm_chat_completion` 增加可配置指数退避重试：
- 重试条件：HTTP 429 / 5xx / 网络异常（httpx.TransportError / ConnectError / TimeoutException）；401/400 等客户端错误不重试。
- 参数：`max_retries=3`、`base_delay=1s`、`max_delay=8s`、jitter；模块级默认值，调用方可覆盖。
- 流式路径同样重试（建连阶段失败可重试，响应中途失败不重试，避免重复消费）。

**测试**：mock httpx 依次返回 429→500→200 验证成功；全部失败抛 LLMError；401 不重试。

### 3.4 模块 4：报告角色提示词修复（修复 E4）

**设计**：`chat.py` report_prompt 分支改为 `_collect_llm([{"role":"system","content": system_prompt}, {"role":"user","content": prompt}], ai_config)`。

**测试**：mock `llm_collect_all` 断言消息列表含 system role 且内容等于 `_generate_report` 返回的 `system_prompt`。

### 3.5 模块 5：对话记忆增强（修复 E5）

**设计**：
- 消息表扩展支持 tool 角色：`ChatMessage.role` 增加 `tool`，保存工具轨迹（tool_call_id=fn_name，content=result JSON）。历史回放时 `_build_tool_messages` 重建完整 assistant tool_calls + tool 消息序列。
- 上下文构建移到后端：前端只传最近一轮消息，后端从 DB 加载该 conversation 的完整历史（含工具轨迹），按 token 预算截断：优先保留最近 N 轮完整内容，超出预算时对中间轮做摘要（复用 generation.py 的 `_html_to_text_summary` 思路）。
- 预算默认约 8K token（可配置），与 `ai_config.max_tokens` 联动。

**API 变更**：`ChatRequest` 的 `history` 降级为可选（后端忽略并改用 DB 加载），保持兼容。

**测试**：历史含工具轨迹的 messages 重建单测；超预算截断/摘要单测；长对话（>10 轮）多轮任务衔接集成测试（mock LLM）。

### 3.6 模块 6：聊天内端到端生成预案（修复 E6、E7）

**设计**：
- 抽取 `generation.py` 的 `_run_batch_generation` + `_finalize_batch_result` 为可复用 service（`app/services/plan_generation_service.py`），供路由与聊天共用。
- `_generate_plan_content` 改为触发真实后台生成：复用 `generate_batch_background` 的队列 + SSE 机制，向聊天 SSE 输出「正在生成第 i/N 章」进度；完成后总结成功/失败章节数，失败章节列出标题。
- 取消支持：聊天端「停止」调用既有 stop 端点语义（置 `_active_generations[plan_id]=False`）。
- 轮数上限：`MAX_ROUNDS` 提升至 8；超限时按已完成工具结果生成部分成功总结（「已完成 X，未完成 Y」），不再笼统报错。

**测试**：mock `_run_batch_generation` 验证聊天触发、进度事件序列、完成总结；部分失败场景总结正确；停止中断恢复状态。

### 3.7 阶段 1 质量门禁

- backend 全量 pytest 无回归；frontend `tsc -b` exit 0。
- 每缺陷一条「修前复现 → 修后通过」用例。
- 0.4.0 打包沿用 package-release.sh（--system 模式）。

## 4. 阶段 2：能力深化（0.4.1）

### 4.1 模块 7：语义法规检索接线（落地 C1）

**现状**：向量库已构建（`data/chroma_db`），`vector_store.RegulationVectorStore.search` 已实现；`chat_dispatch._search_regulation_articles` 未使用。

**设计**：
- `_search_regulation_articles` 改为：`vector_store.search(query, top_k)` 语义检索 → 图谱 `graph.get_node` 补全法规全称/文号/状态 → 按相似度排序返回 top_k 条文（结构同 PRD-14 目标格式）。
- 向量库未命中或异常时 fallback 到现有图谱关键词+子串匹配，返回 `source` 字段（`vector` / `graph_fallback`）供排查。
- 法规库增量更新时同步重建/追加向量（复用 `RegulationVectorStore.add_regulation`，migration 脚本或管理命令）。

**验收**：用 10 组真实法规问题（如「危化品储存距离要求」「有限空间作业审批」）对比新旧检索命中率，语义检索命中率不低于图谱检索且能召回语义近义条文。

### 4.2 模块 8：生成后 AI 自检修订循环（落地 C3）

**设计**：
- 新增 `app/services/plan_review_service.py`：`review_plan(plan, enterprise, sections, ai_config) -> issues[]`。
- 审查维度：章节完整性（对照模板必须章节）、法规引用准确性（引用是否存在于法规库，防止编造）、占位符残留、企业数据一致性（地址/法人/电话与档案一致）、内容与事故类型匹配。
- 修订策略（两级）：
  - **自动修订**：可确定性修复（缺章节标题、占位符格式）由规则/模板直接修复；
  - **LLM 修订**：内容质量问题（法规引用错误、章节内容薄弱）由 LLM 基于审查报告重写对应章节，修订后的章节标记 `reviewed=true`。
- 生成流程集成：批量生成完成后自动触发审查 → 输出审查报告；修订默认自动执行，前端预案页展示审查报告并可「接受/回退修订」（保存修订前快照）。

**API 变更**：`GET /plans/{plan_id}/review` 返回审查报告；`POST /plans/{plan_id}/review/apply` 应用修订。

**测试**：构造含错误法规引用/缺章节/占位符的样本 → 审查命中；修订后内容正确；回退恢复快照。

### 4.3 模块 9：报告数据面扩充（落地 C2）

**设计**：`_generate_report` 的 data_context 扩展维度（在 topic 匹配时采集）：
- 风险源统计（按等级分布）、应急资源统计（按类别）、风险评估报告摘要、法规库统计（总数/最近更新）。
- 新增报告主题支持：企业风险分布、资源覆盖分析、法规合规进度。

**测试**：mock 数据源断言 data_context 包含新维度；各主题报告生成成功。

### 4.4 模块 10：企业画像问答（落地 C4）

**设计**：
- 将企业风险分级管控、评估报告、资源调查报告文本按企业向量化（复用 ChromaDB，collection `enterprise_knowledge`，按 user/enterprise 过滤）。
- 聊天助手新增工具 `query_enterprise_knowledge(enterprise_id, question)`：语义检索该企业画像 → 返回相关片段 → LLM 组织回答。
- 数据变更时增量更新向量（风险源/评估/资源写操作后同步）。

**测试**：构造企业画像样本，验证「这家企业有哪些重大风险」类问题命中正确片段；无数据企业返回引导文案。

## 5. 阶段 3：架构升级（0.5.0）

### 5.1 模块 11：多智能体编排

**设计**：
- 引入 `app/services/agent/orchestrator.py` 与 `AgentRegistry`：
  - `plan_generator_agent`：章节生成（封装现生成引擎）；
  - `plan_reviewer_agent`：审查修订（阶段 2 的 plan_review_service）；
  - `regulation_agent`：法规检索/引用校验（语义 + 图谱）；
  - `report_agent`：数据采集 + 图文报告；
  - `assistant_agent`：现有聊天 function-calling 助手（对外入口）。
- Orchestrator 维护任务依赖图（DAG），按依赖并行/串行调度 agent；每 agent 有独立 system prompt 与工具子集，避免单 agent 27 工具的选择噪声。
- 对外统一：聊天助手仍是入口，复杂任务（生成+审查+修订）自动委托 orchestrator。

**测试**：DAG 调度单测（依赖排序、并行分支、失败中止/降级）；端到端「生成→审查→修订」委托流程。

### 5.2 模块 12：端到端任务工作流

**设计**：
- 预置工作流模板（JSON 定义 steps + dependencies）：
  - `workflow.create_enterprise_plan`：录入企业 → 风险辨识/评估 → 生成预案 → AI 审查修订 → 导出 Word；
  - `workflow.regulatory_compliance`：企业画像 → 法规差距分析 → 报告。
- 工作流执行器：逐步骤执行、持久化状态（`workflow_runs` 表）、支持暂停/继续/失败重试、进度 SSE。
- 聊天入口：用户一句话触发工作流，助手转交执行器并持续汇报进度。

**测试**：工作流状态机单测（各步骤/失败/重试）；真实「录入→生成→导出」演练。

### 5.3 模块 13：跨会话记忆与偏好

**设计**：
- `user_preferences` 表：写作风格偏好（复用 STYLE_PARAM_MAP）、常用企业、报告偏好主题。
- `enterprise_profile_cache`：企业画像摘要缓存（生成时更新），聊天/生成共用，减少重复检索。
- 会话启动时注入偏好到 system prompt；用户显式调整时更新（「以后生成都用简洁风格」）。

**测试**：偏好读写、注入 system prompt 断言、跨会话生效集成测试。

### 5.4 模块 14：模型成本分层路由

**设计**：
- `ai_configs` 支持多系统级配置（`is_system` + 新增 `tier` 字段：`fast`/`standard`/`strong`）。
- `ModelRouter` 按任务分层：工具决策/检索/总结 → fast；章节生成/报告 → standard；审查修订/疑难问答 → strong。
- 每层配置可独立设置模型与上限；降级链（strong 不可用 → standard → fast）。

**测试**：路由选择单测；降级链故障注入测试；成本统计（tokens 按层汇总）观察。

## 6. 错误处理与安全

- 所有新表沿用既有审计惯例（created_at/updated_at，必要时 updated_by）。
- 工具执行失败不中断整轮：dispatch 返回 error JSON，agent 总结时说明失败项。
- 删除/覆盖类工具保留「先确认」既有规则；端到端工作流的导出、删除步骤需用户确认。
- 企业画像向量按 user_id 隔离，检索强制校验所有权（沿用 `_verify_enterprise_ownership`）。
- LLM 重试不重试 401（密钥错误），避免死循环与浪费。

## 7. 交付与版本规划

| 版本 | 内容 | 预计周期 | 验收口径 |
|------|------|----------|----------|
| 0.4.0 | 阶段 1 模块 1-6 | 1-2 周 | 每缺陷修复复现用例通过 + 全量门禁 |
| 0.4.1 | 阶段 2 模块 7-10 | 1-2 周 | 法规命中率对比 + 审查报告演示 |
| 0.5.0 | 阶段 3 模块 11-14 | 2 周 | 端到端工作流演练 + 成本分层观察 |

每版本沿用：git save → 实现（TDD）→ 全量 pytest/tsc → package-release.sh（--system）→ 0.3.x 同款安装/升级流程（备份 → 解压覆盖 → docker compose up -d --build，数据卷不动）。

## 8. 待确认事项

1. 阶段 1 的 `chat_tool_calls` 表与消息轨迹保存方案是否接受（引入新表）。
2. 阶段 2 自动修订默认执行 vs 需人工确认（本文档默认自动执行 + 可回退）。
3. 阶段 3 的模型分层是否受当前成本预算约束（多配置多 key 需求）。
