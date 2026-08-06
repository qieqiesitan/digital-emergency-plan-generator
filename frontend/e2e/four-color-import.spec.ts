import { test, expect, type Page } from "@playwright/test";

const ENTERPRISE_ID = "e2e-four-color-import-enterprise";
const FLOOR_ID = "floor-1";

const FLOOR = {
  id: FLOOR_ID,
  enterprise_id: ENTERPRISE_ID,
  name: "一层",
  sort_order: 0,
  floor_plan_url: null,
  description: null,
  canvas_width: 1200,
  canvas_height: 900,
  canvas_texts: [],
  is_default: true,
  zone_count: 0,
  risk_point_count: 0,
  created_at: "2026-08-06T00:00:00+08:00",
  updated_at: "2026-08-06T00:00:00+08:00",
};

const ANALYZE_ZONES = [
  { client_id: "draft-1", name: "分区1", risk_level: "重大", color: "#ff4d4f", polygons: [{ id: "p1", label: null, points: [{ x: 6.67, y: 8.89 }, { x: 46.67, y: 8.89 }, { x: 46.67, y: 40 }, { x: 6.67, y: 40 }] }] },
  { client_id: "draft-2", name: "分区2", risk_level: "较大", color: "#fa8c16", polygons: [{ id: "p2", label: null, points: [{ x: 53.33, y: 8.89 }, { x: 93.33, y: 8.89 }, { x: 93.33, y: 40 }, { x: 53.33, y: 40 }] }] },
  { client_id: "draft-3", name: "分区3", risk_level: "一般", color: "#fadb14", polygons: [{ id: "p3", label: null, points: [{ x: 6.67, y: 51.11 }, { x: 46.67, y: 51.11 }, { x: 46.67, y: 91.11 }, { x: 6.67, y: 91.11 }] }] },
  { client_id: "draft-4", name: "分区4", risk_level: "低", color: "#52c41a", polygons: [{ id: "p4", label: null, points: [{ x: 53.33, y: 51.11 }, { x: 93.33, y: 51.11 }, { x: 93.33, y: 91.11 }, { x: 53.33, y: 91.11 }] }] },
];

const ANALYZE_DATA = {
  preview_url: "/uploads/four-color-sample.png",
  canvas_width: 600,
  canvas_height: 450,
  zones: ANALYZE_ZONES,
  warnings: [],
};

const COMMIT_DATA = {
  floor: { ...FLOOR, floor_plan_url: "/uploads/four-color-sample.png", canvas_width: 600, canvas_height: 450, zone_count: 4 },
  zones: ANALYZE_ZONES.map((z, i) => ({
    id: `zone-${i + 1}`,
    enterprise_id: ENTERPRISE_ID,
    floor_id: FLOOR_ID,
    floor_name: "一层",
    name: z.name,
    description: null,
    sort_order: i,
    floor_plan_polygon: { version: 2, color_source: "manual", color: z.color, polygons: z.polygons },
    max_risk_level: z.risk_level,
    effective_color: z.color,
    object_count: 0,
    created_at: "2026-08-06T00:00:00+08:00",
    updated_at: "2026-08-06T00:00:00+08:00",
  })),
};

const json = (status: number, body: unknown) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

const USER = {
  id: "e2e-user-id",
  email: "qa_e2e_test@test.com",
  name: "E2E 测试用户",
  role: "admin",
  created_at: "2026-08-06T00:00:00+08:00",
};

async function mockApis(page: Page, workbenchZones: unknown[] = []) {
  const workbenchFloor = workbenchZones.length
    ? { ...FLOOR, zone_count: workbenchZones.length }
    : FLOOR;
  await page.route("**/api/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === "/api/v1/auth/login" && method === "POST") {
      await route.fulfill(json(200, {
        code: 0,
        message: "ok",
        data: {
          access_token: "e2e-mock-token",
          refresh_token: "e2e-mock-refresh",
          token_type: "bearer",
          expires_in: 7200,
        },
      }));
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
    if (path === "/api/v1/enterprises" && method === "GET" && url.searchParams.has("page")) {
      await route.fulfill(json(200, {
        code: 0,
        message: "ok",
        data: {
          items: [{ id: ENTERPRISE_ID, name: "E2E 测试企业", address: null, industry: null, created_at: "2026-08-06T00:00:00+08:00", updated_at: "2026-08-06T00:00:00+08:00" }],
          total: 1,
          page: 1,
          page_size: 100,
        },
      }));
      return;
    }
    if (path === "/api/v1/enterprises/e2e-four-color-import-enterprise/risk-management/workbench" && method === "GET") {
      await route.fulfill(json(200, {
        code: 0,
        message: "ok",
        data: { floors: [workbenchFloor], current_floor_id: FLOOR_ID, zones: workbenchZones, risk_points: [], texts: [] },
      }));
      return;
    }
    if (path.endsWith("/risk-management/floors/floor-1") && method === "GET") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: workbenchFloor }));
      return;
    }
    if (path.endsWith("/four-color/analyze") && method === "POST") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: ANALYZE_DATA }));
      return;
    }
    if (path.endsWith("/four-color/commit") && method === "POST") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: COMMIT_DATA }));
      return;
    }
    if (path.includes("/four-color/") && method === "DELETE") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: null }));
      return;
    }
    await route.fulfill(json(404, { code: 404, message: "not found" }));
  });
  await page.route("**/uploads/four-color-sample.png", route =>
    route.fulfill({ status: 200, contentType: "image/png", path: "e2e/fixtures/four-color-sample.png" }),
  );
}

async function loginAndOpenWorkbench(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("邮箱").fill("qa_e2e_test@test.com");
  await page.getByPlaceholder("密码").fill("test123456");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(dashboard|enterprises)/, { timeout: 10000 });
  await page.goto(`/enterprises/${ENTERPRISE_ID}/risk-mapping-workbench`);
  await expect(page.locator('[data-testid="workbench-canvas"] canvas').first()).toBeVisible({ timeout: 15000 });
}

function dialogFileInput(page: Page) {
  return page.getByRole("dialog", { name: "导入四色分布图" }).locator('input[type="file"]');
}

function dialogZoneInput(page: Page, index: number) {
  return page.getByRole("dialog", { name: "导入四色分布图" }).locator(`input[aria-label="分区名称${index}"]`);
}

test.describe("四色分布图自动识别导入", () => {
  test("上传→预览→确认落图→工作台出现分区", async ({ page }) => {
    await mockApis(page);
    await loginAndOpenWorkbench(page);
    await page.getByRole("button", { name: "导入四色图" }).click();
    await dialogFileInput(page).setInputFiles("e2e/fixtures/four-color-sample.png");
    await expect(dialogZoneInput(page, 1)).toHaveValue("分区1", { timeout: 10000 });
    await expect(page.getByRole("dialog", { name: "导入四色分布图" }).getByText("重大").first()).toBeVisible();
    await expect(page.getByRole("dialog", { name: "导入四色分布图" }).locator("svg polygon")).toHaveCount(4);
    await page.getByRole("button", { name: "确认落图" }).click();
    await expect(page.getByText("四色图导入成功")).toBeVisible();
    await expect(page.getByText("分区1", { exact: true })).toBeVisible();
  });

  test("楼层已有数据时显示替换确认，导入后旧数据消失", async ({ page }) => {
    const OLD_ZONE = {
      id: "old-zone-1",
      enterprise_id: ENTERPRISE_ID,
      floor_id: FLOOR_ID,
      floor_name: "一层",
      name: "旧分区",
      description: null,
      sort_order: 0,
      floor_plan_polygon: null,
      max_risk_level: null,
      effective_color: null,
      object_count: 0,
      created_at: "2026-08-06T00:00:00+08:00",
      updated_at: "2026-08-06T00:00:00+08:00",
    };
    await mockApis(page, [OLD_ZONE]);
    await loginAndOpenWorkbench(page);
    await page.getByText("旧分区", { exact: true }).first().waitFor();
    await page.getByRole("button", { name: "导入四色图" }).click();
    await dialogFileInput(page).setInputFiles("e2e/fixtures/four-color-sample.png");
    await expect(page.getByRole("checkbox")).toBeVisible();
    await expect(page.getByText(/移除该楼层原有分区/)).toBeVisible();
    await page.getByRole("button", { name: "确认落图" }).click();
    await expect(page.getByText("四色图导入成功")).toBeVisible();
    await expect(page.getByText("旧分区", { exact: true })).toHaveCount(0);
    await expect(page.getByText("分区1", { exact: true })).toBeVisible();
  });
});
