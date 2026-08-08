# 后端三连重构设计规格：LLM 调用统一 / 批量生成合并 / chat_dispatch 收尾

> 生成日期：2026-08-08
> 状态：v2（2026-08-08 用户完成一轮代码优化后重新评估更新；v1 已获批准）
> 前置文档：`docs/codebase-optimization-plan.md`（2026-07-20，本规格是其 1.1/1.2/1.3/2.3 项的收尾落地）

---

## 1. 背景与目标

2026-07-20 的《代码库优化方案》中 P0 项「统一 LLM 调用层」「合并 generation.py 批量生成逻辑」「泛化 chat_dispatch CRUD 模式」只落地了一部分：

- `services/llm_client.py` 已建成，但仍有 4 个模块共 9 处调用绕过它自行实现 httpx 直连，厂商 base URL 映射在 6 个文件中重复。
- `generate_batch` 与 `generate_batch_background` 共享约 90% 的准备代码和生成循环，但各自维护一份。
- `chat_dispatch.py` 的 generic CRUD 基础设施已存在，但遗留 3 个未接线的死函数，8 个委托函数各自复制 try/except 样板；`EnterpriseResponse` 与 `EnterpriseBase` 重复声明 8 个字段。

2026-08-08 用户完成的一轮代码优化（plan-generation 增强，commit `d5216ae` 等）已经实现了「批量生成公共引擎」：`_run_batch_generation`、`_finalize_batch_result`、`_clear_generation_state`、`_GenerationCancelled`、`_failed_sections` 记录，并配套 `backend/tests/test_generation_batch_refactor.py`（6 个引擎级测试）。阶段 2 因此从「合并两个函数」缩小为「消除残余准备块重复 + 补测试」。

本规格目标（v2）：在不改变当前基线行为的前提下，完成阶段 1（LLM 调用统一）、阶段 2 收尾（批量准备块去重）、阶段 3（chat_dispatch 收尾），并为重构后的代码补齐回归测试。

## 2. 范围

### 2.1 包含

- 阶段 1：LLM 调用统一（`llm_client.py` 接口扩展 + 9 处调用迁移 + base URL/解密收敛）。
- 阶段 2：批量生成收尾（`generation.py` 公共准备函数提取；公共生成引擎已由 2026-08-08 优化实现，不再重复设计）。
- 阶段 3：chat_dispatch 收尾（死代码删除、委托样板收口、`EnterpriseResponse` 字段去重）。
- 顺带清理（与上述改动同文件，随阶段完成）：
  - `ai_config.py` 的厂商 base URL 映射改为复用 `llm_client.API_BASE_MAP` / `_get_api_base`；
  - `sync.py`、`llm_reranker.py` 改为直接从 `app.services.llm_client` 导入解密函数，消除经 `app.routers.generation` 的间接路由依赖。
- 为每个阶段新增回归测试（后端）。

### 2.2 不包含（明确排除）

- four-color-ai 与 backend 的双份维护（用户明确不着急，另行立项）。
- 仓库噪音清理、前端双代码库、测试盲区整体补强（后续单独推进）。
- 任何行为调整：超时参数统一、错误码统一、重试/熔断、消息文案优化等一律不做，仅消除重复。
- `generation.py` 中已迁移过的 `_stream_llm_chunks` / `_stream_llm` 仅做错误包装适配，不重写其逻辑。

## 3. 总体原则

### 3.1 严格行为等价

用户已确认（选项 A）：重构只消除重复，不改任何外部行为。各调用方现状的差异（超时、payload 键、错误文案、错误处理分支）全部保留，差异点由调用方薄包装维持。

### 3.2 验收标准

用户已确认（选项 B）：

1. backend 全量 pytest 通过（现状 150+ 测试）；
2. 每个阶段新增回归单测通过；
3. 前端 `tsc -b` 与 vitest 不回归（本次不涉及前端代码，仅确认无影响）；
4. 全部完成后 Docker 容器重启，真实冒烟以下链路：
   - AI 对话一次（chat SSE 流式 + 工具调用）；
   - `/generate/batch` SSE 批量生成一次（观察事件序列正常）；
   - `/generate/batch/background` 后台生成一次（观察最终状态与版本快照）；
   - chat 工具调用一次（如导出 DOCX 或生成报告）。
   - 冒烟时同时确认新基线行为：SSE/后台结束后 `_active_generations[plan_id]` 被清除为 False、`_failed_sections` 有值（失败时）、batch_done 事件携带 `failed_sections`。

## 4. 现状盘点（证据）

### 4.1 LLM 调用重复点

| 位置 | 函数 | 现状关键参数 | 错误行为 |
|---|---|---|---|
| `backend/app/routers/chat.py:88` | `_call_llm` | 非流式，timeout=60，tools=CHAT_TOOLS | 抛 `Exception("AI调用失败: {status} {text}")` |
| `backend/app/routers/chat.py:103` | `_call_llm_stream` | 流式，timeout=180，无 tools | 抛 `Exception("AI调用失败: ...")` |
| `backend/app/routers/chat.py:131` | `_collect_llm` | 非流式，timeout=180，无 tools，返回 content | 同 `_call_llm` |
| `backend/app/routers/risk_assessment.py:173` | `_stream_llm_with_messages` | 流式收集为 str | 透传 |
| `backend/app/routers/risk_assessment.py:180` | `_stream_llm_with_messages_chunked` | 流式，timeout=120 | decrypt 失败→HTTPException(500,"AI config key decryption failed")；其他抛 `Exception("LLM call failed: ...")` |
| `backend/app/routers/risk_assessment.py:220` | `_stream_llm_with_system` | 组装 system+user 消息 | 同上 |
| `backend/app/regulations/sync.py:219` | `_ai_extract_articles` | timeout=600，temperature=0.1，max_tokens 覆盖，无 top_p | 任何失败静默 `return []` |
| `backend/app/regulations/sync.py:302` | `ai_parse` | timeout=600，temperature=0.1，无 top_p | 自定义文案："DeepSeek API Key 无效..." / "AI API 错误 (HTTP ...)" |
| `backend/app/regulations/llm_reranker.py:94` | `_call_llm` | timeout=30，temperature=0，max_tokens=500，无 top_p | 抛 `Exception("LLM API error: HTTP {status}")`，调用方回退评分排序 |

厂商 base URL 映射副本位置：`chat.py:92/107/136`、`risk_assessment.py:187`、`sync.py:233/314`、`llm_reranker.py:105`、`ai_config.py:57`。

解密函数间接依赖：`sync.py`、`llm_reranker.py` 从 `app.routers.generation` 导入 `_decrypt_api_key`（实际是 `llm_client.decrypt_api_key` 的再导出），存在路由层依赖。

### 4.2 批量生成重复点

2026-08-08 优化后，`generation.py`（当前 1043 行）已有：

- 公共引擎 `_run_batch_generation`（`generation.py:386`）：逐章生成、写库、Mermaid 预渲染、失败统计、`stream_fn`/`on_progress`/`on_section_done`/`should_stop`/`use_section_number` 回调与开关；
- 公共收尾 `_finalize_batch_result`（`generation.py:463`）：completed/draft 判定 + 版本快照（复用 `versions._build_snapshot`）；
- 状态与失败清单：`_clear_generation_state`（置 False，不再 pop）、`_failed_sections`（供 `get_generation_status` 轮询）、`_GenerationCancelled`（取消不算失败）。

**残余重复**：公共准备块（p 404 → ai_config 400 → 企业/资源/风险上下文收集 → `_enrich_with_reports` → body keys 解析 → 章节过滤）在以下 5 个函数中重复出现：

- `generate_batch`（`generation.py:509`，准备块 517-549）
- `generate_batch_background`（`generation.py:699`，准备块 704-747）
- `generate_section`（`generation.py:800`，准备块 804-826）
- `regenerate_selection`（`generation.py:903`，准备块 ~920）
- `generate_preview`（`generation.py:984`，准备块 ~1012）

其中两个批量端点的准备块逐字一致；另外 3 个函数在准备块之后各有不同逻辑（如 `custom_instruction` 解析、单章重试），本次不纳入提取范围，避免扩大改动面。

**新基线行为（阶段 2 收尾必须保持，不再视为"差异项"）**：

- SSE 与后台都在 finally 中 `_clear_generation_state(plan_id)`（置 False），即旧版「SSE 不清理」的怪癖已被修复；
- `_failed_sections` 在生成开始时清空、结束时写入，`batch_done` 事件携带 `failed_sections`；
- `generate_batch_background` 保留 stale 状态守卫（generating + 无活跃任务 → 重置 draft）与"正在生成中"防重、空章节守卫；
- SSE 用 `_stream_llm_chunks` 逐 chunk 发事件（取消发"生成已取消"并抛 `_GenerationCancelled` 中断）；后台用 `_stream_llm` 非流式收集、取消静默 break（`should_stop`）；
- `use_section_number`：SSE 传 `section_number=i+1`，后台不传（历史行为）。

另有一个冗余：`generate_batch` 函数内 `import asyncio as _asyncio`（`generation.py:563`）与顶层 `asyncio` 导入（`generation.py:22`）重复，收尾时顺手删除。

### 4.3 chat_dispatch 现状

- generic 基础设施已存在：`_generic_list/create/update/delete`（`chat_dispatch.py:88-165`）+ 实体配置 `_RS_CFG` / `_RES_CFG` / `_ENT_CFG` / `_PLAN_CFG`。
- 已接线的委托函数：`_list_resources` / `_create_resource` / `_update_resource` / `_delete_resource` / `_delete_plan` / `_create_enterprise`（含查重）/ `_update_enterprise`。
- 死代码：`_create_risk_source` / `_update_risk_source` / `_delete_risk_source` 为 generic 委托实现，但既未注册进 `_FUNCTIONS`（`chat_dispatch.py:902`），也未在 `CHAT_TOOLS`（`chat.py:24`）声明，无任何调用方。
- 特殊函数（保留手写）：`_list_enterprises`（keyword）、`_get_enterprise`（风险上下文）、`_delete_enterprise`（级联删除）、`_list_risk_sources`（风险管控上下文）、`_list_plans`/`_get_plan`/`_create_plan`（模板章节）、`_list_templates`、报告列表/详情、法规系列、仪表盘、autofill、导出、生成。
- 每个委托函数都复制了 5 行 try/except `_ErrorDict` 样板。

### 4.4 Enterprise 字段重复

`schemas/enterprise.py` 中 `EnterpriseBase`（约 38 行起）已定义 32 个共享字段；`EnterpriseResponse` 重复声明 8 个：

- 同类型（可安全合并）：`last_plan_filing_authority`、`building_overview`、`floor_plan_url`、`gis_lat`、`gis_lng`。
- 类型不同（Base 为 `str|None`，Response 为 `DatetimeStr|None`，序列化格式不同）：`established_date`、`fire_approval_date`、`last_plan_filing_date`。

## 5. 阶段 1：LLM 调用统一

### 5.1 llm_client 接口扩展（`backend/app/services/llm_client.py`）

1. 新增异常 `LLMError(Exception)`：
   - 构造参数：`status_code: int`、`text: str`；
   - `__str__` 返回 `f"AI调用失败: {status_code} {text[:300]}"`（无空格，与 chat.py 非流式现状一致）。
2. `llm_chat_completion(messages, ai_config, stream=False, timeout=120, tools=None, payload_overrides=None, include_top_p=True)`：
   - `tools` 非 None 时 payload 增加 `"tools": tools`；
   - `payload_overrides` 非 None 时浅合并覆盖标准 payload 同名键（用于 temperature/max_tokens 覆盖）；
   - `include_top_p=False` 时不写入 `top_p` 键；
   - 非 200 响应统一抛 `LLMError(resp.status_code, text)`（非流式与流式一致）。
3. 新增 `llm_stream_all(messages, ai_config, timeout=120) -> str`：遍历 `llm_chat_completion(stream=True)` 收集为完整文本。
4. `llm_text_completion` 的错误分支改为基于 `LLMError.status_code` 判断（401 → "AI API Key 无效或已过期，请在系统设置中重新配置 AI 模型" + 500；其他非 200 → 500 + 原消息；超时 → 504；其他异常 → 502），与现有字符串前缀匹配行为等价。

### 5.2 迁移矩阵

| 调用方 | 迁移后调用 | 薄包装职责 |
|---|---|---|
| chat.py `_call_llm` | `llm_chat_completion(messages, cfg, stream=False, timeout=60, tools=CHAT_TOOLS)` | 无（错误透传，LLMError str 与现状一致） |
| chat.py `_call_llm_stream` | `llm_chat_completion(messages, cfg, stream=True, timeout=180)` | catch `LLMError` → 重建 `Exception(f"AI调用失败: {e.status_code} {e.text[:300]}")` |
| chat.py `_collect_llm` | `llm_collect_all(messages, cfg, timeout=180)` | 无 |
| risk_assessment.py `_stream_llm_with_messages_chunked` | `llm_chat_completion(messages, cfg, stream=True, timeout=120)` | 先 try `decrypt_api_key` 失败 → `HTTPException(500, "AI config key decryption failed")`；catch `LLMError` → 重建 `Exception(f"LLM call failed: {e.status_code} {e.text[:300]}")` |
| risk_assessment.py `_stream_llm_with_messages` | `llm_stream_all(messages, cfg, timeout=120)` | 同上（复用 chunked 包装的错误语义） |
| risk_assessment.py `_stream_llm_with_system` | 保持（组装消息后调 `_stream_llm_with_messages`） | 无 |
| sync.py `_ai_extract_articles` | `llm_chat_completion(messages, cfg, timeout=600, include_top_p=False, payload_overrides={"temperature": 0.1, "max_tokens": min(65536, (cfg.max_tokens or 16384) * 2)})` | 任何异常 → `return []`（现状） |
| sync.py `ai_parse` | 同上但 `max_tokens=cfg.max_tokens or 16384` | catch `LLMError` → 含 "Invalid API Key"/"invalid" → 原 "DeepSeek API Key 无效..." 文案；否则 `Exception(f"AI API 错误 (HTTP {e.status_code}): {e.text[:500]}")` |
| llm_reranker.py `_call_llm` | `llm_chat_completion(messages, cfg, timeout=30, include_top_p=False, payload_overrides={"temperature": 0, "max_tokens": 500})` | catch `LLMError` → `Exception(f"LLM API error: HTTP {e.status_code}")` |
| generation.py `_stream_llm_chunks` | 保持现有调用 | catch `LLMError` → `HTTPException(500, f"AI 调用失败: {e.status_code} {e.text[:300]}")`（保持带空格文案） |

说明：

- `_call_llm` 非流式透传 LLMError（str 无空格）与现状文案一致；流式路径因 llm_client 与 chat.py 原文案存在空格差异，由薄包装重建。
- 迁移后删除各调用方文件内的 base URL 映射副本与 httpx 生命周期代码；`chat.py` 保留 `CHAT_TOOLS` 定义与 `_build_tool_messages`。

### 5.3 base URL 与解密收敛

- `ai_config.py` 测试连接改用 `_get_api_base(provider, base_url)`。
- `sync.py` / `llm_reranker.py` 删除 `from app.routers.generation import _decrypt_api_key`，改为 `from app.services.llm_client import decrypt_api_key`。

### 5.4 阶段 1 测试

新增 `backend/tests/test_llm_client_migration.py`，使用 pytest monkeypatch 替换 `httpx.AsyncClient`：

- 对每个迁移函数断言请求 payload（键集合、tools、temperature/max_tokens 覆盖、top_p 存在性）、timeout、Authorization 头与迁移前一致；
- 模拟非 200 响应，断言错误消息逐字等于迁移前文案（chat 非流式/流式、risk_assessment、sync 两处、reranker、generation）；
- 断言 `llm_text_completion` 的 401/超时/连接失败分支映射不变；
- 断言 `llm_stream_all` 收集结果与逐 chunk 拼接一致。

## 6. 阶段 2：批量生成合并

> v2 说明：本阶段从「合并两个批量函数」变为「收尾」。公共引擎已由 2026-08-08 优化实现并有 6 个引擎级测试（`test_generation_batch_refactor.py`），剩余工作为准备块去重与补充测试。

### 6.1 抽取函数（v2 剩余工作）

1. `_get_plan_or_404(plan_id, user, db)`：抽出 p 的 404 查询（两个批量端点共用）。
2. `_collect_batch_context(plan_id, p, request, db, current_user)`：
   - 返回 `(p, ai_config, ent_data, target_sections)`（`section_tuples` 由调用方从 `target_sections` 现取）；
   - 包含：ai_config 400、企业上下文收集、`_enrich_with_reports`、body keys 解析、章节过滤；
   - 不包含：stale 守卫、空章节守卫、置 generating、`_active_generations` 赋值（留在端点，守卫逻辑不随提取而移动）。
3. 删除 `generate_batch` 函数内冗余的 `import asyncio as _asyncio`（`generation.py:563`）。

### 6.2 端点改造

- `generate_batch`：`p = await _get_plan_or_404(...)` → `ctx = await _collect_batch_context(plan_id, p, request, db, current_user)` → 其余逻辑（置 generating、建 queue、`_run_batch_generation` + 事件回调、`_finalize_batch_result`、finally `_clear_generation_state`）**保持现状不变**。
- `generate_batch_background`：`p = await _get_plan_or_404(...)` → stale 守卫/正在生成中判断（保持现状）→ `ctx = await _collect_batch_context(plan_id, p, request, db, current_user)` → 空章节守卫 → 其余逻辑保持现状不变。

除替换为上述两个助手外，两端点内部代码逐字不动（事件序列、回调、失败清单、状态清理均维持 2026-08-08 优化后的新基线）。

### 6.3 阶段 2 测试

在既有 `test_generation_batch_refactor.py`（引擎级 6 测试，保留不动）基础上新增 `backend/tests/test_batch_context.py`：

- `_collect_batch_context`：mock request/db，断言返回的 ai_config 400 分支、keys 解析分支（无 body / 空 body / 带 section_keys）、章节过滤结果；
- `_get_plan_or_404`：404 分支与正常返回；
- 两个端点壳（用 ASGI TestClient + mock DB/LLM）各跑一次冒烟级测试：SSE 事件序列关键事件存在（progress/batch_done）、后台返回消息与守卫分支（正在生成中 / 空章节）。

## 7. 阶段 3：chat_dispatch 收尾 + Enterprise 字段去重

### 7.1 死代码删除

删除 `chat_dispatch.py` 中 `_create_risk_source` / `_update_risk_source` / `_delete_risk_source` 三个函数（未注册、未声明、无调用）。

### 7.2 委托样板收口

新增辅助：

```python
async def _delegate_generic(op, db, user, args, cfg):
    try:
        return await op(db, user, args, cfg)
    except _ErrorDict as e:
        return e.data
```

已接线的委托函数改为单行调用：`return await _delegate_generic(_generic_list, db, user, args, _RES_CFG)`（resource ×4、`_delete_plan`、`_update_enterprise`）；`_create_enterprise` 保留查重逻辑后调用 `_delegate_generic(_generic_create, ...)`。行为等价（现状同样是捕获 `_ErrorDict` 返回 `e.data`）。

### 7.3 EnterpriseResponse 字段去重（`backend/app/schemas/enterprise.py`）

- 删除 Response 中 5 个同类型重复声明：`last_plan_filing_authority`、`building_overview`、`floor_plan_url`、`gis_lat`、`gis_lng`（继承 Base）；
- 保留 3 个日期字段的 Response 覆盖（`established_date` / `fire_approval_date` / `last_plan_filing_date` 为 `DatetimeStr|None`），并加注释说明：Base 为 `str`（输入态），Response 为 `DatetimeStr`（输出序列化格式），不可合并，否则输出格式变化。

### 7.4 阶段 3 测试

新增 `backend/tests/test_chat_dispatch.py`，对 `_FUNCTIONS` 注册的 handler 用黄金断言覆盖关键分支：

- `_list_enterprises` keyword 搜索、`_get_enterprise` 上下文组装、`_create_enterprise` 同名查重；
- `_create_plan` 带模板创建章节、`_delete_plan` 权限校验；
- `_list_resources` / `_create_resource` 委托 generic 的返回结构与 `_ErrorDict` 捕获；
- `_delete_enterprise` 级联删除与 uploads 清理调用；
- 法规检索系列的关键分支。

## 8. 实施顺序与提交策略

按以下顺序实施，每阶段独立提交（符合项目 `git save` / 增量提交习惯）：

1. 阶段 2 收尾（最小、先稳住 generation.py 新基线）→ 提交：`refactor(generation): extract shared batch context helpers`
2. 阶段 1（LLM 统一）→ 提交：`refactor(llm): unify all LLM call sites through llm_client`
3. 阶段 3（chat_dispatch 收尾）→ 提交：`refactor(chat): remove dead handlers, delegate generic CRUD, dedup enterprise schema`

每阶段完成标准：新增单测绿 + backend 全量 pytest 绿。全部完成后执行验收 B 的 Docker 冒烟。

## 9. 风险与回退

- **行为漂移风险**：集中在错误文案与事件序列。缓解：每个差异点都有单测断言；冒烟时逐链路核对。
- **新基线漂移风险**：阶段 2 收尾的基线是 2026-08-08 优化后的代码（状态清理、`_failed_sections`、`use_section_number` 差异），不是更早的旧版行为；提取准备块时不得顺手改动这些行为。
- **提取边界**：`generate_section` / `regenerate_selection` / `generate_preview` 也有相似准备块，但后续逻辑不同，本次不提取，避免范围膨胀；如需提取，另行评估。
- **回退**：每阶段一个提交，出错用 `git undo` 回退到前一 savepoint；工作区并行会话的改动（TASKS.md、.graphifyignore、上传目录）不触碰、不提交。
- **部署**：Docker 容器 4 worker 不热加载，改代码后需 `docker restart emergency-plan-backend` 生效（冒烟步骤已包含）。

## 10. 规格自检记录

- 占位符扫描：无 "待定"/TODO/未完成章节。
- 内部一致性：迁移矩阵与错误处理契约一致；阶段 2 已按 v2 新基线更新（引擎已存在，剩余为准备块去重）。
- 范围检查：聚焦 3 个模块 + 同文件顺带清理，可被一个实现计划覆盖（writing-plans 按阶段拆任务）。
- 模糊性处理：LLMError 消息格式已定（无空格）；日期字段去重方案已定（保留覆盖）；阶段 2 的 SSE/后台状态清理已按新基线（都清理）更新，旧版"SSE 不清理"不再作为保留项。
