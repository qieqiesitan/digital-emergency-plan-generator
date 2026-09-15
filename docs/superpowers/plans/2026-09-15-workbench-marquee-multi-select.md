# 四色分布图工作台：同分区框选多区域批量操作 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在四色分布图工作台的 `select` 工具下支持空白拖拽框选**当前分区**的多个区域，选中后可整体旋转、缩放、移动、删除，一次批量操作只占一步撤销。

**架构：** 纯前端改动。store 的选择状态由单值 `selectedRegionId` 升级为集合 `selectedRegionIds`（唯一权威，单选即长度为 1）；画布用 Konva `Rect` 画选框、命中当前分区的多边形；Konva `Transformer` 由单节点改为多节点实现整体旋转/缩放；整体平移通过拖动任一选中区域时同步其余节点实现；几何命中与批量变换抽成纯函数 `utils/riskMappingMarquee.ts`（复用 `transformPolygonPoints` 的 `center` 参数）。后端与 `floor_plan_polygon` 数据结构不变。

**技术栈：** React 19 + antd 6 + zustand + react-konva/Konva + vitest（frontend 容器 emergency-plan-frontend；静态 8082 容器 shuzihuayuan）。

**运行环境（先读）：**

- 前端源码：宿主 `frontend/src` bind mount 到容器 `/app/src`，5173 dev 即时生效。
- 前端验证一律在容器内执行：`docker exec emergency-plan-frontend npx vitest run <path>`、`docker exec emergency-plan-frontend npx tsc -b`、`docker exec emergency-plan-frontend npx eslint <files>`；宿主 npx 不可用。
- 构建同步：`docker exec emergency-plan-frontend npx vite build` 后
  `docker cp emergency-plan-frontend:/app/dist/. "<宿主 frontend/dist>"`，再
  `docker cp "<宿主 frontend/dist/." shuzihuayuan:/app/dist/`（docker cp 不支持容器直传，需经宿主中转）。
- 本计划不涉及后端，无需重启 backend 容器。
- git：TASKS.md 永不 add；每次 commit 用 pathspec 只加本任务文件，先 `git status --short` 核对。

---

## 文件结构

- 创建 `frontend/src/utils/riskMappingMarquee.ts`：选框构造、多边形×矩形命中、命中区域收集、绕中心批量变换
- 创建 `frontend/src/utils/riskMappingMarquee.test.ts`：上述纯函数单测
- 修改 `frontend/src/store/riskMappingWorkbenchStore.ts`：`selectedRegionIds` 权威 + 三个新 action + 删除/撤销路径适配
- 修改 `frontend/src/store/riskMappingWorkbenchStore.test.ts`：选择集合与批量删除用例
- 修改 `frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`：选择字段适配、框选交互、多节点 Transformer、整体平移
- 修改 `frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`：选择字段适配 + 多选态批量操作面板
- 修改 `frontend/src/components/enterprise/riskMapping/WorkbenchZonePanel.tsx`：待绑定区域选中判断适配
- 修改 `frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx`：删除按钮禁用判断适配
- 修改 `frontend/src/components/enterprise/riskMapping/WorkbenchRiskPointLayer.tsx`：风险点点击时清空区域选择

---

### 任务 1：选框几何与批量变换纯函数

**文件：**
- 创建：`frontend/src/utils/riskMappingMarquee.ts`
- 测试：`frontend/src/utils/riskMappingMarquee.test.ts`

- [ ] **步骤 1：编写失败的测试**

创建 `frontend/src/utils/riskMappingMarquee.test.ts`：

```ts
import { describe, it, expect } from "vitest";
import {
  rectFromPoints,
  polygonIntersectsRect,
  collectRegionsInRect,
  transformRegionsAroundCenter,
} from "./riskMappingMarquee";

const square = (x: number, y: number, size = 10) => [
  { x, y },
  { x: x + size, y },
  { x: x + size, y: y + size },
  { x, y: y + size },
];

describe("rectFromPoints", () => {
  it("两点归一化为正宽高矩形", () => {
    expect(rectFromPoints({ x: 30, y: 40 }, { x: 10, y: 20 })).toEqual({ x: 10, y: 20, width: 20, height: 20 });
  });

  it("拖动距离小于阈值时返回 null", () => {
    expect(rectFromPoints({ x: 10, y: 10 }, { x: 10.1, y: 10.1 }, 0.5)).toBeNull();
  });
});

describe("polygonIntersectsRect", () => {
  const rect = { x: 0, y: 0, width: 20, height: 20 };

  it("完全包含的多边形命中", () => {
    expect(polygonIntersectsRect(square(2, 2, 5), rect)).toBe(true);
  });

  it("部分相交的多边形命中", () => {
    expect(polygonIntersectsRect(square(15, 15, 10), rect)).toBe(true);
  });

  it("完全分离的多边形不命中", () => {
    expect(polygonIntersectsRect(square(50, 50, 5), rect)).toBe(false);
  });

  it("仅边界接触也算命中", () => {
    expect(polygonIntersectsRect(square(20, 5, 5), rect)).toBe(true);
  });

  it("空点集不命中", () => {
    expect(polygonIntersectsRect([], rect)).toBe(false);
  });
});

describe("collectRegionsInRect", () => {
  it("返回命中的区域 id 列表", () => {
    const polygons = [
      { id: "a", points: square(1, 1, 5) },
      { id: "b", points: square(80, 80, 5) },
    ];
    expect(collectRegionsInRect(polygons, { x: 0, y: 0, width: 20, height: 20 })).toEqual(["a"]);
  });
});

describe("transformRegionsAroundCenter", () => {
  const polygons = [{ id: "a", points: square(0, 0, 10) }];

  it("绕配置中心旋转 90 度后中心不变、形状保持", () => {
    const [next] = transformRegionsAroundCenter(polygons, { rotationDeg: 90 }, { x: 5, y: 5 });
    const xs = next.points.map(p => p.x);
    const ys = next.points.map(p => p.y);
    expect((Math.min(...xs) + Math.max(...xs)) / 2).toBeCloseTo(5, 5);
    expect((Math.min(...ys) + Math.max(...ys)) / 2).toBeCloseTo(5, 5);
    expect(Math.max(...xs) - Math.min(...xs)).toBeCloseTo(10, 5);
  });

  it("缩放后顶点仍收敛在 0-100", () => {
    const [next] = transformRegionsAroundCenter(
      [{ id: "a", points: square(90, 90, 10) }],
      { scale: 3 },
      { x: 95, y: 95 },
    );
    for (const p of next.points) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.x).toBeLessThanOrEqual(100);
      expect(p.y).toBeGreaterThanOrEqual(0);
      expect(p.y).toBeLessThanOrEqual(100);
    }
  });
});
```

- [ ] **步骤 2：运行测试确认失败**

运行：`docker exec emergency-plan-frontend npx vitest run src/utils/riskMappingMarquee.test.ts`
预期：FAIL（`Failed to resolve import "./riskMappingMarquee"`）。

- [ ] **步骤 3：实现纯函数**

创建 `frontend/src/utils/riskMappingMarquee.ts`：

```ts
import type { RiskPolygonPoint } from "@/types/riskManagement";
import { clampPoint, transformPolygonPoints } from "@/utils/riskMappingGeometry";

export interface MarqueeRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export const MARQUEE_MIN_SIZE = 0.5; // 百分比单位（约 6px @1200 宽）

export function rectFromPoints(
  a: RiskPolygonPoint,
  b: RiskPolygonPoint,
  minSize = MARQUEE_MIN_SIZE,
): MarqueeRect | null {
  const rect: MarqueeRect = {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x),
    height: Math.abs(a.y - b.y),
  };
  if (rect.width < minSize || rect.height < minSize) return null;
  return rect;
}

const pointInRect = (p: RiskPolygonPoint, r: MarqueeRect) =>
  p.x >= r.x && p.x <= r.x + r.width && p.y >= r.y && p.y <= r.y + r.height;

const pointInPolygon = (p: RiskPolygonPoint, points: RiskPolygonPoint[]) => {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const xi = points[i].x;
    const yi = points[i].y;
    const xj = points[j].x;
    const yj = points[j].y;
    const intersects = yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
};

const orientation = (a: RiskPolygonPoint, b: RiskPolygonPoint, c: RiskPolygonPoint) =>
  (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);

const onSegment = (a: RiskPolygonPoint, b: RiskPolygonPoint, c: RiskPolygonPoint) =>
  Math.min(a.x, b.x) <= c.x &&
  c.x <= Math.max(a.x, b.x) &&
  Math.min(a.y, b.y) <= c.y &&
  c.y <= Math.max(a.y, b.y);

const segmentsIntersect = (p1: RiskPolygonPoint, q1: RiskPolygonPoint, p2: RiskPolygonPoint, q2: RiskPolygonPoint) => {
  const o1 = orientation(p1, q1, p2);
  const o2 = orientation(p1, q1, q2);
  const o3 = orientation(p2, q2, p1);
  const o4 = orientation(p2, q2, q1);
  if (o1 * o2 < 0 && o3 * o4 < 0) return true;
  if (o1 === 0 && onSegment(p1, q1, p2)) return true;
  if (o2 === 0 && onSegment(p1, q1, q2)) return true;
  if (o3 === 0 && onSegment(p2, q2, p1)) return true;
  if (o4 === 0 && onSegment(p2, q2, q1)) return true;
  return false;
};

export function polygonIntersectsRect(points: RiskPolygonPoint[], rect: MarqueeRect): boolean {
  if (points.length < 3) return false;
  if (points.some(p => pointInRect(p, rect))) return true;
  const corners: RiskPolygonPoint[] = [
    { x: rect.x, y: rect.y },
    { x: rect.x + rect.width, y: rect.y },
    { x: rect.x + rect.width, y: rect.y + rect.height },
    { x: rect.x, y: rect.y + rect.height },
  ];
  if (corners.some(c => pointInPolygon(c, points))) return true;
  for (let i = 0; i < points.length; i++) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    for (let j = 0; j < 4; j++) {
      if (segmentsIntersect(a, b, corners[j], corners[(j + 1) % 4])) return true;
    }
  }
  return false;
}

export function collectRegionsInRect<T extends { id: string; points: RiskPolygonPoint[] }>(
  polygons: T[],
  rect: MarqueeRect,
): string[] {
  return polygons.filter(p => polygonIntersectsRect(p.points, rect)).map(p => p.id);
}

export function transformRegionsAroundCenter<T extends { id: string; points: RiskPolygonPoint[] }>(
  polygons: T[],
  options: { scale?: number; rotationDeg?: number; flipX?: boolean; flipY?: boolean },
  center?: RiskPolygonPoint,
): { id: string; points: RiskPolygonPoint[] }[] {
  return polygons.map(p => ({
    id: p.id,
    points: transformPolygonPoints(p.points, { ...options, center }).map(clampPoint),
  }));
}
```

- [ ] **步骤 4：运行测试确认通过**

运行：`docker exec emergency-plan-frontend npx vitest run src/utils/riskMappingMarquee.test.ts`
预期：PASS（12 个用例）。

- [ ] **步骤 5：Commit**

```powershell
git add frontend/src/utils/riskMappingMarquee.ts frontend/src/utils/riskMappingMarquee.test.ts
git commit -m "feat(workbench): 新增选框命中与绕中心批量变换纯函数"
```

---

### 任务 2：store 选择集合升级与组件适配

**文件：**
- 修改：`frontend/src/store/riskMappingWorkbenchStore.ts`
- 修改：`frontend/src/store/riskMappingWorkbenchStore.test.ts`
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`（仅字段适配）
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchZonePanel.tsx`
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx`
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchRiskPointLayer.tsx`
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`（仅字段适配）

- [ ] **步骤 1：编写失败的 store 测试**

在 `frontend/src/store/riskMappingWorkbenchStore.test.ts` 末尾追加：

```ts
describe("region multi-select", () => {
  it("setSelectedRegions 替换选择并清空风险点/文字选择", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ selectedRegionIds: ["pending:r1"], selectedRiskPointId: "p1", selectedTextId: "t1" });
    store.getState().setSelectedRegions(["zone:z1:p1", "zone:z1:p2"]);
    expect(store.getState().selectedRegionIds).toEqual(["zone:z1:p1", "zone:z1:p2"]);
    expect(store.getState().selectedRiskPointId).toBeNull();
    expect(store.getState().selectedTextId).toBeNull();
  });

  it("setSelectedRegions append 去重", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ selectedRegionIds: ["zone:z1:p1"] });
    store.getState().setSelectedRegions(["zone:z1:p1", "zone:z1:p2"], { append: true });
    expect(store.getState().selectedRegionIds).toEqual(["zone:z1:p1", "zone:z1:p2"]);
  });

  it("deleteSelectedRegions 混合删除且只压一步撤销", () => {
    const store = useRiskMappingWorkbenchStore;
    const zone = {
      ...makeZone("z1"),
      floor_plan_polygon: {
        version: 2 as const,
        level_mode: "auto" as const,
        risk_level: null,
        polygons: [
          { id: "p1", label: "p1", points: [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }] },
          { id: "p2", label: "p2", points: [{ x: 2, y: 2 }, { x: 3, y: 2 }, { x: 3, y: 3 }] },
        ],
      },
    };
    store.setState({
      zones: [zone],
      pendingRegions: [
        { id: "r1", floor_id: "f1", points: [{ x: 5, y: 5 }, { x: 6, y: 5 }, { x: 6, y: 6 }], created_at: "2026-09-15T00:00:00+08:00" },
      ],
      selectedRegionIds: ["zone:z1:p1", "pending:r1"],
      past: [],
      future: [],
    });

    store.getState().deleteSelectedRegions();

    expect(store.getState().zones[0].floor_plan_polygon?.polygons.map(p => p.id)).toEqual(["p2"]);
    expect(store.getState().pendingRegions).toHaveLength(0);
    expect(store.getState().selectedRegionIds).toEqual([]);
    expect(store.getState().past).toHaveLength(1);

    undo();
    expect(store.getState().zones[0].floor_plan_polygon?.polygons.map(p => p.id)).toEqual(["p1", "p2"]);
    expect(store.getState().pendingRegions).toHaveLength(1);
  });
});
```

（该文件顶部已 import `undo`；`makeZone` 是文件内既有 helper；若命名不同按文件实际名称调整，勿新建重复 helper。）

- [ ] **步骤 2：运行确认失败**

运行：`docker exec emergency-plan-frontend npx vitest run src/store/riskMappingWorkbenchStore.test.ts`
预期：FAIL（`setSelectedRegions is not a function`）。

- [ ] **步骤 3：升级 store**

`frontend/src/store/riskMappingWorkbenchStore.ts` 逐处修改：

```ts
// interface WorkbenchState
selectedRegionIds: string[];
setSelectedRegions: (ids: string[], options?: { append?: boolean }) => void;
toggleRegionSelection: (id: string) => void;
deleteSelectedRegions: () => void;

// initial
selectedRegionIds: [],
```

新增实现（放在 `setSnapshot` 之后）：

```ts
  setSelectedRegions: (ids, options) => set(state => {
    const next = options?.append ? Array.from(new Set([...state.selectedRegionIds, ...ids])) : ids;
    return { selectedRegionIds: next, selectedRiskPointId: null, selectedTextId: null };
  }),
  toggleRegionSelection: (id) => set(state => {
    const has = state.selectedRegionIds.includes(id);
    return {
      selectedRegionIds: has ? state.selectedRegionIds.filter(x => x !== id) : [...state.selectedRegionIds, id],
      selectedRiskPointId: null,
      selectedTextId: null,
    };
  }),
  deleteSelectedRegions: () => {
    const state = get();
    if (!state.selectedRegionIds.length) return;
    state.commit();
    const current = get();
    const pendingIds = new Set<string>();
    const zonePolygons = new Map<string, Set<string>>();
    for (const id of current.selectedRegionIds) {
      if (id.startsWith("pending:")) {
        pendingIds.add(id.slice("pending:".length));
      } else if (id.startsWith("zone:")) {
        const body = id.slice("zone:".length);
        const separator = body.indexOf(":");
        const zoneId = body.slice(0, separator);
        const polygonId = body.slice(separator + 1);
        if (!zonePolygons.has(zoneId)) zonePolygons.set(zoneId, new Set());
        zonePolygons.get(zoneId)!.add(polygonId);
      }
    }
    set({
      pendingRegions: current.pendingRegions.filter(r => !pendingIds.has(r.id)),
      zones: current.zones.map(z => {
        const removing = zonePolygons.get(z.id);
        if (!removing || !z.floor_plan_polygon) return z;
        return {
          ...z,
          floor_plan_polygon: {
            ...z.floor_plan_polygon,
            polygons: z.floor_plan_polygon.polygons.filter(p => !removing.has(p.id)),
          },
        };
      }),
      selectedRegionIds: [],
    });
  },
```

替换既有引用（保持行为）：

```ts
// deleteZone 内
selectedRegionIds: state.selectedRegionIds.filter(id => !id.startsWith(`zone:${zoneId}:`)),

// deletePendingRegion 内
selectedRegionIds: state.selectedRegionIds.filter(id => id !== `pending:${regionId}`),

// deleteZonePolygon 内
selectedRegionIds: state.selectedRegionIds.filter(id => id !== `zone:${zoneId}:${polygonId}`),

// deleteSelected 开头 guard
if (!state.selectedRegionIds.length && !state.selectedRiskPointId && !state.selectedTextId) return;
// 且把原三段 selectedRegionId 分支整体替换为：
if (get().selectedRegionIds.length) {
  get().deleteSelectedRegions();
  return;
}

// undo / redo 的 restored 对象
selectedRegionIds: state.selectedRegionIds,
```

- [ ] **步骤 4：适配组件引用点**

`WorkbenchCanvas.tsx`（本步骤只做字段适配，框选逻辑在任务 3）：

```ts
const selectedRegionIds = useRiskMappingWorkbenchStore(s => s.selectedRegionIds);
const selectedRegionId = selectedRegionIds[0] ?? null; // 供既有单选分支复用
```

- Esc 分支：`setState({ selectedRegionIds: [], selectedRiskPointId: null, selectedTextId: null })`
- `data-transform-active={tool === "select" && selectedRegionIds.length > 0}`
- 区域点击：`setSelectedRegions([regionId])`（已绑定）与 `setSelectedRegions([`pending:${r.id}`])`（待绑定）；风险点/文字点击改用 `setSelectedRegions([])`
- 区域 selected 判断：`selectedRegionIds.includes(regionId)`（两处）

`WorkbenchZonePanel.tsx`：选中判断改 `selectedRegionIds.includes(`pending:${r.id}`)`，点击改 `setState({ selectedRegionIds: [`pending:${r.id}`], selectedZoneId: null })`。

`WorkbenchToolbar.tsx`：`Boolean(s.selectedRegionIds.length > 0 || s.selectedRiskPointId || s.selectedTextId)`。

`WorkbenchRiskPointLayer.tsx`：`setState({ selectedRiskPointId: p.id, selectedRegionIds: [], selectedTextId: null })`。

`WorkbenchPropertiesPanel.tsx`：`const selectedRegionIds = useRiskMappingWorkbenchStore(s => s.selectedRegionIds); const selectedRegionId = selectedRegionIds[0] ?? null;`（其余单选逻辑不动）。

- [ ] **步骤 5：运行确认通过**

```powershell
docker exec emergency-plan-frontend npx vitest run src/store/riskMappingWorkbenchStore.test.ts
docker exec emergency-plan-frontend npx tsc -b
```
预期：store 测试全绿；tsc 0 error。

- [ ] **步骤 6：Commit**

```powershell
git add frontend/src/store/riskMappingWorkbenchStore.ts frontend/src/store/riskMappingWorkbenchStore.test.ts frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx frontend/src/components/enterprise/riskMapping/WorkbenchZonePanel.tsx frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx frontend/src/components/enterprise/riskMapping/WorkbenchRiskPointLayer.tsx frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx
git commit -m "feat(workbench): 区域选择升级为多选集合并支持批量删除"
```

---

### 任务 3：画布框选交互

**文件：**
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`

- [ ] **步骤 1：实现框选（本任务无纯函数单测，以 tsc + 回归 + 冒烟验证）**

新增 state 与 ref：

```ts
const [marqueeStart, setMarqueeStart] = useState<RiskPolygonPoint | null>(null);
const [marqueeEnd, setMarqueeEnd] = useState<RiskPolygonPoint | null>(null);
const marqueeShiftRef = useRef(false);
```

`handleMouseDown` 在平移分支之后、绘制工具分支之前插入：

```ts
  if (tool === "select") {
    const selectedZoneId = useRiskMappingWorkbenchStore.getState().selectedZoneId;
    if (!selectedZoneId) {
      message.info("请先选择分区后再框选");
      return;
    }
    const p = pointFromEvent(e);
    marqueeShiftRef.current = e.evt.shiftKey;
    setMarqueeStart(p);
    setMarqueeEnd(p);
    return;
  }
```

`handleMouseMove` 顶部（平移提前返回之后）插入：

```ts
  if (marqueeStart) {
    setMarqueeEnd(pointFromEvent(e));
    return;
  }
```

`handleMouseUp` 顶部（平移分支之后）插入：

```ts
  if (marqueeStart) {
    const store = useRiskMappingWorkbenchStore.getState();
    const rect = marqueeEnd
      ? rectFromPoints(marqueeStart, marqueeEnd, (3 / canvasWidth) * 100)
      : null;
    setMarqueeStart(null);
    setMarqueeEnd(null);
    if (!rect) {
      if (!marqueeShiftRef.current) store.setSelectedRegions([]);
      return;
    }
    const zone = store.zones.find(z => z.id === store.selectedZoneId);
    const polygons = zone?.floor_plan_polygon?.polygons ?? [];
    const hitIds = collectRegionsInRect(polygons, rect).map(id => `zone:${zone!.id}:${id}`);
    store.setSelectedRegions(hitIds, { append: marqueeShiftRef.current });
    return;
  }
```

选框渲染（放在 Layer 内区域渲染之前）：

```tsx
{marqueeStart && marqueeEnd && (() => {
  const rect = rectFromPoints(marqueeStart, marqueeEnd, (3 / canvasWidth) * 100);
  if (!rect) return null;
  return (
    <Rect
      x={toCanvasX(rect.x, canvasWidth)}
      y={toCanvasY(rect.y, canvasHeight)}
      width={(rect.width / 100) * canvasWidth}
      height={(rect.height / 100) * canvasHeight}
      fill="rgba(22,119,255,0.12)"
      stroke="#1677ff"
      dash={[6, 4]}
      strokeWidth={1.5}
      listening={false}
    />
  );
})()}
```

区域节点上必须阻止 mousedown 冒泡，保证点击/拖动区域不会启动框选（两个区域渲染块都加）：

```tsx
onMouseDown={e => {
  e.cancelBubble = true;
}}
```

导入补充：

```ts
import { collectRegionsInRect, rectFromPoints } from "@/utils/riskMappingMarquee";
import { Modal, Input, InputNumber, Button, Space, message } from "antd";
```

`handleMouseUp` 现有的 pen/polygon/freehand 分支保持在框选分支之后，不受影响。

- [ ] **步骤 2：验证**

```powershell
docker exec emergency-plan-frontend npx tsc -b
docker exec emergency-plan-frontend npx vitest run src/store/riskMappingWorkbenchStore.test.ts src/utils/riskMappingMarquee.test.ts
```
预期：tsc 0 error；测试全绿。

- [ ] **步骤 3：Commit**

```powershell
git add frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx
git commit -m "feat(workbench): select 工具下支持空白拖拽框选当前分区区域"
```

---

### 任务 4：多选整体旋转/缩放/平移

**文件：**
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`

- [ ] **步骤 1：多节点 Transformer**

替换现有单节点挂载（约 1010-1020 行）：

```tsx
{tool === "select" && (() => {
  const nodes = selectedRegionIds
    .map(id => regionNodeRefs.current.get(id))
    .filter(Boolean);
  if (!nodes.length) return null;
  return (
    <Transformer
      ref={transformerRef}
      nodes={nodes}
      rotateEnabled
      flipEnabled={false}
      anchorSize={10}
      borderStroke="#1677ff"
      anchorStroke="#1677ff"
      anchorFill="#ffffff"
    />
  );
})()}
```

- [ ] **步骤 2：整体变换一次性写回**

`handleRegionTransformStart` 改为记录全部选中节点原点位（`regionTransformOriginRef` 已存在，改为按 regionId 存点集）：

```ts
const handleRegionTransformStart = (regionId: string, points: RiskPolygonPoint[]) => {
  const store = useRiskMappingWorkbenchStore.getState();
  const targets = store.selectedRegionIds.length ? store.selectedRegionIds : [regionId];
  targets.forEach(id => {
    const nodePoints = resolveRegionPoints(id);
    if (nodePoints) regionTransformOriginRef.current.set(id, nodePoints);
  });
};
```

（`resolveRegionPoints(id: string): RiskPolygonPoint[] | null` 为新增 helper：按 `pending:` / `zone:` 前缀从 store 取该区域当前顶点。）

`handleRegionTransformEnd` 改为遍历并一次性写回：

```ts
const handleRegionTransformEnd = () => {
  const origin = new Map(regionTransformOriginRef.current);
  if (!origin.size) return;
  regionTransformOriginRef.current.clear();
  const updates = new Map<string, RiskPolygonPoint[]>();
  origin.forEach((points, regionId) => {
    const node = regionNodeRefs.current.get(regionId);
    if (!node) return;
    const transform = node.getTransform();
    const next = points.map(pt => {
      const canvasPoint = transform.point({ x: toCanvasX(pt.x, canvasWidth), y: toCanvasY(pt.y, canvasHeight) });
      return clampPoint({ x: toPercent(canvasPoint.x, canvasWidth), y: toPercent(canvasPoint.y, canvasHeight) });
    });
    node.scale({ x: 1, y: 1 });
    node.rotation(0);
    node.position({ x: 0, y: 0 });
    node.offset({ x: 0, y: 0 });
    updates.set(regionId, next);
  });
  commit();
  setSnapshot({ zones: applyRegionPointUpdates(useRiskMappingWorkbenchStore.getState().zones, updates) });
};
```

（`applyRegionPointUpdates(zones, updates)` 为新增纯 helper：按 `zone:` 前缀把新顶点写回对应分区的 polygons，返回新 zones 数组；`pending:` 前缀暂不在本任务处理，多选框选只命中已绑定区域。）

- [ ] **步骤 3：整体平移**

新增 ref：

```ts
const groupDragRef = useRef<{ startX: number; startY: number; origin: Map<string, RiskPolygonPoint[]> } | null>(null);
```

已绑定区域 `Line` 的拖动事件改为：

```tsx
onDragStart={e => {
  const store = useRiskMappingWorkbenchStore.getState();
  const isSelected = store.selectedRegionIds.includes(regionId);
  if (!isSelected) store.setSelectedRegions([regionId]);
  const targets = useRiskMappingWorkbenchStore.getState().selectedRegionIds;
  const origin = new Map<string, RiskPolygonPoint[]>();
  targets.forEach(id => {
    const pts = resolveRegionPoints(id);
    if (pts) origin.set(id, pts);
  });
  groupDragRef.current = { startX: e.target.x(), startY: e.target.y(), origin };
}}
onDragMove={e => {
  const group = groupDragRef.current;
  if (!group || group.origin.size < 2) return;
  const dx = e.target.x() - group.startX;
  const dy = e.target.y() - group.startY;
  group.origin.forEach((_pts, id) => {
    if (id === regionId) return;
    regionNodeRefs.current.get(id)?.position({ x: dx, y: dy });
  });
}}
onDragEnd={e => {
  const dx = (e.target.x() / canvasWidth) * 100;
  const dy = (e.target.y() / canvasHeight) * 100;
  const group = groupDragRef.current;
  groupDragRef.current = null;
  const targets = group?.origin ?? new Map([[regionId, p.points]]);
  const updates = new Map<string, RiskPolygonPoint[]>();
  targets.forEach((points, id) => {
    updates.set(id, points.map(pt => clampPoint({ x: pt.x + dx, y: pt.y + dy })));
    regionNodeRefs.current.get(id)?.position({ x: 0, y: 0 });
  });
  e.target.position({ x: 0, y: 0 });
  commit();
  setSnapshot({ zones: applyRegionPointUpdates(useRiskMappingWorkbenchStore.getState().zones, updates) });
}}
```

（替换既有 `zoneDragOriginRef` 用法；`zoneDragOriginRef` 若无其他引用则一并删除。）

- [ ] **步骤 4：验证**

```powershell
docker exec emergency-plan-frontend npx tsc -b
docker exec emergency-plan-frontend npx vitest run
```
预期：tsc 0 error；全量测试通过。

- [ ] **步骤 5：Commit**

```powershell
git add frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx
git commit -m "feat(workbench): 多选区域支持整体旋转/缩放/平移且单步撤销"
```

---

### 任务 5：属性面板多选态批量操作

**文件：**
- 修改：`frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx`

- [ ] **步骤 1：实现多选面板**

在组件内计算多选数据：

```ts
const selectedRegionIds = useRiskMappingWorkbenchStore(s => s.selectedRegionIds);
const multiSelectMode = selectedRegionIds.length > 1;
const selectedPolygons = (() => {
  const store = useRiskMappingWorkbenchStore.getState();
  const zone = store.zones.find(z => z.id === store.selectedZoneId);
  const polygons = zone?.floor_plan_polygon?.polygons ?? [];
  return polygons.filter(p => selectedRegionIds.includes(`zone:${zone!.id}:${p.id}`));
})();
const multiCenter = selectedPolygons.length
  ? polygonCentroid(selectedPolygons.flatMap(p => p.points))
  : null;
```

批量应用 helper：

```ts
const applyMultiTransform = (options: { scale?: number; rotationDeg?: number; flipX?: boolean; flipY?: boolean }) => {
  if (!multiCenter || !selectedPolygons.length) return;
  const store = useRiskMappingWorkbenchStore.getState();
  const zone = store.zones.find(z => z.id === store.selectedZoneId);
  if (!zone?.floor_plan_polygon) return;
  const transformed = transformRegionsAroundCenter(selectedPolygons, options, multiCenter);
  const byId = new Map(transformed.map(t => [t.id, t.points]));
  commit();
  setSnapshot({
    zones: store.zones.map(z =>
      z.id !== zone.id || !z.floor_plan_polygon
        ? z
        : {
            ...z,
            floor_plan_polygon: {
              ...z.floor_plan_polygon,
              polygons: z.floor_plan_polygon.polygons.map(p =>
                byId.has(p.id) ? { ...p, points: byId.get(p.id)! } : p,
              ),
            },
          },
    ),
  });
};
```

多选态 UI（放在属性面板顶部，`selectedPending`/`selectedZonePolygon` 区块之前）：

```tsx
{multiSelectMode && (
  <div style={{ border: "1px solid #8b5cf6", borderRadius: 6, padding: 8, marginBottom: 12 }}>
    <strong>已选中 {selectedRegionIds.length} 个区域</strong>
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
      <span style={{ fontSize: 12, color: "#666" }}>缩放</span>
      <InputNumber style={{ flex: 1 }} min={10} max={500} value={regionScale} onChange={v => setRegionScale(v ?? 100)} addonAfter="%" />
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
      <span style={{ fontSize: 12, color: "#666" }}>旋转</span>
      <InputNumber style={{ flex: 1 }} min={-360} max={360} value={regionRotation} onChange={v => setRegionRotation(v ?? 0)} addonAfter="°" />
    </div>
    <Button block type="primary" style={{ marginTop: 6 }} onClick={() => applyMultiTransform({ scale: regionScale / 100, rotationDeg: regionRotation })}>
      应用变换
    </Button>
    <Space.Compact style={{ width: "100%", marginTop: 6 }}>
      <Button style={{ width: "50%" }} onClick={() => applyMultiTransform({ flipX: true })}>水平翻转</Button>
      <Button style={{ width: "50%" }} onClick={() => applyMultiTransform({ flipY: true })}>垂直翻转</Button>
    </Space.Compact>
    <Button danger block style={{ marginTop: 6 }} icon={<DeleteOutlined />} onClick={() => useRiskMappingWorkbenchStore.getState().deleteSelectedRegions()}>
      删除选中区域
    </Button>
  </div>
)}
```

单选区块（`selectedPending`、`selectedZonePolygon`、单区域"自由变换"）在多选态下隐藏：

```tsx
{!multiSelectMode && selectedPending && (...)}
{!multiSelectMode && selectedZonePolygon?.polygon && selectedZonePolygon.zone && (...)}
{!multiSelectMode && (selectedPending || selectedZonePolygon) && (...单区域自由变换...)}
```

导入补充：

```ts
import { polygonCentroid } from "@/utils/riskMappingGeometry";
import { transformRegionsAroundCenter } from "@/utils/riskMappingMarquee";
```

- [ ] **步骤 2：验证**

```powershell
docker exec emergency-plan-frontend npx tsc -b
docker exec emergency-plan-frontend npx eslint src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx
docker exec emergency-plan-frontend npx vitest run
```
预期：tsc 0 error；eslint 无新增错误（该文件存在既有 `set-state-in-effect` 告警，属历史问题）；全量测试通过。

- [ ] **步骤 3：Commit**

```powershell
git add frontend/src/components/enterprise/riskMapping/WorkbenchPropertiesPanel.tsx
git commit -m "feat(workbench): 属性面板支持多选批量旋转/缩放/翻转/删除"
```

---

### 任务 6：全量回归与部署同步

**文件：** 无代码改动；仅验证、构建与冒烟。

- [ ] **步骤 1：前端全量验证**

```powershell
docker exec emergency-plan-frontend npx vitest run
docker exec emergency-plan-frontend npx tsc -b
```
预期：vitest 全绿（含新增 marquee 与 store 用例）；tsc 0 error。

- [ ] **步骤 2：构建与同步**

```powershell
docker exec emergency-plan-frontend npx vite build
docker cp emergency-plan-frontend:/app/dist/. "C:\Users\55061\Documents\数字化预案自动生成 2\frontend\dist\"
docker cp "C:\Users\55061\Documents\数字化预案自动生成 2\frontend\dist\." shuzihuayuan:/app/dist/
curl -s http://localhost:8082 | Select-String -Pattern 'main-[A-Za-z0-9_-]+\.js' | Select-Object -First 1
```
预期：build 成功；8082 引用新的 main 资源且可访问（`curl -s -o NUL -w "%{http_code}"` 返回 200）。

- [ ] **步骤 3：浏览器冒烟清单**

在 5173 或 8082（硬刷新后）逐条验证：

1. 选中某分区 → `select` 工具下从空白拖出选框 → 框内区域蓝色高亮且出现整体外框。
2. 整体旋转 15° → 保存 → 退出重进，旋转结果保持。
3. 拖动任一选中区域 → 其余选中区域同步平移 → 保存 → 重进保持。
4. 拖外框角整体缩放 → 保存 → 重进保持。
5. 批量删除 → 保存；按一次撤销回到删除前。
6. Shift 框选追加、单击空白清空、未选分区框选提示"请先选择分区后再框选"、绘制工具下不触发框选。

- [ ] **步骤 4：收尾核对**

```powershell
git status --short
git log --oneline -8
```
预期：仅剩 TASKS.md 与无关的他人/历史改动；本计划 5 个 commit 均在 log 中。

---

## 自检

**1. 规格覆盖度：** 选择集合（任务 2）、框选交互（任务 3）、多节点旋转/缩放（任务 4 步骤 1）、整体平移（任务 4 步骤 3）、批量删除（任务 2 步骤 3 + 任务 5 面板按钮 + 任务 2 `deleteSelected` 键盘路径）、多选属性面板（任务 5）、单步撤销（任务 2 的 `commit()` 一次 + store 用例断言 `past.length === 1`）、纯函数单测（任务 1）、浏览器冒烟（任务 6 步骤 3）——规格各节均有对应任务；规格中"未选分区提示""绘制工具不触发""顶点 clamp 0-100"分别落在任务 3、任务 3、任务 1/4。

**2. 占位符扫描：** 无 TODO/待定；每个代码步骤均给出可粘贴代码或精确命令。

**3. 类型一致性：** 全程使用 `selectedRegionIds: string[]`、`setSelectedRegions(ids, { append })`、`toggleRegionSelection(id)`、`deleteSelectedRegions()`、`rectFromPoints(a, b, minSize)`、`polygonIntersectsRect(points, rect)`、`collectRegionsInRect(polygons, rect)`、`transformRegionsAroundCenter(polygons, options, center)`；`RiskPolygonPoint` 来自 `@/types/riskManagement`，与 canvas/geometry 工具一致。规格中提到的 `snapshotOf` 实际不含选择字段（选择态在 undo/redo 的 restored 对象中保留），本计划按实际代码修正为替换 undo/redo 中的 `selectedRegionId`。
