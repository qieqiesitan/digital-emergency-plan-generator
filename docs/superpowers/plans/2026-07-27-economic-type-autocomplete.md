# 经济类型字段 — 选项维护功能 实现计划

> **面向 AI 代理的工作者：** 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 将经济类型字段从「固定选项 Select」改为「预设选项 + 自由输入」的 AutoComplete，同时补全移动端和企业类型定义中缺失的字段。

**架构：** 方案 C（混合模式）——桌面端用 Ant Design `AutoComplete`、移动端用自定义 Input + 预设标签。`ECONOMIC_TYPE_OPTIONS` 常量集中定义在 `constants.ts`，所有页面共用。手动输入的值和 AI 自动填充的值都可以自由写入，无后端枚举约束（保持 `String(50)` 自由文本）。

**技术栈：** React 18 + TypeScript + Ant Design 5 AutoComplete（桌面）+ 自研 mobile-ui Input（移动端）

---

## 涉及文件总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/utils/constants.ts` | 修改 | 集中定义 `ECONOMIC_TYPE_OPTIONS` 常量 |
| `frontend/src/types/enterprise.ts` | 修改 | `Enterprise`/`EnterpriseCreate`/`EnterpriseUpdate` 增加 `economic_type` |
| `frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx` | 修改 | Select → AutoComplete，import constants |
| `frontend/src/pages/Enterprise/EnterpriseEditPage.tsx` | 修改 | Select → AutoComplete，import constants |
| `frontend/src/mobile/screens/EnterpriseCreateScreen.tsx` | 修改 | 新增 economic_type 输入字段 |
| `frontend/src/mobile/screens/EnterpriseEditScreen.tsx` | 修改 | 新增 economic_type 输入字段 |
| `frontend/src/mobile/screens/EnterpriseDetailScreen.tsx` | 修改 | 新增 economic_type 展示 |

> **后端无需改动。** `economic_type` 字段在 ORM 模型、Pydantic schema、API 路由中均已完整支持（`String(50)` 自由文本），创建/更新/查询接口均传输此字段。

---

## 现状分析

### 已有

| 位置 | 现状 |
|------|------|
| `backend/app/models/enterprise.py:29` | `economic_type` 列定义，`String(50)` 自由文本 |
| `backend/app/schemas/enterprise.py:43` | `EnterpriseBase.economic_type: str \| None`，Create/Update/Response 均继承 |
| `backend/app/routers/enterprises.py:53` | `_build_response` 中已包含 `economic_type=e.economic_type` |
| `EnterpriseCreatePage.tsx:13` | 局部常量 `ECONOMIC_TYPES = ["国有","集体","民营","外资","合资","股份制","个体"]` |
| `EnterpriseCreatePage.tsx:108-110` | `<Select>` 展示经济类型，无自由输入能力 |
| `EnterpriseEditPage.tsx:14` | 同上局部常量 + Select |
| `EnterpriseDetailPage.tsx:57` | **已展示** `economic_type`，无需改动 |
| `EnterpriseCreatePage.tsx:226` | `initialValues={{ economic_type: "民营" }}` 默认值 |

### 缺失

| 位置 | 问题 |
|------|------|
| `frontend/src/types/enterprise.ts` | `Enterprise` 和 `EnterpriseCreate`/`EnterpriseUpdate` 接口均无 `economic_type` 字段 |
| `frontend/src/utils/constants.ts` | 无 `ECONOMIC_TYPE_OPTIONS` 常量 |
| 桌面 Create/Edit | Select 不支持自由输入，QCC 返回的非标准类型（如"有限责任公司（自然人投资或控股）"）无法显示/选择 |
| 移动端 Create/Edit/Detail | 完全没有 `economic_type` 字段 |

### 设计决策：为什么用 AutoComplete 而不是 mode="tags" 的 Select

| 方案 | 问题 |
|------|------|
| `Select mode="tags"` | 多值模式，用户可以输入任意文本并回车添加 tag。但这是**单选**字段，用 tags 会让用户困惑——看起来像可以选多个 |
| `Select + dropdownRender` 自定义输入 | 实现复杂，需要在 dropdown 底部嵌入一个输入框 + "使用此值"按钮，交互不自然 |
| **`AutoComplete`** | 原生支持「输入文本 + 下拉匹配选项」模式。用户输入时：匹配预设选项 → 显示下拉；不匹配 → 输完即可。值与 Form 绑定为普通字符串，无额外逻辑 |

采用 `AutoComplete`，配合 `options` 属性传入预设选项，用户自由输入的值直接写入 Form。

---

## 任务分解

### 任务 1：constants.ts — 集中定义 ECONOMIC_TYPE_OPTIONS

**文件：** 修改 `frontend/src/utils/constants.ts`

在当前文件末尾追加常量定义。

- [ ] **步骤 1：追加常量**

```typescript
// 经济类型预设选项（AutoComplete 下拉用，允许用户输入自定义值）
export const ECONOMIC_TYPE_OPTIONS = [
  "国有",
  "集体",
  "民营",
  "外资",
  "合资",
  "股份制",
  "个体",
  "有限责任公司",
  "股份有限公司",
  "股份合作制",
  "联营",
  "外商投资企业",
  "港澳台商投资企业",
  "农民专业合作社",
  "个人独资企业",
  "合伙企业",
] as const;
```

> **为什么扩展到 16 项：** QCC 返回的"企业类型"远不止 7 种，预填更多标准分类能提升 AI 填充后的匹配率，减少用户手动输入。

- [ ] **步骤 2：验证编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/utils/constants.ts
git commit -m "feat: add ECONOMIC_TYPE_OPTIONS constant with 16 standard types"
```

---

### 任务 2：types/enterprise.ts — Enterprise 接口增加 economic_type

**文件：** 修改 `frontend/src/types/enterprise.ts`

- [ ] **步骤 1：Enterprise 接口增加字段**

```typescript
export interface Enterprise {
  // ... existing fields ...
  economic_type: string | null;  // 新增
  // ...
}
```

- [ ] **步骤 2：EnterpriseCreate 接口增加字段**

```typescript
export interface EnterpriseCreate {
  name: string;
  address?: string;
  industry?: string;
  business_scope?: string;
  employee_count?: number | null;
  economic_type?: string | null;  // 新增
  // ... other optional fields
}
```

- [ ] **步骤 3：EnterpriseUpdate 同样可用（extends Partial<EnterpriseCreate>，自动继承）**

`EnterpriseUpdate` 继承自 `Partial<EnterpriseCreate>`，新增字段自动包含——无需修改。

- [ ] **步骤 4：验证编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/types/enterprise.ts
git commit -m "feat: add economic_type to Enterprise and EnterpriseCreate types"
```

---

### 任务 3：EnterpriseCreatePage — Select → AutoComplete

**文件：** 修改 `frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx`

**改动要点：**

1. 删除局部常量 `ECONOMIC_TYPES`（第 13 行）
2. 新增 import `ECONOMIC_TYPE_OPTIONS` from constants
3. 新增 import `AutoComplete` from antd
4. 将 `<Select>` 替换为 `<AutoComplete>`（第 108-110 行）

- [ ] **步骤 1：修改 import**

```typescript
// 新增一行（在现有 antd import 的 Select 之后加 AutoComplete）
import { Form, Input, Select, InputNumber, Button, Card, message, Upload, Space, DatePicker, Collapse, AutoComplete } from "antd";

// 导入常量
import { PRESET_INDUSTRIES, ECONOMIC_TYPE_OPTIONS } from "@/utils/constants";
```

- [ ] **步骤 2：删除局部常量**

删除第 13 行：
```typescript
const ECONOMIC_TYPES = ["国有", "集体", "民营", "外资", "合资", "股份制", "个体"];
```

- [ ] **步骤 3：替换 Select 为 AutoComplete**

第 108-110 行，将：
```tsx
<Form.Item name="economic_type" label="经济类型">
  <Select placeholder="选择经济类型" options={ECONOMIC_TYPES.map(t => ({ value: t, label: t }))} />
</Form.Item>
```
替换为：
```tsx
<Form.Item name="economic_type" label="经济类型">
  <AutoComplete
    placeholder="选择或输入经济类型"
    options={ECONOMIC_TYPE_OPTIONS.map(t => ({ value: t, label: t }))}
    filterOption={(inputValue, option) =>
      option!.value.toUpperCase().indexOf(inputValue.toUpperCase()) !== -1
    }
    allowClear
  />
</Form.Item>
```

- [ ] **步骤 4：验证编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx
git commit -m "refactor: convert economic_type Select to AutoComplete in EnterpriseCreatePage"
```

---

### 任务 4：EnterpriseEditPage — Select → AutoComplete

**文件：** 修改 `frontend/src/pages/Enterprise/EnterpriseEditPage.tsx`

编辑页的改动与创建页完全对称。

- [ ] **步骤 1：修改 import**

```typescript
import { Form, Input, Select, InputNumber, Button, Card, message, Upload, Space, DatePicker, Collapse, AutoComplete } from "antd";
import { PRESET_INDUSTRIES, ECONOMIC_TYPE_OPTIONS } from "@/utils/constants";
```

- [ ] **步骤 2：删除局部常量**

删除第 14 行的 `ECONOMIC_TYPES`。

- [ ] **步骤 3：替换 Select 为 AutoComplete**

找到 `<Form.Item name="economic_type" label="经济类型">` 块（约第 62-63 行），替换为与任务 3 相同的 `<AutoComplete>` 代码。

- [ ] **步骤 4：验证编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Enterprise/EnterpriseEditPage.tsx
git commit -m "refactor: convert economic_type Select to AutoComplete in EnterpriseEditPage"
```

---

### 任务 5：移动端 EnterpriseCreateScreen — 新增 economic_type 字段

**文件：** 修改 `frontend/src/mobile/screens/EnterpriseCreateScreen.tsx`

**改动要点：**

1. 在"法定基本资料"区域（`credit_code` 和 `legal_representative` 附近）新增 `economic_type` 表单字段
2. 引入 `ECONOMIC_TYPE_OPTIONS` 常量
3. 用 `Input`（mobile-ui）作为输入控件，下方用一排 Chip 展示预设快捷选项

- [ ] **步骤 1：新增 import**

```typescript
import { ECONOMIC_TYPE_OPTIONS } from "@/utils/constants";
```

确保已有 import：`Input` from `@/mobile/components/ui/Input` 和 `Chip` from `@/mobile/components/ui/Chip`。

- [ ] **步骤 2：新增 state 用于快捷输入**

在组件顶部添加：
```typescript
const [economicType, setEconomicType] = useState("");
```

- [ ] **步骤 3：在法定基本资料区域新增 economic_type 字段**

在 `credit_code` 和 `legal_representative` 表单项之后插入：

```tsx
{/* 经济类型 — 预设标签 + 自由输入 */}
<div className="mb-4">
  <label className="text-caption text-neutral-500 mb-1 block">经济类型</label>
  <Input
    placeholder="选择或输入经济类型"
    value={economicType}
    onChange={setEconomicType}
    className="bg-white mb-2"
  />
  <div className="flex flex-wrap gap-2">
    {ECONOMIC_TYPE_OPTIONS.map(t => (
      <Chip
        key={t}
        selected={economicType === t}
        onClick={() => setEconomicType(t)}
      >
        {t}
      </Chip>
    ))}
  </div>
</div>
```

- [ ] **步骤 4：提交时将 economicType 写入 payload**

在 `onFinish` / `handleSubmit` 中的 payload 构造处追加：
```typescript
economic_type: economicType || null,
```

- [ ] **步骤 5：验证编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/mobile/screens/EnterpriseCreateScreen.tsx
git commit -m "feat: add economic_type field with preset chips to mobile EnterpriseCreateScreen"
```

---

### 任务 6：移动端 EnterpriseEditScreen — 新增 economic_type 字段

**文件：** 修改 `frontend/src/mobile/screens/EnterpriseEditScreen.tsx`

与任务 5 对称。

- [ ] **步骤 1-4：同任务 5 的 import、state、UI 块、payload 处理**

（代码模板与任务 5 一致，编辑页需要在数据加载时将 `enterprise.economic_type` 回填到 `economicType` state。）

回填逻辑（在 `useQuery` 的 `onSuccess` 或 `useEffect` 中）：
```typescript
if (enterprise?.economic_type) {
  setEconomicType(enterprise.economic_type);
}
```

- [ ] **步骤 5：验证编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/mobile/screens/EnterpriseEditScreen.tsx
git commit -m "feat: add economic_type field with preset chips to mobile EnterpriseEditScreen"
```

---

### 任务 7：移动端 EnterpriseDetailScreen — 新增 economic_type 展示

**文件：** 修改 `frontend/src/mobile/screens/EnterpriseDetailScreen.tsx`

- [ ] **步骤 1：在详情页"法定基本资料"区域添加一行展示**

在 `credit_code` 和 `legal_representative` 展示行附近插入：

```tsx
<div className="flex justify-between py-2 border-b border-neutral-50">
  <span className="text-caption text-neutral-400">经济类型</span>
  <span className="text-body text-neutral-800">{enterprise.economic_type || "-"}</span>
</div>
```

- [ ] **步骤 2：验证编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/mobile/screens/EnterpriseDetailScreen.tsx
git commit -m "feat: display economic_type in mobile EnterpriseDetailScreen"
```

---

## 自检

### 精度覆盖度

| 需求 | 对应任务 |
|------|---------|
| 预设选项可维护 | 任务 1（集中常量定义，修改一处全局生效） |
| 支持自由输入（AI 填充的非标准类型不丢失） | 任务 3+4（AutoComplete）、5+6（Input + Chips） |
| 桌面端创建/编辑可输入经济类型 | 任务 3、4 |
| 移动端创建/编辑/查看经济类型 | 任务 5、6、7 |
| 前端类型定义完整 | 任务 2 |
| 后端无需改动 | 已确认：ORM、Schema、Router 均完整支持 |

### 低风险

- 后端 API 已完整支持 `economic_type`——前端新增字段不会导致 422 或数据丢失
- `EnterpriseDetailPage`（桌面端）已经在第 57 行展示 `economic_type`——无需任何改动
- `EnterpriseBase` 已含 `economic_type`，`EnterpriseUpdate` 自动继承——类型安全由编译器保证
- 移动端用 `Input` + `Chip` 的方式与现有交互模式一致（参考当前的行业输入方式）

### 预估工作量

全部 7 个任务约 **150 行代码**，7 个 commit，预计 1-1.5 小时完成。无后端改动。
