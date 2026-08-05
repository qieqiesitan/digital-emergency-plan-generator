import { test, expect, type Page } from "@playwright/test";

/**
 * 四色分布图工作台 E2E（任务 11）
 *
 * 说明：
 * - 工作台相关 API 使用 Playwright 路由 mock，测试可脱离后端独立运行；
 *   真实服务回归需在部署了 db_migration_risk_mapping_workbench.sql 的环境执行。
 * - 页面文本断言以当前实现为准（工作台页无「四色分布图工作台」标题，
 *   改为断言「分区」「暂无分区」等稳定文案与 canvas 元素）。
 */

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const ENTERPRISE_ID = "e2e-risk-mapping-enterprise";
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
  updated_at: "2026-08-05T00:00:00+08:00",
};

const WORKBENCH_SNAPSHOT = {
  code: 0,
  message: "ok",
  data: {
    floors: [FLOOR],
    current_floor_id: FLOOR_ID,
    zones: [],
    risk_points: [],
    texts: [],
    pending_regions: [],
  },
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

async function mockWorkbenchApis(page: Page) {
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(TOKEN_RESPONSE),
    }),
  );
  await page.route("**/api/v1/users/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 0, message: "ok", data: USER }),
    }),
  );
  await page.route("**/api/v1/roles/my-menus", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 0, message: "ok", data: [] }),
    }),
  );
  await page.route("**/api/v1/enterprises?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: 0,
        message: "ok",
        data: {
          items: [
            {
              id: ENTERPRISE_ID,
              name: "E2E 测试企业",
              address: null,
              industry: null,
              created_at: "2026-08-05T00:00:00+08:00",
              updated_at: "2026-08-05T00:00:00+08:00",
            },
          ],
          total: 1,
          page: 1,
          page_size: 100,
        },
      }),
    }),
  );
  await page.route(`**/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/floors`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 0, message: "ok", data: [FLOOR] }),
    }),
  );
  await page.route(`**/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/workbench**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(WORKBENCH_SNAPSHOT),
    }),
  );
}

async function loginAndOpenWorkbench(page: Page) {
  await page.goto(BASE + "/login");
  await page.getByPlaceholder("邮箱").fill("qa_e2e_test@test.com");
  await page.getByPlaceholder("密码").fill("test123456");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(dashboard|enterprises)/, { timeout: 10000 });
  await page.goto(BASE + `/enterprises/${ENTERPRISE_ID}/risk-mapping-workbench`);
  await expect(page.locator("canvas").first()).toBeVisible({ timeout: 15000 });
}

test.describe("风险分级管控四色分布图工作台", () => {
  test("工作台路由打开并渲染画布", async ({ page }) => {
    await mockWorkbenchApis(page);
    await loginAndOpenWorkbench(page);

    await expect(page).toHaveURL(/\/enterprises\/[^/]+\/risk-mapping-workbench/);
    await expect(page.getByText("分区", { exact: true })).toBeVisible();
    await expect(page.getByText("暂无分区")).toBeVisible();
    await expect(page.getByRole("button", { name: "新建楼层" })).toBeVisible();
    await expect(page.locator('button:has([aria-label="save"])')).toBeVisible();
    await expect(page.locator("canvas").first()).toBeVisible();
  });

  test("矩形绘制产生待绑定区域，保存时触发未绑定确认", async ({ page }) => {
    await mockWorkbenchApis(page);
    await loginAndOpenWorkbench(page);

    // 矩形工具（icon aria-label=border），按下-拖动-松开完成区域
    await page.getByRole("button", { name: "border", exact: true }).click();
    const canvas = page.locator("canvas").first();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("canvas bounding box unavailable");
    // 拖拽范围避开右下角「AI 助手」浮动面板；以下坐标基于 1280x800 viewport 实测
    await page.mouse.move(box.x + 184, box.y + 108);
    await page.mouse.down();
    await page.mouse.move(box.x + 300, box.y + 228, { steps: 6 });
    await page.mouse.up();

    await expect(page.getByText(/未绑定区域 · \d+ 个顶点/)).toBeVisible();
    const saveButton = page.locator('button:has([aria-label="save"])');
    await saveButton.click();
    await expect(page.locator(".ant-modal-confirm-title")).toHaveText("存在待绑定区域");
    await page.getByRole("button", { name: /知\s*道\s*了/ }).click();
  });

  test("文字标注绘制后可保存（绘制/保存闭环）", async ({ page }) => {
    await mockWorkbenchApis(page);
    let savedPayload: unknown = null;
    await page.route(`**/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/workbench/batch-save`, async (route) => {
      const body = route.request().postDataJSON();
      savedPayload = body;
      const texts = (body as { texts?: unknown[] }).texts ?? [];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          code: 0,
          message: "ok",
          data: {
            floor: FLOOR,
            zones: [],
            risk_points: [],
            texts,
            created_zone_map: {},
            created_risk_point_map: {},
          },
        }),
      });
    });

    await loginAndOpenWorkbench(page);

    // 文字工具（icon aria-label=font-size）
    await page.locator('button:has([aria-label="font-size"])').click();
    const canvas = page.locator("canvas").first();
    await canvas.click({ position: { x: 300, y: 300 } });

    // dirty 后保存按钮可用
    const saveButton = page.locator('button:has([aria-label="save"])');
    await expect(saveButton).toBeEnabled();
    await saveButton.click();

    await expect(page.getByText("保存成功")).toBeVisible({ timeout: 10000 });
    expect(savedPayload).not.toBeNull();
    expect((savedPayload as { floor_id: string }).floor_id).toBe(FLOOR_ID);
    expect((savedPayload as { texts: unknown[] }).texts).toHaveLength(1);
    await expect(saveButton).toBeDisabled();
  });
});
