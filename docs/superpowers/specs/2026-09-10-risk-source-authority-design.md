# 风险源清单权威性与冲突留痕设计（2026-09-10）

## 背景与问题

西安宝岳空间科技有限公司的火灾现场处置方案未出现“厨房/燃气灶台”，但风险树中该数据真实存在（厨房分区 4 个对象、12 条事件，其中“燃气灶台 · 火灾爆炸 · 较大 · R=15”自 2026-08-04 就存在，带 3 条管控措施）。

只读排查结论：

1. 预案生成确实注入了风险树数据（提示词 90,571 字符，“厨房”出现 25 次、“燃气灶台”20 次）。
2. 真正原因是 2026-09-08 生成的风险评估报告第一章中，模型**自行**依据企业档案（24 层写字楼、3 人、软件开发）判断“第 1–16 项燃气灶台、油烟排风、冷藏冷冻、餐具清洗、取餐台、就餐区域等食堂厨房类风险源不适用于本企业”并予以排除；ch3 只评估剩余条目导致“较大=0”，ch5 结论与 JSON 摘要固化；预案生成再注入该摘要（`generation.py:614`），最终按摘要写作。
3. 数据库中的风险评估模板/系统提示词**没有**任何“排除/剔除/核对/无关”指令，说明这是模型在数据冲突时自行裁决，属于提示词缺少冲突处理规则 + 数据本身矛盾（风险树含厨房/食堂，企业档案描述办公场所）。
4. 风险源顺序不稳定：`risk_context_builder` 仅按 `RiskZone.sort_order` 排序，而所有分区 `sort_order=0`，对象/单元/事件无排序键；数据库更新会改变行序，导致同一风险源在不同时间的编号不同（报告中厨房为“第 1–16 项”，当前提示词中为第 23–34 项）。

## 目标

1. 确立数据权威顺序：**风险源清单（风险树）为风险事实唯一来源**，企业档案与既有报告摘要只能作为背景，不得据此增删或改判风险源。
2. 模型不得增删、改名、合并丢失或改判清单中的风险源；等级、L/S/R、管控措施一律以清单为准。
3. 冲突不进入正式正文，但以结构化清单留痕（写入报告 summary）。
4. 风险源顺序与编号稳定可复现。

## 非目标

- 不重新生成历史风险评估报告与已生成预案（用户选择方案 A）。
- 不做冲突清单的前端展示（本次只落 summary，接口可查）。
- 不改聊天、法规检索等其它 AI 提示词。
- 不清理风险树中的厨房/食堂数据（用户确认“以风险树为准”）。

## 设计一：固定规则块（代码级 + DB 同步）

### 规则文本（唯一来源，代码常量）

```
【风险数据权威规则（系统固定，任何模板不得覆盖）】
1. 【风险源清单】是风险事实的唯一来源：风险源条目、事故类型、L/S/R、风险等级、管控措施一律以清单为准。
2. 禁止增删、改名、合并丢失或改判清单中的任何风险源；禁止以企业档案、报告摘要、常识推断为由排除清单条目。
3. 清单与【企业档案】或【风险评估报告摘要】不一致时，以清单为准；不一致项写入结构化冲突清单，正文保持干净。
4. 风险源数量、等级分布、类别分布等统计必须由清单逐条计算得出，不得自行估算。
5. 引用风险源时按系统给出的固定顺序与编号（“第N项”），不得重排。
```

### 注入位置（代码级，必选）

- 风险评估报告：[risk_assessment_service.build_chapter_prompt](C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/services/risk_assessment_service.py) 返回前追加，覆盖全部章节与单章生成。
- 资源调查报告：[resource_investigation_service.build_chapter_prompt](C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/services/resource_investigation_service.py) 返回前追加。
- 预案生成：[generation._build_system_prompt](C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/routers/generation.py) 结果里追加，作为 system message，覆盖批量、后台、聊天触发、单章与重生成等全部生成路径；不在聊天助手的其它场景追加。

### DB 提示词同步

新增迁移将上述规则追加到以下系统提示词（幂等：已包含则跳过）：

- `risk_assessment_system`、`risk_assessment_system_default`
- `resource_investigation_system`（含 default）
- `emergency_system` 4 条

章节级模板（`risk_assessment_section` 5 条、`emergency_section` 45 条）不逐条修改，避免 45 处重复维护。

## 设计二：冲突清单（双轨检测）

### 存储

写入对应报告 `summary["data_conflicts"]`（数组）。该字段每次生成/合并时**整体重算替换**，不与上一次结果累加；其余 summary 字段一律保留。

### 结构

```json
{
  "type": "count_mismatch | level_mismatch | category_mismatch | coverage | narrative",
  "item": "厨房/燃气灶台·火灾爆炸",
  "expected": "较大 R=15（清单）",
  "actual": "未出现在 L×S 表或结论中",
  "note": "模型判定与企业档案场所功能不符",
  "source": "code | model"
}
```

### 代码硬校验（source=code，仅风险评估报告）

在 ch5 结构化 JSON 摘要解析/合并后执行，用纯函数 `compute_conflicts(risk_sources, summary) -> list[dict]`：

1. `risk_source_count` 是否等于清单条数
2. `risk_level_distribution` 是否等于按清单统计的等级分布（重大/较大/一般/低）
3. `risk_by_category` 是否等于按清单统计的类别分布（存在时校验）
4. `top_risks` 中每个条目的 `risk_level` 是否与清单一致（按名称匹配后校验）
5. 结构化摘要缺失或无法解析 → 生成一条 `coverage` 冲突，说明“无法校验覆盖完整性”

调用点：风险评估报告全量生成最终落库前、以及 merge 端点重建 summary 后，均重算一次冲突清单。

### 模型定性冲突（source=model）

ch5 的 JSON 摘要新增可选字段 `data_conflicts: [...]`：模型仅可记录“存疑/建议核实”语气的冲突，不允许改写评估结果。代码负责：

- 按上述结构清洗字段，丢弃不符合结构的条目
- 与代码冲突合并，按 `(type, item, expected, actual)` 去重
- 写入 `summary["data_conflicts"]`

### 失败行为

只记录，不阻断、不重试、不修改报告状态；报告照常保存与导出。冲突是否为空由 `data_conflicts` 列表本身体现。

### 预案侧

只应用固定规则（风险树优先、报告摘要仅作背景），不新增存储字段（预案表无 summary）。若同一企业后续重新生成风险评估报告，冲突会记录在报告 summary 中。

## 设计三：稳定排序

[risk_context_builder.py](C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/services/risk_context_builder.py) 统一排序键：

- 分区：`sort_order → created_at → id`
- 对象、单元、事件：同规则（缺失时间/主键时退化为可用字段）

风险源列表按“分区 → 对象 → 单元 → 事件”稳定展开；风险评估报告提示词中的“第N项”与预案提示词中的风险源顺序因此可复现、可交叉引用。排序只影响展示与编号，不改变数据。

## 影响文件（供实现计划细化）

- 新增：`backend/app/services/report_data_authority.py`（规则常量、`compute_conflicts`、`merge_conflicts`、`sanitize_model_conflicts`）
- 修改：`backend/app/services/risk_context_builder.py`（稳定排序）
- 修改：`backend/app/services/risk_assessment_service.py`、`backend/app/services/resource_investigation_service.py`（规则块注入）
- 修改：`backend/app/routers/generation.py`（预案 system prompt 追加规则块）
- 修改：`backend/app/routers/risk_assessment.py`（全量生成与 merge 后写入冲突清单）
- 新增：`backend/db_migration_20260910_risk_source_authority.sql` + `backend/seed_report_prompts.py`、`backend/seed_prompts_full.py` 同步
- 测试：`backend/tests/test_report_data_authority.py`、`backend/tests/test_risk_context_ordering.py`、相关回归

## 测试策略（TDD）

- 排序：同 `sort_order` 时分区间按 `created_at,id` 稳定；更新行后顺序不变；对象/单元/事件同样稳定。
- 规则注入：三条提示词路径（RA 报告、RI 报告、预案 system prompt）都包含规则块；DB 模板路径与代码兜底路径都生效。
- 硬校验：构造“漏项/等级改判/数量不符/摘要缺失”四种摘要，均能产出对应冲突；完全一致时冲突为空。
- 合并与清洗：模型冲突字段缺失、结构错误、重复项的处理；`summary` 其它字段不被覆盖。
- 回归：报告相关测试全绿；预案生成相关测试全绿。
- 真实验证（只读、不触发模型）：用当前企业数据构建三类提示词，断言规则块存在、风险源顺序两次构建完全一致；不验证模型是否服从（需后续真实生成观察）。

## 验收标准

1. 三类提示词中均存在固定规则块，且 DB 系统提示词同步包含该规则。
2. 同一企业连续两次构建的风险源顺序、编号完全一致。
3. 模拟“模型漏掉较大风险源”的摘要时，`summary.data_conflicts` 能准确记录 `level_mismatch`/`count_mismatch`。
4. 报告正文不出现冲突说明文字，冲突仅存在于 summary。
5. 现有功能回归通过，历史报告与已生成预案不被改动。
