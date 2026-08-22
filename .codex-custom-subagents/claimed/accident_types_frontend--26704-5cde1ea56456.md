# Codex Custom Subagents task handoff v1

Task: accident_types_frontend

## 任务：前端事故类型共享模块（GB 6441-2025，TDD）

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

这是隔离 git 分支 `codex/accident-types-2025` 的工作区。命令在 PowerShell 中执行；测试在 `frontend` 子目录执行（先 `cd frontend`）。node_modules 已装好，不要运行 npm install。

### 背景

数字化应急预案系统（React + TypeScript + Vite + Vitest）。本任务建立前端事故类型唯一事实源模块（与后端模块同内容同语义）。后续任务会让各下拉框引用它。

### 第 1 步：创建测试文件（红灯）

创建文件：`frontend\src\utils\accidentTypes.test.ts`，内容如下（完整粘贴）：

```ts
import {
  ACCIDENT_TYPES_2025,
  LEGACY_TO_NEW_ACCIDENT_TYPE_MAP,
  normalizeAccidentType,
} from "./accidentTypes";

describe("accidentTypes (GB 6441-2025)", () => {
  it("exposes exactly 27 ordered types", () => {
    expect(ACCIDENT_TYPES_2025).toEqual([
      "物体打击", "厂（场）内车辆致害", "道路（轨道）车辆致害", "机械致害", "起重致害",
      "触电", "淹溺", "灼烫", "火灾", "高处坠落", "跌落", "坍塌", "水害", "容器爆炸",
      "管道爆炸", "可燃气体爆炸", "可燃液体蒸气爆炸", "粉尘爆炸", "民用爆炸物品爆炸",
      "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "中毒", "窒息", "滑坡",
      "泄漏", "其他",
    ]);
    expect(new Set(ACCIDENT_TYPES_2025).size).toBe(27);
  });

  it("maps all 20 old standard types and 2 presets", () => {
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["瓦斯爆炸"]).toBe("可燃气体爆炸");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["锅炉爆炸"]).toBe("容器爆炸");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["爆炸"]).toBe("其他");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["中毒窒息"]).toBe("中毒");
    expect(Object.keys(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP)).toHaveLength(22);
  });

  it("normalizes new/legacy/unknown values", () => {
    expect(normalizeAccidentType("火灾")).toBe("火灾");
    expect(normalizeAccidentType("中毒和窒息")).toBe("中毒");
    expect(normalizeAccidentType("设备损坏/数据丢失")).toBe("设备损坏/数据丢失");
    expect(normalizeAccidentType("")).toBe("");
  });
});
```

### 第 2 步：运行测试确认失败（必须亲眼看到失败）

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\frontend
npx vitest run src/utils/accidentTypes.test.ts
```

预期：FAIL，`Cannot find module './accidentTypes'`。

### 第 3 步：创建实现文件（绿灯）

创建文件：`frontend\src\utils\accidentTypes.ts`，内容如下（完整粘贴）：

```ts
/** 事故类型共享常量：GB 6441-2025《生产安全事故分类与编码》27 类 + 新旧映射。
 *  全前端事故类型/风险类别唯一事实源。 */

export const ACCIDENT_TYPES_2025 = [
  "物体打击", "厂（场）内车辆致害", "道路（轨道）车辆致害", "机械致害", "起重致害",
  "触电", "淹溺", "灼烫", "火灾", "高处坠落", "跌落", "坍塌", "水害", "容器爆炸",
  "管道爆炸", "可燃气体爆炸", "可燃液体蒸气爆炸", "粉尘爆炸", "民用爆炸物品爆炸",
  "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "中毒", "窒息", "滑坡",
  "泄漏", "其他",
] as const;

/** GB/T 6441-1986 20 类 + 旧系统预设类别 → GB 6441-2025。 */
export const LEGACY_TO_NEW_ACCIDENT_TYPE_MAP: Record<string, string> = {
  "物体打击": "物体打击",
  "车辆伤害": "厂（场）内车辆致害",
  "机械伤害": "机械致害",
  "起重伤害": "起重致害",
  "触电": "触电",
  "淹溺": "淹溺",
  "灼烫": "灼烫",
  "火灾": "火灾",
  "高处坠落": "高处坠落",
  "坍塌": "坍塌",
  "冒顶片帮": "坍塌",
  "透水": "水害",
  "放炮": "民用爆炸物品爆炸",
  "火药爆炸": "民用爆炸物品爆炸",
  "瓦斯爆炸": "可燃气体爆炸",
  "锅炉爆炸": "容器爆炸",
  "容器爆炸": "容器爆炸",
  "其他爆炸": "其他",
  "中毒和窒息": "中毒",
  "其他伤害": "其他",
  "爆炸": "其他",
  "中毒窒息": "中毒",
};

export function normalizeAccidentType(value: string): string {
  if (!value) return "";
  const v = value.trim();
  return LEGACY_TO_NEW_ACCIDENT_TYPE_MAP[v] ?? v;
}
```

### 第 4 步：运行测试确认通过（必须亲眼看到 PASS）

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\frontend
npx vitest run src/utils/accidentTypes.test.ts
```

预期：3 passed。

### 第 5 步：提交（在 worktree 根目录）

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add frontend/src/utils/accidentTypes.ts frontend/src/utils/accidentTypes.test.ts
git commit -m "feat(accident-types): add shared frontend GB 6441-2025 module"
```

### 红线

- 只创建上述两个文件，禁止改动任何其他文件（包括 TASKS.md）
- 不要做状态汇报或计划总结，直接执行
- 不要运行 npm install / npm ci（依赖已装好）
- 中文内容保持 UTF-8 编码，不得使用转义
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 红灯输出摘要（一行）+ 绿灯结果（3 passed）
- commit SHA（git log -1 --format=%h）
- 确认 git status 只含本次两个文件（或干净）
