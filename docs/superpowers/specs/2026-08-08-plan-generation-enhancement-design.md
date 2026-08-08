# 预案生成功能增强（方案 A 全量）— 设计规格

> **日期**：2026-08-08 | **状态**：设计中 | **范围**：3 批独立实施（内容可信度 / 导出与版本 / 质量与体验）

---

## 1. 概述

对现有企业应急预案 AI 生成功能做一次系统性增强，覆盖三方面：

1. **内容可信度**（第 1 批）：堵住 AI 在档案数据缺失时编造信息的风险；让模板元数据（哪些章节可 AI 生成、哪些应自动填充）真正生效。
2. **导出与版本**（第 2 批）：导出编号真实化；版本快照与回滚补全（含图表与风格）。
3. **质量与体验**（第 3 批）：生成后内容级质量校验；失败章节一键重试；移动端批量生成接入同一后端链路；AI 生成前后 Diff 对比。

三批相互独立、可分别验收与提交。**用户已明确：评审/审批等流程状态功能不在本次范围。**

---

## 2. 现状基础

| 组件 | 现状 |
|------|------|
| `generation.py::_collect_enterprise_data` | 企业字段原样注入提示词，空值也注入，无缺失标注 |
| `prompt_cache.py` COMPLIANCE_BLOCK | 有术语/结构底线，无「禁止推断缺失信息」护栏 |
| `seed_templates.py` | 模板已定义 `ai_generatable`/`auto_fill`/`auto_fill_source`/`data_dependencies` |
| `plans.py::_create_sections_from_template` | 只复制 key/title/level/sort_order，丢弃上述 4 个元数据字段 |
| `PlanSection` 模型 / `SectionResponse` | 无元数据字段；前端编辑页硬编码「全部章节可生成」 |
| `PlanProject` 模型 | 无 `plan_number`/`version_number`；`export.py` 用 `getattr` 兜底硬编码 `XXZYT-YA-001` |
| `versions.py` | 快照仅存章节 HTML + `ai_generated`，不含 `mermaid_svgs`/风格参数 |
| `export.py::validate_plan_export` | 仅检查空章节 + Mermaid 类型声明，无内容级校验 |
| `generation.py` | `generate_batch` 与 `generate_batch_background` 约 176 行重复逻辑 |
| 移动端 `PlanEditorScreen` | 批量生成按钮仅提示「请在桌面端使用」；单章生成走 `generate/{key}` SSE |
| 组织架构 `org_structure` | `OrgGroup[]`，每组含 `group_name` 与 `members[]`（role/name/position/phone/responsibilities） |
| `external.py` | 复用 `_create_sections_from_template` 与 `_build_section_prompt`，改动需保持兼容 |

---

## 3. 批次划分总览

| 批次 | 主题 | 包含项 |
|------|------|--------|
| 第 1 批 | 内容可信度 | 3.1 数据防幻觉护栏；3.2 模板元数据落地（含自动填充） |
| 第 2 批 | 导出与版本 | 3.3 导出编号真实化（含签署页数据）；3.4 版本快照补全 |
| 第 3 批 | 质量与体验 | 3.5 生成后质量校验；3.6 失败章节重试；3.7 移动端批量链路统一（含批量代码去重）；3.8 Diff 对比弹窗 |

每批独立 commit、独立回归验证（后端全量 pytest + 前端 tsc/vitest）。

---

# 第 1 批：内容可信度

## 3.1 数据防幻觉护栏

### 目标

企业档案字段缺失时，AI 不得依据先验知识编造地址、法人、电话、信用代码等信息，必须输出「（待补充）」占位符。

### 后端改动

**a. `_collect_enterprise_data`（generation.py:180）加缺失标注**

对所有字符串/文本字段应用统一处理：空字符串或 None → `"（待补充）"`。涉及字段：

`address`、`industry`、`business_scope`、`building_overview`、`org_structure`（空数组→空数组，不标）、`surrounding_info`、`legal_representative`、`credit_code`、`economic_type`、`registered_capital`、`phone`、`land_area`、`building_area`、`safety_officer`、`safety_standardization`、`fire_approval`、`main_products`、`hazardous_chemicals`、`special_equipment`。

实现方式：提取一个私有辅助函数 `_missing(v) -> str`，返回 `v if v not in (None, "") else "（待补充）"`，其余字段保持原样。风险源/应急资源列表为空时保持空列表。

**b. system prompt 追加护栏（prompt_cache.py COMPLIANCE_BLOCK）**

在 COMPLIANCE_BLOCK 末尾追加：

```
【数据真实性护栏——必须严格遵守】
1. 企业档案中以"（待补充）"标注的信息一律视为缺失，禁止推断、禁止编造。
2. 严禁编造地址、法定代表人、联系电话、统一社会信用代码、注册资本等企业基本信息。
3. 正文涉及缺失信息时，直接书写"（待补充）"，不得用其他文字替代。
4. 全部正文内容必须以企业档案数据为唯一事实来源，不得引入档案之外的企业信息。
```

**c. 一致性校验**

生成后关键字段一致性校验并入第 3 批 3.5（与质量校验框架同源），第 1 批不重复实现。

### 验收标准

- `_collect_enterprise_data` 对空地址返回 `"（待补充）"`，不返回 `None`。
- system prompt 含数据真实性护栏文本。
- 现有单测 `test_generation_enterprise_data.py` 更新后通过（断言空字段为「（待补充）」）。

---

## 3.2 模板元数据落地

### 目标

模板中定义的 `ai_generatable`/`auto_fill`/`auto_fill_source`/`data_dependencies` 真正落到章节数据与前端交互上：不可 AI 生成的章节不出现 AI 按钮，应自动填充的章节提供「自动填充」能力。

### 后端改动

**a. `PlanSection` 模型加 4 字段**（models/enterprise.py）

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ai_generatable` | Boolean | True | 是否允许 AI 生成 |
| `auto_fill` | Boolean | False | 是否支持自动填充 |
| `auto_fill_source` | String(50) nullable | None | 填充来源（当前支持 `org_structure`） |
| `data_dependencies` | JSONB | `list` | 依赖的数据维度（如 `["risk_sources"]`） |

**b. 迁移 SQL**（新增 `backend/db_migration_plan_section_metadata.sql`）

```sql
ALTER TABLE plan_sections
  ADD COLUMN IF NOT EXISTS ai_generatable BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS auto_fill BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS auto_fill_source VARCHAR(50),
  ADD COLUMN IF NOT EXISTS data_dependencies JSONB NOT NULL DEFAULT '[]';
```

存量章节获得默认值，不破坏现有数据。

**c. `_create_sections_from_template`（plans.py:39）复制元数据**

递归创建章节时，从模板 structure 读取并写入上述 4 个字段（含 subsections 递归）。`external.py` 调用同一函数，签名不变，自动获得元数据。

**d. `duplicate_plan` 复制章节时一并复制 4 个字段。**

**e. `SectionResponse` schema 加 4 字段**（schemas/plan.py），`sections.py` 的 `model_validate` 自动带出，路由无需改动。

**f. 新增自动填充接口**

`POST /api/v1/plans/{plan_id}/sections/{section_key}/autofill`（sections.py）

逻辑：

1. 校验预案归属当前用户、章节存在且 `auto_fill=True`，否则 400。
2. 按 `auto_fill_source` 分派：
   - `org_structure`：从 `enterprise.org_structure` 构建 HTML。
     - 每个 `OrgGroup` 渲染一个表格：标题为组名，表头「序号 / 姓名 / 职务 / 联系电话 / 职责」，成员为行；成员为空时跳过该组。
     - `org_structure` 为空或所有成员为空 → 400「请先维护企业组织架构」。
   - 其他/未知 source → 400「不支持的自动填充来源」。
3. 将 HTML 写入 `s.content`，`s.ai_generated=False`，commit 后返回 `SectionResponse`。

### 前端改动

**a. `types/plan.ts`**：`PlanSection` 加 4 个字段；`SectionUpdate` 不变。

**b. `PlanEditorPage.tsx`**

- 删除硬编码 `templateSections`（当前全部 `ai_generatable: true` 的平铺映射），改为直接用 `sections` 数组构建树节点，字段来自章节真实元数据。
- `ai_generatable=false` 的章节：不渲染 `AIGenerateButton`。
- `auto_fill=true` 的章节：在 AI 按钮旁渲染「自动填充」按钮，点击调用 autofill 接口，成功后刷新章节数据并提示。
- `SectionTree` 的 🤖 标记改用真实 `ai_generatable`。

**c. `SectionTree.tsx`**：接收真实元数据（由父级传入），`ai_generatable` 控制 🤖 标记。

**d. 移动端 `PlanEditorScreen.tsx`**

- `ChapterNode` 增加 `aiGeneratable`/`autoFill` 字段，构建时取自章节真实元数据（替代当前硬编码 `aiGeneratable: true`）。
- 编辑页 AI 生成入口：`aiGeneratable=false` 时隐藏右上角 AI 按钮，显示「自动填充」按钮（若 `autoFill=true`）。
- `AIGenerationSheet` 的章节选择仅列出 `aiGeneratable=true` 的章节。

### 验收标准

- 新预案按模板创建后，章节接口返回真实元数据：现场处置方案「紧急联系电话」`ai_generatable=false`、`auto_fill=true`、`auto_fill_source="org_structure"`。
- 「紧急联系电话」章节不出现 AI 按钮；点击自动填充后生成真实电话表格，内容非 AI 生成。
- 组织架构为空时自动填充返回 400 且提示维护架构。
- 后端新增测试：模板元数据复制断言（含递归子章节）、autofill 接口（有架构填充 / 空架构 400 / 非 auto_fill 章节 400）、`duplicate_plan` 元数据保留。

---

# 第 2 批：导出与版本

## 3.3 导出编号真实化

### 目标

每份预案拥有真实的预案编号与文档版本号，导出 DOCX 时使用真实值；签署页数据从企业组织架构自动生成。

### 后端改动

**a. `PlanProject` 模型加 2 字段**

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `plan_number` | String(100) nullable | None | 预案编号，创建时自动生成，可手动覆盖 |
| `version_number` | String(50) nullable | None | 文档版本号，如 `A-2026-08`，可手动覆盖 |

与现有 `current_version`（int，版本库序号）语义不同，二者并存不冲突。

**b. 迁移 SQL**（并入 `db_migration_plan_section_metadata.sql` 或新增 `db_migration_plan_number.sql`）

```sql
ALTER TABLE plan_projects
  ADD COLUMN IF NOT EXISTS plan_number VARCHAR(100),
  ADD COLUMN IF NOT EXISTS version_number VARCHAR(50);
```

**c. 创建预案时自动生成编号**（plans.py `create_plan`）

新增私有函数 `_generate_plan_number(enterprise_name, plan_type, seq)`：

- 前缀：企业名去除空格后取前 4 个字符；不足 4 字符原样使用；为空用「企业」。
- 类型码：`comprehensive=ZH`、`special=ZX`、`onsite=XC`。
- 序号：该企业下同类型预案数量 + 1，三位补齐（`001`）。
- 格式：`{前缀}-{类型码}-{序号}`，示例：`陕西宝岳科技-ZH-001`（前 4 字符为「陕西宝岳」）。

`version_number` 默认 `A-{year}-{month:02d}`。

**d. `PlanCreate` schema 支持可选 `plan_number`/`version_number` 覆盖**；`PlanResponse` 增加 2 字段；`_build_plan` 带出。

**e. `export.py::export_plan_docx` 使用真实值**

删除 `getattr(plan, 'plan_number', '') or f"XXZYT-YA-001"` 兜底，改为：字段为空时提示用户在预案信息中补全（400「请先设置预案编号」），不再生成重复的硬编码编号。

**f. 签署页数据接入**

`export_plan_docx` 从 `enterprise.org_structure` 提取全部成员构建 `signers`：

```python
signers = [
    {"seq": i + 1, "name": m.get("name", ""), "title": m.get("position", "")}
    for g in (enterprise.org_structure or [])
    for m in g.get("members", [])
    if m.get("name")
]
```

非空时传给 `generate_plan_docx(signers=signers, ...)`；为空则不渲染签署页（保持现状）。

### 前端改动

**`PlanCreatePage.tsx`**：确认创建步骤新增两个可编辑输入框（预案编号、版本号），预填自动生成值，允许修改后提交。

### 验收标准

- 新预案自动获得编号，同企业同类型预案序号递增。
- 导出 DOCX 封面显示真实编号与版本号；两份不同预案导出编号不同。
- 企业组织架构有成员时，DOCX 含签署页且姓名/职务正确。

---

## 3.4 版本快照补全

### 目标

版本快照与回滚覆盖图表与风格，保证回滚后文档外观与内容一致。

### 后端改动

**a. 快照内容扩展**（`versions.py::create_version` 与 `generation.py` 两处自动快照）

快照结构从：

```json
{"title": "...", "sections": [{"section_key", "title", "content", "ai_generated"}]}
```

扩展为：

```json
{
  "title": "...",
  "style_preference": {...} | null,
  "advanced_prompt_overrides": {...} | null,
  "sections": [{"section_key", "title", "content", "ai_generated", "mermaid_svgs": {...} | null}]
}
```

**b. 回滚恢复**（`versions.py::rollback_version`）

- 章节：恢复 `content` 与 `mermaid_svgs`。
- 预案级：快照含 `style_preference`/`advanced_prompt_overrides` 时恢复对应字段；旧快照缺失该键时跳过（向后兼容，不报错）。

### 验收标准

- 生成含流程图的预案后保存版本，修改章节并回滚，章节内容与 Mermaid 图表均恢复。
- 旧版本（无新字段）回滚不报错，行为与现状一致。

---

# 第 3 批：质量与体验

## 3.5 生成后质量校验

### 目标

导出前提供内容级质量报告，覆盖占位符残留、关键档案信息一致性、章节完整性、Mermaid 语法。

### 后端改动

**a. 新增服务 `backend/app/services/plan_quality_service.py`**

`check_plan(plan, enterprise, sections) -> dict`，返回：

```python
{
  "valid": bool,
  "issues": [{"section_key", "section_title", "issue"}],
  "warnings": [{"section_key", "section_title", "warning"}],
}
```

检查规则（按优先级）：

1. **空章节**：required 或任意章节无内容 → issue（复用现有逻辑）。
2. **占位符残留**：正文含「（待补充）」→ warning（提示人工补全）。
3. **关键档案信息未体现**：企业 `address`/`legal_representative`/`safety_officer` 非空时，对正文做空白归一化后子串匹配；正文完全未出现该值 → warning「正文未体现企业档案 {字段}」。
4. **疑似推断地址**：档案字段缺失（值为「（待补充）」）时，正文出现地址模式（正则 `[\u4e00-\u9fa5]{2,8}(省|市|区|县).{0,8}(路|街|大道)`）→ warning「疑似推断地址，请核实」。
5. **Mermaid 语法**：复用现有类型声明检查，缺失 → warning。
6. **章节完整性**：存在空章节时 `valid=False`。

**b. `export.py::validate_plan_export` 改为调用 `check_plan`**，响应结构保持不变（`valid`/`issues`/`warnings`），不破坏前端既有调用。注意兼容：既有 `ExportValidationResponse.warnings` 为 `list[str]`，而 `check_plan` 的 warnings 为 dict 列表，导出时将其渲染为 `「{section_title}」{warning}` 字符串后返回。

### 前端改动

**`ExportPreviewPage.tsx`**：进入页面时调用 `validate` 接口；存在 issue/warning 时在页面顶部显示报告（Alert 列表），并允许用户返回编辑修正后再导出。

### 验收标准

- 含「（待补充）」或疑似推断地址的预案，导出预览页展示对应 warning。
- 空章节预案 `valid=false`，导出预览页明确提示。
- 新增测试：`check_plan` 各规则（空章节 / 占位符 / 档案字段匹配 / 地址模式 / 合法预案无告警）。

---

## 3.6 失败章节重试

### 目标

批量生成部分章节失败后，前端提供「一键重试失败章节」。

### 后端改动

- `generation.py` 批量逻辑（SSE 与 background 两处）收集 `failed_sections`：`[{"section_key", "title"}]`。
- SSE `batch_done` 事件增加 `failed_sections` 字段。
- background 生成是异步的，前端无法在响应时拿到结果：新增查询端点 `GET /plans/{plan_id}/generate/status`，返回 `{"generating": bool, "failed_sections": [{"section_key","title"}]}`；background 任务完成后将失败清单写入内存字典（与 `_active_generations` 同生命周期），前端在章节刷新时调用该端点获取失败清单并展示「重试失败章节」。

### 前端改动

**`PlanEditorPage.tsx`**：

- `batch_done` 事件中 `failed > 0` 时显示 Alert：「N 个章节生成失败」，附「重试失败章节」按钮。
- 点击后调用既有 `generateBatchStream(planId, failedKeys, ...)` 仅重试失败章节。
- `types/plan.ts` 的 `SSEEvent` 增加 `failed_sections` 可选字段。

### 验收标准

- 模拟单章失败（如临时禁用某章节模板）后，batch_done 携带失败清单，前端可一键重试且只重试失败章节。

---

## 3.7 移动端批量链路统一（含批量代码去重）

### 目标

移动端「批量生成」接入后端统一批量接口；同时消除 `generate_batch` 与 `generate_batch_background` 的重复实现。

### 后端改动

**a. 抽取公共批量执行函数**

在 `generation.py` 新增 `async def _run_batch_generation(bg_db, plan_id, section_tuples, ai_config, ent_data, plan_type, style_preference, advanced_overrides, on_section_done=None)`：

- 逐章生成、写库、渲染 Mermaid、统计 completed/failed/failed_sections。
- 生成结束后统一做状态判定 + 自动版本快照。

`generate_batch`（SSE）与 `generate_batch_background` 均调用该函数，仅保留各自的「事件上报/后台启动」外层差异。行为保持兼容：

- SSE 版本保留 `progress`/`chunk`/`section_done`/`batch_done` 事件流与取消能力。
- background 版本保留立即返回 `{"code":0,"message":...}` 语义。

**b. 失败清单**：公共函数返回 `failed_sections`，两个端点各自透出（见 3.6）。

### 前端改动

**移动端 `PlanEditorScreen.tsx`**：

- 「批量生成」按钮打开 `AIGenerationSheet`（batch 模式），章节选择仅含 `aiGeneratable=true` 章节。
- 点击开始后调用 `generateBatchBackground(planId, selectedKeys)`，成功提示「已在后台开始生成」，完成后 `invalidateQueries(["plan-sections"])` 刷新，并调用 `GET /plans/{id}/generate/status` 获取失败清单展示重试入口。
- 保留单章流式生成能力不变。

**`generationService.ts`**：`generateBatchBackground` 返回体扩展解析 `failed_sections`（可选）。

### 验收标准

- 移动端批量生成走后台接口，成功后章节内容刷新，与 Web 生成结果一致。
- 后端全量测试通过，SSE 与 background 行为与改动前一致（用现有 e2e/接口测试回归）。

---

## 3.8 Diff 对比弹窗

### 目标

单章 AI 生成/重写完成后，若新内容与旧内容不同，弹窗对比并让用户决定接受或回退。

### 前端改动

**a. 新增 `frontend/src/components/plan/DiffPreviewModal.tsx`**

- Props：`open`、`oldText`、`newText`、`onAccept`、`onReject`。
- 双栏并排展示旧/新文本，对差异行做高亮。
- 实现不引入新依赖：按行拆分后简单逐行对比（相同行不加亮，新增/删除行分别高亮）。

**b. `AIGenerateButton.tsx` 集成**

- 生成前记录编辑区当前内容为 `oldContent`（由 `PlanEditorPage` 传入 `onContentChunk` 前的值）。
- 单章生成完成（`done` 事件）后，若 `newText !== oldContent` 且 `oldContent` 非空：弹 DiffPreviewModal。
  - 接受 → 保持现状（后端已落库）。
  - 拒绝 → 调用 `updateSection(planId, sectionKey, { content: oldContent })` 恢复，并刷新章节数据。
- 新章节（无旧内容）不弹窗。

### 验收标准

- 已有内容的章节 AI 生成后弹出对比，接受/拒绝行为正确，拒绝后章节恢复旧内容。
- 空章节生成不弹窗。

---

## 4. 文件清单

### 后端

| 文件 | 操作 | 批次 |
|------|------|------|
| `backend/app/models/enterprise.py` | 修改：PlanSection +4 字段、PlanProject +2 字段 | 1、2 |
| `backend/db_migration_plan_section_metadata.sql` | 新增：章节元数据 + 预案编号迁移 | 1、2 |
| `backend/app/routers/plans.py` | 修改：模板元数据复制、duplicate 复制、编号生成 | 1、2 |
| `backend/app/routers/sections.py` | 修改：+autofill 端点 | 1 |
| `backend/app/services/prompt_cache.py` | 修改：数据真实性护栏 | 1 |
| `backend/app/routers/generation.py` | 修改：缺失标注、批量公共函数、failed_sections、快照扩展 | 1、2、3 |
| `backend/app/schemas/plan.py` | 修改：SectionResponse/PlanCreate/PlanResponse 新字段 | 1、2 |
| `backend/app/routers/versions.py` | 修改：快照扩展、回滚恢复 | 2 |
| `backend/app/routers/export.py` | 修改：真实编号、signers、调用质量校验 | 2、3 |
| `backend/app/services/plan_quality_service.py` | 新增 | 3 |
| `backend/tests/test_plan_section_metadata.py` | 新增 | 1 |
| `backend/tests/test_plan_autofill.py` | 新增 | 1 |
| `backend/tests/test_plan_number.py` | 新增 | 2 |
| `backend/tests/test_plan_quality.py` | 新增 | 3 |
| `backend/tests/test_generation_enterprise_data.py` | 修改：缺失标注断言 | 1 |

### 前端

| 文件 | 操作 | 批次 |
|------|------|------|
| `frontend/src/types/plan.ts` | 修改：PlanSection/SSEEvent 新字段 | 1、3 |
| `frontend/src/pages/Plan/PlanEditorPage.tsx` | 修改：真实元数据、自动填充、重试、Diff 集成 | 1、3 |
| `frontend/src/components/plan/SectionTree.tsx` | 修改：真实 ai_generatable | 1 |
| `frontend/src/components/plan/AIGenerateButton.tsx` | 修改：自动填充入口、Diff 触发 | 1、3 |
| `frontend/src/components/plan/DiffPreviewModal.tsx` | 新增 | 3 |
| `frontend/src/pages/Plan/PlanCreatePage.tsx` | 修改：编号/版本号输入 | 2 |
| `frontend/src/pages/Plan/ExportPreviewPage.tsx` | 修改：质量报告展示 | 3 |
| `frontend/src/services/generationService.ts` | 修改：failed_sections 解析 | 3 |
| `frontend/src/services/planService.ts` | 修改：createPlan 编号参数 | 2 |
| `frontend/src/mobile/screens/PlanEditorScreen.tsx` | 修改：元数据、批量生成、自动填充 | 1、3 |
| `frontend/src/mobile/components/plan/AIGenerationSheet.tsx` | 修改：章节过滤 | 1 |
| `frontend/src/mobile/components/plan/ChapterTree.tsx` | 修改：类型扩展 | 1 |

---

## 5. 兼容性与风险

1. **迁移**：新列全部可空/带默认值，存量数据不受影响；本地与云部署需执行迁移 SQL（沿用现有 `db_migration_*.sql` 执行流程）。
2. **external.py**：`_create_sections_from_template` 签名不变，自动获得元数据；`_collect_enterprise_data` 缺失标注对外部生成同样生效（同链路同护栏）。
3. **批量去重回归**：SSE 与 background 两个端点的对外行为必须保持兼容，用现有测试与 e2e 回归。
4. **旧版本快照**：缺少新字段时回滚跳过对应恢复项，不报错。
5. **Diff 弹窗无新依赖**：用简单逐行对比，避免引入 diff 库。
6. **导出编号**：编号规则可被用户覆盖；同企业同类型序号递增基于数据库 count，并发创建时可能存在极小概率重复，可接受（后续如需严格唯一再加唯一约束）。

---

## 6. 测试计划

每批验收前运行：

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -q
cd frontend && npx tsc -b && npx vitest run
```

各批新增测试见「验收标准」与文件清单；第 1 批完成后补跑 `test_generation_enterprise_data.py` 更新后的断言。

---

## 7. 自检记录

- [x] 无占位符/TODO/待定项。
- [x] 内部一致性：字段命名（`plan_number`/`version_number`/`ai_generatable` 等）在模型、schema、前端类型、迁移 SQL 中一致；接口路径 `/plans/{plan_id}/sections/{section_key}/autofill` 全局唯一。
- [x] 范围聚焦：三批均属于「预案生成功能」，流程状态（评审/审批）明确排除。
- [x] 模糊性消除：编号生成规则、自动填充渲染形式、校验规则、Diff 触发条件均已写明具体行为。
