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

async function gotoEnterpriseWithAuth(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-mock-token");
    localStorage.setItem("refresh_token", "e2e-mock-refresh");
  });
  await page.goto(`/enterprises/${ENTERPRISE_ID}`);
  await expect(page.getByRole("tab", { name: "风险分级管控" })).toBeVisible({ timeout: 15000 });
}

test("层级树按楼层分组且跨楼层分区可见", async ({ page }) => {
  await mockApis(page);
  await gotoEnterpriseWithAuth(page);
  await page.getByRole("tab", { name: "风险分级管控" }).click();

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
  await page.getByRole("tab", { name: "风险分级管控" }).click();

  // 树内第二个「添加分区」= 二层楼层节点操作
  await page.locator(".ant-tree").getByRole("button", { name: "添加分区" }).nth(1).click();
  await expect(page.locator(".ant-drawer .ant-select-content")).toHaveText("二层");

  await page.getByLabel("分区名称").fill("二层新增分区");
  await page.locator(".ant-drawer").getByRole("button", { name: /保\s*存/ }).click();

  await expect.poll(() => createdZonePayload).toBeTruthy();
  expect(createdZonePayload).toMatchObject({ name: "二层新增分区", floor_id: "floor-2" });
});
