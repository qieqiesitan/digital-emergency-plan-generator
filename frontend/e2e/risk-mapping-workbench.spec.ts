import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * 四色分布图工作台 E2E（任务 11）
 *
 * 说明：
 * - 工作台相关 API 使用 Playwright 路由 mock，测试可脱离后端独立运行；
 *   真实服务回归需在部署了 db_migration_risk_mapping_workbench.sql 的环境执行。
 * - 页面文本断言以当前实现为准（工作台页无「四色分布图工作台」标题，
 *   改为断言「分区」「暂无分区」等稳定文案与 canvas 元素）。
 * - baseURL 默认由 playwright.config.ts 提供（webServer 自动拉起
 *   http://localhost:5174），也可用 E2E_BASE_URL 环境变量覆盖。
 */

const ENTERPRISE_ID = "e2e-risk-mapping-enterprise";
const FLOOR_ID = "floor-1";

// mock 数据结构与后端 schema 对齐（backend/app/schemas/risk_management.py）：
// FloorResponse 含 created_at；WorkbenchResponse 无 pending_regions。
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
  created_at: "2026-08-05T00:00:00+08:00",
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
  },
};

const BATCH_SAVE_RESPONSE = {
  code: 0,
  message: "ok",
  data: {
    floor: FLOOR,
    zones: [],
    risk_points: [],
    texts: [],
    created_zone_map: {},
    created_risk_point_map: {},
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

type MockOptions = {
  onBatchSave?: (route: Route, payload: unknown) => void | Promise<void>;
};

/**
 * 单一路由 + URL/方法精确分发：
 * - GET /workbench 与 POST /workbench/batch-save 分开精确匹配，无 glob 重叠；
 * - 未匹配的 /api/* 请求统一返回 404，确保测试 hermetic，不透传真实后端。
 */
async function mockWorkbenchApis(page: Page, options: MockOptions = {}) {
  const json = (status: number, body: unknown) => ({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
  await page.route("**/api/**", async route => {
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
    if (path === "/api/v1/enterprises" && method === "GET" && url.searchParams.has("page")) {
      await route.fulfill(
        json(200, {
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
      );
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/floors` && method === "GET") {
      await route.fulfill(json(200, { code: 0, message: "ok", data: [FLOOR] }));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/workbench` && method === "GET") {
      await route.fulfill(json(200, WORKBENCH_SNAPSHOT));
      return;
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/workbench/batch-save` && method === "POST") {
      if (options.onBatchSave) {
        await options.onBatchSave(route, request.postDataJSON());
      } else {
        await route.fulfill(json(200, BATCH_SAVE_RESPONSE));
      }
      return;
    }
    await route.fulfill(
      json(404, { code: 404, message: "not found", detail: "e2e mock: unmatched /api/* request" }),
    );
  });
}

async function loginAndOpenWorkbench(page: Page) {
  // 相对路径走 config baseURL（默认 http://localhost:5174，可被 E2E_BASE_URL 覆盖）
  await page.goto("/login");
  await page.getByPlaceholder("邮箱").fill("qa_e2e_test@test.com");
  await page.getByPlaceholder("密码").fill("test123456");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(dashboard|enterprises)/, { timeout: 10000 });
  await page.goto(`/enterprises/${ENTERPRISE_ID}/risk-mapping-workbench`);
  await expect(page.locator('[data-testid="workbench-canvas"] canvas').first()).toBeVisible({ timeout: 15000 });
}

test.describe("风险分级管控四色分布图工作台", () => {
  test("工作台路由打开并渲染画布", async ({ page }) => {
    await mockWorkbenchApis(page);
    await loginAndOpenWorkbench(page);

    await expect(page).toHaveURL(/\/enterprises\/[^/]+\/risk-mapping-workbench/);
    await expect(page.getByText("分区", { exact: true })).toBeVisible();
    await expect(page.getByText("暂无分区")).toBeVisible();
    await expect(page.getByRole("button", { name: "新建楼层" })).toBeVisible();
    await expect(page.getByRole("button", { name: "保存工作台" })).toBeVisible();
    await expect(page.locator('[data-testid="workbench-canvas"] canvas').first()).toBeVisible();
  });

  test("矩形绘制产生待绑定区域，保存时触发未绑定确认", async ({ page }) => {
    await mockWorkbenchApis(page);
    await loginAndOpenWorkbench(page);

    // 工具栏按钮已补显式 aria-label（WorkbenchToolbar）
    await page.getByRole("button", { name: "矩形" }).click();
    const canvas = page.locator('[data-testid="workbench-canvas"] canvas').first();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("canvas bounding box unavailable");
    // 相对画布 bounding box 的比例坐标，不依赖具体视口/布局；
    // 拖拽范围落在画布左上部，避开右下角图例与 AI 助手浮动面板。
    await page.mouse.move(box.x + box.width * 0.16, box.y + box.height * 0.14);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.3, { steps: 6 });
    await page.mouse.up();

    await expect(page.getByText(/未绑定区域 · \d+ 个顶点/)).toBeVisible();
    const saveButton = page.getByRole("button", { name: "保存工作台" });
    await saveButton.click();
    await expect(page.locator(".ant-modal-confirm-title")).toHaveText("存在待绑定区域");
    await page.getByRole("button", { name: /知\s*道\s*了/ }).click();
  });

  test("文字标注绘制后可保存（绘制/保存闭环）", async ({ page }) => {
    let savedPayload: unknown = null;
    await mockWorkbenchApis(page, {
      onBatchSave: async (route, payload) => {
        savedPayload = payload;
        const texts = (payload as { texts?: unknown[] }).texts ?? [];
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...BATCH_SAVE_RESPONSE,
            data: { ...BATCH_SAVE_RESPONSE.data, texts },
          }),
        });
      },
    });
    await loginAndOpenWorkbench(page);

    // 文字工具按钮已补显式 aria-label
    await page.getByRole("button", { name: "文字" }).click();
    const canvas = page.locator('[data-testid="workbench-canvas"] canvas').first();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("canvas bounding box unavailable");
    await canvas.click({ position: { x: box.width * 0.4, y: box.height * 0.4 } });

    // 文字工具点击后自动打开编辑弹窗，避免双击时继续新增文字图层
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("dialog").getByRole("button", { name: /保\s*存/ }).click();

    // dirty 后保存按钮可用
    const saveButton = page.getByRole("button", { name: "保存工作台" });
    await expect(saveButton).toBeEnabled();
    await saveButton.click();

    await expect(page.getByText("保存成功")).toBeVisible({ timeout: 10000 });
    expect(savedPayload).not.toBeNull();
    expect((savedPayload as { floor_id: string }).floor_id).toBe(FLOOR_ID);
    expect((savedPayload as { texts: unknown[] }).texts).toHaveLength(1);
    await expect(saveButton).toBeDisabled();
  });

  test("圆形绘制产生待绑定区域，删除所选可删除", async ({ page }) => {
    await mockWorkbenchApis(page);
    await loginAndOpenWorkbench(page);

    await page.getByRole("button", { name: "圆形" }).click();
    const canvas = page.locator('[data-testid="workbench-canvas"] canvas').first();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("canvas bounding box unavailable");
    await page.mouse.move(box.x + box.width * 0.18, box.y + box.height * 0.2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.3, { steps: 6 });
    await page.mouse.up();

    await expect(page.getByText(/未绑定区域 · \d+ 个顶点/)).toBeVisible();
    await page.getByText(/未绑定区域 · \d+ 个顶点/).click();
    await page.getByRole("button", { name: "删除所选" }).click();
    await expect(page.getByText(/未绑定区域 · \d+ 个顶点/)).not.toBeVisible();
  });

  test("多边形点击顶点后双击闭合，并显示待绑定区域", async ({ page }) => {
    await mockWorkbenchApis(page);
    await loginAndOpenWorkbench(page);

    await page.getByRole("button", { name: "多边形" }).click();
    const canvas = page.locator('[data-testid="workbench-canvas"] canvas').first();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("canvas bounding box unavailable");
    await expect(page.locator('[data-testid="workbench-canvas"]')).toHaveAttribute("data-tool", "polygon");
    await canvas.click({ position: { x: box.width * 0.2, y: box.height * 0.2 } });
    await page.waitForTimeout(700);
    await canvas.click({ position: { x: box.width * 0.35, y: box.height * 0.25 } });
    await page.waitForTimeout(700);
    await canvas.click({ position: { x: box.width * 0.28, y: box.height * 0.4 } });
    await page.waitForTimeout(700);
    await expect(page.locator('[data-testid="workbench-canvas"]')).toHaveAttribute("data-draft-count", "3");
    await page.keyboard.press("Enter");

    await expect(page.getByText(/未绑定区域 · \d+ 个顶点/)).toBeVisible();
  });

  test("风险点工具点击后进入属性编辑状态", async ({ page }) => {
    await mockWorkbenchApis(page);
    await loginAndOpenWorkbench(page);

    await page.getByRole("button", { name: "风险点" }).click();
    const canvas = page.locator('[data-testid="workbench-canvas"] canvas').first();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("canvas bounding box unavailable");
    await canvas.click({ position: { x: box.width * 0.42, y: box.height * 0.42 } });

    await expect(page.getByPlaceholder("风险点名称")).toHaveValue("新风险点");
    await page.getByPlaceholder("风险点名称").fill("配电室风险点");
    await page.getByRole("button", { name: "保存风险点" }).click();
    await expect(page.getByText("配电室风险点")).toBeVisible();
  });

  test("返回与画布缩放入口可用", async ({ page }) => {
    await mockWorkbenchApis(page);
    await loginAndOpenWorkbench(page);

    await expect(page.getByRole("button", { name: "返回" })).toBeVisible();
    await expect(page.getByRole("button", { name: "放大" })).toBeVisible();
    await expect(page.getByRole("button", { name: "缩小" })).toBeVisible();
    await expect(page.getByRole("button", { name: "重置缩放" })).toBeVisible();
  });
});
