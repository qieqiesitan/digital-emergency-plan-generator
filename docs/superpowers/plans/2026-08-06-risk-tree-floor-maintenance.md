# 风险管控树楼层维护与空楼层显示 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让风险分级管控树显示全部楼层（含空楼层），并在树区域提供楼层维护抽屉（添加/重命名/设为默认/删除），与工作台楼层数据双向联动。

**架构：** `groupZonesByFloor` 改为返回全部楼层分组（空楼层 zoneCount=0）；新建 `FloorManagementDrawer` 抽屉组件复用后端楼层 CRUD；`RiskManagementTab` 工具栏加「楼层管理」入口；工作台 `EnterpriseFloorManager.refresh` 补一行跨键失效实现双向联动。

**技术栈：** React + antd（Drawer/List/Modal/Popconfirm）+ TanStack Query（frontend）；FastAPI 楼层 CRUD 已完备（backend，仅复用不改）。

---

## 前置说明（仓库约定，每个改动任务开始前都要遵守）

- 当前分支 `codex/risk-tree-floor-maintenance`，从 master 切出；直接在此分支提交，不要 rebase/reset/pull/merge。
- 每个改动任务开始前，按 AGENTS.md 铁律二执行本地保存点（`git save`；无 alias 则记录跳过）并检查调用者/影响面（`codegraph callers` / `codegraph impact`，仅对涉及的符号）。
- 工作区存在未跟踪文件 `backup/risk-mapping-pre-migration-20260805.sql`，不得触碰、不得纳入提交。
- 提交信息遵循 Conventional Commits（`feat(risk-management): ...`）。
- 验证命令统一约定：
  - 前端类型：`cd frontend; npx tsc -b`
  - 前端单测：`cd frontend; npx vitest run`
  - E2E：`cd frontend; npx playwright test e2e/risk-hierarchy-tree.spec.ts`
  - 生产构建：`cd frontend; npx -y node@22 node_modules/vite/bin/vite.js build`
  - 后端回归（本迭代不改后端，仅确认）：`cd backend; .\.venv\Scripts\python.exe -m pytest -q --ignore tests/test_autofill_research.py --ignore _docker_test.py`

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `frontend/src/utils/riskTreeGrouping.ts` | 返回全部楼层分组（含空楼层） | 修改 |
| `frontend/src/utils/riskTreeGrouping.test.ts` | 空楼层用例反转 + 未分配兜底保持 | 修改 |
| `frontend/src/components/enterprise/RiskHierarchyTree.tsx` | 空态条件：有楼层即渲染树 | 修改 |
| `frontend/src/components/enterprise/FloorManagementDrawer.tsx` | 楼层管理抽屉（新建） | 创建 |
| `frontend/src/pages/Enterprise/RiskManagementTab.tsx` | 工具栏「楼层管理」+ 抽屉挂载 | 修改 |
| `frontend/src/components/enterprise/EnterpriseFloorManager.tsx` | `refresh()` 补 invalidate `enterprise-floors` | 修改 |
| `frontend/e2e/risk-hierarchy-tree.spec.ts` | 新增 2 用例（空楼层显示 / 抽屉添加楼层） | 修改 |
| `TASKS.md` | 快照收尾 | 修改 |

设计边界：抽屉组件与树渲染解耦（`FloorManagementDrawer` 只管楼层维护与刷新，树由 `RiskManagementTab` 的 `refetch` 联动），延续仓库"纯逻辑单测 + 组件 E2E"模式。

---

### 任务 1：树显示全部楼层（含空楼层）（TDD）

**文件：**
- 修改：`frontend/src/utils/riskTreeGrouping.ts`
- 测试：`frontend/src/utils/riskTreeGrouping.test.ts`
- 修改：`frontend/src/components/enterprise/RiskHierarchyTree.tsx`

- [ ] **步骤 1：反转空楼层单测**

将 `frontend/src/utils/riskTreeGrouping.test.ts` 中的：

```ts
  it("hides floors that have no zones", () => {
    const floors = [floor("f1", "一层", true), floor("f2", "二层")];
    const groups = groupZonesByFloor([zone("a", "f1")], floors);

    expect(groups.map((g) => g.floorId)).toEqual(["f1"]);
  });
```

替换为：

```ts
  it("includes floors that have no zones with zero counts", () => {
    const floors = [floor("f1", "一层", true), floor("f2", "二层")];
    const groups = groupZonesByFloor([zone("a", "f1")], floors);

    expect(groups.map((g) => g.floorId)).toEqual(["f1", "f2"]);
    expect(groups[1].zoneCount).toBe(0);
    expect(groups[1].zones).toHaveLength(0);
  });
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts`

预期：FAIL（实际返回 `["f1"]`，期望 `["f1", "f2"]`）

- [ ] **步骤 3：修改 `groupZonesByFloor`**

将 `frontend/src/utils/riskTreeGrouping.ts` 尾部：

```ts
  const withZones = groups.filter((g) => g.zones.length > 0);
  for (const g of withZones) {
    g.zoneCount = g.zones.length;
  }
  return unassigned.zones.length > 0 ? [...withZones, unassigned] : withZones;
```

替换为：

```ts
  for (const g of groups) {
    g.zoneCount = g.zones.length;
  }
  return unassigned.zones.length > 0 ? [...groups, unassigned] : groups;
```

- [ ] **步骤 4：运行测试确认通过**

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts`

预期：PASS，3 passed

- [ ] **步骤 5：调整 `RiskHierarchyTree` 空态条件**

将 `frontend/src/components/enterprise/RiskHierarchyTree.tsx` 中的：

```tsx
  if (!data || data.length === 0) {
```

替换为：

```tsx
  // 有楼层即渲染树（空楼层也可添加分区）；无楼层且无分区才显示空态
  if ((!data || data.length === 0) && (floors?.length ?? 0) === 0) {
```

组件内 `Props` 已含 `floors`，无需其他改动。

- [ ] **步骤 6：类型与单测回归**

运行：`cd frontend; npx tsc -b`（预期 exit 0）

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts src/utils/zoneSubmit.test.ts`（预期 PASS）

- [ ] **步骤 7：Commit**

```bash
git add frontend/src/utils/riskTreeGrouping.ts frontend/src/utils/riskTreeGrouping.test.ts frontend/src/components/enterprise/RiskHierarchyTree.tsx
git commit -m "feat(risk-management): show all floors including empty ones in hierarchy tree"
```

---

### 任务 2：新建 `FloorManagementDrawer` 楼层管理抽屉

**文件：**
- 创建：`frontend/src/components/enterprise/FloorManagementDrawer.tsx`

- [ ] **步骤 1：创建组件（完整内容）**

```tsx
import { useCallback, useState } from "react";
import { App, Button, Drawer, Input, List, Modal, Popconfirm, Space, Tag, Typography } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listEnterpriseFloors,
  createEnterpriseFloor,
  updateEnterpriseFloor,
  deleteEnterpriseFloor,
} from "@/services/riskMappingWorkbenchService";
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";

interface Props {
  enterpriseId: string;
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

const apiErrorMessage = (e: unknown, fallback: string) => {
  const err = e as { response?: { data?: { detail?: unknown } } };
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  const msg = (detail as { message?: string } | undefined)?.message;
  return msg || fallback;
};

export default function FloorManagementDrawer({ enterpriseId, open, onClose, onChanged }: Props) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const { data: floors = [] } = useQuery({
    queryKey: ["enterprise-floors", enterpriseId],
    queryFn: () => listEnterpriseFloors(enterpriseId),
    enabled: open,
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");

  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["enterprise-floors", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["risk-floors", enterpriseId] });
    onChanged?.();
  }, [queryClient, enterpriseId, onChanged]);

  const openCreate = () => {
    setEditId(null);
    setName("");
    setModalOpen(true);
  };

  const openRename = (f: EnterpriseFloor) => {
    setEditId(f.id);
    setName(f.name);
    setModalOpen(true);
  };

  const submit = async () => {
    if (!name.trim()) return;
    try {
      if (editId) {
        await updateEnterpriseFloor(enterpriseId, editId, { name: name.trim() });
      } else {
        await createEnterpriseFloor(enterpriseId, { name: name.trim(), sort_order: floors.length });
      }
      setModalOpen(false);
      setName("");
      setEditId(null);
      refresh();
    } catch (e) {
      message.error(apiErrorMessage(e, "保存楼层失败"));
    }
  };

  const setDefault = async (f: EnterpriseFloor) => {
    if (f.is_default) return;
    try {
      await updateEnterpriseFloor(enterpriseId, f.id, { is_default: true });
      refresh();
    } catch (e) {
      message.error(apiErrorMessage(e, "设置默认楼层失败"));
    }
  };

  const removeFloor = async (f: EnterpriseFloor) => {
    try {
      await deleteEnterpriseFloor(enterpriseId, f.id);
      refresh();
    } catch (e) {
      message.error(apiErrorMessage(e, "删除楼层失败（楼层下存在分区或风险点时不可删除）"));
    }
  };

  return (
    <>
      <Drawer title="楼层管理" open={open} onClose={onClose} width={420}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} block style={{ marginBottom: 12 }}>
          添加楼层
        </Button>
        <List
          dataSource={floors}
          renderItem={(f) => (
            <List.Item
              actions={[
                !f.is_default ? (
                  <Button key="default" type="link" size="small" onClick={() => setDefault(f)}>
                    设为默认
                  </Button>
                ) : null,
                <Button key="rename" type="link" size="small" icon={<EditOutlined />} onClick={() => openRename(f)}>
                  重命名
                </Button>,
                <Popconfirm
                  key="delete"
                  title={`确认删除楼层「${f.name}」？`}
                  description="删除后无法恢复；楼层下存在分区或风险点时后端会拒绝。"
                  onConfirm={() => removeFloor(f)}
                >
                  <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <span>{f.name}</span>
                    {f.is_default && <Tag color="blue">默认</Tag>}
                  </Space>
                }
                description={`${f.zone_count ?? 0} 分区 · ${f.risk_point_count ?? 0} 风险点`}
              />
            </List.Item>
          )}
        />
        <Typography.Text type="secondary" style={{ display: "block", marginTop: 12 }}>
          平面图上传与分区绘制请在「四色分布图工作台」进行。
        </Typography.Text>
      </Drawer>

      <Modal
        title={editId ? "重命名楼层" : "添加楼层"}
        open={modalOpen}
        onOk={submit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="请输入楼层名称，如：三层"
          maxLength={50}
          onPressEnter={submit}
          autoFocus
        />
      </Modal>
    </>
  );
}
```

- [ ] **步骤 2：类型检查**

运行：`cd frontend; npx tsc -b`

预期：exit 0（如 `List.Item actions` 类型报错，确认 actions 内 `null` 项由 `ReactNode` 类型允许；若仍报错则先过滤：`actions={[...].filter(Boolean) as React.ReactNode[]}`）

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/components/enterprise/FloorManagementDrawer.tsx
git commit -m "feat(risk-management): add floor management drawer"
```

---

### 任务 3：`RiskManagementTab` 集成 + 工作台联动

**文件：**
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`
- 修改：`frontend/src/components/enterprise/EnterpriseFloorManager.tsx`

- [ ] **步骤 1：`RiskManagementTab` 导入与状态**

在 import 区追加：

```tsx
import { ApartmentOutlined } from "@ant-design/icons";
import FloorManagementDrawer from "@/components/enterprise/FloorManagementDrawer";
```

在 `const [smartGuideOpen, setSmartGuideOpen] = useState(false);` 之后追加：

```tsx
  const [floorDrawerOpen, setFloorDrawerOpen] = useState(false);
```

- [ ] **步骤 2：工具栏按钮与抽屉挂载**

工具栏（`<Space style={{ marginBottom: 12 }}>` 内，放在「四色分布图工作台」按钮之后）追加：

```tsx
           <Button icon={<ApartmentOutlined />} onClick={() => setFloorDrawerOpen(true)}>楼层管理</Button>
```

在 `{/* SMART GUIDE MODAL */}` 之前追加：

```tsx
       <FloorManagementDrawer
         enterpriseId={enterpriseId}
         open={floorDrawerOpen}
         onClose={() => setFloorDrawerOpen(false)}
         onChanged={refetch}
       />
```

- [ ] **步骤 3：`EnterpriseFloorManager` 联动一行**

将 `frontend/src/components/enterprise/EnterpriseFloorManager.tsx` 中：

```tsx
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["risk-floors", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["risk-workbench", enterpriseId] });
  };
```

替换为：

```tsx
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["risk-floors", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["risk-workbench", enterpriseId] });
    // 风险分级管控页使用独立楼层键，双向联动保证两边数据一致
    queryClient.invalidateQueries({ queryKey: ["enterprise-floors", enterpriseId] });
  };
```

- [ ] **步骤 4：类型与单测回归**

运行：`cd frontend; npx tsc -b`（预期 exit 0）

运行：`cd frontend; npx vitest run src/utils/riskTreeGrouping.test.ts src/utils/zoneSubmit.test.ts`（预期 PASS）

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/components/enterprise/EnterpriseFloorManager.tsx
git commit -m "feat(risk-management): wire floor management drawer and sync floor queries"
```

---

### 任务 4：E2E 新增 2 用例

**文件：**
- 修改：`frontend/e2e/risk-hierarchy-tree.spec.ts`

- [ ] **步骤 1：让 mock 支持层级数据覆盖与有状态楼层列表**

将 `mockApis` 签名改为：

```ts
async function mockApis(
  page: Page,
  onZoneCreate?: (payload: unknown) => void,
  onZoneUpdate?: (payload: unknown) => void,
  hierarchyData: typeof HIERARCHY = HIERARCHY,
  floorsData: typeof FLOOR_1[] = [FLOOR_1, FLOOR_2],
) {
```

将 `floors` 路由的返回改为 `data: floorsData`，将 `hierarchy` 路由的返回改为 `hierarchyData`，并新增楼层创建路由（放在 `zones` POST 之前）：

```ts
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/floors` && method === "GET") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: floorsData }));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/floors` && method === "POST") {
      const body = request.postDataJSON() as { name?: string };
      const created = {
        ...FLOOR_1,
        id: `floor-${floorsData.length + 1}`,
        name: body.name ?? "新楼层",
        sort_order: floorsData.length,
        is_default: false,
        zone_count: 0,
        risk_point_count: 0,
      };
      floorsData.push(created);
      await route.fulfill(json(201, { code: 0, message: "ok", data: created }));
      return;
    }
```

注意：`floorsData` 为闭包数组，`push` 后同一 mock 内后续 GET 返回最新列表。

- [ ] **步骤 2：新增用例 1（树显示空楼层）**

在文件末尾追加：

```ts
test("树显示没有分区的空楼层", async ({ page }) => {
  const emptyFloorHierarchy = {
    code: 0,
    message: "ok",
    data: [HIERARCHY.data[0]], // 只有一层有分区
  };
  await mockApis(page, undefined, undefined, emptyFloorHierarchy);
  await gotoEnterpriseWithAuth(page);
  await page.getByRole("tab", { name: "风险分级管控" }).click();

  await expect(page.locator(".ant-tree")).toContainText("二层");
  await expect(page.locator(".ant-tree")).toContainText("0 分区");
  await expect(page.locator(".ant-tree")).toContainText("危险品储存区");
});
```

- [ ] **步骤 3：新增用例 2（抽屉添加楼层后树出现新楼层）**

```ts
test("通过楼层管理抽屉添加楼层后树出现新楼层", async ({ page }) => {
  await mockApis(page);
  await gotoEnterpriseWithAuth(page);
  await page.getByRole("tab", { name: "风险分级管控" }).click();

  await page.getByRole("button", { name: "楼层管理" }).click();
  await expect(page.getByText("楼层管理", { exact: true }).last()).toBeVisible();
  await page.getByRole("button", { name: "添加楼层" }).click();
  await page.getByPlaceholder("请输入楼层名称，如：三层").fill("三层");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText("三层")).toBeVisible();

  // 关闭抽屉后，树应出现新楼层节点
  await page.locator(".ant-drawer-close").click();
  await expect(page.locator(".ant-tree")).toContainText("三层");
});
```

若「保存」按钮选择器命中多个，改用 `page.locator(".ant-modal").getByRole("button", { name: "保存" })`。

- [ ] **步骤 4：运行 E2E**

运行：`cd frontend; npx playwright test e2e/risk-hierarchy-tree.spec.ts`

预期：PASS，5 passed（原 3 + 新 2）

- [ ] **步骤 5：Commit**

```bash
git add frontend/e2e/risk-hierarchy-tree.spec.ts
git commit -m "test(risk-management): add empty floor and drawer e2e cases"
```

---

### 任务 5：全量验证 + TASKS 收尾

**文件：**
- 修改：`TASKS.md`

- [ ] **步骤 1：运行全量验证**

```bash
cd backend; .\.venv\Scripts\python.exe -m pytest -q --ignore tests/test_autofill_research.py --ignore _docker_test.py
cd frontend; npx tsc -b
cd frontend; npx vitest run
cd frontend; npx playwright test e2e/risk-hierarchy-tree.spec.ts e2e/risk-mapping-workbench.spec.ts
cd frontend; npx -y node@22 node_modules/vite/bin/vite.js build
```

预期：后端全通过（69）；tsc exit 0；vitest 全通过；两个 E2E 文件全通过（树 5 + 工作台 12）；生产构建成功。

- [ ] **步骤 2：更新 TASKS.md 快照并提交**

将「当前状态快照」更新为：功能完成、验证结果（命令与通过数）、可复现命令、未处理事项。

```bash
git add TASKS.md
git commit -m "chore(risk-management): update task snapshot after floor maintenance iteration"
```

---

## 自检结论

**1. 规格覆盖度：** 规格 1.4 决策表逐项对应：空楼层显示（任务 1）、未分配兜底保持（任务 1 单测）、维护入口与能力（任务 2/3）、双向联动（任务 3）、空态规则（任务 1）、测试（任务 1/4）。规格 4 边界（409 文案、默认楼层、空楼层删除）由抽屉直接透传后端 detail 覆盖。

**2. 占位符扫描：** 无「待定/TODO/后续实现」；每个代码步骤含完整代码；E2E 选择器给出回退方案。

**3. 类型一致性：** 统一 `enterprise-floors` / `risk-floors` 查询键；`FloorManagementDrawer` props（`enterpriseId/open/onClose/onChanged`）跨任务 2/3 一致；`groupZonesByFloor` 返回结构不变，`RiskHierarchyTree` 调用不变。
