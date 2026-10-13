import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * 智能引导导入 E2E：AI 生成层级含重名分区与误标风险点对象时，
 * 导入应跳过重名分区、对象不再创建为风险点。
 */

const ENTERPRISE_ID = "e2e-smart-guide-enterprise";
const EXISTING_ZONE = {
  id: "existing-zone-1",
  enterprise_id: ENTERPRISE_ID,
  floor_id: "f1",
  floor_name: "一层",
  name: "储罐区",
  description: null,
  sort_order: 0,
  floor_plan_polygon: null,
  max_risk_level: null,
  effective_color: null,
  object_count: 0,
  created_at: "2026-08-05T00:00:00+08:00",
  updated_at: "2026-08-05T00:00:00+08:00",
  objects: [],
};

const ENTERPRISE = {
  id: ENTERPRISE_ID,
  name: "去重测试企业",
  credit_code: null,
  legal_representative: null,
  economic_type: null,
  established_date: null,
  registered_capital: null,
  business_scope: null,
  industry: null,
  address: null,
  building_overview: null,
  hazardous_chemicals: null,
  special_equipment: null,
  floor_plan_url: null,
  org_structure: [],
  surrounding_info: { nearby_units: [], sensitive_targets: [], traffic_info: "" },
  created_at: "2026-08-05T00:00:00+08:00",
  updated_at: "2026-08-05T00:00:00+08:00",
};

const AI_HIERARCHY = {
  zones: [
    {
      name: "储罐区",
      description: null,
      objects: [
        {
          name: "1号储罐",
          category: "罐区",
          is_risk_point: true,
          units: [],
          events: [
            {
              accident_type: "火灾爆炸",
              description: null,
              risk_level: "较大",
              risk_score: "R=16",
              method_type: "LS",
              method_params: { l: 4, s: 4 },
              measures: [
                {
                  measure_category: "engineering",
                  measure_type: null,
                  description: "设置液位联锁",
                  check_items: [],
                },
              ],
            },
          ],
        },
      ],
    },
    {
      name: "原料库",
      description: null,
      objects: [
        {
          name: "货架",
          category: "仓库",
          is_risk_point: false,
          units: [],
          events: [],
        },
      ],
    },
  ],
  summary: {},
};

test("智能引导导入：重名分区并入现有分区、对象保留 is_risk_point 语义", async ({ page }: { page: Page }) => {
  const createdPayloads: unknown[] = [];
  page.on("pageerror", (err) => {
    console.log("PAGEERROR:", err.message);
    console.log(err.stack?.split("\n").slice(0, 6).join("\n"));
  });
  const json = (status: number, body: unknown) => ({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });

  await page.route("**/api/**", async (route: Route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path === "/api/v1/auth/login" && method === "POST") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { access_token: "t", refresh_token: "r", token_type: "bearer", expires_in: 7200 } }));
    }
    if (path === "/api/v1/users/me" && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "u", email: "qa_e2e_test@test.com", name: "测试", role: "admin" } }));
    }
    if (path === "/api/v1/roles/my-menus" && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: [] }));
    }
    if (path === "/api/v1/enterprises" && method === "GET" && url.searchParams.has("page")) {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { items: [ENTERPRISE], total: 1, page: 1, page_size: 100 } }));
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}` && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: ENTERPRISE }));
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/floors` && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: [] }));
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/hierarchy` && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: [EXISTING_ZONE] }));
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/zones` && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: [EXISTING_ZONE] }));
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/ai/smart-guide` && method === "POST") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { hierarchy: AI_HIERARCHY.zones, summary: AI_HIERARCHY.summary } }));
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/zones` && method === "POST") {
      createdPayloads.push(req.postDataJSON());
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "new-zone-1", name: req.postDataJSON().name, floor_id: "f1", enterprise_id: ENTERPRISE_ID } }));
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/objects` && method === "POST") {
      createdPayloads.push(req.postDataJSON());
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "new-obj-1", name: req.postDataJSON().name, is_risk_point: false, zone_id: req.postDataJSON().zone_id } }));
    }
    if (path.includes("/objects/") && path.endsWith("/events") && method === "POST") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "ev1", accident_type: req.postDataJSON().accident_type } }));
    }
    if (path.includes("/events/") && path.endsWith("/measures") && method === "POST") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "m1", description: req.postDataJSON().description } }));
    }
    return route.fulfill(json(404, { code: 404, message: "not found" }));
  });

  await page.goto("/login");
  await page.getByPlaceholder("邮箱").fill("qa_e2e_test@test.com");
  await page.getByPlaceholder("密码").fill("test123456");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(dashboard|enterprises)/);

  // 直达风险分级管控模块路由（企业驾驶舱已改为模块导航，不再有 tab）
  await page.goto(`/enterprises/${ENTERPRISE_ID}/risk-management`);
  await expect(page.getByRole("button", { name: "添加分区" }).first()).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: /智能导引/ }).click();
  await page.locator("textarea").first().fill("厂区有原料库和储罐");
  await page.getByRole("button", { name: /AI 分析/ }).click();
  await expect(page.getByText(/AI 已按企业档案与现有风险树查漏补缺/)).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: /确认并导入全部/ }).click();

  // 提示文案："导入完成：新增 N 条，并入现有 M 条，跳过重复 K 条"
  // 新增 5 = 原料库分区 + 1号储罐 + 火灾爆炸事件 + 设置液位联锁措施 + 货架；并入 1 = 重名「储罐区」并入现有分区
  await expect(page.getByText(/导入完成：新增 5 条/)).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/并入现有 1 条/)).toBeVisible();

  const payloads = createdPayloads as Array<Record<string, unknown>>;
  // 重名「储罐区」不重复新建分区，其子级对象并入现有分区下创建
  expect(payloads.some((p) => p.name === "储罐区")).toBe(false);
  const tank = payloads.find((p) => p.name === "1号储罐");
  expect(tank?.zone_id).toBe("existing-zone-1");
  // 不同名「原料库」正常新建
  expect(payloads.some((p) => p.name === "原料库")).toBe(true);
  // 对象保留 AI 输出的 is_risk_point 语义（不会被强制标为风险点）
  const shelf = payloads.find((p) => p.name === "货架") as { is_risk_point?: boolean } | undefined;
  expect(shelf?.is_risk_point).toBe(false);
});
