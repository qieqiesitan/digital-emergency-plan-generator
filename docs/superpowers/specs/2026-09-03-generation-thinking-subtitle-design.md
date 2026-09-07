# 预案生成“思考要点字幕”设计（2026-09-03）

## 背景与目标

预案章节生成使用推理型模型（deepseek-v4-flash）时，每章请求会先经历较长的“思考期”再输出正文。实测单章首字等待可达 100 秒以上、整章约 116 秒，批量生成期间界面长时间只有进度条、无任何过程反馈，体验上表现为“卡死/没反应”。

目标：在不改变生成链路（保持串行、保持前文注入与提示词不变）的前提下，把模型的思考过程转化为轻量的“要点字幕”实时展示，让用户明确感知到“模型仍在工作、正在想什么”，并区分思考阶段与写作阶段。

## 范围

### 做

- 展示入口：桌面端批量生成（SSE）、桌面端单章生成（SSE）、移动端单章生成（SSE）、移动端批量生成（后台生成 + 轮询）。
- 字幕形态（已与用户视觉确认，v2 原型）：聊天式思考短句，无“正在思考：”前缀，短句随推理逐句替换，最长约 40 字，刷新间隔约 2 秒；进入写作阶段后字幕消失，正文实时上屏。
- 阶段兜底：推理流不可用或切不出要点句时，显示阶段文案与已用秒数（如“正在分析本章所需的企业风险与法规信息… · 1 分 43 秒”）。
- 隐私：推理内容仅在进程内存中瞬时加工，不落库、不进日志、不进版本快照，生成结束/取消/异常后清理。

### 不做（本期）

- 提示词瘦身 / 企业数据按章节裁剪（方向 3，已搁置）。
- 并发生成章节（方向 2 约束：每章需前文已生成内容，保持串行）。
- 修改 max_tokens / reasoning 预算策略（已有空返回重试兜底，本期不改）。
- 桌面“选中段落重生成”与“风格预览”的字幕（入口较小，后续如需再扩）。
- 思考要点的历史留存或断线补看。

## 约束与原则

- 生成调用链保持现状：逐章串行、previous_context 注入、空结果自动重试一次。
- llm_client 现有调用方契约不变：新增回调均为可选参数，默认行为与现在完全一致。
- 字幕是纯展示层：推理回调异常、事件丢失、状态查询失败都不得影响生成本身。
- 推理文本不进日志；logger 只记录阶段切换等非内容信息。

## 后端设计

### 1. 暴露推理流（llm_client）

在 `_stream_response` 与 `llm_chat_completion`（stream 路径）增加可选参数 `reasoning_cb: Callable[[str], None] | None`：

- 每当 SSE delta 中出现 `reasoning_content` 时，把该片段交给 `reasoning_cb`（不缓冲、不落库）。
- 默认 `None` 时行为与现在完全一致；`_stream_llm_chunks` 同步增加同名可选参数并透传。
- 非流式路径（`llm_collect_all`）不涉及，保持原样。

### 2. 要点加工（轻量规则，不额外调用模型）

新增纯函数模块（建议 `backend/app/services/thinking_brief.py`）：

- 按当前章节累积收到的推理文本（进程内存，仅本次生成期间）。
- 按句切分（`。！？\n`），候选句过滤：长度 8–60 字，且含“分析/结合/需要/根据/确保/考虑/风险/资源/组织/疏散/法规/火灾/事故”等要点词之一。
- 输出“最新一条尚未展示的候选句”，截断至 40 字；同一句不重复推送。
- 无可展示句时返回阶段兜底文案（由调用方拼上“已用时”）。

### 3. SSE 通道（桌面批量、两端单章）

- 新增事件：`{"type": "thinking", "section_key": "...", "message": "结合火灾风险源分布与组织架构，先明确报警与初起处置分工"}`。
- 节流：同一章节两次 `thinking` 事件间隔 ≥ 1.5 秒。
- 收到第一个正文 chunk 后停止发送 `thinking`（进入写作阶段）；下一章开始时重置累积缓冲。
- 现有 `chunk/progress/section_done/batch_done/error` 事件语义不变。

### 4. 后台/聊天批量通道（移动端批量）

- `run_batch_generation` 的默认分支（`stream_fn is None`）从非流式 `_stream_llm` 改为“内部流式收集”（复用 `_stream_llm_chunks_with_retry`），对外行为与 token 消耗不变。
- 流式过程中通过 `reasoning_cb` 更新进程内状态（见下），从而支持移动端轮询读到实时要点。

### 5. 进程内生成状态（新模块 generation_progress）

新增 `backend/app/services/generation_progress.py`，提供进程内 dict（keyed by plan_id）的读写与清理：

```text
{
  "phase": "idle | thinking | writing | done",   // done 表示本章结束/整批结束
  "section_key": "...",
  "section_title": "...",
  "index": 1,            // 当前第几章（1-based）
  "total": 7,
  "thinking_brief": "...",   // 最新要点句或阶段文案
  "started_at": 1234567890.0,
  "updated_at": 1234567890.0
}
```

- SSE 批量/后台批量/聊天批量统一通过该模块维护状态；SSE 路径同时发事件。
- `GET /plans/{id}/generate/status` 在保留 `generating`、`failed_sections` 的基础上返回上述字段；无状态时返回 `phase: "idle"`。
- 清理时机：整批 finalize、取消、异常兜底恢复 status 时统一 `clear(plan_id)`；轮询端在 `generating=false` 后停止。

### 6. 隐私与安全

- 推理原文与加工缓冲仅存在于后端进程内存，键为 plan_id；不写任何表、不写日志、不进 `plan_versions.snapshot`。
- 状态接口只返回“最新一条要点句”，不返回原始推理全文；后端重启即全部丢失。

## 前端设计（以 v2 原型为准）

### 文案与样式

- 字幕：普通正文级文字（约 13px，深灰 #374151），无前缀、无底色强调，句末带光标；一条只占 1–2 行。
- 章节级信息仍由进度区展示：“批量生成中 · 第 2/7 章 / 已用时 1 分 43 秒”。
- 写作阶段：字幕消失，正文照常流式上屏；写作中若有“✅ 正在撰写…”轻提示（沿用现有生成中文案即可）。

### 桌面端（PlanEditorPage）

- 处理新增 `thinking` 事件：更新当前章节字幕；收到该章节首个 content chunk 时清空字幕。
- 新章节 `progress` 事件到来时重置字幕缓冲与显示。
- 生成结束/失败/停止时清空字幕。

### 移动端单章（PlanEditorScreen 单章 SSE）

- `onData` 中新增 `event.type === "thinking"` 分支：更新生成横幅下的字幕；绝不能落入“content 累积”逻辑。
- 首个 content chunk 到达后清除字幕，保留现有正文实时刷新。

### 移动端批量（后台 + 轮询）

- 轮询间隔从 15 秒改为“生成中 3 秒”；停止条件沿用：`generating=false` 或 `failed_sections.length>0`。
- 轮询上限从固定 8 次改为次数上限 200 次（约 10 分钟）兜底，避免生成长任务被静默放弃（修复现状“约 2 分钟放弃”的问题）。
- 渲染：生成横幅显示“2 / 7 · 思考中 1 分 43 秒”+ 字幕；`phase=writing` 时隐藏字幕；结束后显示原有失败重试提示。

## 错误处理

- `reasoning_cb` 内部异常一律捕获忽略，不影响正文生成。
- 推理流缺失（非推理模型、代理裁剪、断流）→ 仅显示阶段文案 + 计时。
- `thinking` 事件丢失或前端漏处理 → 不影响章节保存；前端必须保证未知事件不会拼入正文。
- 状态查询失败/无状态 → 前端继续用已有轮询逻辑，不阻塞。

## 测试策略

后端单测：

- 要点加工：候选句筛选、去重、40 字截断、无可展示句时兜底文案。
- llm_client：`reasoning_cb` 收到 reasoning_content 片段；缺省参数行为不变（现有测试不破）。
- 节流：同一章节 thinking 事件间隔 ≥ 1.5 秒。
- generation_progress：状态写入/读取/清理；finalize 与取消路径均清理。
- status 端点：返回新增字段；无状态时 phase=idle。
- 后台批量默认分支改流式后：空返回重试仍生效（既有测试覆盖）。

前端单测：

- `thinking` 事件渲染字幕、不进入正文累积。
- 移动端轮询渲染 phase/current/total/thinking_brief/elapsed。

真实验证：

- 手动生成一章：观察“思考字幕出现 → 约 2 秒更新 → 写作时消失 → 正文上屏”。
- 移动端批量：点批量生成后离开页面，3 秒轮询可见字幕与进度；生成长任务不再 2 分钟静默放弃。

## 涉及文件（供实现计划细化，非最终清单）

- 后端：`app/services/llm_client.py`、`app/routers/generation.py`、`app/services/plan_generation_service.py`、新增 `app/services/generation_progress.py`、新增 `app/services/thinking_brief.py`、对应测试。
- 前端：`services/generationService.ts`（类型与状态读取）、`pages/Plan/PlanEditorPage.tsx`、`mobile/screens/PlanEditorScreen.tsx`、`types/plan.ts`。

## 范围扩展：风险评估报告 / 应急资源调查报告（2026-09-03 追加）

同一“思考要点字幕”能力扩展到两份报告的分章节 AI 生成（两者均为 SSE 逐章生成，事件结构与预案一致）。

### 做

- 后端：`risk_assessment.py` 与 `resource_investigation.py` 的 `generate` 端点逐章输出 `thinking` 事件；共享 `_stream_llm_with_messages_chunked` 增加可选 `reasoning_cb`；新增“逐章事件队列”辅助函数，把推理要点实时透出（推理仍只存内存、不落库）。
- 前端：桌面 `RiskAssessmentTab`、`ResourceInvestigationTab` 与移动 `RiskAssessmentScreen`、`ResourceInvestigationScreen` 处理 `thinking` 事件并在进度区显示字幕；`types/riskAssessment.ts` 的 `SSEEvent` 增加 `"thinking"`。

### 不做

- 两份报告的“合并（merge）”与预览/导出流程不加字幕（非逐章 LLM 流）。
- 报告生成不做空结果重试改造（本期仅加字幕；保留现状）。

### 验证

- 后端：逐章事件辅助函数单测（thinking/chunk/end/error）、两个端点回归。
- 前端：4 个文件类型检查与手工验收——生成报告时进度区出现约 2 秒一更的思考字幕，写作阶段消失。

## 2026-09-07 复核修订（报告部分）

09-03 之后代码发生了报告侧重构（ReportWorkspace、章节级生成端点、单章/重生成共用生成器、逐章落库），原“范围扩展”章节中后端/前端落点需要修订：

- 后端：字幕事件需同时覆盖 **4 处逐章 LLM 流**——risk/resource 各自的“全量生成”循环，以及各自的单章/重生成共用生成器（`_risk_section_event_generator` / `_ri_section_event_generator`，桌面工作台单章生成走后者）。统一在共享的 `_stream_llm_with_messages_chunked`（risk_assessment.py，resource 复用导入）上加 `reasoning_cb`，并复用逐章事件队列辅助函数。
- 前端：桌面端字幕 UI 应加在**通用 `components/report/ReportWorkspace.tsx`**（全量生成与单章生成两处 SSE switch）；`RiskAssessmentTab.tsx` / `ResourceInvestigationTab.tsx` 只是 ReportWorkspace 的薄包装，不再承载 SSE 处理。移动端 `RiskAssessmentScreen` / `ResourceInvestigationScreen` 仍走全量 SSE，保持不变。
- 命名注意：后端已有 `report_generation_progress.py`（把“已完成章节”逐章**落库**）；本设计新增的是预案批量用的进程内 `generation_progress`（仅轮询、不落库），两者职责不同、不得混用或合并。
- 执行注意：`backend/app/routers/risk_assessment.py` 存在他人未提交改动（章节摘要重建与四色图兜底）。执行报告任务前应先提交/暂存该文件既有改动，避免与字幕改动混提。
