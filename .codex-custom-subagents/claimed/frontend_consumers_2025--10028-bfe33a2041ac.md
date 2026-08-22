# Codex Custom Subagents task handoff v1

Task: frontend_consumers_2025

## 任务：前端事故类型消费点接入共享 27 类模块

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行；测试在 `frontend` 子目录执行（先 `cd frontend`）。前置依赖已提交：`frontend/src/utils/accidentTypes.ts`（ACCIDENT_TYPES_2025 / LEGACY_TO_NEW_ACCIDENT_TYPE_MAP / normalizeAccidentType）。node_modules 已装好，不要运行 npm install。

### 背景

前端存在多处散落的事故类型清单（15 类、12 类、内联 10 类、移动端自由文本）。全部改为引用共享模块 `ACCIDENT_TYPES_2025`（27 类）。

### 改动清单（逐文件）

**1. `frontend\src\utils\riskMethodEngine.ts`（:32）**

删除这一行（本地 15 类清单）：

```ts
export const ACCIDENT_TYPES = ["物体打击","车辆伤害","机械伤害","起重伤害","触电","淹溺","灼烫","火灾","高处坠落","坍塌","锅炉爆炸","容器爆炸","其他爆炸","中毒和窒息","其他伤害"];
```

**2. `frontend\src\components\enterprise\RiskEventForm.tsx`**

- import 行（:9）：`import { computeRiskLS, computeRiskLEC, getCellClass, ACCIDENT_TYPES, RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";` 改为：
  `import { computeRiskLS, computeRiskLEC, getCellClass, RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";`
  并新增一行：`import { ACCIDENT_TYPES_2025 } from "@/utils/accidentTypes";`
- :415 `options={ACCIDENT_TYPES.map(...)}` 改为 `options={ACCIDENT_TYPES_2025.map(...)}`
- :414 占位文案 `placeholder="选择 GB6441 事故类型"` 改为 `placeholder="选择 GB 6441-2025 事故类型"`

**3. `frontend\src\utils\constants.ts`（:1-4）**

删除 `PRESET_RISK_CATEGORIES` 常量（12 类数组）。若其他文件 import 了它，一并改。

**4. `frontend\src\components\enterprise\RiskSourceForm.tsx`**

- import（:8）：`import { PRESET_RISK_CATEGORIES } from "@/utils/constants";` 改为 `import { ACCIDENT_TYPES_2025 } from "@/utils/accidentTypes";`
- :143 `options={PRESET_RISK_CATEGORIES.map(...)}` 改为 `options={ACCIDENT_TYPES_2025.map(...)}`

**5. `frontend\src\pages\Plan\PlanCreatePage.tsx`（:116-125）**

- 顶部 import 区新增：`import { ACCIDENT_TYPES_2025 } from "@/utils/accidentTypes";`
- 内联 options 数组（10 个字符串字面量）替换为：`options={ACCIDENT_TYPES_2025.map((t) => ({ value: t, label: t }))}`

**6. `frontend\src\mobile\screens\PlanCreateScreen.tsx`**

- import 区新增：`import { ACCIDENT_TYPES_2025, normalizeAccidentType } from "@/utils/accidentTypes";`
- 现有 `accidentOptions`（约 :60-67，`[...new Set(rows.map(r => r.accident_type))]`）改为：

```tsx
const recommended = useMemo(
  () =>
    [...new Set(rows.map((r) => normalizeAccidentType(r.accident_type)))]
      .filter((t) => ACCIDENT_TYPES_2025.includes(t as (typeof ACCIDENT_TYPES_2025)[number])),
  [rows],
);

const accidentOptions = useMemo(
  () => [...recommended, ...ACCIDENT_TYPES_2025.filter((t) => !recommended.includes(t))],
  [recommended],
);
```

- 渲染区（约 :205-235）：删除 `{accidentOptions.length > 0 ? (...) : (<Input .../>)}` 三元结构，直接渲染 chips（保留原 chip 的 selected/onClick 交互），始终展示 27 类（推荐值在前）。删除不再使用的 `<Input>` 兜底分支。

### 验证

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\frontend
npx tsc -b
npx vitest run
```

预期：tsc exit 0；vitest 全部通过。若有测试引用被删常量（PRESET_RISK_CATEGORIES / ACCIDENT_TYPES）导致失败，把测试值改为仍存在的值（如「火灾」）或新值。

另执行全库扫描确认旧清单零残留（在 worktree 根）：

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
rg -n "PRESET_RISK_CATEGORIES|ACCIDENT_TYPES\b" frontend/src --glob "*.ts" --glob "*.tsx"
```

预期：零命中（accidentTypes 模块本身除外）。

### 提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add frontend/src/utils/riskMethodEngine.ts frontend/src/utils/constants.ts frontend/src/components/enterprise/RiskEventForm.tsx frontend/src/components/enterprise/RiskSourceForm.tsx frontend/src/pages/Plan/PlanCreatePage.tsx frontend/src/mobile/screens/PlanCreateScreen.tsx
git commit -m "feat(accident-types): switch frontend dropdowns and mobile chips to GB 6441-2025"
```

（若因测试适配需额外 add 测试文件，允许并说明。）

### 红线

- 只改动上述文件及必要的测试适配文件；不要做无关重构
- 不要运行 npm install / npm ci
- 不要更新 TASKS.md
- 中文内容保持 UTF-8
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 每个文件的改动摘要
- tsc / vitest 结果、rg 残留扫描结果
- commit SHA（git log -1 --format=%h）
