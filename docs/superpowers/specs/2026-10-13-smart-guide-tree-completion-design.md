# 智能导引「补全现有风险树」设计规格

日期：2026-10-13
状态：设计已确认（用户选择方案 1：在现有「🚀 智能导引」里完成"完善风险树"），待用户审查本文档后进入实现。

## 1. 背景与问题

用户需求：风险树中 AI 智能生成逻辑要"根据企业基本情况和用户输入的内容进行完善风险树"。

现状（代码证据）：

1. 「🚀 智能导引」= `frontend/src/components/enterprise/RiskSmartGuideModal.tsx`（弹窗标题"AI 智能生成风险层级"）
   → `frontend/src/services/riskManagementService.ts::aiSmartGuide` → 后端 `POST /risk-management/ai/smart-guide`
   （`backend/app/routers/risk_management.py:1291`）→ `backend/app/services/risk_ai_service.py::smart_guide`。
2. 已传给 AI 的企业信息只有 6 个字段（name/industry/business_scope/building_overview/hazardous_chemicals/
   special_equipment）+ 危化品台账；企业档案中 `main_equipment_list`（主要设备清单）、`special_equipment_detail`
   （特种设备明细）、`natural_conditions`（自然条件）、`fire_protection_summary`（消防概况）、`surrounding_info`
   （周边环境）、`main_products`（主要产品）、`annual_capacity`（年产能）等与风险辨识高度相关的字段**没有**用上。
3. 已有风险树只传分区名+对象名（`existing_names`），prompt 规则为"**不得**生成与现有分区名称相同或语义重复的分区；
   描述若已对应现有分区，将该分区名写入 summary 的 duplicates 数组，而不是重复生成"——即 AI 看不到现有树结构，
   **无法对已有分区/对象/单元补下级**，用户描述到已有分区时会被要求直接跳过。
4. 导入侧其实已经具备"合并补充"能力（`RiskSmartGuideModal.importMut` + `frontend/src/utils/smartGuideImport.ts`）：
   同名分区/对象/单元/事件自动并入，事件下只补缺失措施（按"类别+描述"去重）。**缺口只在生成侧**：
   AI 不知道现有树缺什么、也没被允许去补。

## 2. 目标与非目标

目标（用户已确认）：

- AI 生成时同时依据：①企业档案完整字段 ②现有风险树完整结构 ③用户输入的补充说明（可为空）。
- 生成结果以"查漏补缺"为目的：已有分区缺对象补对象，对象缺单元/事件补单元/事件，单元缺事件补事件，
  已有事件缺措施补措施；用户描述的全新内容照常生成。
- 预览中可直观区分「新增」与「并入现有」，导入逻辑复用现有合并能力，不改。

非目标（本次不做）：

- 不实现右键菜单「智能填充下级」（ai-fill，另一入口，仍为未实现状态）。
- 不改事件/措施表单里的「✨ AI 建议」（传参缺口另行处理）。
- 不做"无描述一键全树补全"的独立入口（描述留空即覆盖此用法）。
- 不改导入合并算法、不改响应 schema 结构。

## 3. 方案总览（数据流）

```
用户点击"下一步→AI 分析"（描述可为空）
  └─ 前端并行：aiSmartGuide(eid, description) + getFullHierarchy(eid)
       ├─ 后端 /ai/smart-guide：
       │    1. 读企业档案 → build_smart_guide_enterprise_info(ent, ledger_rows)
       │    2. 读现有树完整层级（selectinload 链）→ 结构化 dict
       │    3. _serialize_existing_tree(zones, max_chars=20000) → 紧凑 JSON 文本（超长逐级裁剪）
       │    4. smart_guide(description, info, ai_config, existing_tree_text) 新 prompt：
       │       企业档案 + 现有树 + 用户补充 → "查漏补缺"输出（zones 树，同名节点作为合并路径）
       └─ 前端预览：buildMergeBadges 标记每个节点「新增/并入」
  └─ 导入：现有 importMut 合并逻辑不变
```

## 4. 后端改动

### 4.1 `backend/app/services/risk_ai_service.py`

新增纯函数（便于单测）：

- `build_smart_guide_enterprise_info(ent, ledger_rows: list[dict]) -> dict`
  构造企业信息 dict，字段清单：
  现有保留：`name / industry / business_scope / building_overview / hazardous_chemicals / special_equipment / chemicals_ledger`；
  新增：`address / employee_count / main_products / annual_capacity / main_equipment_list /
  special_equipment_detail / natural_conditions / fire_protection_summary / surrounding_info`。
  空值（None / "" / []）一律不放入 dict，避免噪声。
  （`surrounding_info` 为 JSONB dict：nearby_units/sensitive_targets/traffic_info，原样携带，体量可控。）
  不纳入：`risk_method_config`（前端无编辑入口，仅少量导出用途，YAGNI）。

- `serialize_existing_tree(zones: list[dict], max_chars: int = 20000) -> tuple[str, bool]`
  输入为纯 dict 结构（路由先把 ORM 转 dict，单测无需 ORM）：
  `[{name, objects: [{name, units: [{name, unit_type, events: [{accident_type, measures: [{measure_category, description}]}]}], events: [...]}]}]`
  （对象级直接事件与单元级事件同结构；不含画布坐标、description 等长文本。）
  裁剪分级（逐级降级，取第一个满足 max_chars 的级别）：
  - L1 full：措施列 `description`（每条截 60 字）；
  - L2 compact：措施只列数量（`"measures": 3`）；
  - L3 skeleton：只列 分区→对象→单元名/事件类型（措施、unit_type 去掉）；
  - L4：L3 + 按分区顺序截断到预算内，返回 `truncated=True`。
  返回 `(text, truncated)`；truncated 时 prompt 追加说明"现有树过大，仅展示部分内容，未展示部分不要臆断缺失"。

改造 `smart_guide()`：

- 签名改为 `smart_guide(description, enterprise_info, ai_config, existing_tree_text: str = "", tree_truncated: bool = False)`；
  删除 `existing_names` 参数（同步更新路由与测试）。
- prompt 重写为三段输入 + 查漏补缺规则，关键文案：
  - 三段：`用户补充说明（可能为空）` / `企业基本情况` / `企业现有风险分级管控树（JSON，供你查漏补缺）`；
  - 空描述时写「（用户未填写补充说明，请仅依据企业档案与现有风险树分析）」；
  - **删除**旧规则第 5 条「不得生成与现有分区重名/语义重复的分区；描述若已对应现有分区写入 summary 的
    duplicates 数组」（`risk_ai_service.py:335` 一带，前端未消费 summary.duplicates，删除无影响）；
  - 规则要求（要点）：
    1. 输出将与现有树合并，同名分区/对象/单元自动并入，**路径中的已有节点名称必须与现有树完全一致**；
    2. 对照现有树查漏补缺（补对象/单元/事件/措施），不得重复已有事件（同父节点同事故类型）；
    3. 用户补充说明中的新内容正常生成；已存在节点不要改写其描述/等级；
    4. 每事件 LS 评估（L/S 1-5）+ risk_level/risk_score，每事件至少 2 条措施；
    5. 同类设备编号命名；对象 `is_risk_point` 一律 false；
    6. 输出上限从「5 分区/50 对象」调整为「8 分区/80 对象」，优先覆盖最重要缺口（防止超时，实测后可再调）。
- 输出 JSON 格式与归一化（`_normalize_smart_guide_hierarchy`）不变；timeout 保持 60s。

### 4.2 `backend/app/routers/risk_management.py`（ai_smart_guide 端点）

- 企业信息改用 `build_smart_guide_enterprise_info(ent, ledger_rows)`（ledger 行先转为 dict）。
- 现有树读取改为完整层级（照抄 `get_hierarchy` 的 selectinload 链：
  `RiskZone.objects → units → events → measures` + `objects → events → measures`），
  转纯 dict → `serialize_existing_tree()` → 文本与 truncated 标志 → 传入 `smart_guide`。
- `SmartGuideRequest.description` 改为默认空串（`description: str = ""`），支持"不填描述只补全"。
  （`backend/app/schemas/risk_management.py`）
- 其余（normalize summary、`SmartGuideResponse` 映射、容错）不动。

## 5. 前端改动

### 5.1 `frontend/src/utils/smartGuideImport.ts`

新增纯函数 `buildMergeBadges(index: ExistingIndex, hierarchy: SmartGuideZone[], nameOverrides: Record<string, string>): Map<string, "new" | "merge">`：

- key 体系与预览树一致：`z-{zi}` / `z-{zi}-o-{oi}` / `{objKey}-u-{ui}` / `{parentKey}-ev-{ei}`；
- 判定与导入逻辑一一对应：分区按名查 `index.zones`；对象按 `index.objects.get(zoneName)`；
  单元按对象 id 查 `index.units`；事件（单元级与对象级）按父 id 查 `index.eventIds`；
- 父节点为"新增"时其子节点一律 "new"；改名（nameOverrides）参与判定；
- 措施级不标记（YAGNI）。

### 5.2 `frontend/src/components/enterprise/RiskSmartGuideModal.tsx`

- 描述可选：去掉 `handleStartAnalysis` 的"请先描述区域情况"拦截；输入框标题改
  「请描述需要 AI 分析的区域情况（可选）」；提示文案改为"可不填：留空时 AI 将依据企业档案与现有风险树
  自动查漏补缺；填写设备、工艺、物料、周边等补充说明可让结果更准确"。
- 生成时并行拉现有树：`guideMut.mutationFn` 用 `Promise.allSettled([aiSmartGuide(...), getFullHierarchy(eid)])`；
  AI 失败照旧报错；`getFullHierarchy` 失败不阻塞（预览无标记）。索引存 state（`buildExistingIndex`）。
- 预览标记：`badges = useMemo(buildMergeBadges(...), [hierarchy, index, nameOverrides])`；
  节点名后加小 Tag——「新增」（绿色）/「并入」（蓝色）；底部汇总行增加"将新增 X · 并入 Y"（只统计勾选节点，四级节点）。
- 预览 Alert 文案更新：说明 AI 已按企业档案+现有树查漏补缺；同名节点并入现有（只补充缺失内容），
  新增节点单独创建；已有节点的描述/等级不会被改写。
- service 签名不变：`aiSmartGuide(eid, description)`（允许空串）。

## 6. 接口与契约

- `POST /risk-management/ai/smart-guide` 请求体 `{description: string}`（可空串/缺省）；响应结构不变
  （`{hierarchy, summary}`）。
- 前端预览树、勾选、改名、导入合并、导入结果统计（新增/并入/跳过）行为均不变。
- 导入匹配仍是"全局按名称"（跨楼层不区分），沿用现状。

## 7. 测试计划（TDD：先补测试再改实现）

后端（`backend/tests/`）：

1. `test_smart_guide_import.py` 更新 `test_smart_guide_prompt_includes_existing_names` →
   `test_smart_guide_prompt_includes_existing_tree`：传入现有树结构，断言 prompt 含分区/对象/事件名与
   查漏补缺关键词、且不再含旧规则文案；
2. 新增 `test_smart_guide_prompt_includes_extended_enterprise_fields`：`main_equipment_list` 等字段内容出现在 prompt；
3. 新增 `test_smart_guide_prompt_handles_empty_description`：空描述 → 出现"未填写补充说明"文案；
4. 新增 `serialize_existing_tree` 系列：小树 L1 含措施描述；超长树逐级降级；超限截断返回 truncated=True；
5. 新增 `build_smart_guide_enterprise_info` 系列：字段齐全、空值剔除、ledger 合并；
6. 源码守护（延续 `test_smart_guide_summary_shape.py` 风格）：路由调用 `serialize_existing_tree` 且传 `existing_tree`。

前端（`frontend/src/utils/smartGuideImport.test.ts` 追加）：

1. `buildMergeBadges`：全新树 → 全 "new"；与现有树同构 → 全 "merge"；
2. 混合场景（分区并入 + 对象新增；已有对象补单元；已有单元补事件；对象级事件）；
3. 改名 override 参与判定；新增父节点下子节点全 "new"。

## 8. 验证计划

- 后端：`pytest backend/tests/test_smart_guide_import.py test_smart_guide_summary_shape.py` +
  全量 `pytest`（当前基线 2205 passed / 1 skipped）。
- 前端：`tsc -b`、`vitest`（smartGuideImport 相关 + 全量）、`eslint src`、`npm run build`。
- 浏览器实测（playwright 脚本，沿用 `output/playwright/e2e-20261013/` 惯例）：
  1. 造一棵"缺下级"的树（如：分区"储罐区"下有对象无事件；某对象有事件无措施）；
  2. 打开智能导引——①留空描述跑一次 ②填描述跑一次；
  3. 断言：生成内容包含对已有分区/对象的补充（同名路径）+ 描述中的新内容；预览出现「新增/并入」标记；
  4. 导入后回读接口：已有对象下出现补的事件/措施，且已有节点未被改写（描述、等级保持）；
  5. 证据落盘 JSON + 截图。

## 9. 已知边界与风险

- 现有树超大时 AI 只见截断后的部分（prompt 有说明），可能漏补展示区外的缺口；用户可再次运行或分区域描述。
- AI 输出的已有节点名称若与现有树不一致（如"储罐区"→"罐区"），会按新增处理；预览可改名或取消勾选。
- 单次输出上限 8 分区/80 对象：缺口极多时需要多次运行（沿用现状行为，先防止超时）。
- prompt 变长（企业档案 + 树文本 ≤ 20000 字符）对主流模型上下文无压力；若企业配置了小上下文模型，靠裁剪分级兜底。
