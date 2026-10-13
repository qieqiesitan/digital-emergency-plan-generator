import { test, expect, type Page } from "@playwright/test";

/**
 * 风险分级管控分区树楼层分组 E2E
 * - 全部 API 使用 Playwright 路由 mock，可脱离后端独立运行；
 * - baseURL 默认由 playwright.config.ts 提供（webServer 自动拉起 http://localhost:5174）；
 * - 直接进入受保护路由前先注入 mock token（AuthContext 读取 localStorage）。
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
    {
      id: "zone-3",
      floor_id: null,
      floor_name: null,
      name: "历史遗留分区",
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

/** 企业驾驶舱摘要（进入企业页需要，缺失会让 tab 区域被错误态替换） */
const COCKPIT_SUMMARY = {
  code: 0,
  message: "ok",
  data: {
    risk_counts: { major: 2, larger: 4, general: 18, low: 10, total: 34 },
    zone_risks: [
      { zone_name: "危险品储存区", counts: { major: 1, larger: 2, general: 8, low: 2 }, total: 13 },
    ],
    top_risks: [
      { name: "危险品储存区", level: "重大", score: 82, responsible_unit: "生产部" },
    ],
    risk_index: 38,
    hazard_counts: { open: 3, due: 2, overdue: 0 },
    todos: [
      { priority: "high", title: "风险评估报告未生成", note: "建议本周完成 · AI 可辅助生成" },
    ],
    completion: { percent: 78, modules: [
      { key: "enterprise_info", label: "基本信息", done: true },
      { key: "reports", label: "报告", done: false },
    ] },
    recent_activities: [{ actor: "系统", action: "企业档案更新", time: "2026-08-16T10:32:00+08:00" }],
  },
};

/** /overview（右侧四色图数据源）按楼层的 mock 分区 */
function makeOverviewZone(id: string, name: string, floorId: string, floorName: string) {
  return {
    id,
    enterprise_id: ENTERPRISE_ID,
    floor_id: floorId,
    floor_name: floorName,
    name,
    description: null,
    sort_order: 0,
    floor_plan_polygon: {
      version: 2,
      level_mode: "manual",
      risk_level: "较大",
      polygons: [
        { id: `${id}-p1`, label: null, points: [{ x: 10, y: 10 }, { x: 90, y: 10 }, { x: 90, y: 90 }, { x: 10, y: 90 }] },
      ],
    },
    max_risk_level: "较大",
    effective_color: "#fa8c16",
    object_count: 0,
    created_at: "2026-08-05T00:00:00+08:00",
    updated_at: "2026-08-05T00:00:00+08:00",
  };
}

async function mockApis(
  page: Page,
  onZoneCreate?: (payload: unknown) => void,
  onZoneUpdate?: (payload: unknown) => void,
  hierarchyData: typeof HIERARCHY = HIERARCHY,
  floorsData: Array<typeof FLOOR_1> = [FLOOR_1, FLOOR_2],
  onOverview?: (floorId: string) => void,
) {
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
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/cockpit-summary` && method === "GET") {
      await route.fulfill(json(200, COCKPIT_SUMMARY));
      return;
    }
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
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/hierarchy` && method === "GET") {
      await route.fulfill(json(200, hierarchyData));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/overview` && method === "GET") {
      const requestedFloor = url.searchParams.get("floor_id") ?? floorsData[0]?.id ?? "floor-1";
      onOverview?.(requestedFloor);
      const floor = floorsData.find((f) => f.id === requestedFloor) ?? floorsData[0];
      const zones = !floor
        ? []
        : requestedFloor === "floor-2"
          ? [makeOverviewZone("zone-2", "二层办公区", "floor-2", "二层")]
          : [makeOverviewZone("zone-1", "危险品储存区", "floor-1", "一层")];
      await route.fulfill(json(200, { code: 0, message: "ok", data: { floor, zones, risk_points: [] } }));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/zones` && method === "POST") {
      onZoneCreate?.(request.postDataJSON());
      await route.fulfill(json(200, { code: 0, message: "ok", data: { id: "new-zone-1" } }));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/zones/zone-3` && method === "PUT") {
      onZoneUpdate?.(request.postDataJSON());
      await route.fulfill(json(200, { code: 0, message: "ok", data: { id: "zone-3" } }));
      return;
    }
    await route.fulfill(json(404, { code: 404, message: "not found", data: null }));
  });
}

async function gotoEnterpriseWithAuth(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-mock-token");
    localStorage.setItem("refresh_token", "e2e-mock-refresh");
  });
  // 直达风险分级管控模块路由（企业驾驶舱已改为模块导航，不再有 tab）
  await page.goto(`/enterprises/${ENTERPRISE_ID}/risk-management`);
  await expect(page.getByRole("button", { name: "添加分区" }).first()).toBeVisible({ timeout: 15000 });
}

test("层级树按楼层分组且跨楼层分区可见", async ({ page }) => {
  await mockApis(page);
  await gotoEnterpriseWithAuth(page);

  await expect(page.locator(".ant-tree")).toContainText("一层");
  await expect(page.locator(".ant-tree")).toContainText("二层");
  await expect(page.locator(".ant-tree")).toContainText("默认");
  // 默认楼层分区直接可见
  await expect(page.locator(".ant-tree")).toContainText("危险品储存区");
  // 展开二层楼层节点后，二层分区可见（antd Tree 展开需点击该节点内 switcher，标题点击是选中）
  await page.locator(".ant-tree-treenode").filter({ hasText: "二层" }).locator(".ant-tree-switcher").click();
  await expect(page.locator(".ant-tree")).toContainText("二层办公区");
});

test("从楼层节点添加分区时 payload 携带目标楼层", async ({ page }) => {
  let createdZonePayload: unknown = null;
  await mockApis(page, (payload) => {
    createdZonePayload = payload;
  });
  await gotoEnterpriseWithAuth(page);

  // 树内第二个「添加分区」= 二层楼层节点操作
  await page.locator(".ant-tree").getByRole("button", { name: "添加分区" }).nth(1).click();
  await expect(page.locator(".ant-drawer .ant-select-content")).toHaveText("二层");

  await page.getByLabel("分区名称").fill("二层新增分区");
  await page.locator(".ant-drawer").getByRole("button", { name: /保\s*存/ }).click();

  await expect.poll(() => createdZonePayload).toBeTruthy();
  expect(createdZonePayload).toMatchObject({ name: "二层新增分区", floor_id: "floor-2" });
});

test("编辑未分配楼层分区时保存不携带 floor_id（避免静默迁移）", async ({ page }) => {
  let updatedZonePayload: unknown = null;
  await mockApis(page, undefined, (payload) => {
    updatedZonePayload = payload;
  });
  await gotoEnterpriseWithAuth(page);

  // 展开「未分配楼层」节点（最后一个楼层节点的 switcher）
  await page.locator(".ant-tree-treenode").filter({ hasText: "未分配楼层" }).locator(".ant-tree-switcher").click();
  // 点击「历史遗留分区」行的「编辑分区」按钮
  await page.locator(".ant-tree-treenode").filter({ hasText: "历史遗留分区" }).getByRole("button", { name: "编辑分区" }).click();
  // 修改名称并保存
  await page.getByLabel("分区名称").fill("历史遗留分区-改名");
  await page.locator(".ant-drawer").getByRole("button", { name: /保\s*存/ }).click();

  await expect.poll(() => updatedZonePayload).toBeTruthy();
  expect(updatedZonePayload).toMatchObject({ name: "历史遗留分区-改名" });
  expect(updatedZonePayload).not.toHaveProperty("floor_id");
});

test("树显示没有分区的空楼层", async ({ page }) => {
  const emptyFloorHierarchy = {
    code: 0,
    message: "ok",
    data: [HIERARCHY.data[0]], // 只有一层有分区
  };
  await mockApis(page, undefined, undefined, emptyFloorHierarchy);
  await gotoEnterpriseWithAuth(page);

  await expect(page.locator(".ant-tree")).toContainText("二层");
  await expect(page.locator(".ant-tree")).toContainText("0 分区");
  await expect(page.locator(".ant-tree")).toContainText("危险品储存区");
});

test("右侧节点详情与四色图跟随树选择联动（含地图反选）", async ({ page }) => {
  const overviewFloors: string[] = [];
  await mockApis(page, undefined, undefined, HIERARCHY, [FLOOR_1, FLOOR_2], (fid) => overviewFloors.push(fid));
  await gotoEnterpriseWithAuth(page);

  const mapPanel = page.getByTestId("risk-tree-map-panel");
  const detailCard = page.getByTestId("risk-tree-node-detail");
  await expect(mapPanel).toBeVisible({ timeout: 15000 });
  // 初始展示默认楼层
  await expect(mapPanel).toHaveAttribute("data-floor-id", "floor-1");
  await expect(detailCard).toContainText("点击左侧风险树节点");
  await expect.poll(() => overviewFloors.includes("floor-1")).toBe(true);

  // ① 树选中分区 → 详情更新 + 地图高亮该分区
  await page.locator(".ant-tree-treenode").filter({ hasText: "危险品储存区" }).first().click();
  await expect(mapPanel).toHaveAttribute("data-highlight-zone", "zone-1");
  await expect(detailCard).toContainText("危险品储存区");
  await expect(detailCard).toContainText("楼层：一层");

  // ② 点楼层节点 → 地图切换到该楼层
  await page.locator(".ant-tree-treenode").filter({ hasText: "二层" }).first().locator(".ant-tree-node-content-wrapper").click();
  await expect(mapPanel).toHaveAttribute("data-floor-id", "floor-2");
  await expect.poll(() => overviewFloors.includes("floor-2")).toBe(true);
  await expect(mapPanel).toHaveAttribute("data-highlight-zone", "");

  // ③ 点地图上的分区 → 树反选并自动展开到该分区，详情同步
  await page.locator('[data-testid="risk-distribution-stage"] canvas').first().click();
  await expect(page.locator(".ant-tree-node-selected")).toContainText("二层办公区");
  await expect(mapPanel).toHaveAttribute("data-highlight-zone", "zone-2");
  await expect(detailCard).toContainText("二层办公区");
});

test("通过楼层管理抽屉添加楼层后树出现新楼层", async ({ page }) => {
  await mockApis(page);
  await gotoEnterpriseWithAuth(page);

  await page.getByRole("button", { name: "楼层管理" }).click();
  await expect(page.getByText("楼层管理", { exact: true }).last()).toBeVisible();
  await page.getByRole("button", { name: "添加楼层" }).click();
  await page.getByPlaceholder("请输入楼层名称，如：三层").fill("三层");
  // antd 会在两字按钮文案中自动插入空格（"保 存"），用正则匹配
  await page.locator(".ant-modal").getByRole("button", { name: /保\s*存/ }).click();
  await expect(page.locator(".ant-drawer").getByText("三层")).toBeVisible();

  // 关闭抽屉后，树应出现新楼层节点
  await page.locator(".ant-drawer-close").click();
  await expect(page.locator(".ant-tree")).toContainText("三层");
});
