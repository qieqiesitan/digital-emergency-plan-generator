# 智能引导导入 422 修复与生成去重设计

日期：2026-08-06
分支：codex/smart-guide-import-fix

## 1. 背景与问题

### 1.1 AI 生成层级导入 422

用户反馈：风险分级管控 → 智能引导 → AI 智能生成风险层级后，点击「确认并导入全部」报错 `导入失败: Request failed with status code 422`。

根因（已实际复现）：
- 后端 `RiskObjectCreate.validate_risk_point` 要求 `is_risk_point=True` 的对象必须同时提供 `zone_id` 与 `location_x/location_y`（业务规则：风险点必须绑定分区和坐标，用于四色分布工作台绘制）。
- `_normalize_smart_guide_hierarchy`（backend/app/services/risk_ai_service.py）未强制 AI 输出对象的 `is_risk_point` 为 False；AI 对储罐、反应釜等危险设备输出 `is_risk_point: true`。
- 前端导入（frontend/src/components/enterprise/RiskSmartGuideModal.tsx 的 `importMut`）调用 `createObject` 只传 `zone_id/name/category/is_risk_point`，不传坐标。
- 复现证据：`POST /enterprises/{id}/risk-management/objects`，body `{"name":"...","is_risk_point":true}` → 422 `Value error, 风险点必须绑定分区和坐标`。

### 1.2 相邻缺陷：普通表单风险点坐标被丢弃

排查中发现：`RiskObjectForm` 在勾选「是否为重大风险点」后提供平面图坐标点选与 X/Y 输入，但 `RiskManagementTab.handleFormSubmit` 的 object 分支组装 payload 时只传 `name/category/description/is_risk_point`，丢弃 `location/location_x/location_y`。因此用户勾选风险点并填写坐标后保存，依然 422。

### 1.3 AI 生成未参考现有分区

`smart_guide` 的 prompt 只注入企业信息与用户描述，不包含现有分区/对象清单，AI 容易生成与现有分区名称相同或语义重复的层级。

## 2. 设计决策

### D1：AI 生成的层级对象一律不标风险点（修 422 主路径）

- 后端 `_normalize_smart_guide_hierarchy` 对每个对象强制 `obj["is_risk_point"] = False`。理由：文本生成没有画布坐标系，不可能产出合法的风险点坐标；风险点必须由用户在工作台画布上手动放置。
- 前端导入 `createObject` 传 `is_risk_point: false`（防御，即使后端漏处理也不 422）。

### D2：AI 生成前注入现有分区清单（后端自动完成）

- `smart-guide` 路由查询当前企业已有分区名（`RiskZone.name`，按企业过滤，不区分楼层）与对象名（`RiskObject.name`），传给 `smart_guide()`。
- `smart_guide()` 新增 `existing_names` 参数（`{"zones": [...], "objects": [...]}`），拼入 prompt：
  - 不得生成与现有分区名称相同或语义重复的分区；
  - 描述若已对应现有分区，应把该分区列入 summary 的 `duplicates` 提示，而不是重复生成；
  - 同一区域内多个同类设备允许存在，但命名需用编号区分（如「1号储罐」「2号储罐」），避免对象名重复。
- 路由在服务端查库，前端调用方（`aiSmartGuide`）无需改动参数。

### D3：前端导入 zone 级去重兜底

- `RiskSmartGuideModal` 打开时（`open` 且 step=input）并行拉取现有分区清单（`listZones(enterpriseId)`），维护 `existingZoneNames: Set<string>`。
- 导入循环中，若分区名（含 `nameOverrides` 改名后的名称）已存在于现有集合，跳过该分区及其全部子节点，计入 `skippedZones`。
- 对象级不自动跳过：同一分区内多个同类同名设备可能是合法业务事实（如多个储罐），自动跳过会误伤；对象重名由 D2 的 prompt 约束规避。
- 成功消息：`成功导入 N 条数据`；若 `skippedZones > 0`，追加 `，跳过 M 个重名分区`。

### D4：修复普通表单风险点坐标丢失

- `RiskManagementTab.handleFormSubmit` 的 object 分支（新增与编辑）补传 `location/location_x/location_y`（保留 `null` 语义：未填则传 `null`，避免缺字段）。
- 不改变后端校验规则；表单已提供坐标输入，属于前端组装遗漏。

## 3. 数据流

```
用户打开智能引导弹窗
  ├─ 前端：listZones → existingZoneNames（供导入去重）
  └─ 用户描述 → POST /ai/smart-guide {description}
        └─ 路由：查库现有 zones/objects → smart_guide(description, info, existing_names)
              └─ prompt 注入去重约束 → AI 返回层级
                    └─ normalize：强制 is_risk_point=False → 响应
用户预览（对象不再带风险点标记）
  └─ 确认导入：遍历创建；分区名与 existingZoneNames 重复 → 跳过并计数
        └─ createZone/createObject(...is_risk_point:false)/createUnit/createEvent/createMeasure
              └─ 消息：成功 N 条，跳过 M 个重名分区
```

## 4. 测试计划

### 后端（backend/tests/test_risk_mapping_service.py 或新增 test_smart_guide_import.py）

1. `_normalize_smart_guide_hierarchy`：输入含 `is_risk_point: true` 的对象 → 输出强制 False；缺失字段默认补齐。
2. `smart_guide` prompt 注入：monkeypatch `llm_text_completion` 返回固定 JSON，断言 messages 中用户 prompt 包含「现有分区」清单文本与去重约束。
3. 回归：`RiskObjectCreate` `is_risk_point=true` 无坐标仍 422（现有行为不变）。

### 前端

1. vitest（新增 `src/utils/smartGuideImport.test.ts`）：抽取纯函数 `buildImportPlan(hierarchy, checkedKeys, nameOverrides, existingZoneNames)`，断言重名分区被跳过并计数。
2. E2E（frontend/e2e/risk-mapping-workbench.spec.ts 新增或独立 spec）：mock 现有分区 + AI 层级，断言导入成功、跳过重名分区提示、AI 对象不再创建风险点。

## 5. 受影响文件

- backend/app/services/risk_ai_service.py：`_normalize_smart_guide_hierarchy` 强制 is_risk_point=False；`smart_guide` 增加 existing_names 参数与 prompt 去重约束。
- backend/app/routers/risk_management.py：`ai_smart_guide` 路由查库注入 existing_names。
- frontend/src/components/enterprise/RiskSmartGuideModal.tsx：打开时拉现有分区；导入去重；createObject 传 is_risk_point:false；成功消息含跳过数。
- frontend/src/pages/Enterprise/RiskManagementTab.tsx：object 分支补传 location/location_x/location_y。
- frontend/src/utils/smartGuideImport.ts（新增）：导入计划纯函数，可单测。
- backend/tests/test_risk_mapping_service.py（或新增）：normalize / prompt 注入测试。
- frontend/src/utils/smartGuideImport.test.ts（新增）：去重单测。
- frontend/e2e/：智能引导导入 E2E。

## 6. 非目标

- 不改变后端「风险点必须绑定分区和坐标」校验规则。
- 不实现对象级自动去重（误伤合法同名设备）。
- 不实现「替换整套层级 / 增量补齐」交互升级（后续迭代）。
- 不动楼层维护分支内容；本功能独立分支实现后合并。
