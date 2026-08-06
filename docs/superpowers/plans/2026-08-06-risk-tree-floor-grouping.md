# 风险分级管控分区树楼层分组 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让风险分级管控分区层级树按楼层分组展示（企业 -> 楼层 -> 分区 -> 对象 -> 单元 -> 事件 -> 措施），并让分区创建/编辑真正归属楼层。

**架构：** 后端 `/hierarchy` 在未传 `floor_id` 时返回企业全部楼层分区（响应结构不变，总览页单楼层行为不变）；前端用纯函数 `groupZonesByFloor` 将分区按楼层分组，`RiskHierarchyTree` 顶层渲染楼层节点，`RiskZoneForm` 增加楼层选择并让平面图标注底图跟随所选楼层。

**技术栈：** FastAPI（backend）、React + antd + TanStack Query + Konva 系（frontend）、pytest / vitest / Playwright。

---

## 前置说明（仓库约定，每个改动任务开始前都要遵守）

- 每个改动任务开始前，先按 AGENTS.md 铁律二执行本地保存点（`git save`；若当前环境无此 alias 则记录跳过）并检查调用者/影响面（`codegraph callers` / `codegraph impact` / `graphify explain`，仅对涉及的符号）。
- 提交信息遵循仓库现有 Conventional Commits 风格（`feat(risk-management): ...`）。
- 工作区已有用户未提交改动（`frontend/src/components/enterprise/riskMapping/RiskDistributionStage.tsx`、`backend/app/regulations/data/chroma_db/chroma.sqlite3`、`backup/risk-mapping-pre-migration-20260805.sql`），**不得触碰、不得纳入任何提交**。
- 验证命令统一约定：
  - 后端单测：`cd backend; python -m pytest -q tests/test_risk_hierarchy.py -v`
  - 后端全量：`cd backend; python -m pytest -q --ignore tests/test_autofill_research.py --ignore _docker_test.py`
  - 前端类型：`cd frontend; npx tsc -b`
  - 前端单测：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts src/utils/zoneSubmit.test.ts`
  - E2E：`cd frontend; npx playwright test e2e/risk-hierarchy-tree.spec.ts`
  - 生产构建：`cd frontend; npx -y node@22 node_modules/vite/bin/vite.js build`

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/routers/risk_management.py` | `/hierarchy` 多楼层返回 + 排序纯函数 | 修改 |
| `backend/tests/test_risk_hierarchy.py` | 排序纯函数单测 | 创建 |
| `frontend/src/utils/zoneSubmit.ts` | `buildZonePayload` 透传 `floor_id` | 修改 |
| `frontend/src/utils/zoneSubmit.test.ts` | `floor_id` 透传断言 | 修改 |
| `frontend/src/utils/riskTreeGrouping.ts` | 纯函数：分区按楼层分组、未分配兜底 | 创建 |
| `frontend/src/utils/riskTreeGrouping.test.ts` | 分组纯函数单测 | 创建 |
| `frontend/src/components/enterprise/RiskHierarchyTree.tsx` | 顶层楼层节点渲染、展开策略、楼层操作 | 修改 |
| `frontend/src/components/enterprise/RiskZoneForm.tsx` | 楼层 Select + 标注底图跟随楼层 | 修改 |
| `frontend/src/pages/Enterprise/RiskManagementTab.tsx` | 并行加载 floors、add-zone 分支、编辑楼层、详情面板 | 修改 |
| `frontend/e2e/risk-hierarchy-tree.spec.ts` | 多楼层树 E2E | 创建 |
| `docs/superpowers/specs/2026-08-06-risk-tree-floor-grouping-design.md` | 修正接口函数名（listFloors -> listEnterpriseFloors） | 修改 |
| `TASKS.md` | 快照收尾 | 修改 |

设计边界：分组逻辑（`riskTreeGrouping.ts`）与渲染（`RiskHierarchyTree.tsx`）分离，前者可纯函数单测，与仓库现有"纯逻辑单测、组件由 E2E 覆盖"的模式一致。

---

### 任务 1：后端楼层排序纯函数（TDD）

**文件：**
- 修改：`backend/app/routers/risk_management.py`（在 `# ── Hierarchy ──` 注释后、`get_hierarchy` 前新增函数，约 line 690）
- 测试：`backend/tests/test_risk_hierarchy.py`（创建）

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_risk_hierarchy.py`：

```python
from types import SimpleNamespace

from app.routers.risk_management import sort_zones_by_floor


def _zone(floor_id, sort_order, name):
    return SimpleNamespace(id=name, floor_id=floor_id, sort_order=sort_order)


def test_sort_zones_by_floor_orders_by_floor_then_zone():
    zones = [
        _zone("f2", 1, "z2-1"),
        _zone("f1", 2, "z1-2"),
        _zone("f1", 0, "z1-0"),
        _zone("f2", 0, "z2-0"),
    ]
    order = {"f1": 0, "f2": 1}
    assert [z.id for z in sort_zones_by_floor(zones, order)] == ["z1-0", "z1-2", "z2-0", "z2-1"]


def test_sort_zones_by_floor_puts_unknown_floor_last():
    zones = [
        _zone(None, 0, "unassigned"),
        _zone("f1", 5, "z1"),
    ]
    order = {"f1": 0}
    assert [z.id for z in sort_zones_by_floor(zones, order)] == ["z1", "unassigned"]
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd backend; python -m pytest -q tests/test_risk_hierarchy.py -v`

预期：FAIL，`ImportError: cannot import name 'sort_zones_by_floor' from 'app.routers.risk_management'`

- [ ] **步骤 3：编写最少实现代码**

在 `backend/app/routers/risk_management.py` 的 `# ── Hierarchy ──` 之后插入：

```python
def sort_zones_by_floor(zones: list, floor_order: dict[str, int]) -> list:
    """按（楼层顺序，分区 sort_order）排序；未知/空楼层排最后。

    floor_order 由 enterprise_floors.sort_order 生成：{floor_id: index}。
    纯函数，便于单元测试。
    """
    fallback = len(floor_order)
    return sorted(zones, key=lambda z: (floor_order.get(z.floor_id, fallback), z.sort_order))
```

- [ ] **步骤 4：运行测试确认通过**

运行：`cd backend; python -m pytest -q tests/test_risk_hierarchy.py -v`

预期：PASS，2 passed

- [ ] **步骤 5：Commit**

```bash
cd C:\Users\55061\Documents\数字化预案自动生成 2
git add backend/app/routers/risk_management.py backend/tests/test_risk_hierarchy.py
git commit -m "feat(risk-management): add floor-aware zone sorting helper"
```

---

### 任务 2：后端 `/hierarchy` 返回全部楼层分区

**文件：**
- 修改：`backend/app/routers/risk_management.py:691-714`（`get_hierarchy` 整体替换）

- [ ] **步骤 1：替换 `get_hierarchy` 实现**

将 `@router.get("/hierarchy", ...)` 整个函数（现 line 691-714）替换为：

```python
@router.get("/hierarchy", response_model=ApiResponse[list[HierarchyZoneResponse]])
async def get_hierarchy(enterprise_id: str, floor_id: str | None = Query(None), current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    floors = (await db.execute(
        select(EnterpriseFloor).where(EnterpriseFloor.enterprise_id == enterprise_id).order_by(EnterpriseFloor.sort_order)
    )).scalars().all()
    floor_order = {f.id: i for i, f in enumerate(floors)}
    if floor_id:
        floor = next((f for f in floors if f.id == floor_id), None)
        if not floor:
            raise HTTPException(404, "楼层不存在")
        zones = (await db.execute(
            select(RiskZone).where(RiskZone.enterprise_id == enterprise_id, RiskZone.floor_id == floor_id)
            .options(
                selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures),
                selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures),
            )
            .order_by(RiskZone.sort_order)
        )).scalars().all()
    else:
        zones = (await db.execute(
            select(RiskZone).where(RiskZone.enterprise_id == enterprise_id)
            .options(
                selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures),
                selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures),
            )
        )).scalars().all()
        zones = sort_zones_by_floor(zones, floor_order)
    floors_by_id = {f.id: f for f in floors}
    out = []
    for z in zones:
        resp = HierarchyZoneResponse.model_validate(z)
        f = floors_by_id.get(z.floor_id)
        resp.floor_name = f.name if f else None
        normalized = normalize_polygon(z.floor_plan_polygon, z.name)
        resp.floor_plan_polygon = RiskZoneFloorPlanPolygon.model_validate(normalized) if normalized else None
        resp.max_risk_level = max_risk_level(z)
        resp.effective_color = effective_color(resp.floor_plan_polygon, resp.max_risk_level)
        out.append(resp)
    return ApiResponse(data=out)
```

行为说明（写进 commit message 或 PR 描述）：不传 `floor_id` 时不再隐式创建/限定默认楼层，改为返回全部楼层分区并排序；传 `floor_id` 时行为与原实现等价（楼层校验 + 单楼层过滤）。`floor_id` 为 null 的旧分区也会返回，`floor_name` 为 null，由前端归入「未分配楼层」。

- [ ] **步骤 2：运行后端全量回归**

运行：`cd backend; python -m pytest -q --ignore tests/test_autofill_research.py --ignore _docker_test.py`

预期：PASS（原 67 用例全通过；新增 2 个用例在任务 1 已通过）

- [ ] **步骤 3：Commit**

```bash
git add backend/app/routers/risk_management.py
git commit -m "feat(risk-management): return zones across all floors from hierarchy endpoint"
```

---

### 任务 3：`buildZonePayload` 透传 `floor_id`（TDD）

**文件：**
- 修改：`frontend/src/utils/zoneSubmit.ts`
- 测试：`frontend/src/utils/zoneSubmit.test.ts`

- [ ] **步骤 1：编写失败的测试**

在 `frontend/src/utils/zoneSubmit.test.ts` 的 `describe("buildZonePayload")` 内追加：

```ts
  it("includes floor_id when the zone form carries a floor", () => {
    const payload = buildZonePayload({ name: "储罐区", floor_id: "floor-2" });

    expect(payload.floor_id).toBe("floor-2");
  });

  it("omits floor_id when undefined, so edits never clear an existing floor", () => {
    const payload = buildZonePayload({ name: "储罐区" });

    expect(payload).not.toHaveProperty("floor_id");
  });
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd frontend; npx vitest run src/utils/zoneSubmit.test.ts`

预期：FAIL（新用例 `payload.floor_id` 为 undefined）

- [ ] **步骤 3：编写最少实现代码**

`frontend/src/utils/zoneSubmit.ts` 修改为：

```ts
export interface ZoneSubmitValues {
  name?: string;
  description?: string;
  floor_plan_polygon?: RiskZoneFloorPlanPolygon | null;
  floor_id?: string | null;
}

export function buildZonePayload(
  values: ZoneSubmitValues
): Pick<RiskZoneCreate, "name" | "description" | "floor_plan_polygon" | "floor_id"> {
  const payload: Pick<RiskZoneCreate, "name" | "description" | "floor_plan_polygon" | "floor_id"> = {
    name: values.name || "",
    description: values.description || "",
  };
  if (values.floor_plan_polygon) {
    payload.floor_plan_polygon = values.floor_plan_polygon;
  }
  if (values.floor_id) {
    payload.floor_id = values.floor_id;
  }
  return payload;
}
```

- [ ] **步骤 4：运行测试确认通过**

运行：`cd frontend; npx vitest run src/utils/zoneSubmit.test.ts`

预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/utils/zoneSubmit.ts frontend/src/utils/zoneSubmit.test.ts
git commit -m "feat(risk-management): pass floor_id through zone submit payload"
```

---

### 任务 4：楼层分组纯函数（TDD）

**文件：**
- 创建：`frontend/src/utils/riskTreeGrouping.ts`
- 测试：`frontend/src/utils/riskTreeGrouping.test.ts`

- [ ] **步骤 1：编写失败的测试**

创建 `frontend/src/utils/riskTreeGrouping.test.ts`：

```ts
import { describe, it, expect } from "vitest";
import { groupZonesByFloor } from "./riskTreeGrouping";
import type { HierarchyZone } from "@/types/riskManagement";
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";

function zone(id: string, floorId: string | null): HierarchyZone {
  return {
    id,
    name: `分区-${id}`,
    description: null,
    floor_id: floorId,
    floor_name: floorId ? `楼层-${floorId}` : null,
    floor_plan_polygon: null,
    objects: [],
  };
}

function floor(id: string, name: string, isDefault = false): EnterpriseFloor {
  return {
    id,
    enterprise_id: "e1",
    name,
    sort_order: 0,
    floor_plan_url: null,
    canvas_texts: [],
    is_default: isDefault,
    zone_count: 0,
    risk_point_count: 0,
    updated_at: "2026-08-06T00:00:00+08:00",
  };
}

describe("groupZonesByFloor", () => {
  it("groups zones by floor in floor sort order", () => {
    const floors = [floor("f2", "二层"), floor("f1", "一层", true)];
    const groups = groupZonesByFloor([zone("a", "f1"), zone("b", "f2"), zone("c", "f1")], floors);

    expect(groups.map((g) => g.floorId)).toEqual(["f1", "f2"]);
    expect(groups[0].zones.map((z) => z.id)).toEqual(["a", "c"]);
    expect(groups[1].zones.map((z) => z.id)).toEqual(["b"]);
    expect(groups[0].isDefault).toBe(true);
  });

  it("collects null or unknown floor zones into a trailing unassigned group", () => {
    const floors = [floor("f1", "一层")];
    const groups = groupZonesByFloor([zone("x", null), zone("y", "ghost")], floors);

    expect(groups).toHaveLength(1);
    expect(groups[0].floorName).toBe("未分配楼层");
    expect(groups[0].zones.map((z) => z.id)).toEqual(["x", "y"]);
  });

  it("hides floors that have no zones", () => {
    const floors = [floor("f1", "一层", true), floor("f2", "二层")];
    const groups = groupZonesByFloor([zone("a", "f1")], floors);

    expect(groups.map((g) => g.floorId)).toEqual(["f1"]);
  });
});
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts`

预期：FAIL，模块不存在

- [ ] **步骤 3：编写实现代码**

创建 `frontend/src/utils/riskTreeGrouping.ts`：

```ts
import type { HierarchyZone } from "@/types/riskManagement";
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";

export interface FloorZoneGroup {
  floorId: string | null;
  floorName: string;
  isDefault: boolean;
  zoneCount: number;
  riskPointCount: number;
  zones: HierarchyZone[];
}

const UNASSIGNED_NAME = "未分配楼层";

export function groupZonesByFloor(
  zones: HierarchyZone[],
  floors: EnterpriseFloor[]
): FloorZoneGroup[] {
  const floorOrder = new Map(floors.map((f, i) => [f.id, i]));
  const groups: FloorZoneGroup[] = floors.map((f) => ({
    floorId: f.id,
    floorName: f.name,
    isDefault: f.is_default,
    zoneCount: 0,
    riskPointCount: f.risk_point_count ?? 0,
    zones: [],
  }));
  const unassigned: FloorZoneGroup = {
    floorId: null,
    floorName: UNASSIGNED_NAME,
    isDefault: false,
    zoneCount: 0,
    riskPointCount: 0,
    zones: [],
  };
  for (const z of zones) {
    const idx = z.floor_id != null ? floorOrder.get(z.floor_id) : undefined;
    if (idx === undefined) {
      unassigned.zones.push(z);
    } else {
      groups[idx].zones.push(z);
    }
  }
  const withZones = groups.filter((g) => g.zones.length > 0);
  for (const g of withZones) {
    g.zoneCount = g.zones.length;
  }
  return unassigned.zones.length > 0 ? [...withZones, unassigned] : withZones;
}
```

- [ ] **步骤 4：运行测试确认通过**

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts`

预期：PASS，3 passed

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/utils/riskTreeGrouping.ts frontend/src/utils/riskTreeGrouping.test.ts
git commit -m "feat(risk-management): add floor grouping helper for hierarchy tree"
```

---

### 任务 5：`RiskHierarchyTree` 渲染楼层节点

**文件：**
- 修改：`frontend/src/components/enterprise/RiskHierarchyTree.tsx`

- [ ] **步骤 1：更新导入与类型**

```tsx
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";
import { groupZonesByFloor } from "@/utils/riskTreeGrouping";

export interface TreeNodeMeta {
  id: string;
  type: "floor" | "zone" | "object" | "unit" | "event" | "measure";
  name: string;
  floor_plan_polygon?: RiskZoneFloorPlanPolygon | null;
  parentId?: string;
  parentType?: "zone" | "object" | "unit" | "event";
  floorId?: string | null;
  floorName?: string | null;
}

interface Props {
  data: HierarchyZone[];
  floors?: EnterpriseFloor[];
  onSelect: (node: TreeNodeMeta) => void;
  onRefresh?: () => void;
  onAction: (action: string, meta: TreeNodeMeta) => void;
}
```

- [ ] **步骤 2：扩展 EMOJI 与 ACTION_ITEMS、TitleRow**

```tsx
const EMOJI: Record<TreeNodeMeta["type"], string> = {
  floor: "\u{1F3E2}", // 🏢
  zone: "\u{1F3ED}",
  object: "\u{1F4E6}",
  unit: "\u2699\uFE0F",
  event: "\u26A0\uFE0F",
  measure: "\u{1F6E1}\uFE0F",
};

const ACTION_ITEMS: Record<TreeNodeMeta["type"], { key: string; label: string; icon: React.ReactNode }[]> = {
  floor: [{ key: "add-zone", label: "添加分区", icon: <PlusOutlined /> }],
  zone: [/* 原内容不变 */],
  object: [/* 原内容不变 */],
  unit: [/* 原内容不变 */],
  event: [/* 原内容不变 */],
  measure: [/* 原内容不变 */],
};
```

`TitleRow` 增加可选 props，并在名称后渲染楼层信息：

```tsx
function TitleRow({
  meta,
  riskLevel,
  childCount,
  isRiskPoint,
  isDefaultFloor,
  zoneCount,
  riskPointCount,
  disableActions,
  onAction,
}: {
  meta: TreeNodeMeta;
  riskLevel?: string | null;
  childCount: number;
  isRiskPoint?: boolean;
  isDefaultFloor?: boolean;
  zoneCount?: number;
  riskPointCount?: number;
  disableActions?: boolean;
  onAction: (key: string, meta: TreeNodeMeta) => void;
}) {
  const actions = disableActions ? [] : ACTION_ITEMS[meta.type];

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, width: "100%", minWidth: 0, overflow: "hidden", lineHeight: "28px" }}>
      <span style={{ flexShrink: 0 }}>
        {isRiskPoint && <span style={{ color: "#ff4d4f", marginRight: 2 }}>{"\u25C6"}</span>}
        {EMOJI[meta.type]}
      </span>
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, minWidth: 0 }}>
        {meta.name}
      </span>
      {isDefaultFloor && (
        <Tag color="blue" style={{ margin: 0, fontSize: 11, lineHeight: "18px" }}>
          默认
        </Tag>
      )}
      {typeof zoneCount === "number" && (
        <span style={{ fontSize: 11, color: "#8c8c8c", background: "#f5f5f5", borderRadius: 10, padding: "0 6px", lineHeight: "20px", flexShrink: 0 }}>
          {zoneCount} 分区 · {riskPointCount ?? 0} 风险点
        </span>
      )}
      {riskLevel && (
        <Tag color={RISK_LEVEL_COLORS[riskLevel] || "#d9d9d9"} style={{ margin: 0, fontSize: 11, lineHeight: "18px" }}>
          {riskLevel}
        </Tag>
      )}
      {childCount > 0 && (
        <span style={{ fontSize: 11, color: "#8c8c8c", background: "#f5f5f5", borderRadius: 10, padding: "0 6px", lineHeight: "20px", flexShrink: 0 }}>
          {childCount}
        </span>
      )}
      {actions.length > 0 && (
        <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 2, flexShrink: 0, paddingLeft: 8 }}>
          {actions.map((action) => (
            <Tooltip key={action.key} title={action.label}>
              <Button type="text" size="small" icon={action.icon} aria-label={action.label}
                onClick={(event) => { event.stopPropagation(); onAction(action.key, meta); }}
                style={{ color: action.key === "delete" ? "#ff4d4f" : "#1677ff" }} />
            </Tooltip>
          ))}
        </span>
      )}
    </span>
  );
}
```

注意：`ACTION_ITEMS` 中 zone/object/unit/event/measure 保持原内容逐字不变，只新增 floor 键。

- [ ] **步骤 3：替换 `buildTreeData` 并新增计数函数**

新增（放在 `buildTreeData` 之前）：

```tsx
function countZoneTree(zones: HierarchyZone[]): number {
  return zones.reduce(
    (acc, z) =>
      acc +
      1 +
      (z.objects || []).reduce(
        (oa, o) =>
          oa +
          1 +
          (o.units || []).reduce(
            (ua, u) =>
              ua +
              1 +
              (u.events || []).reduce(
                (ea, ev) => ea + 1 + (ev.measures || []).length,
                0
              ),
            0
          ) +
          (o.events || []).reduce(
            (ea, ev) => ea + 1 + (ev.measures || []).length,
            0
          ),
        0
      ),
    0
  );
}
```

将 `buildTreeData` 的签名与返回段替换为（内部 `measuresToNodes/eventsToNodes/unitsToNodes/objectsToNodes` 四个辅助函数保持不变）：

```tsx
function buildTreeData(zones: HierarchyZone[], floors: EnterpriseFloor[]): DataNode[] {
  const groups = groupZonesByFloor(zones, floors);
  return groups.map((g) => {
    const childNodes = g.zones.map((z) => {
      const objectNodes = objectsToNodes(z.objects || [], z.id);
      return {
        key: "zone-" + z.id,
        title: "",
        children: objectNodes.length > 0 ? objectNodes : undefined,
        isLeaf: objectNodes.length === 0,
        _meta: {
          id: z.id,
          type: "zone" as const,
          name: z.name,
          floor_plan_polygon: z.floor_plan_polygon,
          floorId: z.floor_id,
          floorName: z.floor_name,
        },
        _riskLevel: null,
        _childCount: objectNodes.length,
      };
    });
    return {
      key: g.floorId ? `floor-${g.floorId}` : "floor-unassigned",
      title: "",
      children: childNodes,
      isLeaf: childNodes.length === 0,
      _meta: {
        id: g.floorId ?? "unassigned",
        type: "floor" as const,
        name: g.floorName,
        floorId: g.floorId,
        floorName: g.floorName,
      },
      _riskLevel: null,
      _childCount: childNodes.length,
      _floorInfo: {
        isDefault: g.isDefault,
        zoneCount: g.zoneCount,
        riskPointCount: g.riskPointCount,
      },
      _disableActions: g.floorId === null,
    };
  });
}
```

- [ ] **步骤 4：更新 totalNodes / 展开策略 / titleRender / Tree props**

```tsx
export default function RiskHierarchyTree({ data, floors, onSelect, onAction }: Props) {
  const treeData = useMemo(() => buildTreeData(data, floors ?? []), [data, floors]);
  const totalNodes = useMemo(() => {
    const groups = groupZonesByFloor(data, floors ?? []);
    return groups.reduce((acc, g) => acc + 1 + countZoneTree(g.zones), 0);
  }, [data, floors]);
  const multiFloor = useMemo(() => groupZonesByFloor(data, floors ?? []).length > 1, [data, floors]);
  const defaultExpandedKeys = useMemo(() => {
    if (!multiFloor) return undefined;
    const defaultFloor = floors?.find((f) => f.is_default);
    if (!defaultFloor) return undefined;
    return [`floor-${defaultFloor.id}`];
  }, [multiFloor, floors]);
```

`titleRender` 读取并透传楼层信息：

```tsx
  const titleRender = useCallback(
    (nodeData: DataNode) => {
      const n = nodeData as DataNode & {
        _meta?: TreeNodeMeta;
        _riskLevel?: string | null;
        _childCount?: number;
        _isRiskPoint?: boolean;
        _floorInfo?: { isDefault: boolean; zoneCount: number; riskPointCount: number };
        _disableActions?: boolean;
      };
      if (!n._meta) return <span>{String(nodeData.title)}</span>;
      return (
        <TitleRow
          meta={n._meta}
          riskLevel={n._riskLevel}
          childCount={n._childCount ?? 0}
          isRiskPoint={n._isRiskPoint}
          isDefaultFloor={n._floorInfo?.isDefault}
          zoneCount={n._floorInfo?.zoneCount}
          riskPointCount={n._floorInfo?.riskPointCount}
          disableActions={n._disableActions}
          onAction={handleAction}
        />
      );
    },
    [handleAction]
  );
```

Tree 组件 props 调整：

```tsx
  return (
    <Tree
      treeData={treeData}
      titleRender={titleRender}
      onSelect={handleSelect}
      showLine={{ showLeafIcon: false }}
      blockNode
      defaultExpandAll={totalNodes < 100 && !multiFloor}
      defaultExpandedKeys={defaultExpandedKeys}
      virtual={totalNodes > 200}
      height={totalNodes > 200 ? 600 : undefined}
      style={{ background: "transparent", fontSize: 13 }}
    />
  );
```

- [ ] **步骤 5：类型与单测回归**

运行：`cd frontend; npx tsc -b`
预期：exit 0

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts src/utils/zoneSubmit.test.ts`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/components/enterprise/RiskHierarchyTree.tsx
git commit -m "feat(risk-management): render floor nodes in hierarchy tree"
```

---

### 任务 6：`RiskZoneForm` 楼层选择 + 标注底图联动

**文件：**
- 修改：`frontend/src/components/enterprise/RiskZoneForm.tsx`

- [ ] **步骤 1：导入与类型**

```tsx
import { Select } from "antd";
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";

interface RiskZoneFormValues {
  name: string;
  description?: string;
  floor_id?: string | null;
  floor_plan_polygon?: { version: 2; color_source: "auto" | "manual"; color: string | null; polygons: { id: string; label?: string; points: PolygonPoint[] }[] };
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (values: RiskZoneFormValues) => void;
  initialValues?: RiskZoneFormValues;
  floorPlanUrl?: string | null;
  floors?: EnterpriseFloor[];
}

export default function RiskZoneForm({ open, onClose, onSubmit, initialValues, floorPlanUrl, floors }: Props) {
  const [form] = Form.useForm<RiskZoneFormValues>();
  const defaultFloorId = floors?.find((f) => f.is_default)?.id;
  const selectedFloorId = Form.useWatch("floor_id", form);
  const activeFloor = floors?.find((f) => f.id === selectedFloorId);
  const planUrl = activeFloor?.floor_plan_url ?? floorPlanUrl;
```

- [ ] **步骤 2：Form initialValues 合并默认楼层 + 增加楼层 Select**

```tsx
        <Form
          form={form}
          layout="vertical"
          initialValues={{ ...initialValues, floor_id: initialValues?.floor_id ?? defaultFloorId }}
          onFinish={handleFinish}
        >
```

在「描述说明」Form.Item 之后、「平面图标注」之前插入：

```tsx
          {floors && floors.length > 0 && (
            <Form.Item name="floor_id" label="所属楼层">
              <Select
                options={floors.map((f) => ({ value: f.id, label: `${f.name}${f.is_default ? "（默认）" : ""}` }))}
                placeholder="请选择楼层"
              />
            </Form.Item>
          )}
```

- [ ] **步骤 3：渲染处改用 `planUrl`**

将函数体内所有 `floorPlanUrl` 引用替换为 `planUrl`，共 3 处：
1. `{floorPlanUrl ? ( <Button ...>在平面图上标注</Button> ... ) : (...未上传平面图...)}`
2. `{!floorPlanUrl ? (<div ...>未上传平面图</div>) : (...)}`
3. `<img ref={imgRef} src={floorPlanUrl} alt="厂区平面图" ... />`

`handleFinish` 保持不变（`onSubmit(values)` 已含 `floor_id`）。

- [ ] **步骤 4：类型与单测回归**

运行：`cd frontend; npx tsc -b`
预期：exit 0

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts src/utils/zoneSubmit.test.ts`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/enterprise/RiskZoneForm.tsx
git commit -m "feat(risk-management): add floor selector and per-floor plan background to zone form"
```

---

### 任务 7：`RiskManagementTab` 集成

**文件：**
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`

- [ ] **步骤 1：引入 floors 查询并传给树与表单**

```tsx
import { listEnterpriseFloors } from "@/services/riskMappingWorkbenchService";
```

在 `hierarchy` useQuery 之后新增：

```tsx
  const { data: floors = [] } = useQuery({
    queryKey: ["enterprise-floors", enterpriseId],
    queryFn: () => listEnterpriseFloors(enterpriseId),
  });
```

（`EnterpriseDetailPage` 使用相同 queryKey，react-query 会自动去重，不产生重复请求。）

树渲染处（现 line 250）：

```tsx
        {hierarchy.length === 0 ? <Empty description="暂无数据，请添加风险分区" /> : <RiskHierarchyTree data={hierarchy} floors={floors} onSelect={setSelectedNode} onRefresh={refetch} onAction={handleTreeAction} />}
```

表单渲染处（现 line 278）：

```tsx
      {form.type === "zone" && <RiskZoneForm key={`zone-${form.id || "new"}`} open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} initialValues={form.initialValues} floorPlanUrl={floorPlanUrl || undefined} floors={floors} />}
```

- [ ] **步骤 2：`handleTreeAction` 增加楼层节点 add-zone 分支**

替换现 `case "add-zone":`（line 123-125）：

```tsx
      case "add-zone":
        setForm({
          type: "zone",
          open: true,
          parentId: meta.id,
          initialValues: meta.floorId ? { name: "", floor_id: meta.floorId } : undefined,
        });
        break;
```

编辑分区时预填楼层（两处等价分支 `case "edit":` 与 `case "edit-zone":` 内的 zone initialValues 都改为）：

```tsx
            meta.type === "zone"
              ? { name: meta.name, floor_plan_polygon: meta.floor_plan_polygon ?? undefined, floor_id: meta.floorId ?? undefined }
              : meta.type === "object"
                ? { name: meta.name, zone_id: meta.parentId }
                : meta.type === "unit"
                  ? { name: meta.name }
                  : meta.type === "event"
                    ? { accident_type: meta.name }
                    : { description: meta.name },
```

- [ ] **步骤 3：详情面板支持楼层节点**

将右侧详情面板的 `{selectedNode ? (() => {...})() : ...}` 改为：

```tsx
        {selectedNode ? (() => {
          if (selectedNode.type === "floor") {
            const f = floors.find((x) => x.id === selectedNode.id);
            return (
              <div style={{ fontSize: 13, lineHeight: 1.8 }}>
                <p><strong>{selectedNode.name}</strong></p>
                {f?.is_default && <p><Tag color="blue">默认楼层</Tag></p>}
                <p>分区数：{f?.zone_count ?? 0}</p>
                <p>风险点数：{f?.risk_point_count ?? 0}</p>
              </div>
            );
          }
          const info = hierarchyMap[selectedNode.id] || {};
          return (/* 原内容逐字不变 */);
        })() : <p style={{ color: "#8c8c8c", fontSize: 13 }}>点击层级树中的节点查看详情</p>}
```

- [ ] **步骤 4：类型与回归**

运行：`cd frontend; npx tsc -b`
预期：exit 0

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts src/utils/zoneSubmit.test.ts`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskManagementTab.tsx
git commit -m "feat(risk-management): wire floors into risk management tab"
```

---

### 任务 8：多楼层树 E2E

**文件：**
- 创建：`frontend/e2e/risk-hierarchy-tree.spec.ts`

- [ ] **步骤 1：创建 E2E 文件（完整内容）**

```ts
import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * 风险分级管控分区树楼层分组 E2E
 * - 全部 API 使用 Playwright 路由 mock，可脱离后端独立运行；
 * - baseURL 默认由 playwright.config.ts 提供（webServer 自动拉起 http://localhost:5174）。
 */

const ENTERPRISE_ID = "e2e-risk-tree-enterprise";

const FLOOR_1 = {
  id: "floor-1",
  enterprise_id: ENTERPRISE_ID,
  name: "一层",
  sort_order: 0,
  floor_plan_url: null,
  description: null,
  canvas_width: 1200,
  canvas_height: 900,
  canvas_texts: [],
  is_default: true,
  zone_count: 1,
  risk_point_count: 1,
  created_at: "2026-08-05T00:00:00+08:00",
  updated_at: "2026-08-05T00:00:00+08:00",
};

const FLOOR_2 = {
  ...FLOOR_1,
  id: "floor-2",
  name: "二层",
  sort_order: 1,
  is_default: false,
  zone_count: 1,
  risk_point_count: 0,
};

const HIERARCHY = {
  code: 0,
  message: "ok",
  data: [
    {
      id: "zone-1",
      floor_id: "floor-1",
      floor_name: "一层",
      name: "危险品储存区",
      description: null,
      floor_plan_polygon: null,
      max_risk_level: null,
      effective_color: null,
      objects: [],
    },
    {
      id: "zone-2",
      floor_id: "floor-2",
      floor_name: "二层",
      name: "二层办公区",
      description: null,
      floor_plan_polygon: null,
      max_risk_level: null,
      effective_color: null,
      objects: [],
    },
  ],
};

const ENTERPRISE = {
  id: ENTERPRISE_ID,
  name: "E2E 多层企业",
  address: null,
  industry: null,
  business_scope: null,
  building_overview: null,
  hazardous_chemicals: null,
  special_equipment: null,
  org_structure: [],
  surrounding_info: {},
  risk_sources_count: 0,
  resources_count: 0,
  floor_plan_url: null,
  created_at: "2026-08-05T00:00:00+08:00",
  updated_at: "2026-08-05T00:00:00+08:00",
};

const USER = {
  id: "e2e-user-id",
  email: "qa_e2e_test@test.com",
  name: "E2E 测试用户",
  role: "admin",
  created_at: "2026-08-05T00:00:00+08:00",
};

const TOKEN_RESPONSE = {
  code: 0,
  message: "ok",
  data: {
    access_token: "e2e-mock-token",
    refresh_token: "e2e-mock-refresh",
    token_type: "bearer",
    expires_in: 7200,
  },
};

async function mockApis(page: Page, onZoneCreate?: (payload: unknown) => void) {
  const json = (status: number, body: unknown) => ({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === "/api/v1/auth/login" && method === "POST") {
      await route.fulfill(json(200, TOKEN_RESPONSE));
      return;
    }
    if (path === "/api/v1/users/me" && method === "GET") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: USER }));
      return;
    }
    if (path === "/api/v1/roles/my-menus" && method === "GET") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: [] }));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}` && method === "GET") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: ENTERPRISE }));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/floors` && method === "GET") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: [FLOOR_1, FLOOR_2] }));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/hierarchy` && method === "GET") {
      await route.fulfill(json(200, HIERARCHY));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/zones` && method === "POST") {
      onZoneCreate?.(request.postDataJSON());
      await route.fulfill(json(200, { code: 0, message: "ok", data: { id: "new-zone-1" } }));
      return;
    }
    await route.fulfill(json(404, { code: 404, message: "not found", data: null }));
  });
}

test("层级树按楼层分组且跨楼层分区可见", async ({ page }) => {
  await mockApis(page);
  await page.goto(`/enterprises/${ENTERPRISE_ID}`);
  await page.getByRole("tab", { name: "风险分级管控" }).click();

  await expect(page.locator(".ant-tree")).toContainText("一层");
  await expect(page.locator(".ant-tree")).toContainText("二层");
  await expect(page.locator(".ant-tree")).toContainText("默认");
  // 默认楼层分区直接可见
  await expect(page.locator(".ant-tree")).toContainText("危险品储存区");
  // 展开二层楼层节点后，二层分区可见
  await page.locator(".ant-tree").getByText("二层", { exact: true }).click();
  await expect(page.locator(".ant-tree")).toContainText("二层办公区");
});

test("从楼层节点添加分区时 payload 携带目标楼层", async ({ page }) => {
  let createdZonePayload: unknown = null;
  await mockApis(page, (payload) => { createdZonePayload = payload; });
  await page.goto(`/enterprises/${ENTERPRISE_ID}`);
  await page.getByRole("tab", { name: "风险分级管控" }).click();

  // 树内第二个「添加分区」= 二层楼层节点操作
  await page.locator(".ant-tree").getByRole("button", { name: "添加分区" }).nth(1).click();
  await expect(page.locator(".ant-select-selection-item")).toHaveText("二层");

  await page.getByLabel("分区名称").fill("二层新增分区");
  await page.getByRole("button", { name: "保存" }).click();

  await expect.poll(() => createdZonePayload).toBeTruthy();
  expect(createdZonePayload).toMatchObject({ name: "二层新增分区", floor_id: "floor-2" });
});
```

- [ ] **步骤 2：运行 E2E 确认通过**

运行：`cd frontend; npx playwright test e2e/risk-hierarchy-tree.spec.ts`

预期：PASS，2 passed

若「保存」按钮选择器不稳定，改用 antd Drawer 内的 `page.locator(".ant-drawer").getByRole("button", { name: "保存" })`。

- [ ] **步骤 3：Commit**

```bash
git add frontend/e2e/risk-hierarchy-tree.spec.ts
git commit -m "test(risk-management): add multi-floor hierarchy tree e2e"
```

---

### 任务 9：全量验证 + 文档与 TASKS 收尾

**文件：**
- 修改：`docs/superpowers/specs/2026-08-06-risk-tree-floor-grouping-design.md`（函数名修正）
- 修改：`TASKS.md`

- [ ] **步骤 1：修正规格文档接口函数名**

`docs/superpowers/specs/2026-08-06-risk-tree-floor-grouping-design.md` 中两处「listFloors」替换为「listEnterpriseFloors」：
- 1.4 已确认决策表「楼层数据源」行
- 2.1 现有基础第 3 条

（实际导出名为 `listEnterpriseFloors`，见 `frontend/src/services/riskMappingWorkbenchService.ts`。）

- [ ] **步骤 2：运行全量验证**

```bash
cd backend; python -m pytest -q --ignore tests/test_autofill_research.py --ignore _docker_test.py
cd frontend; npx tsc -b
cd frontend; npx vitest run
cd frontend; npx playwright test e2e/risk-hierarchy-tree.spec.ts e2e/risk-mapping-workbench.spec.ts
cd frontend; npx -y node@22 node_modules/vite/bin/vite.js build
```

预期：后端全通过；tsc exit 0；vitest 全通过；两个 E2E 文件全通过；生产构建成功。

- [ ] **步骤 3：更新 TASKS.md 快照并提交**

将 TASKS.md「当前状态快照」更新为：功能完成、验证结果（命令与通过数）、可复现命令、未处理事项（用户未提交的 RiskDistributionStage.tsx / chroma.sqlite3 / backup SQL 保持原样）。

```bash
git add docs/superpowers/specs/2026-08-06-risk-tree-floor-grouping-design.md TASKS.md
git commit -m "chore(risk-management): finalize floor grouping spec api name and task snapshot"
```

---

## 自检结论

**1. 规格覆盖度：** 规格 1.4 决策表逐项对应任务：后端多楼层返回（任务 2）、楼层节点与展开策略（任务 5）、未分配兜底（任务 4/5）、buildZonePayload 透传（任务 3）、表单楼层 Select 与底图跟随（任务 6）、编辑迁移楼层（任务 6/7，后端复用既有逻辑）、详情面板（任务 7）、测试（任务 1/3/4/8）。规格 5 边界场景（无楼层、楼层删除、移动楼层）由任务 4 兜底分组与既有后端逻辑覆盖。

**2. 占位符扫描：** 无「待定/TODO/后续实现」；每个代码步骤均含完整代码；E2E 选择器给出回退方案。

**3. 类型一致性：** 统一使用 `listEnterpriseFloors`、`groupZonesByFloor`、`FloorZoneGroup`、`floor_id`；树节点 key 统一 `floor-{id}` / `floor-unassigned`；`TreeNodeMeta` 新增 `floorId/floorName` 字段跨任务 5/7 一致。
