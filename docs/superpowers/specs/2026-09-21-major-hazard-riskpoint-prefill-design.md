# 重大危险源单元：从风险点带出填写项设计（2026-09-21）

## 0. 前置修复：保存基本信息会清空关联与落点（P0，必须先做）

### 0.1 缺陷

在单元上点一次"保存"，`risk_object_id`、`floor_id`、`polygon` 三个字段会被静默置空：
已关联的风险点被解除、平面图落点被抹掉。用户只改了一个联系电话，也会丢掉这两样东西。

### 0.2 根因（三段证据连成的链）

1. `backend/app/schemas/major_hazard.py:14-25` —— `UnitIn` 的 `risk_object_id` / `floor_id` /
   `polygon` 默认值均为 `None`。
2. 实测（本次会话，`backend\.venv\Scripts\python.exe`）：
   `UnitIn(name='x', unit_type='storage').model_dump()` →
   `{'risk_object_id': None, 'floor_id': None, 'polygon': None}`。
3. `backend/app/routers/major_hazard.py:120-128` —— `update_unit` 用
   `for key, value in payload.model_dump().items(): setattr(unit, key, value)`，
   **未传 `exclude_unset`**，于是"请求体里没出现的字段"也被写成 `None`。
4. 前端两个入口都只提交表单里的 6 个字段：
   `frontend/src/pages/Enterprise/MajorHazardListPage.tsx:100-104`（台账页编辑弹窗）、
   `frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx:57-61`（详情页保存）。

### 0.3 影响面

- 任何一次编辑保存都会解除风险点关联、抹掉平面图落点。
- `UnitPolygonEditor` 画好的落点保不住——真库 6 个单元 `floor_id` 全为 `NULL`，
  与此行为一致（**这是可疑关联，不是已证实的因果**；浏览器实测一次即可确认）。
- 本规格第 2 节要做的"自动带出"会被这个缺陷直接吃掉：带出的值一旦保存就随关联一起消失。

### 0.4 修复方案

```python
for key, value in payload.model_dump(exclude_unset=True).items():
    setattr(unit, key, value)
```

与仓库既有约定一致：同文件 `:297`（记录更新）、`backend/app/routers/enterprises.py:193`
均使用 `exclude_unset=True`，且该处注释明确"未传字段不更新；显式传 null 允许清空可空字段"。

语义说明：

- 未传字段不动。
- 清空文本字段 = 前端传空串（antd 输入框清空即传 `""`），落库为 `""` 而非 `NULL`；见 §7 风险 1。
- 落点清空仍走 `PUT /units/{id}/polygon` 显式传 `null`（该端点契约是 `floor_id` 与 `polygon` 必须成对），不受本次修复影响。

### 0.5 为什么必须先做

不做这一步，第 2 节的带出结果保存后必然丢失，整个需求的验收无法通过。

## 1. 背景与目标

### 1.1 背景（现状事实）

用户诉求：填写时能自动获取已有数据，不用重复填写；且已明确定调为**"省一遍打字"**——
一次性把默认值带出来，**不做持续联动、不回写**。

现状（本次只读调研确认）：

- 风险点表单（`frontend/src/components/enterprise/RiskObjectForm.tsx`）与单元表单存在 4 组同义字段，
  同一片区域、同一个人要录两遍（见 §2.1 映射表）。
- 关联入口 `frontend/src/components/enterprise/majorHazard/RiskObjectPicker.tsx` **只写一个
  `risk_object_id`**，不带任何字段。
- 后端 `UnitOut`（`backend/app/schemas/major_hazard.py:24`）也只回这个 id，
  所以界面即使想带出也拿不到数据。
- 重大危险源侧**已有**的带出只有两处，均有台账/标准作数据源：品种名 → 临界量 Q 与 β
  （`UnitChemicalTable.tsx:144-167`）、台账条目 → 设计最大量建议值（同文件 `:118-142`）。

计划 7（`docs/superpowers/plans/2026-09-17-cross-module-linkage.md`）已全部落地，
它做到的是"能连"，没做到"连了自动带出"。本规格是它的自然延伸。

### 1.2 目标

在单元详情页选中风险点的那一刻，把风险点上已有的位置、责任部门、责任人、联系电话
填进单元表单的**空白项**，并标明来源；用户可以改，照常点保存。

### 1.3 非目标（本规格明确不做）

- 不做持续联动、双向同步、回写（用户已定）。
- 不做反向带出（在风险点表单里选重大危险源单元）。
- 不做隐患登记、作业票、风险事件侧的带出（另行评估）。
- 不做存量数据批量对齐（真库现仅 1 条关联，不值当写迁移脚本）。
- 不把"关联风险点"选择器搬进台账页新增弹窗（即上一轮讨论的方案 B）。
- 不改动品种侧已有的两处带出。
- 不做单元名称、平面图多边形的带出（理由见 §2.4）。

## 2. 带出机制

### 2.1 字段映射（规格表）

| 单元表单字段 | 风险点来源字段 | 带出规则 |
|---|---|---|
| 所在位置 `address` | `RiskObject.location` | 空白则填 |
| 责任部门 `department` | `RiskObject.responsible_unit` | 空白则填 |
| 责任人 `responsible_person` | `RiskObject.responsible_person` | 空白则填 |
| 联系电话 `responsible_phone` | `RiskObject.contact_phone` | 空白则填 |
| 单元名称 `name` | —— | 不带出 |
| 楼层 / 平面图 `floor_id` / `polygon` | —— | 不带出 |
| 品种清单 | 危化品台账（已有能力） | 不变 |

### 2.2 空白判定与覆盖规则

- 空白定义：`v == null || String(v).trim() === ""`。仅含空格视为空白。
- 只写空白项；已有值一律不覆盖（目标是省重复输入，不是纠正人工值）。
- 带出只改表单显示值，**落库要等用户点保存**；关联本身仍即时生效（现状契约不变）。
- 用户在带出后手工修改某字段，该字段的来源标记消失（见 §2.3）。

### 2.3 来源标记

- 被带出的字段，在 `Form.Item` 的 label 后挂一个蓝色 `Tag`，文案 **「来自风险点」**。
- 用户修改该字段后标记消失（页面用 `prefilledFields: Set<string>` 记录，字段 `onChange` 时移除自己）。
- 不复用作业票的 `PrefillBadge` + `FieldSource`：后者的枚举里 `risk_object` 文案是"作业对象"，
  语义不符，硬套会让用户看到错误来源。视觉语言保持一致（蓝色小 Tag）即可。
- 带出完成后给一次 `message.info`：「已从风险点带出 N 项，请检查后保存」。

### 2.4 为什么不带单元名称、楼层、多边形

- **名称**：风险点与单元不是同一命名维度。风险点可能是"机柜及服务器"，单元是"罐区A"；
  自动填过去会误导审核人。
- **楼层 + 多边形**：`PUT /units/{id}/polygon` 的契约是 `floor_id` 与 `polygon`
  **必须同时提供或同时清空**（`backend/app/routers/major_hazard.py:341-345`，否则 422）。
  只带 `floor_id` 会被接口拒绝；而风险点上的是坐标点（`location_x/y`），
  不是单元边界，照搬过去等于画了一个错误的单元区域。落点继续由用户在 `UnitPolygonEditor` 里画。

## 3. 接口变更

只改一个端点的返回体，**无新增端点、无表结构变更、无迁移**。

`GET /api/v1/major-hazard/linkable/risk-objects`
（`backend/app/services/major_hazard_linkage.py:70-86` `list_linkable_risk_objects`）

返回项由 `{id, name, zone_id, floor_id}` 扩展为：

```json
{
  "id": "...", "name": "...", "zone_id": "...", "floor_id": "...",
  "location": "...", "responsible_unit": "...",
  "responsible_person": "...", "contact_phone": "..."
}
```

安全性不变：该端点已有 `ensure_enterprise_owned` 校验，查询本身按
`enterprise_id` + `is_risk_point=true` 过滤，不会跨企业泄露字段。

顺带加固（同一端点族，改动很小——各加一次同企业查询）：`create_unit` / `update_unit` 收到 `risk_object_id` 时
应做同企业校验。目前只有 `PUT /units/{id}/risk-object`（`major_hazard.py:383-392`）走
`link_risk_object` 的校验，`POST` / `PUT /units` 直接落库，可被构造请求塞入他企业的 id。

## 4. 前端变更

| 文件 | 变更 |
|---|---|
| `frontend/src/components/enterprise/majorHazard/riskObjectPrefill.ts`（新增） | 纯函数 `buildUnitPrefill(source, current)` 返回只含空白项的补丁；字段中文名常量 |
| `frontend/src/types/majorHazard.ts` | `LinkableRiskObject` 增加 4 个可选字段 |
| `frontend/src/components/enterprise/majorHazard/RiskObjectPicker.tsx` | 增加可选回调 `onLinked?(object: LinkableRiskObject \| null)`，在 `linkRiskObject` 成功后调用（解除关联时传 `null`） |
| `frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx` | 接住回调 → `form.setFieldsValue(patch)` → 记 `prefilledFields` → 提示；表单 label 挂 Tag；字段 `onChange` 清除自身标记 |

为什么单独成文件：组件文件只能导出组件（`react-refresh/only-export-components`），
常量与纯函数混在组件文件里会触发 lint。参照 `frontend/src/components/enterprise/workTicket/fieldSources.ts`。

## 5. 错误处理与降级

- 风险点列表加载失败：选择器保持禁用 + 全局拦截器提示（现状不变）。
- 风险点 4 个字段全为空：不填、不提示、不报错（没有内容可带）。
- 带出后保存失败：值留在表单里（未落库），用户可重试；不产生"半保存"状态。
- 关联成功但用户不点保存：关联生效、带出的值丢失——这是"关联即时生效 + 字段需保存"的既有契约，
  用 §2.3 的提示语明确告知，不额外改变契约。
- 并发：带出值取本次列表快照，另一用户同时改了风险点允许存在偏差；每次打开详情页会重新拉取列表。

## 6. 测试与验证

后端（pytest 必须从仓库根目录跑）：

1. `backend/tests/test_major_hazard_linkage.py`：`list_linkable_risk_objects` 返回新增 4 字段。
2. `backend/tests/test_major_hazard_api.py`（新增用例，**本次 P0 修复的回归网**）：
   `PUT /units/{id}` 只带 `name` / `unit_type` 时，对象的 `risk_object_id`、`floor_id`、`polygon`
   保持不变；显式传 `null` 时仍可清空。
3. `backend/tests/test_major_hazard_api.py`（新增用例）：`POST /units` 与 `PUT /units/{id}`
   收到他企业 `risk_object_id` 时拒绝（422）。

前端：

4. `riskObjectPrefill.test.ts`：空白才填、非空不动、纯空格算空、来源全空返回空补丁。
5. 容器内门禁：`docker exec emergency-plan-frontend npx tsc -b` / `vitest run` / `eslint src` / `npm run build`。

浏览器实测（**必做**——单测与类型检查抓不到"存不住"这类问题）：

6. 探针流程：建单元 → 选风险点 → 断言 4 项已填、已填项未被覆盖 → 改一个字段令标记消失
   → 点保存 → 重新加载页面 → 断言 `risk_object_id` 仍在、字段已落库。
7. 8082 生产构建验证沿用既有流程（容器内 build → `docker cp` 中转 → 重启 `shuzihuayuan`）。

## 7. 工作量与风险

预计 1 个实现计划 / 4 个任务：

1. P0 修复 `update_unit` + 回归测试
2. `list_linkable_risk_objects` 补字段 + 测试（含同企业校验加固）
3. `riskObjectPrefill.ts` 纯函数 + 单测
4. 页面接线 + 来源标记 + 浏览器探针

风险：

1. **空串与 NULL 的展示差异**：修好后清空字段会存成 `""`，而展示层的 `?? "—"` 兜底只处理
   `null`。需检查 `MajorHazardListPage` 表格列与 `MajorHazardUnitPage` 表单的展示是否出现空白列。
2. **带出的责任人可能与实际不符**：定位是"默认值"而非"权威值"，字段可改、标记提示来源；
   不改成覆盖式以免抹掉人工值。
3. **两个编辑入口**：台账页编辑弹窗与详情页表单写同一批字段，两处都要覆盖到。

## 8. 验收清单

- [ ] 真库现存关联（罐区A（冒烟测试） → 机柜及服务器）在保存基本信息后仍在
- [ ] 选中风险点后 4 项空白字段被填，已填字段未被覆盖
- [ ] 带出字段显示「来自风险点」标记，用户修改后标记消失
- [ ] 后端 `pytest` 全绿（现基线 2176 passed / 1 skipped，只增不减）
- [ ] 前端 `tsc -b` / `vitest` / `eslint` / `build` 全绿
- [ ] 浏览器探针实测：保存后关联与带出字段都还在
